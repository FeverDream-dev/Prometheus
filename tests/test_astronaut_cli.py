"""Astronaut CLI command tests."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from prometheus_cli.cli import app

runner = CliRunner()


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "astronaut-proj"
    ws.mkdir()
    return ws


def test_astronaut_help():
    res = runner.invoke(app, ["astronaut", "--help"])
    assert res.exit_code == 0
    for cmd in ("start", "status", "pause", "resume", "stop", "tick", "report"):
        assert cmd in res.output


def test_astronaut_status_empty(workspace):
    res = runner.invoke(app, ["astronaut", "status", "--workspace", str(workspace)])
    assert res.exit_code == 0


def test_astronaut_pause_creates_file(workspace):
    res = runner.invoke(app, ["astronaut", "pause", "--workspace", str(workspace)])
    assert res.exit_code == 0
    assert (workspace / ".prometheus" / "PAUSE").exists()


def test_astronaut_resume_clears_file(workspace):
    runner.invoke(app, ["astronaut", "pause", "--workspace", str(workspace)])
    assert (workspace / ".prometheus" / "PAUSE").exists()
    res = runner.invoke(app, ["astronaut", "resume", "--workspace", str(workspace)])
    assert res.exit_code == 0
    assert not (workspace / ".prometheus" / "PAUSE").exists()


def test_astronaut_stop_creates_file(workspace):
    res = runner.invoke(app, ["astronaut", "stop", "--workspace", str(workspace)])
    assert res.exit_code == 0
    assert (workspace / ".prometheus" / "STOP").exists()


def test_astronaut_report_empty(workspace):
    res = runner.invoke(app, ["astronaut", "report", "--workspace", str(workspace)])
    assert res.exit_code == 0


def test_astronaut_tick_runs(workspace):
    res = runner.invoke(app, ["astronaut", "tick", "--workspace", str(workspace), "--seed", "42"])
    assert res.exit_code == 0
