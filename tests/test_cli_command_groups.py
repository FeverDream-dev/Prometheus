"""Verify every command group required by the product spec is registered in the CLI."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from prometheus_cli.cli import app

runner = CliRunner()


COMMAND_GROUPS = {
    "models": ["list", "inspect", "pull", "unload"],
    "bundles": ["list", "inspect", "qualify"],
    "provider": ["list", "smoke"],
    "sandbox": ["doctor", "test"],
    "mcp": ["list", "test"],
    "memory": [],
    "astronaut": ["start", "status", "pause", "resume", "stop", "tick", "report"],
    "vision": ["doctor", "inspect", "compare"],
    "assets": ["doctor", "setup", "models", "generate", "manifest"],
}


@pytest.mark.parametrize("group,subcommands", list(COMMAND_GROUPS.items()))
def test_command_group_exists(group, subcommands):
    res = runner.invoke(app, [group, "--help"])
    assert res.exit_code == 0, f"'{group} --help' failed: {res.output}"
    for sub in subcommands:
        assert sub in res.output, f"'{group} --help' missing subcommand '{sub}'"


def test_top_level_help_shows_all_groups():
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    for group in COMMAND_GROUPS:
        assert group in res.output, f"group '{group}' not in top-level help"


def test_memory_subcommands():
    res = runner.invoke(app, ["memory", "--help"])
    assert res.exit_code == 0
    for action in ("inspect", "rebuild", "export"):
        assert action in res.output


def test_models_list_runs():
    res = runner.invoke(app, ["models", "list", "--base-url", "http://127.0.0.1:1"])
    assert res.exit_code in (0, 1)


def test_provider_list_runs():
    res = runner.invoke(app, ["provider", "list"])
    assert res.exit_code == 0
    assert "ollama" in res.output


def test_sandbox_doctor_runs():
    res = runner.invoke(app, ["sandbox", "doctor"])
    assert res.exit_code == 0


def test_bundles_list_runs():
    res = runner.invoke(app, ["bundles", "list", "--json"])
    assert res.exit_code == 0


def test_vision_doctor_runs():
    res = runner.invoke(app, ["vision", "doctor"])
    assert res.exit_code == 0


def test_assets_doctor_runs():
    res = runner.invoke(app, ["assets", "doctor"])
    assert res.exit_code == 0
