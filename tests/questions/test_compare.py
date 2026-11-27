from decimal import Decimal

from museum.questions import Result, compare

KEYS = ("store_id", "week")


def result(*rows, columns=("store_id", "week", "revenue")):
    return Result(columns=columns, rows=tuple(rows))


def test_row_order_does_not_matter():
    a = result((1, "w1", 10), (2, "w1", 20))
    b = result((2, "w1", 20), (1, "w1", 10))
    assert compare(a, b, KEYS).ok


def test_column_order_does_not_matter():
    a = result((1, "w1", 10))
    b = Result(columns=("revenue", "week", "store_id"), rows=((10, "w1", 1),))
    assert compare(a, b, KEYS).ok


def test_integers_must_match_exactly():
    comparison = compare(result((1, "w1", 10)), result((1, "w1", 11)), KEYS)
    assert not comparison.ok
    assert "revenue is 11, expected 10" in comparison.report()


def test_decimals_and_integer_floats_count_as_integers():
    assert compare(result((1, "w1", 10)), result((1, "w1", Decimal("10"))), KEYS).ok
    assert compare(result((1, "w1", 10)), result((1, "w1", 10.0)), KEYS).ok


def test_ratios_are_compared_after_rounding():
    a, b = result((1, "w1", 0.1234561)), result((1, "w1", 0.1234564))
    assert compare(a, b, KEYS, decimals=6).ok
    assert not compare(a, b, KEYS, decimals=7).ok
    assert compare(result((1, "w1", Decimal("0.5000001"))), result((1, "w1", 0.5)), KEYS).ok


def test_missing_and_unexpected_rows_are_reported():
    comparison = compare(
        result((1, "w1", 10), (2, "w1", 20)), result((1, "w1", 10), (3, "w1", 5)), KEYS
    )
    report = comparison.report()
    assert "missing row {'store_id': 2, 'week': 'w1'}" in report
    assert "unexpected row {'store_id': 3, 'week': 'w1'}" in report


def test_duplicate_keys_and_column_mismatch_fail():
    assert not compare(result((1, "w1", 10)), result((1, "w1", 10), (1, "w1", 10)), KEYS).ok
    other = Result(columns=("store_id", "week", "net"), rows=((1, "w1", 10),))
    comparison = compare(result((1, "w1", 10)), other, KEYS)
    assert "columns differ" in comparison.report()


def test_report_is_truncated():
    many = result(*[(i, "w1", i) for i in range(30)])
    report = compare(many, result(), KEYS).report()
    assert "and 20 more" in report
