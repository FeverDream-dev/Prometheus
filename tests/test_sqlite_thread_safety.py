"""Regression test for the SQLite thread-safety bug that crashed the TUI.

The bug: ``SessionStore.__init__`` created a single ``sqlite3.connect()`` with
the default ``check_same_thread=True`` and stored it as ``self._conn``. When the
TUI created the store on the main thread and then called it from a Textual
worker thread, Python raised::

    sqlite3.ProgrammingError: SQLite objects created in a thread can only be
    used in that same thread.

These tests prove the exact regression cannot return: a SessionStore created in
one thread must be safely usable from any other thread through the public API.
"""
from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from prometheus_cli.session import SessionStore


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "thread_safety.db")


class TestNoLongLivedConnection:
    def test_no_conn_attribute_stored(self, store: SessionStore):
        assert not hasattr(store, "_conn") or store.__dict__.get("_conn") is None

    def test_close_is_safe_to_call_multiple_times(self, store: SessionStore):
        store.close()
        store.close()

    def test_context_manager_does_not_leak_connection(self, tmp_path: Path):
        with SessionStore(tmp_path / "ctx.db") as s:
            sid = s.create_session("obj", "pilot", "/repo")
            assert s.get_session(sid) is not None


class TestCrossThreadUsage:
    def test_create_session_from_different_thread(self, store: SessionStore):
        sid_holder: list[str] = []

        def worker():
            sid_holder.append(
                store.create_session("cross-thread obj", "pilot", "/repo")
            )

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        assert sid_holder
        session = store.get_session(sid_holder[0])
        assert session is not None
        assert session["objective"] == "cross-thread obj"

    def test_write_and_read_from_multiple_threads(self, store: SessionStore):
        sid = store.create_session("parent obj", "pilot", "/repo")
        errors: list[Exception] = []

        def writer(thread_id: int):
            try:
                for i in range(10):
                    store.append_event(sid, "worker_event", {"thread": thread_id, "i": i})
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        events = store.events_since(sid, 0)
        worker_events = [e for e in events if e["type"] == "worker_event"]
        assert len(worker_events) == 40

    def test_concurrent_thread_pool_writes(self, store: SessionStore):
        sids: list[str] = []

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [
                pool.submit(store.create_session, f"obj-{i}", "pilot", "/repo")
                for i in range(32)
            ]
            for f in futures:
                sids.append(f.result())

        assert len(sids) == 32
        assert len(set(sids)) == 32
        sessions = store.list_sessions(limit=50)
        assert len(sessions) == 32

    def test_read_methods_safe_from_foreign_thread(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        store.add_task(sid, "task A", weight=3)
        store.add_task(sid, "task B", weight=1)
        store.add_evidence(sid, "log", "data")

        results: dict[str, object] = {}

        def reader():
            try:
                results["events"] = store.events_since(sid, 0)
                results["last_seq"] = store.last_event_seq(sid)
                results["evidence"] = store.evidence_for(sid)
                results["completion"] = store.completion_percent(sid)
                results["task_count"] = store.task_count(sid)
                results["session"] = store.get_session(sid)
            except Exception as exc:
                results["error"] = exc

        t = threading.Thread(target=reader)
        t.start()
        t.join()

        assert "error" not in results
        assert isinstance(results["events"], list)
        assert isinstance(results["last_seq"], int)
        assert len(results["evidence"]) == 1
        assert results["completion"] == 0.0
        assert results["task_count"] == 2
        assert results["session"] is not None


class TestWritemodeIntegrity:
    def test_rollback_isolation_per_operation(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        try:
            with store._tx() as conn:
                conn.execute(
                    "INSERT INTO tasks (id, session_id, description, weight, "
                    "critical, accepted, created_at) VALUES (?,?,?,?,?,?,?)",
                    ("bad", sid, "will fail", 1, 0, 0, "now"),
                )
                conn.execute(
                    "INSERT INTO tasks (id, session_id, description, weight, "
                    "critical, accepted, created_at) VALUES (?,?,?,?,?,?,?)",
                    ("bad", sid, "dup", 1, 0, 0, "now"),
                )
        except sqlite3.IntegrityError:
            pass
        assert store.task_count(sid) == 0

    def test_durable_across_reopen_after_threaded_use(self, tmp_path: Path):
        db = tmp_path / "persist.db"
        s1 = SessionStore(db)
        sid = s1.create_session("thread obj", "pilot", "/repo")

        def worker():
            s1.append_event(sid, "thread_event", {"ok": True})

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        s1.close()

        s2 = SessionStore(db)
        events = s2.events_since(sid, 0)
        assert any(e["type"] == "thread_event" for e in events)
        s2.close()
