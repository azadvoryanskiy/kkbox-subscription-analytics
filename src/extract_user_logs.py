"""Convert the 30 GB user_logs.csv inside its .7z archive into a compact Parquet file.

The archive is streamed through 7-Zip straight into DuckDB, so the CSV is never
unpacked to disk. Run once; src/build_db.py then reads the Parquet file.

Needs the 7-Zip command-line tool: brew install sevenzip

Usage (from the repo root):
    python src/extract_user_logs.py
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "raw" / "user_logs.csv.7z"
OUTPUT = ROOT / "data" / "processed" / "user_logs_history.parquet"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = OUTPUT.with_name(OUTPUT.name + ".tmp")
    start = time.time()

    with tempfile.TemporaryDirectory() as tmp:
        fifo = Path(tmp) / "user_logs.csv"
        os.mkfifo(fifo)
        # The shell opens the pipe for writing, so starting 7-Zip doesn't block here.
        unzip = subprocess.Popen(
            f'7zz x -so "{ARCHIVE}" > "{fifo}"', shell=True, stderr=subprocess.DEVNULL
        )
        con = duckdb.connect()
        con.execute("SET memory_limit = '4GB'")
        try:
            con.execute(f"""
                COPY (
                    SELECT
                        msno,
                        try_strptime(date, '%Y%m%d')::DATE AS date,
                        num_25, num_50, num_75, num_985, num_100, num_unq, total_secs
                    FROM read_csv('{fifo}', header = true, auto_detect = false, columns = {{
                        'msno': 'VARCHAR',
                        'date': 'VARCHAR',
                        'num_25': 'INTEGER',
                        'num_50': 'INTEGER',
                        'num_75': 'INTEGER',
                        'num_985': 'INTEGER',
                        'num_100': 'INTEGER',
                        'num_unq': 'INTEGER',
                        'total_secs': 'DOUBLE'
                    }})
                ) TO '{tmp_output}' (FORMAT parquet, COMPRESSION zstd)
            """)
        except BaseException:
            unzip.kill()
            tmp_output.unlink(missing_ok=True)
            raise
        # A failed or cut-off 7-Zip run would look like a clean end of file to
        # DuckDB, so the exit code is the only proof the whole file was read.
        if unzip.wait() != 0:
            tmp_output.unlink(missing_ok=True)
            raise RuntimeError(f"7-Zip exited with code {unzip.returncode}")

    tmp_output.rename(OUTPUT)
    rows, users, first, last, bad_dates = con.execute(f"""
        SELECT count(*), count(DISTINCT msno), min(date), max(date),
               count(*) FILTER (WHERE date IS NULL)
        FROM read_parquet('{OUTPUT}')
    """).fetchone()
    print(f"{rows:,} rows, {users:,} users, {first} to {last}, {bad_dates:,} unparsed dates")
    print(f"{OUTPUT.relative_to(ROOT)}: {OUTPUT.stat().st_size / 1e9:.2f} GB "
          f"in {(time.time() - start) / 60:.1f} min")


if __name__ == "__main__":
    main()
