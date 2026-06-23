"""Tests that TUI objective submission is thread-safe end-to-end.

This exercises the same code path that crashed in production: the TUI creates a
SessionStore on the event-loop thread, then ``run_worker`` spawns a daemon
thread that calls ``Orchestrator.run`` which uses that store.  Before the fix
this raised ``sqlite3.ProgrammingError``.  These tests prove the fix holds.
"""
from __future__ import annotations

import sqlite3
import threading
from unittest.mock import MagicMock

import pytest

from prometheus_cli.models import (
    AgentTurn,
    AutonomyMode,
    ModelBundle,
    ModelSpec,
    Settings,
)
from prometheus_cli.session import SessionStore


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "prometheus_home"
    home.mkdir(parents=True, exist_ok=True)
    import prometheus_cli.tui as tui_mod
    import prometheus_cli.config as config_mod

    monkeypatch.setattr(tui_mod, "ensure_home", lambda: home)
    monkeypatch.setattr(config_mod, "CONFIG_HOME", home)
    return home


def _make_bundle() -> ModelBundle:
    return ModelBundle(
        name="Test Bundle",
        models=[ModelSpec(model="test-model:latest", role="controller")],
    )


class TestObjectiveSubmissionThreadSafe:
    def test_store_created_on_main_used_in_worker_no_error(self, tmp_path):
        store = SessionStore(tmp_path / "ts.db")
        errors: list[Exception] = []

        def worker():
            try:
                sid = store.create_session("build a portfolio site", "pilot", "/repo")
                store.append_event(sid, "started", {})
                store.add_task(sid, "acceptance: site renders", weight=10)
                store.add_evidence(sid, "screenshot", "captured")
            except Exception as exc:
                errors.append(exc)

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=5)

        assert errors == []
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].objective == "build a portfolio site"

    def test_orchestrator_run_in_worker_thread(self, fake_home, tmp_path):
        store = SessionStore(fake_home / "sessions" / "prometheus.db")
        settings = Settings(
            mode=AutonomyMode.PILOT,
            workspace=tmp_path,
            bundle_file=tmp_path / "bundle.yaml",
        )
        bundle = _make_bundle()

        mock_provider = MagicMock()
        mock_provider.complete.return_value = AgentTurn(
            status="complete",
            message="done",
            completion_percent=100,
        ).model_dump_json()

        errors: list[Exception] = []
        result_holder: list = []

        def worker():
            try:
                from prometheus_cli.orchestrator import Orchestrator

                orch = Orchestrator(
                    settings, bundle,
                    approve=lambda c, r: True,
                    session_store=store,
                )
                orch.controller = mock_provider
                result = orch.run("build a portfolio site")
                result_holder.append(result)
            except Exception as exc:
                errors.append(exc)

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=10)

        assert errors == [], f"Worker raised: {errors}"
        assert result_holder
        assert result_holder[0].status in {"complete", "blocked", "needs_user"}

        sessions = store.list_sessions()
        assert len(sessions) >= 1

    def test_concurrent_sessions_different_threads(self, fake_home):
        store = SessionStore(fake_home / "sessions" / "prometheus.db")
        errors: list[Exception] = []

        def make_session(tag: str):
            try:
                sid = store.create_session(f"obj-{tag}", "pilot", "/repo")
                store.append_event(sid, "event", {"tag": tag})
                store.add_task(sid, f"criterion-{tag}", weight=5)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=make_session, args=(f"t{i}",)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == []
        assert len(store.list_sessions(limit=20)) == 8

    def test_sqlite_thread_error_does_not_occur(self, tmp_path):
        store = SessionStore(tmp_path / "regression.db")

        exc_holder: list[Exception] = []

        def worker():
            try:
                store.create_session("obj", "pilot", "/repo")
            except sqlite3.ProgrammingError as exc:
                exc_holder.append(exc)
            except Exception as exc:
                exc_holder.append(exc)

        main_thread = threading.current_thread().ident

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        worker_thread = t.ident
        assert main_thread != worker_thread
        assert exc_holder == []


class TestStoreLifecycleInTui:
    def test_store_closed_after_complete(self, tmp_path, fake_home):
        store = SessionStore(tmp_path / "lifecycle.db")
        sid = store.create_session("obj", "pilot", "/repo")
        store.set_status(sid, "complete")
        store.close()

        store2 = SessionStore(tmp_path / "lifecycle.db")
        assert store2.get_session(sid)["status"] == "complete"
        store2.close()
