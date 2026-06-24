"""Tests that TUI worker exceptions are caught and rendered as clean error cards.

When the orchestrator (running in a daemon worker thread) raises an exception,
the TUI must:
  * NOT show a raw Python traceback to the user.
  * Show a clean, user-friendly error card.
  * Log the full traceback to a file under ``~/.prometheus/logs/``.
  * Set the status to ``"error"``.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from prometheus_cli.models import AutonomyMode, Settings


@pytest.fixture
def transcript_lines():
    return []


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "prometheus_home"
    home.mkdir(parents=True, exist_ok=True)
    import prometheus_cli.tui as tui_mod
    import prometheus_cli.config as config_mod

    monkeypatch.setattr(tui_mod, "ensure_home", lambda: home)
    monkeypatch.setattr(config_mod, "CONFIG_HOME", home)
    return home


@pytest.fixture
def make_app(tmp_path, transcript_lines, fake_home):
    from prometheus_cli.tui import PrometheusApp

    def _make():
        app = PrometheusApp(workspace=tmp_path, demo=False)
        original_log = app._log

        def capture_log(msg):
            transcript_lines.append(msg)
            original_log(msg)

        app._log = capture_log
        return app

    return _make


class TestWorkerErrorRendering:
    def test_error_card_rendered_not_raw_traceback(self, make_app, transcript_lines):
        app = make_app()
        exc = RuntimeError("simulated provider failure")
        app._log_worker_error(exc)
        joined = "\n".join(transcript_lines)

        assert "RuntimeError" in joined
        assert "simulated provider failure" in joined
        assert "Objective failed" in joined
        assert "Traceback" not in joined

    def test_error_card_has_log_reference(self, make_app, transcript_lines, fake_home):
        app = make_app()
        exc = ValueError("bad value")
        app._log_worker_error(exc)
        joined = "\n".join(transcript_lines)

        assert "Details logged" in joined
        assert str(fake_home / "logs") in joined

    def test_error_log_file_written(self, make_app, fake_home):
        app = make_app()
        exc = ConnectionError("ollama unreachable")
        app._log_worker_error(exc)

        log_dir = fake_home / "logs"
        assert log_dir.exists()
        log_files = list(log_dir.glob("tui_worker_error_*.log"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "ConnectionError" in content
        assert "ollama unreachable" in content

    def test_status_set_to_error(self, make_app):
        app = make_app()
        app._log_worker_error(Exception("boom"))
        assert app.status == "error"

    def test_long_message_truncated_in_card(self, make_app, transcript_lines):
        app = make_app()
        long_msg = "x" * 500
        app._log_worker_error(ValueError(long_msg))
        joined = "\n".join(transcript_lines)
        assert "…" in joined
        assert "x" * 500 not in joined


class TestOrchestratorExceptionHandling:
    def test_orchestrate_catches_and_logs(self, make_app, transcript_lines, fake_home):
        app = make_app()

        with (
            patch("prometheus_cli.tui.Orchestrator") as mock_orch_class,
            patch("prometheus_cli.tui.SessionStore") as mock_store,
        ):
            mock_orch_class.return_value.run.side_effect = sqlite_prog_error()
            mock_store.return_value = mock_store

            class FakeBundle:
                name = "Test"

            app._orchestrate("objective", Settings(mode=AutonomyMode.PILOT), FakeBundle(), fake_home)

        joined = "\n".join(transcript_lines)
        assert "Objective failed" in joined
        assert app.status == "error"

    def test_orchestrate_catches_generic_exception(
        self, make_app, transcript_lines, fake_home
    ):
        app = make_app()

        with (
            patch("prometheus_cli.tui.Orchestrator") as mock_orch_class,
            patch("prometheus_cli.tui.SessionStore") as mock_store,
        ):
            mock_orch_class.return_value.run.side_effect = RuntimeError("network down")
            mock_store.return_value = mock_store

            class FakeBundle:
                name = "Test"

            app._orchestrate("objective", Settings(mode=AutonomyMode.PILOT), FakeBundle(), fake_home)

        joined = "\n".join(transcript_lines)
        assert "RuntimeError" in joined
        assert "network down" in joined
        assert "Traceback" not in joined


def sqlite_prog_error():
    import sqlite3

    return sqlite3.ProgrammingError(
        "SQLite objects created in a thread can only be used in that same thread."
    )
