"""Fairness locks: fail when locked files change.

`fairness-lock.json` at the repo root records a SHA-256 for every locked file, grouped by
lock name (for example `predictions`, later `models-frozen`). CI runs `check`, so a locked
file can only change if the lock file changes in the same diff, where reviewers see it.

    python -m museum.fairness lock predictions docs/predictions.md
    python -m museum.fairness check

Line endings are normalized before hashing, so a Windows checkout (CRLF) and a Linux
checkout (LF) of the same file give the same hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

LOCK_FILE = "fairness-lock.json"


def file_hash(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def expand(paths: Sequence[str], repo: Path) -> list[str]:
    """Files under the given paths, as sorted repo-relative posix paths."""
    files: set[str] = set()
    for raw in paths:
        target = repo / raw
        if target.is_dir():
            files.update(p.relative_to(repo).as_posix() for p in target.rglob("*") if p.is_file())
        elif target.is_file():
            files.add(target.relative_to(repo).as_posix())
        else:
            raise FileNotFoundError(f"nothing to lock at {raw}")
    return sorted(files)


def snapshot(paths: Sequence[str], repo: Path) -> dict[str, str]:
    return {name: file_hash(repo / name) for name in expand(paths, repo)}


def read_locks(repo: Path) -> dict[str, dict]:
    path = repo / LOCK_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_locks(repo: Path, locks: dict[str, dict]) -> None:
    text = json.dumps(locks, indent=2, sort_keys=True) + "\n"
    (repo / LOCK_FILE).write_text(text, encoding="utf-8")


def lock(name: str, paths: Sequence[str], repo: Path, update: bool = False) -> int:
    locks = read_locks(repo)
    if name in locks and not update:
        print(f"fairness lock {name!r} already exists; use --update to replace it", file=sys.stderr)
        return 1
    locks[name] = {"paths": list(paths), "files": snapshot(paths, repo)}
    write_locks(repo, locks)
    print(f"fairness lock {name!r}: {len(locks[name]['files'])} files recorded")
    return 0


def problems(name: str, entry: dict, repo: Path) -> list[str]:
    recorded: dict[str, str] = entry["files"]
    try:
        current = snapshot(entry["paths"], repo)
    except FileNotFoundError as missing:
        return [f"{name}: {missing}"]
    found = []
    for path in sorted(recorded.keys() | current.keys()):
        if path not in current:
            found.append(f"{name}: {path} was removed")
        elif path not in recorded:
            found.append(f"{name}: {path} was added")
        elif recorded[path] != current[path]:
            found.append(f"{name}: {path} was changed")
    return found


def check(repo: Path) -> int:
    locks = read_locks(repo)
    if not locks:
        print(f"fairness check: no {LOCK_FILE}, nothing is locked yet")
        return 0
    found = [line for name, entry in sorted(locks.items()) for line in problems(name, entry, repo)]
    if found:
        print("fairness check failed, locked files differ from the lock:", file=sys.stderr)
        for line in found:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"fairness check: all locks hold ({', '.join(sorted(locks))})")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m museum.fairness")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repository root")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="fail if any locked file changed")
    lock_cmd = commands.add_parser("lock", help="record hashes for a named lock")
    lock_cmd.add_argument("name")
    lock_cmd.add_argument("paths", nargs="+")
    lock_cmd.add_argument("--update", action="store_true", help="replace an existing lock")
    args = parser.parse_args(argv)
    if args.command == "lock":
        return lock(args.name, args.paths, args.repo, update=args.update)
    return check(args.repo)


if __name__ == "__main__":
    raise SystemExit(main())
