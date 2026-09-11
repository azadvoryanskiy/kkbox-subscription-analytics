# Data notes

What's actually in the KKBox files, checked right after loading. Every number
here comes from `src/data_checks.py`, so it can be re-run.

## At a glance

| Table | Rows | Users | Period |
|---|---|---|---|
| `members` | 6,769,473 | 6.77M | registrations 2004 – Apr 2017 |
| `transactions` | 22,978,755 | 2.43M | Jan 2015 – Mar 2017 (two files combined) |
| `user_logs` | 18,396,362 | 1.10M | March 2017 only |
| `churn_labels` | 970,960 | 0.97M | subscriptions expiring in March 2017 |

Prices are in New Taiwan dollars (NT$). The standard plan is 30 days for NT$149.

## The two transaction files, and why both are needed

This is the most important thing in the data.

- `transactions.csv` (21.5M rows) looks like the full history, but it isn't.
  It only has transactions that expire by 31 Mar 2017.
- `transactions_v2.csv` (1.4M rows) has everything from March 2017, plus the
  earlier transactions that expire after 31 Mar 2017. It's the other half of
  the history, not a newer version of the same file.
- The two files don't share a single row, and the split is clean: only 14 rows
  (2 users) break the rule. 62,517 users appear only in `transactions_v2.csv`.

**Why it matters.** With `transactions.csv` alone, 1.26M users seem to stop
paying by the end of January 2017. 99,470 of them (7.9%) actually renewed; the
renewal just sits in the other file. For subscriptions ending in December 2016
and January 2017, 21–30% of these "churners" are false. A churn analysis on the
first file alone overstates churn, and does it most in the latest months, which
are the ones a manager cares about.

Both files are loaded into one table. A `source_file` column keeps track of
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
  "the membership ends here".
- 15.8% of renewals happen more than a day before the previous expiry (early or
  overlapping renewals). Subscription time has to be merged by date, not added up.
- 3.0% of renewals come after a gap of more than 30 days. These are win-backs.
- 289,730 user-days have more than one transaction. The period model needs a
  rule for ordering them.
- Volume roughly doubles over two years, and cancellations spike in December
  2015 to about twice their usual rate.

## Listening logs (`user_logs_v2`)

- **Only March 2017:** 31 days, 1.10M users. Listening behaviour is a snapshot
  of the month right before the March renewal decision, not a history.
- The median user was active on 18 days that month and played 76 minutes and
  18 unique songs on an active day.
- 4,200 user-days log more than 24 hours of play in a day. Impossible, so bad records.
- No duplicate user-days and no negative play time.

## Churn labels (`train_v2`)

- 970,960 users whose subscription expires in March 2017. **8.99% churned.**
- KKBox's definition: a user churns if there is no new valid subscription
  within 30 days after the current one expires.
- Every labelled user appears in transactions, 88.7% in members and 77.7% in
  the March logs. Log coverage is the same for churners and non-churners
  (77.5% vs 77.7%), so "no logs" is not a churn signal on its own.

## Two views of churn

Transactions run to 31 Mar 2017. KKBox's labels look for a renewal within 30
days of a March expiry, so their outcome can land in April 2017, which no file
covers. That splits the project into two views:

- **History (expiries Jan 2015 – Feb 2017).** Churn is derived from the
  transactions with the same 30-day rule as KKBox. This gives two years of
  renewal outcomes for cohorts and lifecycle analysis.
- **March 2017 snapshot.** The KKBox label is the outcome, and the March
  listening logs show behaviour just before it. The March transactions also let
  us check our churn rule against KKBox's label.

## Modelling decisions

The churn rule was confirmed on Sept 10 2026. The rest are technical
clean-up choices and can be revisited if the model shows a problem.

| Issue | Decision |
|---|---|
| Two transaction files | Combine them; `source_file` records the origin of each row |
| Duplicate rows | Drop |
| Expiry before 2013 | Exclude the row |
| Expiry after 2018 | Keep; the user is still subscribed when the data ends |
| Unreliable `payment_plan_days` | Take subscription length from the expiry date |
| Cancel rows | The cancel row's expiry date is the end of the membership |
| Churn | No new paid subscription within 30 days of expiry (same as KKBox) |
| Win-back | A paid subscription that starts more than 30 days after the previous one ended |
| Trial | 7-day plan with NT$0 paid |
| Demographics | Not used for segmentation. Too much is missing. Segments come from billing and listening behaviour instead |
| Channel | `registered_via` codes 3, 4, 7, 9; everything else, including missing, is "other/unknown" |
| Play time over 24h a day | Exclude the user-day |
