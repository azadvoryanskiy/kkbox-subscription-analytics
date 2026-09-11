# Data notes

What's actually in the KKBox files, checked right after loading, and the rules
the subscription model is built on. Every number here comes from
`src/data_checks.py` or the queries it's based on, so it can be re-run.

## At a glance

| Table | Rows | Users | Period |
|---|---|---|---|
| `members` | 6,769,473 | 6.77M | registrations 2004 – Apr 2017 |
| `transactions` | 22,978,755 | 2.43M | Jan 2015 – Mar 2017 (two files combined) |
| `user_logs` | 410,502,905 | 5.3M | Jan 2015 – Mar 2017, one row per user per day (two files combined) |
| `churn_labels` | 1,963,891 | 1.08M | subscriptions expiring in Feb and Mar 2017 |

Prices are in New Taiwan dollars (NT$). The standard plan is 30 days for NT$149.

## The `_v2` files continue the history, they don't replace it

This is the most important thing in the data.

- `transactions.csv` (21.5M rows) looks like the full history, but it isn't.
  It only has transactions that expire by 31 Mar 2017.
- `transactions_v2.csv` (1.4M rows) has everything from March 2017, plus the
  earlier transactions that expire after 31 Mar 2017. It's the other half of
  the history, not a newer version of the same file.
- The two files don't share a single row, and the split is clean: only 14 rows
  (2 users) break the rule. 62,517 users appear only in `transactions_v2.csv`.
- The logs and labels work the same way: `user_logs.csv` covers Jan 2015 –
  Feb 2017 and `user_logs_v2.csv` covers March 2017; `train.csv` labels
  February expiries and `train_v2.csv` labels March.

**Why it matters.** With `transactions.csv` alone, 1.26M users seem to stop
paying by the end of January 2017. 99,470 of them (7.9%) actually renewed; the
renewal just sits in the other file. For subscriptions ending in December 2016
and January 2017, 21–30% of these "churners" are false. A churn analysis on the
first file alone overstates churn, and does it most in the latest months, which
are the ones a manager cares about.

Each pair is loaded into one table, and a `source_file` column keeps track of
where each row came from.

## Members

- **Demographics are mostly missing.** Age is 0 for 67% of users and gender is
  blank for 65%. City 1 holds 71% of all users, and 91% of them have no age.
  It looks like a default "unknown" value, not a real city.
- **Registration channel is complete.** Four codes (`registered_via` 4, 3, 9, 7)
  cover 99.4% of users. The codes are anonymised, so the write-up can say
  "channel 4" but not "Facebook ads".
- **The channel mix shifts a lot over time.** Among paying users, channel 4
  barely exists before 2015 and makes up 46% of 2016 sign-ups. Any comparison
  of channels has to account for this, or it will just compare years.
- 437,810 users with transactions (18%) have no member row. Their channel is
  unknown.

## Transactions

- 3,339 exact duplicate rows.
- 1,804 rows have an expiry date before 2013, mostly 1970-01-01. Junk.
- 9,718 rows expire after 2018, some as late as 2036. These users are simply
  still subscribed when the data ends, so they're not a problem for churn.
- `payment_plan_days` is 0 on 3.8% of rows, even though those users paid NT$149
  and got about 31 days. The plan length field can't be trusted on its own.
- **Free trials:** 582k rows with a 7-day plan and NT$0 paid, across 536k users.
  This is the trial step of the lifecycle.
- **Cancellations** are 3.9% of rows. On a cancel row, the expiry date is almost
  always the cancel date itself (median gap 0 days). So a cancel row means
  "the membership ends here". Cancel rows also repeat the amount of the plan
  they cancel (645k of them do), so that amount is not revenue.
- 15.8% of renewals happen more than a day before the previous expiry (early or
  overlapping renewals). Subscription time has to be merged by date, not added up.
- 3.0% of renewals come after a gap of more than 30 days. These are win-backs.
- 289,730 user-days have more than one transaction. The model orders them:
  payments before cancels, then by expiry date.
- Volume roughly doubles over two years, and cancellations spike in December
  2015 to about twice their usual rate.

## Listening logs

- `user_logs.csv` is 30 GB unpacked (392M rows, 5.23M users). It stays in its
  `.7z` archive; `src/extract_user_logs.py` streams it into a Parquet file
  without unpacking. `user_logs_v2.csv` adds 18.4M rows for March 2017.
- **Bad records:** 147,193 user-days log more than 24 hours of play, and
  61,493 have negative play time (all in the older file). Both are left out.
- No duplicate user-days.
- The database keeps weekly totals per user (`core.user_weeks`, 94M rows). The
  daily rows stay in the files and are read through the `staging.user_logs`
  view; storing them in the database would add about 7 GB.
- The median active week has 5 listening days and 331 minutes of play.

## Churn labels (`train.csv`, `train_v2.csv`)

- Two months of KKBox labels: 992,931 users whose subscription expires in
  February 2017 (**6.39% churned**) and 970,960 in March 2017 (**8.99% churned**).
  881,701 users are in both: monthly subscribers who renewed in February and
  came up for renewal again in March.
- KKBox describes its rule as: a user churns if there is no new valid
  subscription within 30 days after the current one expires.
- Every labelled user appears in transactions with an expiry in the label
  month, and 88% are in members.

### What KKBox's label actually measures

One rule reproduces **99.96%** of the February labels: *churned, unless a paid
transaction is dated on or after the expiry date and within 30 days of it.*

So the label is about a payment event, not about membership. A user who
renews a few days early, often onto a longer plan, has no payment after the
expiry date and gets labelled churned, even though their membership never
lapsed.

In February 2017, **37.6% of the users KKBox labels as churned were still
members.** The gap is biggest exactly where customers are most committed:

| Current plan (Feb 2017) | Users | KKBox label churn | Membership lapsed |
|---|---|---|---|
| Monthly | 964,951 | 5.1% | 3.4% |
| 3–6 months | 16,187 | 46.8% | 21.5% |
| 12+ months | 9,001 | 60.0% | 26.3% |
| All | 992,931 | 6.39% | 4.04% |

A model trained on this label would learn that customers who commit to a long
plan are likely to leave. That's close to backwards.

## The subscription model

`sql/02_subscriptions.sql` turns billing rows into subscriptions.

- A **subscription** is an unbroken stretch of membership. It starts with a
  user's first transaction, or with a transaction more than 30 days after their
  membership lapsed (a **win-back**).
- The current expiry date is the one on the user's latest transaction.
  Renewals move it forward and cancels pull it back. This holds up: a new
  payment shortens the expiry only 0.06% of the time, while cancel rows
  shorten it 54% of the time.
- A subscription **churns** when the membership expires and nothing new comes
  in within 30 days. When that 30-day window runs past 31 Mar 2017, the
  outcome isn't known yet and the status is `active_at_data_end`.
- Result: **3,073,709 subscriptions across 2,425,986 users.** 21.1% are
  win-backs, 16.2% start with a free trial, 60.1% had churned by the end of the
  data, and the median subscription lasts 146 days.
- Against KKBox's February labels, the membership rule agrees on 97.54% of
  users. The whole difference is the payment-vs-membership point above.
- **Known limit:** for users who were already subscribed before January 2015,
  the model only sees the part of the subscription inside the data, so their
  start dates are too late. 37,464 subscriptions even start with a cancel row
  for this reason. Cohort analysis will use users who registered in 2015 or later.

## Modelling decisions

The churn rule needs a second look: it was agreed as "the same as KKBox", and
KKBox's label turned out to measure payments rather than membership (see
above). The rest are technical clean-up choices and can be revisited if the
analysis shows a problem.

| Issue | Decision |
|---|---|
| `_v2` files | Combine each pair; `source_file` records the origin of each row |
| Duplicate rows | Drop |
| Expiry before 2013 | Exclude the row |
| Expiry after 2018 | Keep; the user is still subscribed when the data ends |
| Unreliable `payment_plan_days` | Take subscription length from the expiry date |
| Cancel rows | The cancel row's expiry date is the end of the membership; its amount is not revenue |
| Churn | **To confirm.** Proposed: the membership lapsed for more than 30 days. KKBox's payment rule is kept as a check |
| Win-back | A transaction more than 30 days after the previous membership ended |
| Trial | 7-day plan with NT$0 paid |
| Subscriptions started before 2015 | Real start unknown; cohorts use users who registered from 2015 on |
| Demographics | Not used for segmentation. Too much is missing. Segments come from billing and listening behaviour instead |
| Channel | `registered_via` codes 3, 4, 7, 9; everything else, including missing, is "other/unknown" |
| Play time negative or over 24h a day | Exclude the user-day |
| Daily logs | Stay in files behind a view; the database keeps weekly totals |
