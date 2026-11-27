"""Reference answers: spec loading, independence from staging and models, Q01 vs manifest."""

import ast
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pytest

import museum.oracle
from museum.oracle import run_oracle
from museum.questions import QUESTIONS_DIR, discover, load_question
from museum.questions.spec import QuestionError


def test_discover_finds_q01():
    ids = [q.id for q in discover()]
    assert "q01" in ids


def test_spec_problems_are_reported(tmp_path):
    folder = tmp_path / "q99_broken"
    folder.mkdir()
    with pytest.raises(QuestionError, match="question.yaml"):
        load_question(folder)
    (folder / "question.yaml").write_text(
        "id: q99\ntitle: t\ndescription: d\ngrain: g\nkeys: [a]\ncolumns: {b: x}\nrules: []\n",
        encoding="utf-8",
    )
    with pytest.raises(QuestionError, match="not listed in columns"):
        load_question(folder)


def test_oracle_python_imports_nothing_from_staging_or_models():
    source = Path(museum.oracle.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not any(name.startswith(("dbt", "museum.warehouse")) for name in imported)


def _referenced_tables(sql: str) -> set[str]:
    sql = re.sub(r"--[^\n]*", "", sql)
    ctes = set(re.findall(r"(\w+)\s+as\s*\(", sql, flags=re.IGNORECASE))
    tables = set(re.findall(r"\b(?:from|join)\s+([a-z_][\w.]*)", sql, flags=re.IGNORECASE))
    return tables - ctes


@pytest.mark.parametrize("question", discover(), ids=lambda q: q.id)
def test_oracle_sql_reads_only_the_landing(question):
    tables = _referenced_tables(question.oracle_sql)
    assert tables, "oracle reads no table"
    assert all(t.startswith("landing_") for t in tables), tables


def test_q01_adds_up_to_the_manifest(small_landing, small_manifest):
    question = load_question(QUESTIONS_DIR / "q01_weekly_store_revenue")
    result = run_oracle(question, small_landing)
    manifest = json.loads(small_manifest.read_text(encoding="utf-8"))
    assert set(result.columns) == set(question.columns)
    assert sum(result.column("net_revenue")) == manifest["net_revenue"]["total"]

    weekly = defaultdict(int)
    for day, net in manifest["net_revenue"]["by_order_date"].items():
        d = date.fromisoformat(day)
        weekly[d - timedelta(days=d.weekday())] += net
    by_week = defaultdict(int)
    for week, net in zip(result.column("week_start"), result.column("net_revenue"), strict=True):
        by_week[week] += net
    assert dict(by_week) == dict(weekly)


def test_q01_has_one_row_per_store_and_week(small_landing):
    question = load_question(QUESTIONS_DIR / "q01_weekly_store_revenue")
    result = run_oracle(question, small_landing)
    keys = list(zip(result.column("store_id"), result.column("week_start"), strict=True))
    assert len(keys) == len(set(keys))
    assert all(week.weekday() == 0 for week in result.column("week_start"))
