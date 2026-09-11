# %% [markdown]
# # 1. How big is the problem, and where do we lose people?
#
# Questions 1 and 2 of the project ([questions](../docs/questions.md)).
#
# Everything here runs on the DuckDB database that `src/build_db.py` builds.
# Churn means the membership lapsed for more than 30 days, with billing gaps
# excluded. The rules are in the [data notes](../docs/data_notes.md).

# %%
import os
import sys
from pathlib import Path

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
os.chdir(ROOT)  # the daily-logs view reads files by relative path
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import pandas as pd
from IPython.display import display

import charts
from analysis import connect, km, survival_at

charts.use_style()
pd.set_option("display.max_columns", 20)
con = connect()

# %% [markdown]
# ## Q1. Paying subscribers, month by month
#
# `marts.monthly_subscribers` counts paying subscribers only: from their first
# payment to the end of the subscription. 2015 is a warm-up year, because
# anyone who was already subscribed before January 2015 shows up as "new" on
# their first transaction in the data. So the view starts in January 2016.

# %%
bridge = con.sql("""
    SELECT month, subscribers_start, new_subscribers, returning_subscribers,
           churned, subscribers_end, churn_rate, revenue_per_subscriber
    FROM marts.monthly_subscribers
    WHERE month >= DATE '2016-01-01'
""").df()

display(bridge.assign(
    month=bridge.month.dt.strftime("%b %Y"),
    churn_rate=(100 * bridge.churn_rate).round(2),
    revenue_per_subscriber=bridge.revenue_per_subscriber.round(),
).set_index("month"))

growth = bridge.subscribers_end.iloc[-1] / bridge.subscribers_start.iloc[0] - 1
h1 = bridge[bridge.month < "2016-07-01"].new_subscribers.mean()
h2 = bridge[(bridge.month >= "2016-07-01") & (bridge.month < "2017-01-01")].new_subscribers.mean()
print(f"Subscribers {bridge.subscribers_start.iloc[0]:,} -> {bridge.subscribers_end.iloc[-1]:,} ({100 * growth:+.0f}%)")
print(f"New subscribers per month: {h1:,.0f} in H1 2016, {h2:,.0f} in H2 2016, "
      f"{bridge[bridge.month >= '2017-01-01'].new_subscribers.mean():,.0f} in Jan-Feb 2017")
print(f"Churned per month since Jul 2016: {bridge[bridge.month >= '2016-07-01'].churned.min():,} "
      f"to {bridge[bridge.month >= '2016-07-01'].churned.max():,}")

# %%
fig, ax = charts.figure()
k = 1000
ax.set_xlim(bridge.month.iloc[0] - pd.Timedelta(days=12), bridge.month.iloc[-1] + pd.Timedelta(days=12))
ax.set_ylim(0, 85)
h_new = charts.line(ax, bridge.month, bridge.new_subscribers / k, charts.BLUE, "New")
h_churn = charts.line(ax, bridge.month, bridge.churned / k, charts.ORANGE, "Churned")
h_ret = charts.line(ax, bridge.month, bridge.returning_subscribers / k, charts.GRAY, "Returning")
ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}k" if v else "0"))
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
charts.legend(ax, [(h_new, "New"), (h_churn, "Churned"), (h_ret, "Returning")])
charts.titles(fig, ax, "About as many subscribers leave each month as join",
              "Paying subscribers per month, Jan 2016 – Feb 2017")
charts.save(fig, "01_monthly_flows.png")

# %% [markdown]
# **What it says.** The base grew by 30%, but churn (33–43k a month since mid-2016)
# runs at about the level of new subscribers, and new subscribers have slowed down.
# The February 2016 peak is partly a batch of dormant subscriptions on one payment
# method that all ended on 25 February (details in the findings).

# %% [markdown]
# ## Q2. The lifecycle of a new subscriber
#
# New users only: registered from 2015 on, so their whole history is visible.
#
# ### Free trials

# %%
firsts = con.sql("""
    SELECT s.*, u.channel
    FROM core.subscriptions AS s
    JOIN core.users AS u USING (user_id)
    WHERE s.subscription_number = 1 AND u.registered_in_window
""")
display(con.sql("""
    SELECT CASE WHEN started_with_trial THEN 'free trial' ELSE 'paid from day 1' END AS first_subscription,
           count(*) AS users,
           round(100 * avg(is_paid::INT), 1) AS pct_ever_paid
    FROM firsts GROUP BY 1
""").df())
display(con.sql("""
    SELECT channel, count(*) AS trials, round(100 * avg(is_paid::INT), 1) AS pct_converted
    FROM firsts
    WHERE started_with_trial AND (is_paid OR status = 'churned')
    GROUP BY 1 HAVING count(*) > 100 ORDER BY trials DESC
""").df())

# %% [markdown]
# ### Survival from the first payment
#
# Kaplan-Meier, so subscriptions still running when the data ends count for as
# long as they were observed. "Month N" is 30·N + 15 days after the first
# payment: past the N-th renewal date plus a little slack.

# %%
subs = con.sql("""
    SELECT s.started_with_trial,
           CASE WHEN s.first_paid_plan_days <= 31 THEN 'monthly' ELSE '3-12 months' END AS first_plan,
           least(s.end_date, DATE '2017-03-31') - s.first_payment_date AS days,
           (s.status = 'churned')::INT AS churned
    FROM core.subscriptions AS s
    JOIN core.users AS u USING (user_id)
    WHERE s.paid_number = 1 AND u.registered_in_window AND s.end_date >= s.first_payment_date
""").df()

MONTHS = [1, 2, 3, 6, 12, 18]
groups = {
    "all new subscribers": subs,
    "free trial first": subs[subs.started_with_trial],
    "paid from day 1": subs[~subs.started_with_trial],
    "monthly first plan": subs[subs.first_plan == "monthly"],
    "3-12 month first plan": subs[subs.first_plan == "3-12 months"],
}
curves = {name: km(g.days.values, g.churned.values) for name, g in groups.items()}
survival = pd.DataFrame(
    {name: [len(groups[name])] + [round(100 * survival_at(c, 30 * m + 15), 1) for m in MONTHS]
     for name, c in curves.items()},
    index=["subscriptions"] + [f"month {m}" for m in MONTHS],
).T
display(survival)

# %%
all_curve = curves["all new subscribers"]
hazard = []
prev = 1.0
for m in range(1, 13):
    cur = survival_at(all_curve, 30 * m + 15)
    hazard.append(100 * (1 - cur / prev))
    prev = cur
hazard = pd.Series(hazard, index=range(1, 13), name="pct_leaving_that_month")
display(hazard.round(1).to_frame().T)

# %%
fig, ax = charts.figure(height=3.6)
ax.set_xlim(0.3, 12.7)
ax.set_ylim(0, 13)
colors = [charts.BLUE] + [charts.GRAY] * 11
charts.bars(ax, hazard.index, hazard.values, colors)
charts.note(ax, 1, hazard.iloc[0] + 0.4, f"{hazard.iloc[0]:.1f}%", ha="center", va="bottom")
charts.note(ax, 2, hazard.iloc[1] + 0.4, f"{hazard.iloc[1]:.1f}%", ha="center", va="bottom")
ax.set_xticks(range(1, 13))
ax.set_xlabel("Month after the first payment")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
ax.yaxis.set_major_locator(mticker.MultipleLocator(4))
charts.titles(fig, ax, "The first renewal is where new subscribers are lost",
              "Share of new subscribers still paying who leave in that month, users registered 2015–2017")
charts.save(fig, "01_first_renewal.png")

# %%
fig, ax = charts.figure(height=3.6)
ax.set_xlim(0, 19.5)
ax.set_ylim(0, 105)
days = range(0, 18 * 30 + 16, 5)
for name, color in [("monthly first plan", charts.BLUE), ("3-12 month first plan", charts.ORANGE)]:
    ys = [100 * survival_at(curves[name], d) for d in days]
    xs = [d / 30 for d in days]
    charts.line(ax, xs, ys, color, name)
    charts.note(ax, xs[-1] + 0.3, ys[-1], f"{ys[-1]:.0f}%")
ax.set_xticks([0, 3, 6, 9, 12, 15, 18])
ax.set_xlabel("Months after the first payment")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
ax.yaxis.set_major_locator(mticker.MultipleLocator(25))
handles = ax.get_lines()
charts.legend(ax, [(handles[0], "Started on a monthly plan"), (handles[2], "Started on a 3–12 month plan")])
charts.titles(fig, ax, "A long first plan delays churn; it doesn't prevent it",
              "Share of new subscribers still subscribed (Kaplan-Meier)")
charts.save(fig, "01_first_plan_survival.png")

# %% [markdown]
# **What it says.** Free trials convert in single digits, and the few who convert
# churn faster than people who paid from day one. For everyone, the first renewal is
# the big drop; after month 3 the monthly loss settles at 2–3%. A long first plan
# holds people through its own length and then loses them faster, ending below the
# monthly plan by month 18.
