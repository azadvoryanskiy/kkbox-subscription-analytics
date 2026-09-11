"""Build the local DuckDB database from the raw KKBox CSVs.

Rebuilds data/processed/kkbox.duckdb from scratch: runs every file in sql/
in name order, then prints the row count of each table.

Usage (from the repo root):
    python src/build_db.py
"""

import os
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "kkbox.duckdb"
SQL_DIR = ROOT / "sql"


def main() -> None:
    os.chdir(ROOT)  # SQL files use paths relative to the repo root
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Start from an empty file: DuckDB doesn't shrink a file when tables are
    # replaced, so rebuilding in place keeps growing it.
    DB_PATH.unlink(missing_ok=True)

    con = duckdb.connect(str(DB_PATH))
    con.execute("SET memory_limit = '8GB'")
    con.execute("SET preserve_insertion_order = false")  # explicit ORDER BYs still hold
    # Cap spill-to-disk so a heavy query fails instead of filling the disk.
    con.execute("SET max_temp_directory_size = '6GB'")

    for path in sorted(SQL_DIR.glob("*.sql")):
        start = time.time()
        con.execute(path.read_text())
        print(f"{path.name}: {time.time() - start:.0f}s")

    tables = con.execute("""
        SELECT table_schema || '.' || table_name
        FROM information_schema.tables
        ORDER BY 1
    """).fetchall()
    print()
    for (name,) in tables:
        rows = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"{name:<30} {rows:>12,}")

    con.close()
    print(f"\nDatabase: {DB_PATH.relative_to(ROOT)} ({DB_PATH.stat().st_size / 1e9:.2f} GB)")


if __name__ == "__main__":
    main()
