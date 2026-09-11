-- Subscription model: turns billing rows into subscription periods.
--
-- A subscription is an unbroken stretch of membership. It starts with a
-- user's first transaction, or with a transaction that comes more than 30 days
-- after their membership lapsed (a win-back). It ends when the membership
-- expires and nothing new comes in within 30 days. That's churn, the same rule
-- KKBox uses for its labels.
--
-- The current expiry date is always the one on the user's latest transaction:
-- renewals move it forward, a cancel row pulls it back to about the cancel
-- date. docs/data_notes.md has the checks behind these rules.

CREATE SCHEMA IF NOT EXISTS core;

-- Clean billing rows in the order they happened, tagged with the subscription
-- they belong to.
CREATE OR REPLACE TABLE core.transactions AS
WITH clean AS (
    SELECT DISTINCT ON (user_id, transaction_date, expire_date, payment_method_id,
                        plan_days, list_price, amount_paid, is_auto_renew, is_cancel) *
    FROM staging.transactions
    WHERE year(expire_date) >= 2013  -- 1970-01-01 and similar junk
),
ordered AS (
    SELECT
        *,
        row_number() OVER w AS event_seq,
        lag(expire_date) OVER w AS prev_expiry
    FROM clean
    -- Same-day rows: payments before cancels, then by expiry date.
    WINDOW w AS (PARTITION BY user_id
                 ORDER BY transaction_date, is_cancel, expire_date,
                          payment_method_id, amount_paid, plan_days)
)
SELECT
    * EXCLUDE (prev_expiry),
    plan_days = 7 AND amount_paid = 0 AS is_free_trial,
    prev_expiry IS NULL OR transaction_date > prev_expiry + 30 AS starts_subscription,
    sum((prev_expiry IS NULL OR transaction_date > prev_expiry + 30)::INT)
        OVER (PARTITION BY user_id ORDER BY event_seq) AS subscription_number
FROM ordered
ORDER BY user_id, event_seq;


-- One row per subscription.
CREATE OR REPLACE TABLE core.subscriptions AS
WITH s AS (
    SELECT
        user_id,
        subscription_number,
        min(transaction_date) AS start_date,
        arg_max(expire_date, event_seq) AS end_date,
        count(*) AS n_transactions,
        count(*) FILTER (WHERE amount_paid > 0 AND NOT is_cancel) AS n_payments,
        -- Cancel rows repeat the amount of the plan they cancel; not revenue.
        coalesce(sum(amount_paid) FILTER (WHERE NOT is_cancel), 0) AS revenue,
        arg_min(is_free_trial, event_seq) AS started_with_trial,
        min(transaction_date) FILTER (WHERE amount_paid > 0 AND NOT is_cancel) AS first_payment_date,
        arg_min(plan_days, event_seq) FILTER (WHERE amount_paid > 0 AND NOT is_cancel) AS first_paid_plan_days,
        arg_max(plan_days, event_seq) FILTER (WHERE amount_paid > 0 AND NOT is_cancel) AS last_paid_plan_days,
        arg_min(payment_method_id, event_seq) AS first_payment_method,
        arg_max(payment_method_id, event_seq) AS last_payment_method,
        arg_max(is_auto_renew, event_seq) FILTER (WHERE NOT is_cancel) AS last_auto_renew,
        bool_or(is_cancel) AS had_cancel,
        arg_max(is_cancel, event_seq) AS ended_with_cancel
    FROM core.transactions
    GROUP BY 1, 2
)
SELECT
    *,
    end_date - start_date AS length_days,
    n_payments > 0 AS is_paid,
    subscription_number > 1 AS is_winback,
    -- Churn is only known once the 30-day window after expiry is inside the
    -- data, which ends on 31 Mar 2017.
    CASE WHEN end_date + 30 <= DATE '2017-03-31' THEN 'churned'
         ELSE 'active_at_data_end' END AS status
FROM s
ORDER BY user_id, subscription_number;
