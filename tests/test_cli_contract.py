from __future__ import annotations

from devvault.cli import main


def test_cli_help_returns_0() -> None:
    assert main(["-h"]) == 0


def test_cli_parse_error_returns_2() -> None:
    # argparse uses exit code 2 for parse errors
    assert main(["--definitely-not-a-real-flag"]) == 2


def test_cli_subcommand_help_returns_0() -> None:
    assert main(["scan", "-h"]) == 0
