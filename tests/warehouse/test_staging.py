"""The shared staging layer: one view per landed version, one view per latest version."""

from datetime import date

import duckdb
import pytest

from museum.generator.schemas import KEYS
from museum.warehouse import BuildError, Paths, build

from ..helpers import scalar


def staging(paths: Paths) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(paths.database("staging")), read_only=True)


@pytest.mark.parametrize("table_name", sorted(KEYS))
def test_views_match_the_landing(small_staging, small, table_name):
    keys = ", ".join(KEYS[table_name])
    landed_keys = scalar(small, f"select count(*) from (select distinct {keys} from {table_name})")
    landed_rows = scalar(small, f"select count(*) from {table_name}")
    with staging(small_staging) as con:
        assert scalar(con, f"select count(*) from stg_{table_name}") == landed_keys
        assert scalar(con, f"select count(*) from stg_{table_name}__versions") == landed_rows


def test_latest_views_hold_the_newest_version(small_staging, small):
    voided = "select count(*) from {} where status = 'voided'"
    with staging(small_staging) as con:
        assert scalar(con, voided.format("stg_sales_order")) == scalar(
            small, voided.format("sales_order_final")
        )


def test_every_model_database_exists(small_staging):
    for model in ("staging", "3nf", "kimball", "data_vault", "obt"):
        assert small_staging.database(model).exists(), model


def test_phones_are_ten_digits(small_staging):
    with staging(small_staging) as con:
        bad = "select count(*) from stg_customer where not regexp_full_match(phone, '0[0-9]{9}')"
        assert scalar(con, bad) == 0


def test_as_of_hides_later_extracts(small_data_dir, tmp_path):
    paths = Paths.for_scale(small_data_dir, "small", warehouse=tmp_path / "as_of")
    as_of = date(2024, 6, 30)
    build("staging", paths, as_of=as_of)
    with staging(paths) as con:
        for table_name in KEYS:
            newest = scalar(con, f"select max(_load_date) from stg_{table_name}__versions")
            assert newest <= as_of, table_name
        last_sale = scalar(con, "select max(ordered_at) from stg_sales_order")
        assert last_sale.date() <= as_of


def test_build_refuses_a_missing_landing(tmp_path):
    with pytest.raises(BuildError, match="museum generate"):
        build("staging", Paths.for_scale(tmp_path, "small"))


def test_models_not_built_yet_are_reported(small_staging):
    with pytest.raises(NotImplementedError):
        build("kimball", small_staging)
