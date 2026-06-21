"""Vision CLI command tests."""
from __future__ import annotations

from typer.testing import CliRunner

from prometheus_cli.cli import app

runner = CliRunner()


def test_vision_help():
    res = runner.invoke(app, ["vision", "--help"])
    assert res.exit_code == 0
    for cmd in ("doctor", "inspect", "compare"):
        assert cmd in res.output


def test_vision_doctor_runs():
    res = runner.invoke(app, ["vision", "doctor"])
    assert res.exit_code == 0
    assert "vision doctor" in res.output.lower() or "Playwright" in res.output


def test_vision_compare_nonexistent_files():
    res = runner.invoke(app, ["vision", "compare", "/nonexistent1.json", "/nonexistent2.json"])
    assert res.exit_code != 0
