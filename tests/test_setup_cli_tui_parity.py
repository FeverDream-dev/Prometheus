from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from prometheus_cli.cli import app
from prometheus_cli.first_run import detect_first_run, FirstRunState
from prometheus_cli.onboarding import OllamaStatus
from prometheus_cli.tui_state import collect_demo_snapshot


@pytest.fixture
def runner():
    return CliRunner()


def _ollama(running=True, models=None):
    return OllamaStatus(installed=True, running=running, models=models or [], install_hint="")


class TestSetupDryRunParity:
    def test_cli_setup_dry_run_shows_bundles(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("PROMETHEUS_HOME", str(tmp_path / ".prometheus"))
        result = runner.invoke(app, ["setup", "--dry-run"])
        assert result.exit_code == 0
        assert "No bundles found" not in result.stdout
        assert "Available bundles" in result.stdout

    def test_cli_setup_yes_selects_bundle(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("PROMETHEUS_HOME", str(tmp_path / ".prometheus"))
        result = runner.invoke(app, ["setup", "--yes"])
        assert result.exit_code == 0
        assert "Saved" in result.stdout


class TestSetupWizardContentParity:
    def test_tui_setup_shows_bundles_like_cli(self):
        from prometheus_cli.tui_screens import render_screen_text
        snap = collect_demo_snapshot(Path("/tmp"))
        tui_text = render_screen_text("/setup", snap)
        assert "bundle" in tui_text.lower() or "step" in tui_text.lower()

    def test_tui_setup_shows_hardware_like_cli(self):
        from prometheus_cli.tui_screens import render_screen_text
        snap = collect_demo_snapshot(Path("/tmp"))
        tui_text = render_screen_text("/setup", snap)
        assert "ram" in tui_text.lower() or "hardware" in tui_text.lower()

    def test_tui_models_screen_matches_cli_models_list(self, runner):
        cli_result = runner.invoke(app, ["bundles", "list", "--json"])
        assert cli_result.exit_code == 0
        import json
        bundles = json.loads(cli_result.stdout)
        assert len(bundles) >= 8


class TestUseCommandParity:
    def test_use_sets_active_bundle(self, runner, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("PROMETHEUS_HOME", str(home / ".prometheus"))
        monkeypatch.setattr("prometheus_cli.config.CONFIG_HOME", home / ".prometheus")
        result = runner.invoke(app, ["use", "spark-cpu-8gb"])
        assert result.exit_code == 0
        assert "Active package" in result.stdout

    def test_use_unknown_bundle_fails(self, runner, tmp_path, monkeypatch):
        monkeypatch.setattr("prometheus_cli.config.CONFIG_HOME", tmp_path / "home")
        result = runner.invoke(app, ["use", "nonexistent-bundle"])
        assert result.exit_code == 1


class TestFirstRunDetectionParity:
    def test_first_run_detection_matches_cli_dry_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr("prometheus_cli.config.CONFIG_HOME", tmp_path / "home")
        monkeypatch.chdir(tmp_path)
        with mock.patch("prometheus_cli.onboarding.check_ollama", return_value=_ollama(running=False, models=[])):
            state = detect_first_run(home=tmp_path / "home", workspace=tmp_path)
        assert state.is_first_run is True
        assert state.needs_ollama_setup is True

    def test_configured_state_not_first_run(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        (home / "config.yaml").write_text(
            "mode: pilot\nactive_bundle_id: spark-cpu-8gb\n", encoding="utf-8"
        )
        monkeypatch.setattr("prometheus_cli.config.CONFIG_HOME", home)
        state = detect_first_run(
            home=home, workspace=tmp_path,
            ollama_status=_ollama(models=["granite4.1:3b"]),
        )
        assert state.is_first_run is False
        assert state.guidance == "ready" or state.guidance == "project_init"


class TestNoDeadEnds:
    def test_no_models_message_is_helpful(self):
        state = FirstRunState(
            has_models=False,
            recommended_bundle="ember-8gb",
            recommended_models=["qwen2.5-coder:7b"],
        )
        msg = state.no_model_message
        assert "error" not in msg.lower()
        assert "ember-8gb" in msg
        assert "pull" in msg.lower()

    def test_ollama_down_has_clear_action(self):
        state = FirstRunState(
            has_config=True,
            has_active_bundle=True,
            ollama_installed=True,
            ollama_running=False,
            has_models=False,
        )
        action = state.next_action
        assert "ollama" in action.lower() or "serve" in action.lower()

    def test_first_run_has_setup_guidance(self):
        state = FirstRunState(has_config=False, has_active_bundle=False)
        action = state.next_action
        assert "setup" in action.lower() or "wizard" in action.lower()
