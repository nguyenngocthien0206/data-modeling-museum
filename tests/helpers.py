from datetime import timedelta
from pathlib import Path

import duckdb

from museum.generator import load_profile
from museum.generator.schemas import KEYS, SCHEMAS


def tiny_profile(seed: int | None = None):
    small = load_profile("small", seed=seed)
    return small.with_changes(
        name="tiny",
        stores=3,
        new_stores=0,
        closed_stores=0,
        members=400,
        end=small.start + timedelta(days=44),
        expect_orders=(0, 10**9),
        expect_lines=(0, 10**9),
    )


def connect(landing: Path) -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB over the landing.

    `<table>` stacks every landed version; `<table>_final` keeps the latest version per key,
    which is the state of the source at the end of the period.
    """
    con = duckdb.connect()
    for table_name in SCHEMAS:
        pattern = (landing / table_name / "*" / "*.parquet").as_posix()
        keys = ", ".join(KEYS[table_name])
        con.execute(f"create view {table_name} as select * from read_parquet('{pattern}')")
        con.execute(
            f"""create view {table_name}_final as select * from {table_name}
                qualify row_number() over (partition by {keys} order by _load_date desc) = 1"""
        )
    return con


def scalar(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()[0]
