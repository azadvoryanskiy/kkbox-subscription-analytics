"""Export the dashboard data: small aggregates from the marts, as JSON.

Only aggregates leave the database, a few hundred rows in total and nothing at
the user level. The files are committed, so the dashboard is a plain static
page that GitHub Pages can serve without the data or a build step.

Usage (from the repo root, after src/build_db.py):
    python src/export_dashboard_data.py
"""

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "kkbox.duckdb"
OUT_DIR = ROOT / "dashboard" / "data"

CHANNEL = """CASE WHEN channel IN ('channel 3', 'channel 4', 'channel 7', 'channel 9')
                  THEN replace(channel, 'channel', 'Channel')
                  ELSE 'Other / unknown' END"""

QUERIES = {
    # Paying subscribers by month, Jan 2016 – Feb 2017.
    "monthly": f"""
        SELECT strftime(month, '%Y-%m') AS month, {CHANNEL} AS channel,
               sum(subscribers_start) AS subscribers_start, sum(new_subscribers) AS new,
               sum(returning_subscribers) AS returning, sum(churned) AS churned,
               sum(subscribers_end) AS subscribers_end
        FROM marts.dash_monthly GROUP BY ALL ORDER BY 1, 2""",
    # Renewal decisions with periods ending in 2016.
    "renewals": f"""
        SELECT {CHANNEL} AS channel, payment_type, tenure, tenure_order,
               sum(decisions) AS decisions, sum(churned) AS churned
        FROM marts.dash_renewals GROUP BY ALL ORDER BY 1, 2, 4""",
    # Monthly-plan renewals in 2016 by listening in the 4 weeks before.
    "listening": f"""
        SELECT {CHANNEL} AS channel, payment_type, active_days, bucket_order,
               sum(decisions) AS decisions, sum(churned) AS churned
        FROM marts.dash_listening GROUP BY ALL ORDER BY 1, 2, 4""",
    # New subscribers from cohorts Sep 2015 – Feb 2016, months 0–12 after first payment.
    "retention": f"""
        SELECT {CHANNEL} AS channel, months_since_first_payment AS month,
               sum(cohort_users) AS users, sum(active_users) AS active
        FROM marts.cohort_retention
        WHERE cohort_month BETWEEN DATE '2015-09-01' AND DATE '2016-02-01'
          AND months_since_first_payment <= 12
        GROUP BY ALL ORDER BY 1, 2""",
    # Paid subscribers who churned Jul 2015 – Jun 2016 and whether they paid again.
    "winback": f"""
        SELECT {CHANNEL} AS channel, how_it_ended, sum(churned) AS churned,
               sum(back_90d) AS back_90d, sum(back_180d) AS back_180d, sum(back_270d) AS back_270d
        FROM marts.dash_winback GROUP BY ALL ORDER BY 1, 2""",
    # The switcher check; not split by channel.
    "switchers": """
        SELECT path, setup_now, path_order, subscriptions, churned_by_5th
        FROM marts.dash_switchers ORDER BY path_order""",
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    for name, sql in QUERIES.items():
        rel = con.sql(sql)
        rows = [dict(zip(rel.columns, (int(v) if isinstance(v, (int,)) else v for v in row)))
                for row in rel.fetchall()]
        path = OUT_DIR / f"{name}.json"
        path.write_text(json.dumps(rows, separators=(",", ":")))
        print(f"{path.relative_to(ROOT)}: {len(rows)} rows, {path.stat().st_size / 1024:.1f} KB")
    con.close()


if __name__ == "__main__":
    main()
