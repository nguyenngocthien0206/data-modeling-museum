from datetime import timedelta
from pathlib import Path

import duckdb
import pytest

from museum.cli import main
from museum.generator import landing_root, load_profile
from museum.generator.schemas import SCHEMAS


def tiny_profile(seed: int | None = None):
    small = load_profile("small", seed=seed)
    return small.with_changes(
        name="tiny",
        stores=3,
        members=400,
        end=small.start + timedelta(days=44),
        expect_orders=(0, 10**9),
        expect_lines=(0, 10**9),
    )


def connect(landing: Path) -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with one view per landed table (all extracts stacked)."""
    con = duckdb.connect()
    for table_name in SCHEMAS:
        pattern = (landing / table_name / "*" / "*.parquet").as_posix()
        con.execute(f"create view {table_name} as select * from read_parquet('{pattern}')")
    return con


def scalar(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()[0]


@pytest.fixture(scope="session")
def small_landing(tmp_path_factory) -> Path:
    """The small profile generated once per test session, through the CLI."""
    data_dir = tmp_path_factory.mktemp("data")
    assert main(["generate", "--scale", "small", "--data-dir", str(data_dir)]) == 0
    return landing_root(data_dir, load_profile("small"))


@pytest.fixture(scope="session")
def small(small_landing) -> duckdb.DuckDBPyConnection:
    return connect(small_landing)
