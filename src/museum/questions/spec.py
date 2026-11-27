"""A question lives in `questions/<id>_<slug>/`: `question.yaml`, `oracle.sql`, per-model SQL."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

QUESTIONS_DIR = Path(__file__).resolve().parents[3] / "questions"
REQUIRED = ("id", "title", "description", "grain", "keys", "columns", "rules")


class QuestionError(ValueError):
    """A question folder is incomplete or inconsistent."""


@dataclass(frozen=True)
class Question:
    id: str
    title: str
    description: str
    grain: str
    keys: tuple[str, ...]
    columns: dict[str, str]
    rules: tuple[str, ...]
    ratio_decimals: int
    folder: Path

    @property
    def oracle_sql(self) -> str:
        return (self.folder / "oracle.sql").read_text(encoding="utf-8")

    def model_sql(self, name: str) -> Path:
        """`kimball.sql` or `<model>__<layer>.sql` next to the spec."""
        return self.folder / f"{name}.sql"


def load_question(folder: Path) -> Question:
    spec_path = folder / "question.yaml"
    if not spec_path.exists():
        raise QuestionError(f"{folder.name}: missing question.yaml")
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED if key not in raw]
    if missing:
        raise QuestionError(f"{folder.name}: question.yaml is missing {missing}")
    if not folder.name.startswith(f"{raw['id']}_"):
        raise QuestionError(f"{folder.name}: folder must start with the id {raw['id']!r}")
    keys = tuple(raw["keys"])
    unknown = [k for k in keys if k not in raw["columns"]]
    if unknown:
        raise QuestionError(f"{folder.name}: keys {unknown} are not listed in columns")
    if not (folder / "oracle.sql").exists():
        raise QuestionError(f"{folder.name}: missing oracle.sql")
    return Question(
        id=str(raw["id"]),
        title=str(raw["title"]),
        description=str(raw["description"]).strip(),
        grain=str(raw["grain"]),
        keys=keys,
        columns={str(k): str(v) for k, v in raw["columns"].items()},
        rules=tuple(str(r) for r in raw["rules"]),
        ratio_decimals=int(raw.get("ratio_decimals", 6)),
        folder=folder,
    )


def discover(root: Path = QUESTIONS_DIR) -> list[Question]:
    """Every main question folder (`q..._...`), in id order."""
    return [load_question(p) for p in sorted(root.glob("q[0-9]*_*")) if p.is_dir()]
