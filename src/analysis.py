"""Small helpers shared by the notebooks."""

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "kkbox.duckdb"


def connect(memory_limit: str = "6GB") -> duckdb.DuckDBPyConnection:
    """Read-only connection to the project database, with a cap on spill-to-disk."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute(f"SET memory_limit = '{memory_limit}'")
    con.execute("SET max_temp_directory_size = '5GB'")
    return con


def km(days, churned) -> pd.Series:
    """Kaplan-Meier curve: share still subscribed after each number of days.

    `days` is how long each subscription was observed, `churned` is 1 if it
    ended in churn and 0 if it was still running when the data ends.
    """
    t = (
        pd.DataFrame({"d": days, "e": churned})
        .groupby("d")
        .agg(events=("e", "sum"), n=("e", "size"))
        .sort_index()
    )
    at_risk = t["n"][::-1].cumsum()[::-1]
    return (1 - t["events"] / at_risk).cumprod()


def survival_at(curve: pd.Series, day: float) -> float:
    before = curve[curve.index <= day]
    return float(before.iloc[-1]) if len(before) else 1.0
