-- Staging layer: typed copies of the four KKBox files.
--
-- The CSVs in data/raw are the raw layer. Staging only fixes types and swaps
-- the user key; it drops no rows and makes no cleaning decisions. Cleaning
-- (e.g. junk ages) happens downstream, once the data checks tell us what's there.
--
-- msno is a 44-character hashed user id. We replace it with a compact integer
-- user_id: the database gets much smaller and joins get faster.
--
-- Transactions come from two files that don't overlap: transactions.csv holds
-- rows expiring up to 31 Mar 2017, transactions_v2.csv holds rows expiring later
-- plus all of March 2017. Neither is complete on its own (see docs/data_notes.md).

CREATE SCHEMA IF NOT EXISTS staging;

CREATE OR REPLACE TABLE staging.user_map AS
WITH all_ids AS (
    SELECT msno FROM read_csv('data/raw/members_v3.csv', header = true, all_varchar = true)
    UNION
    SELECT msno FROM read_csv('data/raw/transactions.csv', header = true, all_varchar = true)
    UNION
    SELECT msno FROM read_csv('data/raw/transactions_v2.csv', header = true, all_varchar = true)
    UNION
    SELECT msno FROM read_csv('data/raw/user_logs_v2.csv', header = true, all_varchar = true)
    UNION
    SELECT msno FROM read_csv('data/raw/train_v2.csv', header = true, all_varchar = true)
)
SELECT
    msno,
    row_number() OVER (ORDER BY msno)::INTEGER AS user_id
FROM all_ids;


CREATE OR REPLACE TABLE staging.members AS
SELECT
    u.user_id,
    m.city,
    m.bd AS age_raw,                 -- known to contain zeros and junk values
    NULLIF(m.gender, '') AS gender,
    m.registered_via,
    try_strptime(m.registration_init_time, '%Y%m%d')::DATE AS registration_date
FROM read_csv('data/raw/members_v3.csv', header = true, columns = {
    'msno': 'VARCHAR',
    'city': 'INTEGER',
    'bd': 'INTEGER',
    'gender': 'VARCHAR',
    'registered_via': 'INTEGER',
    'registration_init_time': 'VARCHAR'
}) AS m
JOIN staging.user_map AS u USING (msno)
ORDER BY u.user_id;


CREATE OR REPLACE TABLE staging.transactions AS
SELECT
    u.user_id,
    t.payment_method_id,
    t.payment_plan_days AS plan_days,
    t.plan_list_price AS list_price,
    t.actual_amount_paid AS amount_paid,
    t.is_auto_renew = 1 AS is_auto_renew,
    try_strptime(t.transaction_date, '%Y%m%d')::DATE AS transaction_date,
    try_strptime(t.membership_expire_date, '%Y%m%d')::DATE AS expire_date,
    t.is_cancel = 1 AS is_cancel,
    regexp_extract(t.filename, '([^/]+)\.csv$', 1) AS source_file
FROM read_csv(['data/raw/transactions.csv', 'data/raw/transactions_v2.csv'], header = true, filename = true, columns = {
    'msno': 'VARCHAR',
    'payment_method_id': 'INTEGER',
    'payment_plan_days': 'INTEGER',
    'plan_list_price': 'INTEGER',
    'actual_amount_paid': 'INTEGER',
    'is_auto_renew': 'INTEGER',
    'transaction_date': 'VARCHAR',
    'membership_expire_date': 'VARCHAR',
    'is_cancel': 'INTEGER'
}) AS t
JOIN staging.user_map AS u USING (msno)
ORDER BY u.user_id, transaction_date, expire_date;


CREATE OR REPLACE TABLE staging.user_logs AS
SELECT
    u.user_id,
    try_strptime(l.date, '%Y%m%d')::DATE AS date,
    l.num_25,                        -- songs played < 25% of their length
    l.num_50,                        -- 25–50%
    l.num_75,                        -- 50–75%
    l.num_985,                       -- 75–98.5%
    l.num_100,                       -- 98.5–100%
    l.num_unq,                       -- unique songs played
    l.total_secs                     -- total seconds played
FROM read_csv('data/raw/user_logs_v2.csv', header = true, columns = {
    'msno': 'VARCHAR',
    'date': 'VARCHAR',
    'num_25': 'INTEGER',
    'num_50': 'INTEGER',
    'num_75': 'INTEGER',
    'num_985': 'INTEGER',
    'num_100': 'INTEGER',
    'num_unq': 'INTEGER',
    'total_secs': 'DOUBLE'
}) AS l
JOIN staging.user_map AS u USING (msno)
ORDER BY u.user_id, date;


CREATE OR REPLACE TABLE staging.churn_labels AS
SELECT
    u.user_id,
    t.is_churn = 1 AS is_churn
FROM read_csv('data/raw/train_v2.csv', header = true, columns = {
    'msno': 'VARCHAR',
    'is_churn': 'INTEGER'
}) AS t
JOIN staging.user_map AS u USING (msno)
ORDER BY u.user_id;
