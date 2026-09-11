# KKBox subscriber churn: product analytics case study

**Question:** which subscribers is a music streaming service losing, and what would I change?

Work in progress. The full write-up will live in `docs/` and on the portfolio site.

The questions the project answers: [docs/questions.md](docs/questions.md).

## Data

KKBox is a Taiwanese music streaming service. The data comes from the
[WSDM Cup 2018 churn challenge](https://www.kaggle.com/competitions/kkbox-churn-prediction-challenge)
on Kaggle: real subscription transactions and daily listening logs.

The data is from 2015–2017. It's old, but subscription mechanics (plans, auto-renew,
cancellations, win-back) haven't changed.

To reproduce, accept the competition rules on Kaggle, download these files and
unpack them into `data/raw/`:

| File | Contents |
|---|---|
| `members_v3.csv` | users: city, age, registration channel and date |
| `transactions.csv` | subscription history Jan 2015 – Feb 2017, but only transactions that expire by 31 Mar 2017 |
| `transactions_v2.csv` | March 2017, plus the earlier transactions that expire after 31 Mar 2017 |
| `user_logs.csv.7z` | daily listening activity, Jan 2015 – Feb 2017 (keep it zipped: 7 GB, 30 GB unpacked) |
| `user_logs_v2.csv` | daily listening activity, March 2017 |
| `train.csv` | KKBox churn labels for subscriptions expiring in February 2017 |
| `train_v2.csv` | KKBox churn labels for subscriptions expiring in March 2017 |

The `_v2` files are not newer versions: each one continues the history of the
file without `_v2`. You need both of each pair.

The data is not committed to this repo.

What's in the data, its quirks and how they're handled: [docs/data_notes.md](docs/data_notes.md).

## Build

```bash
brew install sevenzip                 # 7-Zip command-line tool, to stream the logs archive
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/extract_user_logs.py       # once: user_logs.csv.7z -> Parquet, ~2 min
python src/build_db.py                # builds data/processed/kkbox.duckdb
python src/data_checks.py             # optional: the numbers behind docs/data_notes.md
```
