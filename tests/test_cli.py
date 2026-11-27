import subprocess
import sys

import pytest

from museum import cli

COMMANDS = ["generate", "build", "verify", "bench", "challenge", "report", "all"]


def test_help_lists_every_command(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    for command in COMMANDS:
        assert command in out


@pytest.mark.parametrize(
    "argv",
    [
        ["build", "--model", "kimball"],
        ["verify"],
        ["bench"],
        ["challenge", "run", "n1_1_admin_merger"],
        ["challenge", "diff", "n1_1_admin_merger", "obt"],
        ["report"],
        ["all", "--scale", "small"],
    ],
)
def test_stubs_exit_not_implemented(argv, capsys):
    assert cli.main(argv) == cli.NOT_IMPLEMENTED
    assert "not implemented yet" in capsys.readouterr().err


def test_unknown_model_is_rejected():
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["build", "--model", "snowflake_schema"])
    assert exit_info.value.code == 2


def test_module_entry_point_runs():
    result = subprocess.run(
        [sys.executable, "-m", "museum", "--help"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "generate" in result.stdout
