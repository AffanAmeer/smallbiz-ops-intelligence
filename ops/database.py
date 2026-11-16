"""Store validated tables in a local SQLite file.

SQLite is a full SQL database that lives in a single file (ops.db) and comes
with Python, so there is no server to install. Saving the cleaned data means
the dashboard reads from one trusted source, and you can also open ops.db in
any SQLite tool and query it with plain SQL.
"""

import sqlite3
from pathlib import Path

import pandas as pd

from ops.schemas import SCHEMAS

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "ops.db"


def save_dataset(df: pd.DataFrame, dataset: str, db_path: Path | str = DEFAULT_DB_PATH) -> None:
    """Replace the table for this dataset with the given (already validated) data."""
    if dataset not in SCHEMAS:
        raise ValueError(f"Unknown dataset '{dataset}'.")
    with sqlite3.connect(db_path) as conn:
        df.to_sql(dataset, conn, if_exists="replace", index=False)


def load_dataset(dataset: str, db_path: Path | str = DEFAULT_DB_PATH) -> pd.DataFrame | None:
    """Read a dataset back. Returns None if it has never been saved."""
    if dataset not in SCHEMAS:
        raise ValueError(f"Unknown dataset '{dataset}'.")
    if not Path(db_path).exists():
        return None
    with sqlite3.connect(db_path) as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (dataset,)
        ).fetchone()
        if not exists:
            return None
        df = pd.read_sql_query(f"SELECT * FROM {dataset}", conn)

    # SQLite stores dates as text, so turn them back into real dates.
    for col, col_type in SCHEMAS[dataset]["columns"].items():
        if col_type == "date":
            df[col] = pd.to_datetime(df[col])
    return df


def run_query(sql: str, db_path: Path | str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Run a read-only SQL query, e.g. for the 'SQL explorer' in the app."""
    if not sql.strip().lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed here.")
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        return pd.read_sql_query(sql, conn)
