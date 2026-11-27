"""Session fixtures shared by every test package: the small profile, generated once."""

from pathlib import Path

import duckdb
import pytest

from museum.cli import main
from museum.generator import landing_root, load_profile, manifest_path
from museum.warehouse import Paths

from .helpers import connect


@pytest.fixture(scope="session")
def small_data_dir(tmp_path_factory) -> Path:
    """The small profile generated once per test session, through the CLI."""
    data_dir = tmp_path_factory.mktemp("data")
    assert main(["generate", "--scale", "small", "--data-dir", str(data_dir)]) == 0
    return data_dir


@pytest.fixture(scope="session")
def small_landing(small_data_dir) -> Path:
    return landing_root(small_data_dir, load_profile("small"))


@pytest.fixture(scope="session")
def small_manifest(small_data_dir) -> Path:
    return manifest_path(small_data_dir, load_profile("small"))


@pytest.fixture(scope="session")
def small(small_landing) -> duckdb.DuckDBPyConnection:
    return connect(small_landing)


@pytest.fixture(scope="session")
def small_staging(small_data_dir) -> Paths:
    """Staging built (models and dbt tests) on the small profile, through the CLI."""
    args = ["build", "--model", "staging", "--scale", "small", "--data-dir", str(small_data_dir)]
    assert main(args) == 0
    return Paths.for_scale(small_data_dir, "small")
