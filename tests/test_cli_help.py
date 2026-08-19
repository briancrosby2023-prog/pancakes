from __future__ import annotations

import sys

from operation_pancake.cli import main


def test_cli_help_does_not_require_subcommand(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["operation-pancake", "--help"])

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0

    output = capsys.readouterr().out
    assert "usage: operation-pancake" in output
    assert "search" in output
    assert "acquire" in output
