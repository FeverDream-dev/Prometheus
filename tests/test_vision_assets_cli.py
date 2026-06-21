from __future__ import annotations

from typer.testing import CliRunner

from prometheus_cli.cli import app

runner = CliRunner()


def test_vision_doctor_runs():
    result = runner.invoke(app, ["vision", "doctor"])
    assert result.exit_code == 0
    assert "vision doctor" in result.output.lower() or "Vision" in result.output


def test_vision_help_shows_commands():
    result = runner.invoke(app, ["vision", "--help"])
    assert result.exit_code == 0
    assert "doctor" in result.output
    assert "inspect" in result.output
    assert "compare" in result.output


def test_assets_doctor_runs():
    result = runner.invoke(app, ["assets", "doctor"])
    assert result.exit_code == 0
    assert "AssetForge" in result.output


def test_assets_help_shows_commands():
    result = runner.invoke(app, ["assets", "--help"])
    assert result.exit_code == 0
    for cmd in ("doctor", "setup", "models", "generate", "remove-bg", "manifest"):
        assert cmd in result.output


def test_assets_models_lists_known_models():
    result = runner.invoke(app, ["assets", "models"])
    assert result.exit_code == 0
    assert "sdxl-turbo" in result.output
    assert "FLUX.1-schnell" in result.output


def test_astronaut_tick_runs():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        result = runner.invoke(app, ["astronaut", "tick", "--workspace", td, "--seed", "42"])
        assert result.exit_code == 0
        assert "tick" in result.output.lower()


def test_astronaut_report_shows_empty_state():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        result = runner.invoke(app, ["astronaut", "report", "--workspace", td])
        assert result.exit_code == 0


def test_tui_has_vision_and_assets_slash_commands():
    from prometheus_cli.tui_commands import SLASH_COMMANDS
    assert "/vision" in SLASH_COMMANDS
    assert "/assets" in SLASH_COMMANDS
    assert "/astronaut" in SLASH_COMMANDS


def test_assets_setup_runs():
    result = runner.invoke(app, ["assets", "setup"])
    assert result.exit_code == 0


def test_cli_top_level_has_vision_and_assets():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "vision" in result.output
    assert "assets" in result.output
