from datetime import date, datetime

import numpy as np
import pyarrow.parquet as pq
import pytest

from museum.generator.landing import LandingWriter, SchemaMismatch
from museum.generator.seeds import stream

AT = datetime(2024, 1, 1, 8, 0)


def channel_columns(**overrides):
    columns = {
        "channel_code": ["dine_in"],
        "channel_name": ["Tại quầy"],
        "created_at": [AT],
        "updated_at": [AT],
    }
    columns.update(overrides)
    return columns


def test_writes_partitioned_file_with_load_date(tmp_path):
    writer = LandingWriter(tmp_path)
    path = writer.write("channel", date(2024, 1, 1), channel_columns())
    assert path == tmp_path / "channel" / "load_date=2024-01-01" / "part-0.parquet"
    table = pq.read_table(path)
    assert table.column("_load_date").to_pylist() == [date(2024, 1, 1)]
    assert writer.rows == {"channel": 1}


def test_empty_batch_writes_nothing(tmp_path):
    writer = LandingWriter(tmp_path)
    empty = {k: [] for k in channel_columns()}
    assert writer.write("channel", date(2024, 1, 1), empty) is None
    assert not (tmp_path / "channel").exists()


def test_rejects_missing_and_extra_columns(tmp_path):
    writer = LandingWriter(tmp_path)
    columns = channel_columns()
    del columns["channel_name"]
    with pytest.raises(SchemaMismatch, match="missing"):
        writer.write("channel", date(2024, 1, 1), columns)
    with pytest.raises(SchemaMismatch, match="unexpected"):
        writer.write("channel", date(2024, 1, 1), channel_columns(colour=["red"]))


def test_rejects_wrong_types_and_required_nulls(tmp_path):
    writer = LandingWriter(tmp_path)
    with pytest.raises(SchemaMismatch):
        writer.write("channel", date(2024, 1, 1), channel_columns(created_at=["yesterday"]))
    with pytest.raises(SchemaMismatch, match="nulls"):
        writer.write("channel", date(2024, 1, 1), channel_columns(channel_name=[None]))


def test_streams_are_reproducible_and_independent():
    a = stream(1, "sales", 5).random(3)
    assert np.array_equal(a, stream(1, "sales", 5).random(3))
    assert not np.array_equal(a, stream(1, "sales", 6).random(3))
    assert not np.array_equal(a, stream(1, "shifts", 5).random(3))
    assert not np.array_equal(a, stream(2, "sales", 5).random(3))
