"""Data quality checks behind docs/data_notes.md.

Read-only: prints what's in each staging table and flags the known quirks.

Usage (from the repo root, after src/build_db.py):
    python src/data_checks.py
"""

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "kkbox.duckdb"

CHECKS = {
    "Members: missing demographics": """
        SELECT
            round(avg((age_raw = 0)::INT), 3) AS age_zero_share,
            round(avg((gender IS NULL)::INT), 3) AS gender_missing_share,
            round(avg((city = 1)::INT), 3) AS city_1_share
        FROM staging.members
    """,
    "Members: registration channels": """
        SELECT registered_via, count(*) AS users,
               round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
        FROM staging.members
        GROUP BY 1 ORDER BY users DESC LIMIT 6
    """,
    "Members: channel mix by sign-up year, paying users only (%)": """
        SELECT year(registration_date) AS year,
               round(100 * avg((registered_via = 3)::INT)) AS ch3,
               round(100 * avg((registered_via = 4)::INT)) AS ch4,
               round(100 * avg((registered_via = 7)::INT)) AS ch7,
               round(100 * avg((registered_via = 9)::INT)) AS ch9
        FROM staging.members
        WHERE user_id IN (SELECT user_id FROM staging.transactions)
          AND year(registration_date) >= 2012
        GROUP BY 1 ORDER BY 1
    """,
    "Transactions: overview": """
        SELECT min(transaction_date) AS first_tx, max(transaction_date) AS last_tx,
               count(*) AS rows, count(DISTINCT user_id) AS users,
               count(DISTINCT user_id) FILTER (
                   WHERE user_id NOT IN (SELECT user_id FROM staging.members)
               ) AS users_without_member_row
        FROM staging.transactions
    """,
    "Transactions: how the two source files split": """
        SELECT source_file, count(*) AS rows,
               max(transaction_date) AS last_tx,
               min(expire_date) FILTER (WHERE transaction_date < DATE '2017-03-01'
                                          AND year(expire_date) >= 2013) AS min_expiry_pre_march,
               max(expire_date) FILTER (WHERE transaction_date < DATE '2017-03-01') AS max_expiry_pre_march
        FROM staging.transactions
        GROUP BY 1 ORDER BY 1
    """,
    "Transactions: rows present in both files (expect 0)": """
        SELECT count(*) AS rows_in_both FROM (
            SELECT * EXCLUDE (source_file) FROM staging.transactions WHERE source_file = 'transactions'
            INTERSECT
            SELECT * EXCLUDE (source_file) FROM staging.transactions WHERE source_file = 'transactions_v2'
        )
    """,
    "Transactions: false churn if transactions.csv were used alone": """
        WITH last_full AS (
            SELECT user_id, max(expire_date) AS last_expiry
            FROM staging.transactions
            WHERE source_file = 'transactions' AND NOT is_cancel AND year(expire_date) >= 2013
            GROUP BY 1
        ),
        looks_churned AS (  -- no renewal in the file, and the 30-day window closes by 28 Feb 2017
            SELECT * FROM last_full WHERE last_expiry <= DATE '2017-01-29'
        )
        SELECT count(*) AS users_looking_churned,
               count(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM staging.transactions t
                   WHERE t.user_id = l.user_id AND t.source_file = 'transactions_v2'
                     AND t.transaction_date <= l.last_expiry + 30
               )) AS actually_renewed,
               round(100.0 * actually_renewed / users_looking_churned, 1) AS pct_false_churn
        FROM looks_churned AS l
    """,
    "Transactions: quirks": """
        SELECT
            count(*) - (SELECT count(*) FROM (
                SELECT DISTINCT * EXCLUDE (source_file) FROM staging.transactions
            )) AS exact_duplicates,
            count(*) FILTER (WHERE year(expire_date) < 2013) AS expiry_before_2013,
            round(avg((plan_days = 0)::INT), 3) AS plan_days_zero_share,
            count(*) FILTER (WHERE plan_days = 7 AND amount_paid = 0) AS free_7_day_rows,
            count(DISTINCT user_id) FILTER (WHERE plan_days = 7 AND amount_paid = 0) AS free_7_day_users,
            round(avg(is_cancel::INT), 3) AS cancel_share
        FROM staging.transactions
    """,
    "Transactions: days from cancel to expiry (5/25/50/75/95 pct)": """
        SELECT quantile_cont(expire_date - transaction_date, [0.05, 0.25, 0.5, 0.75, 0.95])
                   AS days
        FROM staging.transactions
        WHERE is_cancel AND year(expire_date) >= 2013
    """,
    "Transactions: renewal timing vs previous expiry": """
        WITH t AS (
            SELECT transaction_date,
                   lag(expire_date) OVER (PARTITION BY user_id
                                          ORDER BY transaction_date, expire_date) AS prev_expiry
            FROM staging.transactions
            WHERE NOT is_cancel
        )
        SELECT round(avg((transaction_date < prev_expiry - 1)::INT), 3) AS early_renewal_share,
               round(avg((transaction_date > prev_expiry + 30)::INT), 3) AS gap_over_30d_share
        FROM t WHERE prev_expiry IS NOT NULL
    """,
    "Transactions: user-days with more than one transaction": """
        SELECT count(*) AS user_days FROM (
            SELECT user_id, transaction_date FROM staging.transactions
            GROUP BY 1, 2 HAVING count(*) > 1
        )
    """,
    "User logs: overview by source file": """
        SELECT source_file, min(date) AS first_day, max(date) AS last_day,
               count(*) AS rows, count(DISTINCT user_id) AS users,
               count(*) FILTER (WHERE total_secs > 86400) AS over_24h_days,
               count(*) FILTER (WHERE total_secs < 0) AS negative_days
        FROM staging.user_logs
        GROUP BY 1 ORDER BY 1
    """,
    "User logs: duplicate user-days among valid days (expect 0)": """
        SELECT sum(log_rows - active_days) AS duplicate_user_days,
               max(active_days) AS max_days_in_a_week
        FROM core.user_weeks
    """,
    "Churn labels: rate and coverage by expiry month": """
        SELECT expiry_month, count(*) AS users,
               round(avg(is_churn::INT), 4) AS churn_rate,
               round(avg((user_id IN (SELECT user_id FROM staging.transactions))::INT), 3)
                   AS in_transactions,
               round(avg((user_id IN (SELECT user_id FROM staging.members))::INT), 3)
                   AS in_members,
               round(avg((user_id IN (SELECT user_id FROM staging.user_logs))::INT), 3)
                   AS in_march_logs
        FROM staging.churn_labels
        GROUP BY 1 ORDER BY 1
    """,
    "Churn labels: share of users with a subscription expiring in the label month": """
        SELECT c.expiry_month,
               round(avg((EXISTS (
                   SELECT 1 FROM staging.transactions t
                   WHERE t.user_id = c.user_id
                     AND date_trunc('month', t.expire_date) = c.expiry_month
               ))::INT), 3) AS has_expiry_in_month,
               count(*) FILTER (WHERE c.user_id IN (
                   SELECT user_id FROM staging.churn_labels GROUP BY 1 HAVING count(*) > 1
               )) AS users_in_both_months
        FROM staging.churn_labels AS c
        GROUP BY 1 ORDER BY 1
    """,
    "Model: subscriptions overview": """
        SELECT count(*) AS subscriptions, count(DISTINCT user_id) AS users,
               round(100 * avg(is_winback::INT), 1) AS pct_winback,
               round(100 * avg(started_with_trial::INT), 1) AS pct_start_with_trial,
               round(100 * avg((status = 'churned')::INT), 1) AS pct_churned,
               median(length_days) AS median_length_days
        FROM core.subscriptions
    """,
    "Model: lapses and billing gaps (share of gap weeks with listening)": """
        SELECT count(*) FILTER (WHERE lapsed_before) AS lapses,
               count(*) FILTER (WHERE lapse_listening_share > 0.25) AS over_25pct,
               count(*) FILTER (WHERE is_billing_gap) AS over_50pct_billing_gaps,
               count(*) FILTER (WHERE lapse_listening_share >= 0.8) AS over_80pct,
               count(*) FILTER (WHERE expiry_extended) AS expiries_extended
        FROM core.transactions
    """,
    "Model: paid subscriptions that end before their first payment (edge case)": """
        SELECT count(*) AS subscriptions
        FROM core.subscriptions
        WHERE paid_number IS NOT NULL AND end_date < first_payment_date
    """,
    "Model: churn vs KKBox February 2017 labels": """
        WITH e AS (  -- each labelled user's expiry date in February
            SELECT user_id, max(expire_date) AS expiry
            FROM core.transactions
            WHERE expire_date BETWEEN DATE '2017-02-01' AND DATE '2017-02-28'
            GROUP BY 1
        ),
        feb AS (
            SELECT
                c.is_churn AS kkbox_churn,
                -- Our rule: the membership lapsed for more than 30 days.
                EXISTS (SELECT 1 FROM core.subscriptions s
                        WHERE s.user_id = c.user_id
                          AND s.end_date BETWEEN DATE '2017-02-01' AND DATE '2017-02-28')
                    AS membership_churn,
                -- KKBox's rule, reverse-engineered: no paid transaction dated
                -- on or after the expiry, within 30 days.
                NOT EXISTS (SELECT 1 FROM core.transactions t
                            WHERE t.user_id = c.user_id AND NOT t.is_cancel
                              AND t.amount_paid > 0
                              AND t.transaction_date BETWEEN e.expiry AND e.expiry + 30)
                    AS payment_churn
            FROM staging.churn_labels AS c
            JOIN e USING (user_id)
            WHERE c.expiry_month = DATE '2017-02-01'
        )
        SELECT count(*) AS users,
               round(100 * avg(kkbox_churn::INT), 2) AS kkbox_churn_pct,
               round(100 * avg(membership_churn::INT), 2) AS membership_churn_pct,
               round(100 * avg((kkbox_churn = membership_churn)::INT), 2) AS agree_membership_rule,
               round(100 * avg((kkbox_churn = payment_churn)::INT), 2) AS agree_payment_rule
        FROM feb
    """,
    "Activity: weekly listening table": """
        SELECT count(*) AS user_weeks, count(DISTINCT user_id) AS users,
               min(week) AS first_week, max(week) AS last_week,
               median(active_days) AS median_active_days,
               round(median(minutes_played)) AS median_minutes
        FROM core.user_weeks
    """,
}


def main() -> None:
    pd.set_option("display.width", 200)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute("SET max_temp_directory_size = '6GB'")
    for title, sql in CHECKS.items():
        print(f"== {title}")
        print(con.sql(sql).df().to_string(index=False), end="\n\n")
    con.close()


if __name__ == "__main__":
    main()
