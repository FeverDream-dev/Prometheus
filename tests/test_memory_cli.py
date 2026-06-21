"""Memory CLI command tests."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from prometheus_cli.cli import app

runner = CliRunner()


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "project"
    ws.mkdir()
    return ws


def test_memory_inspect_empty_workspace(workspace):
    res = runner.invoke(app, ["memory", "inspect", "--workspace", str(workspace)])
    assert res.exit_code == 0
    assert "Intent" in res.output


def test_memory_status(workspace):
    res = runner.invoke(app, ["memory", "status", "--workspace", str(workspace)])
    assert res.exit_code == 0
    assert "PROMETHEUS memory" in res.output or "memory" in res.output.lower()


def test_memory_rebuild(workspace):
    res = runner.invoke(app, ["memory", "rebuild", "--workspace", str(workspace)])
    assert res.exit_code == 0
    assert "Rebuilt" in res.output


def test_memory_export(workspace):
    dest = workspace / "export.json"
    res = runner.invoke(app, ["memory", "export", str(dest), "--workspace", str(workspace)])
    assert res.exit_code == 0


def test_memory_export_default_path(workspace):
    res = runner.invoke(app, ["memory", "export", "--workspace", str(workspace)])
    assert res.exit_code == 0
    assert (workspace / "prometheus-memory-export.json").exists()
