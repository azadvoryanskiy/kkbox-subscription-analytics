-- Listening activity, aggregated to user-weeks.
--
-- The daily logs (410M rows) are read through the staging.user_logs view. Days
-- with impossible play time (negative, or more than 24 hours) are bad records
-- and are left out entirely.
--
-- Aggregating all ~100M user-weeks in one pass needs more memory than a laptop
-- has, so the table is filled in eight passes, one slice of users at a time.

CREATE OR REPLACE TABLE core.user_weeks (
    user_id            INTEGER,
    week               DATE,     -- weeks start on Monday
    active_days        INTEGER,  -- distinct days with listening
    log_rows           INTEGER,  -- rows behind them; more than active_days would mean duplicate days
    songs_played       BIGINT,
    songs_completed    BIGINT,   -- played at least 98.5% through
    daily_unique_songs BIGINT,   -- summed per day, not unique over the week
    minutes_played     DOUBLE
);

CREATE OR REPLACE TEMP MACRO user_weeks_slice(k) AS TABLE
SELECT
    user_id,
    date_trunc('week', date)::DATE AS week,
    -- One bit per weekday: counts distinct days without a costly DISTINCT.
    bit_count(bit_or((1 << (isodow(date) - 1))::INTEGER))::INTEGER AS active_days,
    count(*)::INTEGER AS log_rows,
    sum(num_25 + num_50 + num_75 + num_985 + num_100) AS songs_played,
    sum(num_985 + num_100) AS songs_completed,
    sum(num_unq) AS daily_unique_songs,
    round(sum(total_secs) / 60, 1) AS minutes_played
FROM staging.user_logs
WHERE total_secs BETWEEN 0 AND 86400
  AND user_id % 8 = k
GROUP BY 1, 2
ORDER BY 1, 2;

INSERT INTO core.user_weeks SELECT * FROM user_weeks_slice(0);
INSERT INTO core.user_weeks SELECT * FROM user_weeks_slice(1);
INSERT INTO core.user_weeks SELECT * FROM user_weeks_slice(2);
INSERT INTO core.user_weeks SELECT * FROM user_weeks_slice(3);
INSERT INTO core.user_weeks SELECT * FROM user_weeks_slice(4);
INSERT INTO core.user_weeks SELECT * FROM user_weeks_slice(5);
INSERT INTO core.user_weeks SELECT * FROM user_weeks_slice(6);
INSERT INTO core.user_weeks SELECT * FROM user_weeks_slice(7);
