"""Tests that the TUI blocks objective submission when no bundle/model is active.

Required behaviour:
  * If no active bundle is configured, submitting an objective must NOT call
    the orchestrator.  Instead the TUI shows a setup/action card.
  * If Ollama is running but has 0 required models, the TUI shows model-pull
    guidance instead of calling the orchestrator.
  * No exception is raised into the transcript.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from prometheus_cli.models import AutonomyMode, Settings


@pytest.fixture
def transcript_lines():
    return []


@pytest.fixture
def make_app(tmp_path, transcript_lines):
    from prometheus_cli.tui import PrometheusApp

    def _make(demo=False, bundle_path=None, settings=None):
        app = PrometheusApp(
            bundle_path=bundle_path,
            workspace=tmp_path,
            demo=demo,
        )
        original_log = app._log

        def capture_log(msg):
            transcript_lines.append(msg)
            original_log(msg)

        app._log = capture_log
        if settings is not None:
            patch("prometheus_cli.tui.load_settings", return_value=settings).start()
        return app

    return _make


def _settings_no_bundle():
    return Settings(
        mode=AutonomyMode.PILOT,
        active_bundle_id=None,
        bundle_file=None,
    )


class TestNoBundleBlocksObjective:
    def test_no_bundle_shows_setup_card(self, make_app, transcript_lines):
        app = make_app(demo=False, settings=_settings_no_bundle())
        app._run_objective("develop a portfolio website")
        joined = "\n".join(transcript_lines)
        assert "No active bundle configured" in joined
        assert "/setup" in joined
        assert "/bundles" in joined

    def test_no_bundle_does_not_start_orchestrator(self, make_app, transcript_lines):
        app = make_app(demo=False, settings=_settings_no_bundle())
        with patch("prometheus_cli.tui.Orchestrator") as mock_orch:
            app._run_objective("develop a portfolio website")
            assert not mock_orch.called
        assert app.status != "running"

    def test_no_bundle_does_not_create_session_store(self, make_app):
        app = make_app(demo=False, settings=_settings_no_bundle())
        with patch("prometheus_cli.tui.SessionStore") as mock_store:
            app._run_objective("develop a portfolio website")
            assert not mock_store.called
        assert app._store is None

    def test_recommended_bundle_shown_in_card(self, make_app, transcript_lines):
        app = make_app(demo=False, settings=_settings_no_bundle())
        app._run_objective("build something")
        joined = "\n".join(transcript_lines)
        assert "/use" in joined


class TestMissingModelsBlocksObjective:
    def test_ollama_zero_models_shows_pull_card(self, make_app, transcript_lines):
        settings = Settings(
            mode=AutonomyMode.PILOT,
            active_bundle_id="spark-cpu-8gb",
            bundle_file=Path("/fake/bundle.yaml"),
        )
        app = make_app(demo=False, settings=settings)

        from prometheus_cli.onboarding import OllamaStatus

        mock_ollama = OllamaStatus(
            installed=True, running=True, models=[], install_hint="",
        )
        with (
            patch("prometheus_cli.onboarding.check_ollama", return_value=mock_ollama),
            patch("prometheus_cli.tui.load_bundle"),
            patch("prometheus_cli.tui.Orchestrator") as mock_orch,
        ):
            app._run_objective("develop a portfolio website")
            assert not mock_orch.called

        joined = "\n".join(transcript_lines)
        assert "required models" in joined.lower() or "0 models" in joined
        assert "/models pull" in joined or "/setup" in joined

    def test_ollama_missing_some_models_shows_missing_list(
        self, make_app, transcript_lines
    ):
        settings = Settings(
            mode=AutonomyMode.PILOT,
            active_bundle_id="ember-8gb",
            bundle_file=Path("/fake/bundle.yaml"),
        )
        app = make_app(demo=False, settings=settings)

        from prometheus_cli.models import ModelBundle, ModelSpec
        from prometheus_cli.onboarding import OllamaStatus

        bundle = ModelBundle(
            name="Ember",
            models=[
                ModelSpec(model="qwen3.5:4b", role="controller"),
                ModelSpec(model="granite4.1:3b", role="reviewer"),
            ],
        )
        mock_ollama = OllamaStatus(
            installed=True, running=True,
            models=["qwen3.5:4b"], install_hint="",
        )
        with (
            patch("prometheus_cli.onboarding.check_ollama", return_value=mock_ollama),
            patch("prometheus_cli.tui.load_bundle", return_value=bundle),
            patch("prometheus_cli.tui.Orchestrator") as mock_orch,
        ):
            app._run_objective("develop a portfolio website")
            assert not mock_orch.called

        joined = "\n".join(transcript_lines)
        assert "granite4.1:3b" in joined
        assert "/models pull" in joined

    def test_ollama_not_running_shows_start_hint(self, make_app, transcript_lines):
        settings = Settings(
            mode=AutonomyMode.PILOT,
            active_bundle_id="spark-cpu-8gb",
            bundle_file=Path("/fake/bundle.yaml"),
        )
        app = make_app(demo=False, settings=settings)

        from prometheus_cli.onboarding import OllamaStatus

        mock_ollama = OllamaStatus(
            installed=True, running=False, models=[], install_hint="",
        )
        with (
            patch("prometheus_cli.onboarding.check_ollama", return_value=mock_ollama),
            patch("prometheus_cli.tui.Orchestrator") as mock_orch,
        ):
            app._run_objective("build something")
            assert not mock_orch.called

        joined = "\n".join(transcript_lines)
        assert "not running" in joined.lower()
        assert "ollama serve" in joined


class TestDemoModeBypassesGuard:
    def test_demo_mode_does_not_block(self, make_app, transcript_lines):
        app = make_app(demo=True)
        app._run_objective("develop a portfolio website")
        joined = "\n".join(transcript_lines)
        assert "demo mode" in joined.lower()
        assert "No active bundle" not in joined


class TestNoExceptionLeaked:
    def test_no_traceback_in_transcript(self, make_app, transcript_lines):
        app = make_app(demo=False, settings=_settings_no_bundle())
        app._run_objective("develop a portfolio website")
        joined = "\n".join(transcript_lines)
        assert "Traceback" not in joined
        assert "ProgrammingError" not in joined
        assert "sqlite3" not in joined.lower()
