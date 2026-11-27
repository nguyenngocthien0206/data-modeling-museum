"""Run the dbt project in `warehouse/` against one scale's data.

Paths reach dbt through environment variables read by `profiles.yml` and the landing
source; dbt's own target and log folders go next to the DuckDB files, so a build never
writes into the repository.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2] / "warehouse"

# Model id (CLI, folders, docs) -> DuckDB file and catalog name. A catalog cannot start
# with a digit, so the 3NF model lives in `three_nf` (ADR-0005).
DATABASES = {
    "staging": "staging",
    "3nf": "three_nf",
    "kimball": "kimball",
    "data_vault": "data_vault",
    "obt": "obt",
}
BUILT_MODELS = ("staging",)  # dbt folders that exist so far


@dataclass(frozen=True)
class Paths:
    landing: Path
    warehouse: Path

    @classmethod
    def for_scale(cls, data_dir: Path, scale: str, warehouse: Path | None = None) -> Paths:
        root = Path(data_dir) / scale
        return cls(landing=root / "landing", warehouse=Path(warehouse or root / "warehouse"))

    def database(self, model: str) -> Path:
        return self.warehouse / f"{DATABASES[model]}.duckdb"


class BuildError(RuntimeError):
    """dbt reported a failure."""


def run_dbt(command: list[str], paths: Paths, as_of: date | None = None) -> None:
    """Run dbt in its own process.

    dbt-duckdb keeps its DuckDB connection open for the life of the process, so running it
    in-process would lock the files against anyone reading them afterwards (tests, the
    question runner). A child process also keeps build timings free of our own overhead.
    """
    if not paths.landing.is_dir():
        raise BuildError(f"no landing at {paths.landing}; run `museum generate` first")
    paths.warehouse.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "MUSEUM_LANDING_DIR": paths.landing.resolve().as_posix(),
        "MUSEUM_WAREHOUSE_DIR": paths.warehouse.resolve().as_posix(),
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
    }
    dbt_dir = paths.warehouse / ".dbt"
    variables = {"as_of_load_date": as_of.isoformat() if as_of else None}
    args = [
        sys.executable,
        "-c",
        "import sys; from dbt.cli.main import cli; sys.exit(cli())",
        *command,
        "--project-dir",
        str(PROJECT_DIR),
        "--profiles-dir",
        str(PROJECT_DIR),
        "--target-path",
        str(dbt_dir / "target"),
        "--log-path",
        str(dbt_dir / "logs"),
        "--vars",
        json.dumps(variables),
    ]
    completed = subprocess.run(args, env=env, check=False)
    if completed.returncode != 0:
        log = dbt_dir / "logs" / "dbt.log"
        raise BuildError(f"dbt {' '.join(command)} failed (exit {completed.returncode}); see {log}")


def build(model: str | None, paths: Paths, as_of: date | None = None) -> list[str]:
    """`dbt build` (models and tests) for one model, or for everything built so far."""
    targets = [model] if model else list(BUILT_MODELS)
    for target in targets:
        if target not in BUILT_MODELS:
            raise NotImplementedError(f"model {target!r} is not implemented yet")
    selector = " ".join(f"path:models/{t}" for t in targets)
    run_dbt(["build", "--select", selector], paths, as_of)
    return targets
