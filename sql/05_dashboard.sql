-- Dashboard marts: small aggregates behind the Evidence dashboard.
--
-- Every table carries the sign-up channel, so one filter can scope the whole
-- page. Definitions match the notebooks and docs/findings.md.

CREATE SCHEMA IF NOT EXISTS marts;

-- Paying subscribers by month and channel (same rules as marts.monthly_subscribers).
CREATE OR REPLACE TABLE marts.dash_monthly AS
WITH months AS (
    SELECT
        range::DATE AS month_start,
        (range + INTERVAL 1 MONTH - INTERVAL 1 DAY)::DATE AS month_end
    FROM range(DATE '2016-01-01', DATE '2017-03-01', INTERVAL 1 MONTH)
),
paid AS (
    SELECT s.first_payment_date AS paid_start, s.end_date, s.paid_number, u.channel
    FROM core.subscriptions AS s
    JOIN core.users AS u USING (user_id)
    WHERE s.paid_number IS NOT NULL AND s.end_date >= s.first_payment_date
)
SELECT
    m.month_start AS month,
    p.channel,
    count(*) FILTER (WHERE p.paid_start < m.month_start AND p.end_date >= m.month_start) AS subscribers_start,
    count(*) FILTER (WHERE p.paid_start BETWEEN m.month_start AND m.month_end AND p.paid_number = 1) AS new_subscribers,
    count(*) FILTER (WHERE p.paid_start BETWEEN m.month_start AND m.month_end AND p.paid_number > 1) AS returning_subscribers,
    count(*) FILTER (WHERE p.end_date BETWEEN m.month_start AND m.month_end) AS churned,
    count(*) FILTER (WHERE p.paid_start <= m.month_end AND p.end_date > m.month_end) AS subscribers_end
FROM months AS m
CROSS JOIN paid AS p
GROUP BY 1, 2
ORDER BY 1, 2;


-- Renewal decisions in 2016: how many, and how many ended in churn.
CREATE OR REPLACE TABLE marts.dash_renewals AS
SELECT
    date_trunc('month', r.period_end)::DATE AS month,
    u.channel,
    CASE WHEN r.is_auto_renew THEN 'Auto-renew' ELSE 'Manual' END AS payment_type,
    CASE WHEN r.payment_number = 1 THEN '1st'
         WHEN r.payment_number <= 3 THEN '2nd–3rd'
         WHEN r.payment_number <= 12 THEN '4th–12th'
         ELSE '13th+' END AS tenure,
    CASE WHEN r.payment_number = 1 THEN 1 WHEN r.payment_number <= 3 THEN 2
         WHEN r.payment_number <= 12 THEN 3 ELSE 4 END AS tenure_order,
    count(*) AS decisions,
    sum(r.churned::INT) AS churned
FROM core.renewals AS r
JOIN core.users AS u USING (user_id)
WHERE r.period_end BETWEEN DATE '2016-01-01' AND DATE '2016-12-31'
GROUP BY ALL
ORDER BY 1, 2, 3, 5;


-- Monthly-plan renewals in 2016 by listening in the ~4 weeks before the
-- period ended.
CREATE OR REPLACE TABLE marts.dash_listening AS
WITH decisions AS (
    SELECT row_number() OVER () AS id, user_id, period_end, churned, is_auto_renew
    FROM core.renewals
    WHERE period_end BETWEEN DATE '2016-01-01' AND DATE '2016-12-31' AND plan_days <= 31
),
activity AS (
    SELECT d.id, coalesce(sum(w.active_days), 0) AS days_last4
    FROM decisions AS d
    LEFT JOIN core.user_weeks AS w
        ON w.user_id = d.user_id AND w.week >= d.period_end - 34 AND w.week + 6 < d.period_end
    GROUP BY d.id
)
SELECT
    u.channel,
    CASE WHEN d.is_auto_renew THEN 'Auto-renew' ELSE 'Manual' END AS payment_type,
    CASE WHEN a.days_last4 = 0 THEN '0' WHEN a.days_last4 <= 7 THEN '1–7'
         WHEN a.days_last4 <= 14 THEN '8–14' WHEN a.days_last4 <= 21 THEN '15–21'
         ELSE '22–28' END AS active_days,
    CASE WHEN a.days_last4 = 0 THEN 1 WHEN a.days_last4 <= 7 THEN 2
         WHEN a.days_last4 <= 14 THEN 3 WHEN a.days_last4 <= 21 THEN 4 ELSE 5 END AS bucket_order,
    count(*) AS decisions,
    sum(d.churned::INT) AS churned
FROM decisions AS d
JOIN activity AS a USING (id)
JOIN core.users AS u USING (user_id)
GROUP BY ALL
ORDER BY 1, 2, 4;


-- Paid subscribers who churned Jul 2015 – Jun 2016: how many paid again, and when.
CREATE OR REPLACE TABLE marts.dash_winback AS
WITH paid AS (
    SELECT
        s.*,
        lead(s.first_payment_date) OVER (PARTITION BY s.user_id ORDER BY s.subscription_number)
            AS next_paid_start
    FROM core.subscriptions AS s
    WHERE s.is_paid
),
lost AS (
    SELECT
        p.user_id,
        CASE WHEN p.ended_with_cancel THEN 'Cancelled'
             WHEN p.last_auto_renew THEN 'Auto-renew payment stopped'
             ELSE 'Manual, didn''t renew' END AS how_it_ended,
        p.next_paid_start - p.end_date AS days_to_return
    FROM paid AS p
    WHERE p.status = 'churned' AND p.end_date BETWEEN DATE '2015-07-01' AND DATE '2016-06-30'
)
SELECT
    u.channel,
    l.how_it_ended,
    count(*) AS churned,
    count(*) FILTER (WHERE l.days_to_return <= 90) AS back_90d,
    count(*) FILTER (WHERE l.days_to_return <= 180) AS back_180d,
    count(*) FILTER (WHERE l.days_to_return <= 270) AS back_270d
FROM lost AS l
JOIN core.users AS u USING (user_id)
GROUP BY ALL
ORDER BY 1, 2;


-- The switcher check (docs/findings.md, question 3): monthly subscriptions
-- with two payments on one setup, then a third payment on the same or the other.
CREATE OR REPLACE TABLE marts.dash_switchers AS
WITH p AS (
    SELECT
        user_id,
        subscription_number,
        max(CASE WHEN payment_number = 1 THEN is_auto_renew::INT END) AS a1,
        max(CASE WHEN payment_number = 2 THEN is_auto_renew::INT END) AS a2,
        max(CASE WHEN payment_number = 3 THEN is_auto_renew::INT END) AS a3,
        max(CASE WHEN payment_number = 3 THEN period_end END) AS end3,
        max(CASE WHEN payment_number = 3 THEN churned::INT END) AS churn3,
        max(CASE WHEN payment_number = 4 THEN churned::INT END) AS churn4,
        max(CASE WHEN payment_number = 5 THEN churned::INT END) AS churn5,
        max(plan_days) FILTER (WHERE payment_number <= 5) AS max_plan
    FROM core.renewals
    GROUP BY 1, 2
)
SELECT
    CASE WHEN a1 = 0 AND a3 = 1 THEN 'Manual, then switched to auto-renew'
         WHEN a1 = 0 AND a3 = 0 THEN 'Manual, stayed manual'
         WHEN a1 = 1 AND a3 = 0 THEN 'Auto-renew, then switched to manual'
         ELSE 'Auto-renew, stayed on auto-renew' END AS path,
    CASE WHEN a3 = 1 THEN 'Now on auto-renew' ELSE 'Now manual' END AS setup_now,
    CASE WHEN a1 = 0 AND a3 = 1 THEN 1 WHEN a1 = 0 THEN 2 WHEN a3 = 0 THEN 3 ELSE 4 END AS path_order,
    count(*) AS subscriptions,
    sum((coalesce(churn3, 0) + coalesce(churn4, 0) + coalesce(churn5, 0) > 0)::INT) AS churned_by_5th
FROM p
WHERE a3 IS NOT NULL AND a1 = a2 AND max_plan <= 31
  AND end3 BETWEEN DATE '2015-03-01' AND DATE '2016-09-30'
GROUP BY ALL
ORDER BY path_order;
