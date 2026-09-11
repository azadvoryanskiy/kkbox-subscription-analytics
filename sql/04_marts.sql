-- Marts: the tables behind the case study and the dashboard.

CREATE SCHEMA IF NOT EXISTS marts;

-- Paying subscribers month by month.
--
-- A paying subscriber counts from their first payment to the end of the
-- subscription; trial-only subscriptions are the trial funnel, not subscriber
-- churn. Churn is counted in the month the membership ended. The last full
-- month is February 2017: later ends aren't confirmed as churn yet.
--
-- 2015 is a warm-up year. Anyone already subscribed before January 2015 shows
-- up as "new" on their first transaction in the data, so 2015 overstates new
-- subscribers. Use the bridge from January 2016.
CREATE OR REPLACE TABLE marts.monthly_subscribers AS
WITH months AS (
    SELECT
        range::DATE AS month_start,
        (range + INTERVAL 1 MONTH - INTERVAL 1 DAY)::DATE AS month_end
    FROM range(DATE '2015-01-01', DATE '2017-03-01', INTERVAL 1 MONTH)
),
paid AS (
    SELECT first_payment_date AS paid_start, end_date, paid_number
    FROM core.subscriptions
    WHERE paid_number IS NOT NULL
      AND end_date >= first_payment_date
),
bridge AS (
    SELECT
        m.month_start AS month,
        count(*) FILTER (WHERE p.paid_start < m.month_start AND p.end_date >= m.month_start)
            AS subscribers_start,
        count(*) FILTER (WHERE p.paid_start BETWEEN m.month_start AND m.month_end
                           AND p.paid_number = 1) AS new_subscribers,
        count(*) FILTER (WHERE p.paid_start BETWEEN m.month_start AND m.month_end
                           AND p.paid_number > 1) AS returning_subscribers,
        count(*) FILTER (WHERE p.end_date BETWEEN m.month_start AND m.month_end)
            AS churned,
        count(*) FILTER (WHERE p.paid_start <= m.month_end AND p.end_date > m.month_end)
            AS subscribers_end
    FROM months AS m
    CROSS JOIN paid AS p
    GROUP BY 1
),
revenue AS (
    SELECT date_trunc('month', transaction_date)::DATE AS month, sum(amount_paid) AS revenue
    FROM core.transactions
    WHERE NOT is_cancel
    GROUP BY 1
)
SELECT
    b.*,
    round(b.churned / b.subscribers_start, 4) AS churn_rate,
    r.revenue,
    round(r.revenue / ((b.subscribers_start + b.subscribers_end) / 2), 1) AS revenue_per_subscriber
FROM bridge AS b
LEFT JOIN revenue AS r USING (month)
ORDER BY month;


-- New subscribers by the month of their first payment: the share with a paid
-- subscription running at the end of each later month. People who left and
-- came back count as subscribed again. Only users who registered from 2015 on,
-- so every "first payment" really is their first.
CREATE OR REPLACE TABLE marts.cohort_retention AS
WITH new_users AS (
    SELECT s.user_id, date_trunc('month', s.first_payment_date)::DATE AS cohort_month, u.channel
    FROM core.subscriptions AS s
    JOIN core.users AS u USING (user_id)
    WHERE s.paid_number = 1 AND u.registered_in_window
),
month_ends AS (
    SELECT (range + INTERVAL 1 MONTH - INTERVAL 1 DAY)::DATE AS month_end
    FROM range(DATE '2015-01-01', DATE '2017-03-01', INTERVAL 1 MONTH)
),
active AS (
    SELECT DISTINCT n.user_id, me.month_end
    FROM new_users AS n
    JOIN core.subscriptions AS s
        ON s.user_id = n.user_id AND s.paid_number IS NOT NULL
    JOIN month_ends AS me
        ON me.month_end BETWEEN s.first_payment_date AND s.end_date
)
SELECT
    n.cohort_month,
    n.channel,
    datediff('month', n.cohort_month, me.month_end) AS months_since_first_payment,
    count(*) AS cohort_users,
    count(a.user_id) AS active_users,
    round(count(a.user_id) / count(*), 4) AS retention
FROM new_users AS n
JOIN month_ends AS me ON me.month_end >= n.cohort_month
LEFT JOIN active AS a ON a.user_id = n.user_id AND a.month_end = me.month_end
GROUP BY ALL
ORDER BY 1, 2, 3;
