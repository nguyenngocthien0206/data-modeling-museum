"""Compare a model's answer with the reference answer.

Rows are matched on the question's key columns, so row order never matters. Integers
(and decimals with no fractional part) must match exactly; other numbers are compared
after rounding to the question's `ratio_decimals`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

MAX_REPORTED = 10


@dataclass(frozen=True)
class Result:
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]

    @classmethod
    def from_cursor(cls, cursor) -> Result:
        columns = tuple(d[0] for d in cursor.description)
        return cls(columns=columns, rows=tuple(tuple(r) for r in cursor.fetchall()))

    def column(self, name: str) -> list:
        i = self.columns.index(name)
        return [row[i] for row in self.rows]


@dataclass
class Comparison:
    ok: bool
    problems: list[str] = field(default_factory=list)

    def report(self) -> str:
        if self.ok:
            return "answers match"
        shown = self.problems[:MAX_REPORTED]
        hidden = len(self.problems) - len(shown)
        lines = ["answers differ:", *(f"  {p}" for p in shown)]
        if hidden:
            lines.append(f"  ... and {hidden} more")
        return "\n".join(lines)


def normalize(value, decimals: int):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else round(float(value), decimals)
    if isinstance(value, float):
        return int(value) if value.is_integer() else round(value, decimals)
    return value


def _index(result: Result, keys: tuple[str, ...], decimals: int, side: str, problems: list):
    positions = [result.columns.index(k) for k in keys]
    rows: dict[tuple, dict[str, object]] = {}
    for row in result.rows:
        values = {c: normalize(v, decimals) for c, v in zip(result.columns, row, strict=True)}
        key = tuple(values[result.columns[i]] for i in positions)
        if key in rows:
            problems.append(f"{side} has the key {key} more than once")
        rows[key] = values
    return rows


def compare(
    expected: Result, actual: Result, keys: tuple[str, ...], decimals: int = 6
) -> Comparison:
    problems: list[str] = []
    if set(expected.columns) != set(actual.columns):
        missing = sorted(set(expected.columns) - set(actual.columns))
        extra = sorted(set(actual.columns) - set(expected.columns))
        return Comparison(False, [f"columns differ: missing {missing}, unexpected {extra}"])
    want = _index(expected, keys, decimals, "reference", problems)
    got = _index(actual, keys, decimals, "answer", problems)
    for key in sorted(want.keys() - got.keys(), key=repr):
        problems.append(f"missing row {dict(zip(keys, key, strict=True))}")
    for key in sorted(got.keys() - want.keys(), key=repr):
        problems.append(f"unexpected row {dict(zip(keys, key, strict=True))}")
    for key in sorted(want.keys() & got.keys(), key=repr):
        for column in expected.columns:
            if want[key][column] != got[key][column]:
                where = dict(zip(keys, key, strict=True))
                problems.append(
                    f"{where}: {column} is {got[key][column]!r}, expected {want[key][column]!r}"
                )
    return Comparison(ok=not problems, problems=problems)
