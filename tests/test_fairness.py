import json
from pathlib import Path

import pytest

from museum import fairness

PREDICTIONS = "docs/predictions.md"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / PREDICTIONS).write_text("kimball wins Q01\n", encoding="utf-8")
    (tmp_path / "warehouse").mkdir()
    (tmp_path / "warehouse" / "dim.sql").write_text("select 1\n", encoding="utf-8")
    return tmp_path


def test_passes_when_nothing_is_locked(repo, capsys):
    assert fairness.check(repo) == 0
    assert "nothing is locked" in capsys.readouterr().out


def test_passes_while_locked_files_are_unchanged(repo):
    assert fairness.lock("predictions", [PREDICTIONS], repo) == 0
    (repo / "README.md").write_text("other files may change\n", encoding="utf-8")
    assert fairness.check(repo) == 0


def test_fails_when_a_locked_file_changes(repo, capsys):
    fairness.lock("predictions", [PREDICTIONS], repo)
    (repo / PREDICTIONS).write_text("obt wins Q01\n", encoding="utf-8")
    assert fairness.check(repo) == 1
    assert f"{PREDICTIONS} was changed" in capsys.readouterr().err


def test_line_endings_do_not_matter(repo):
    fairness.lock("predictions", [PREDICTIONS], repo)
    (repo / PREDICTIONS).write_bytes(b"kimball wins Q01\r\n")
    assert fairness.check(repo) == 0


def test_folder_lock_catches_added_and_removed_files(repo, capsys):
    fairness.lock("models-frozen", ["warehouse"], repo)
    (repo / "warehouse" / "new_model.sql").write_text("select 2\n", encoding="utf-8")
    (repo / "warehouse" / "dim.sql").unlink()
    assert fairness.check(repo) == 1
    err = capsys.readouterr().err
    assert "warehouse/new_model.sql was added" in err
    assert "warehouse/dim.sql was removed" in err


def test_relocking_needs_update_flag(repo):
    fairness.lock("predictions", [PREDICTIONS], repo)
    (repo / PREDICTIONS).write_text("changed during review\n", encoding="utf-8")
    assert fairness.lock("predictions", [PREDICTIONS], repo) == 1
    assert fairness.lock("predictions", [PREDICTIONS], repo, update=True) == 0
    assert fairness.check(repo) == 0


def test_lock_file_is_readable_json(repo):
    fairness.lock("predictions", [PREDICTIONS], repo)
    locks = json.loads((repo / fairness.LOCK_FILE).read_text(encoding="utf-8"))
    assert locks["predictions"]["paths"] == [PREDICTIONS]
    assert set(locks["predictions"]["files"]) == {PREDICTIONS}


def test_cli(repo):
    assert fairness.main(["--repo", str(repo), "lock", "predictions", PREDICTIONS]) == 0
    assert fairness.main(["--repo", str(repo), "check"]) == 0
