"""Reference answers, computed straight from the raw landing (design section 8).

The oracle never touches staging, dbt or any model: it opens a fresh in-memory DuckDB,
exposes every landed table as `landing_<table>` (all versions, exactly as extracted), and
runs the question's `oracle.sql`, which does its own deduplication. A bug in staging can
therefore never make four models agree on a wrong number.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from museum.generator.schemas import SCHEMAS
from museum.questions import Question, Result


def landing_connection(landing: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for table_name in SCHEMAS:
        pattern = (Path(landing) / table_name / "*" / "*.parquet").as_posix()
        con.execute(
            f"create view landing_{table_name} as "
            f"select * from read_parquet('{pattern}', hive_partitioning = false)"
        )
    return con


def run_oracle(question: Question, landing: Path) -> Result:
    with landing_connection(landing) as con:
        return Result.from_cursor(con.execute(question.oracle_sql))
