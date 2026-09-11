-- Subscription model: turns billing rows into subscription periods.
--
-- A subscription is an unbroken stretch of membership. It starts with a
-- user's first transaction, or with a transaction that comes more than 30 days
-- after their membership lapsed (a win-back). It ends when the membership
-- expires and nothing new comes in within 30 days. That's churn.
--
-- The current expiry date is always the one on the user's latest transaction:
-- renewals move it forward, a cancel row pulls it back to about the cancel date.
--
-- Billing gaps: not every lapse is real. Whole groups of users sometimes stop
-- being billed and are re-billed months later in one batch, and they keep
-- listening the whole time. A lapse counts as a billing gap, not churn, when
-- the user listened in more than half of the full weeks inside it. After a
-- real, final churn, under 1% of users listen like that.
--
-- docs/data_notes.md has the checks behind all of these rules.

CREATE SCHEMA IF NOT EXISTS core;

-- Clean billing rows in the order they happened, tagged with the subscription
-- they belong to.
CREATE OR REPLACE TABLE core.transactions AS
WITH deduped AS (
    SELECT DISTINCT ON (user_id, transaction_date, expire_date, payment_method_id,
                        plan_days, list_price, amount_paid, is_auto_renew, is_cancel) *
    FROM staging.transactions
    WHERE year(expire_date) >= 2013  -- 1970-01-01 and similar junk
),
flagged_expiry AS (
    -- A paid plan lasts at least its plan length. 0.09% of paid rows carry an
    -- expiry more than 5 days short of it, mostly from one rare payment
    -- method. Shortfalls of a day or two are just calendar months and stay.
    SELECT
        *,
        NOT is_cancel AND amount_paid > 0 AND plan_days > 0
            AND expire_date < transaction_date + plan_days - 5 AS expiry_extended
    FROM deduped
),
clean AS (
    SELECT * REPLACE (
        CASE WHEN expiry_extended THEN transaction_date + plan_days
             ELSE expire_date END AS expire_date
    )
    FROM flagged_expiry
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
),
lapses AS (
    -- Transactions that come more than 30 days after the membership ran out,
    -- with the number of full Monday-to-Sunday weeks inside the gap.
    SELECT
        user_id,
        event_seq,
        prev_expiry,
        transaction_date,
        greatest(1, (date_trunc('week', transaction_date - 7)::DATE
                     - (date_trunc('week', prev_expiry)::DATE + 7)) // 7 + 1) AS gap_weeks
    FROM ordered
    WHERE transaction_date > prev_expiry + 30
),
lapse_listening AS (
    SELECT
        l.user_id,
        l.event_seq,
        count(w.week) / l.gap_weeks AS listening_share
    FROM lapses AS l
    LEFT JOIN core.user_weeks AS w
        ON w.user_id = l.user_id
       AND w.week > l.prev_expiry
       AND w.week + 6 < l.transaction_date
    GROUP BY l.user_id, l.event_seq, l.gap_weeks
),
flagged AS (
    SELECT
        o.* EXCLUDE (prev_expiry),
        ll.event_seq IS NOT NULL AS lapsed_before,        -- billing says the membership lapsed
        ll.listening_share AS lapse_listening_share,
        coalesce(ll.listening_share > 0.5, false) AS is_billing_gap,
        o.prev_expiry IS NULL
            OR coalesce(ll.listening_share <= 0.5, false) AS starts_subscription
    FROM ordered AS o
    LEFT JOIN lapse_listening AS ll USING (user_id, event_seq)
)
SELECT
    *,
    plan_days = 7 AND amount_paid = 0 AS is_free_trial,
    sum(starts_subscription::INT) OVER (PARTITION BY user_id ORDER BY event_seq)
        AS subscription_number
FROM flagged
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
        count(*) FILTER (WHERE is_billing_gap) AS n_billing_gaps,
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
    -- 1 = the user's first paid subscription; later ones are returning subscribers.
    CASE WHEN n_payments > 0
         THEN sum((n_payments > 0)::INT) OVER (PARTITION BY user_id ORDER BY subscription_number)
    END AS paid_number,
    -- Churn is only known once the 30-day window after expiry is inside the
    -- data, which ends on 31 Mar 2017.
    CASE WHEN end_date + 30 <= DATE '2017-03-31' THEN 'churned'
         ELSE 'active_at_data_end' END AS status
FROM s
ORDER BY user_id, subscription_number;


-- One row per user, with the attributes most analyses need.
CREATE OR REPLACE TABLE core.users AS
SELECT
    u.user_id,
    m.registration_date,
    CASE WHEN m.registered_via IN (3, 4, 7, 9) THEN 'channel ' || m.registered_via
         WHEN m.user_id IS NULL THEN 'unknown'
         ELSE 'other' END AS channel,
    -- Users who registered inside the data window: their whole history is visible.
    coalesce(m.registration_date >= DATE '2015-01-01', false) AS registered_in_window
FROM staging.user_map AS u
LEFT JOIN staging.members AS m USING (user_id);


-- One row per paid period: did the subscriber pay again, or was it the end?
-- This is the unit behind renewal rates. Periods whose outcome falls after the
-- data ends are left out.
CREATE OR REPLACE TABLE core.renewals AS
WITH paid AS (
    SELECT
        *,
        row_number() OVER w AS payment_number,  -- 1 = first payment of the subscription
        count(*) OVER (w ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING) AS later_payments
    FROM core.transactions
    WHERE NOT is_cancel AND amount_paid > 0
    WINDOW w AS (PARTITION BY user_id, subscription_number ORDER BY event_seq)
),
r AS (
    SELECT
        p.user_id,
        p.subscription_number,
        s.paid_number,
        p.payment_number,
        p.transaction_date,
        -- The last payment's period ends when the subscription does (a cancel
        -- can pull it in); earlier ones end at their own expiry.
        CASE WHEN p.later_payments = 0 THEN s.end_date ELSE p.expire_date END AS period_end,
        p.plan_days,
        p.list_price,
        p.amount_paid,
        p.amount_paid < p.list_price AS is_discounted,
        p.is_auto_renew,
        p.payment_method_id,
        s.started_with_trial,
        CASE WHEN p.later_payments > 0 THEN 'renewed'
             WHEN s.status = 'churned' THEN 'churned'
             ELSE 'unknown' END AS outcome
    FROM paid AS p
    JOIN core.subscriptions AS s USING (user_id, subscription_number)
)
SELECT * EXCLUDE (outcome), outcome = 'churned' AS churned
FROM r
WHERE outcome <> 'unknown'
ORDER BY user_id, subscription_number, payment_number;
