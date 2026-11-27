"""Write daily extracts in the landing layout.

    <root>/<table>/load_date=YYYY-MM-DD/part-0.parquet

Each file carries a `_load_date` column. A batch that does not match its table schema
(missing or extra columns, wrong types, nulls in a required column) is refused.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from museum.generator.schemas import SCHEMAS


class SchemaMismatch(ValueError):
    """A batch does not match the schema of its table."""


def conform(table_name: str, columns: dict) -> pa.Table:
    schema = SCHEMAS[table_name]
    expected, given = set(schema.names), set(columns)
    if expected != given:
        missing, extra = sorted(expected - given), sorted(given - expected)
        raise SchemaMismatch(f"{table_name}: missing {missing}, unexpected {extra}")
    try:
        table = pa.Table.from_pydict({name: columns[name] for name in schema.names}, schema=schema)
    except (pa.ArrowInvalid, pa.ArrowTypeError) as error:
        raise SchemaMismatch(f"{table_name}: {error}") from error
    for field in schema:
        if not field.nullable and table.column(field.name).null_count:
            raise SchemaMismatch(f"{table_name}: nulls in required column {field.name}")
    return table


class LandingWriter:
    def __init__(self, root: Path):
        self.root = root
        self.rows: dict[str, int] = {}

    def reset(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)

    def path(self, table_name: str, load_date: date) -> Path:
        partition = f"load_date={load_date.isoformat()}"
        return self.root / table_name / partition / "part-0.parquet"

    def write(self, table_name: str, load_date: date, columns: dict) -> Path | None:
        table = conform(table_name, columns)
        if table.num_rows == 0:
            return None
        load = pa.array([load_date] * table.num_rows, type=pa.date32())
        table = table.append_column(pa.field("_load_date", pa.date32(), nullable=False), load)
        target = self.path(table_name, load_date)
        target.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, target, compression="zstd")
        self.rows[table_name] = self.rows.get(table_name, 0) + table.num_rows
        return target
