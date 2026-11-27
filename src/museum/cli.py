"""Command line entry point: `uv run museum <command>`.

Commands that are not built yet are stubs that exit with code 2.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from museum import __version__

MODELS = ("staging", "3nf", "kimball", "data_vault", "obt")
SCALES = ("small", "medium", "large")
NOT_IMPLEMENTED = 2


def _add_scale(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scale", choices=SCALES, default="small", help="data size profile")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="museum",
        description="One coffee chain, four data models, measured side by side.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    generate = commands.add_parser("generate", help="generate the simulated source data")
    _add_scale(generate)
    generate.add_argument("--seed", type=int, default=None, help="override the profile seed")
    generate.add_argument(
        "--data-dir", type=Path, default=Path("data"), help="where data/<scale>/landing goes"
    )

    build = commands.add_parser("build", help="build staging and the data models")
    _add_scale(build)
    build.add_argument("--model", choices=MODELS, help="build only this model")

    verify = commands.add_parser("verify", help="check every model against the reference answers")
    _add_scale(verify)
    verify.add_argument("--model", choices=MODELS[1:], help="verify only this model")

    bench = commands.add_parser("bench", help="run the metrics")
    _add_scale(bench)

    challenge = commands.add_parser("challenge", help="run or inspect a challenge")
    challenge_commands = challenge.add_subparsers(dest="action", required=True, metavar="<action>")
    run = challenge_commands.add_parser("run", help="run a challenge on the models")
    run.add_argument("challenge_id")
    _add_scale(run)
    diff = challenge_commands.add_parser("diff", help="print a model's diff for a challenge")
    diff.add_argument("challenge_id")
    diff.add_argument("model", choices=MODELS[1:])

    report = commands.add_parser("report", help="generate result tables and charts")
    _add_scale(report)

    run_all = commands.add_parser("all", help="run everything in order")
    _add_scale(run_all)

    return parser


def run_generate(args: argparse.Namespace) -> int:
    from museum.generator import generate, landing_root, load_profile

    profile = load_profile(args.scale, seed=args.seed)
    summary = generate(profile, args.data_dir)
    print(f"generated {summary.profile} (seed {summary.seed}, {summary.days} days)")
    print(f"  landing: {landing_root(args.data_dir, profile)}")
    for table_name, rows in summary.rows.items():
        print(f"  {table_name:<16} {rows:>12,} rows")
    print(f"  took {summary.seconds} s")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        return run_generate(args)
    name = args.command if args.command != "challenge" else f"challenge {args.action}"
    print(f"museum {name}: not implemented yet", file=sys.stderr)
    return NOT_IMPLEMENTED
