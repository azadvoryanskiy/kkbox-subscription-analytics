# KKBox subscriber churn: product analytics case study

**Question:** which subscribers is a music streaming service losing, and what
would I change?

KKBox, a Taiwanese music streaming service, grew its paying base 30% in 14
months, from 904,000 to 1.18M. But that growth is running out: new sign-ups fell
from about 49,000 a month to 38,000 while churn stayed flat, so by February 2017
it was losing almost exactly as many subscribers as it signed up. This project
models 23M real billing transactions and 410M days of listening to find where
that churn comes from.

**Read the [case study](docs/case_study.md)** for the short version, or
**[open the interactive dashboard](https://azadvoryanskiy.github.io/kkbox-subscription-analytics/)** (source in [dashboard/](dashboard/)).

## What I found

- **Churn is mostly about how people pay.** Manual renewals are 13% of renewal
  decisions and 57% of churn. The first renewal is the riskiest moment.
- **Channels, long plans and free trials look bad in the raw numbers**, but once
  payment type and tenure are accounted for, the differences almost disappear.
- **It's the setup, not just the person.** Manual payers who switched to
  auto-renew churned at about a third of the rate of those who stayed manual.

**Recommendation:** switch auto-renew on by default at checkout for new
subscribers in the channels where most people pay manually, tested with an A/B
test on churn at the first renewal (design in the case study).

Three things in the data had to be fixed before any of this was trustworthy:
half the transaction history sits in a second file, KKBox's own churn label
counts payments rather than membership, and some "churn" was billing outages.
All three are in the [data notes](docs/data_notes.md).

## What's in the repo

| Path | What it is |
|---|---|
| [docs/case_study.md](docs/case_study.md) | The case study: problem, data, findings, recommendation, test design |
| [docs/findings.md](docs/findings.md) | The full analysis, question by question |
| [docs/questions.md](docs/questions.md) | The six questions the project answers |
| [docs/data_notes.md](docs/data_notes.md) | What's in the data, its traps, and every modelling rule |
| [notebooks/](notebooks/) | The analysis, with charts: [01 subscribers and lifecycle](notebooks/01_subscribers_and_lifecycle.ipynb), [02 who churns](notebooks/02_who_churns.ipynb), [03 listening and win-back](notebooks/03_listening_and_winback.ipynb) |
| [dashboard/](dashboard/) | The interactive dashboard: one static page (HTML + Apache ECharts) on small exported aggregates, filterable by channel |
| [sql/](sql/) | The data model in DuckDB SQL: staging, weekly listening, subscriptions, marts, dashboard marts |
| [src/](src/) | Build script, data checks, logs extraction, dashboard export, chart and analysis helpers |

The data is from 2015–2017. It's old, but subscription mechanics (plans,
auto-renew, cancellations, win-back) haven't changed.

## Data

The data comes from the
[WSDM Cup 2018 churn challenge](https://www.kaggle.com/competitions/kkbox-churn-prediction-challenge)
on Kaggle. It isn't committed to this repo. To reproduce, accept the
competition rules on Kaggle and put these files into `data/raw/`:

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

## Build

```bash
brew install sevenzip                 # 7-Zip command-line tool, to stream the logs archive
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/extract_user_logs.py       # once: user_logs.csv.7z -> Parquet, ~2 min
python src/build_db.py                # builds data/processed/kkbox.duckdb, ~3 min
python src/data_checks.py             # optional: the numbers behind docs/data_notes.md
jupytext --to ipynb --execute notebooks/01_subscribers_and_lifecycle.py   # re-run a notebook
python src/export_dashboard_data.py   # refresh dashboard/data/*.json
python -m http.server 8765 --directory dashboard   # preview the dashboard at localhost:8765
```

The dashboard is a plain static page: no build step, no server. It reads six
small JSON files of aggregates (about 27 KB in total, nothing at user level),
so it can be published without the underlying data.

The notebooks are kept as `.py` files (the source) and `.ipynb` files (the
rendered output with charts). Charts are saved to `docs/img/`.
