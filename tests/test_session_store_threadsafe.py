"""Thread-safety tests for SessionStore covering the full public API surface.

Every public method of :class:`SessionStore` is called from a thread that did
NOT create the store.  This mirrors exactly what happens in the TUI: the store
is constructed on the Textual event-loop thread (``_run_objective``) and then
driven from a daemon worker thread (``_orchestrate`` → ``Orchestrator.run``).
"""
from __future__ import annotations

import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from prometheus_cli.session import SessionStore


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "threadsafe.db")


class TestEveryMethodFromForeignThread:
    def test_all_write_methods(self, store: SessionStore):
        errors: list[str] = []

        def worker():
            try:
                sid = store.create_session("obj", "pilot", "/repo", "b.yaml")
                store.append_event(sid, "step", {"n": 1})
                tid = store.add_task(sid, "task", weight=5, critical=True)
                store.set_task_accepted(tid, True)
                store.add_evidence(sid, "test", "passed")
                store.record_checkpoint(sid, "sha1", "checkpoint msg")
                store.set_status(sid, "complete")
            except Exception:
                errors.append(traceback.format_exc())

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        assert errors == []
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].status == "complete"
        assert sessions[0].completion_percent == 100.0

    def test_all_read_methods(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        store.append_event(sid, "e1", {})
        store.add_task(sid, "t", weight=10)
        store.add_evidence(sid, "log", "data")
        store.record_checkpoint(sid, "sha", "msg")

        results: dict[str, object] = {}
        errors: list[str] = []

        def reader():
            try:
                results["events"] = store.events_since(sid, 0)
                results["last_seq"] = store.last_event_seq(sid)
                results["evidence"] = store.evidence_for(sid)
                results["checkpoints"] = store.list_checkpoints(sid)
                results["completion"] = store.completion_percent(sid)
                results["critical_ok"] = store.all_critical_passed(sid)
                results["meets"] = store.meets_target(sid)
                results["session"] = store.get_session(sid)
                results["list"] = store.list_sessions()
                results["count"] = store.task_count(sid)
            except Exception:
                errors.append(traceback.format_exc())

        t = threading.Thread(target=reader)
        t.start()
        t.join()

        assert errors == []
        assert len(results["events"]) >= 1
        assert isinstance(results["last_seq"], int)
        assert len(results["evidence"]) == 1
        assert len(results["checkpoints"]) == 1
        assert results["session"] is not None
        assert len(results["list"]) == 1
        assert results["count"] == 1


class TestConcurrentMultiStoreAccess:
    def test_two_stores_same_db_concurrent_writes(self, tmp_path: Path):
        db = tmp_path / "shared.db"
        s1 = SessionStore(db)
        s2 = SessionStore(db)
        errors: list[str] = []

        def writer(store: SessionStore, tag: str):
            try:
                for i in range(20):
                    store.append_event(
                        store.create_session(f"{tag}-{i}", "pilot", "/r"),
                        "event",
                        {"tag": tag, "i": i},
                    )
            except Exception:
                errors.append(traceback.format_exc())

        t1 = threading.Thread(target=writer, args=(s1, "A"))
        t2 = threading.Thread(target=writer, args=(s2, "B"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == []
        s3 = SessionStore(db)
        sessions = s3.list_sessions(limit=100)
        assert len(sessions) == 40

    def test_thread_pool_stress(self, tmp_path: Path):
        store = SessionStore(tmp_path / "stress.db")

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = []
            for i in range(50):
                futures.append(
                    pool.submit(
                        store.create_session, f"stress-{i}", "pilot", "/repo"
                    )
                )
            for f in futures:
                f.result()

        assert len(store.list_sessions(limit=100)) == 50


class TestTuiWorkerPattern:
    def test_store_created_on_main_used_in_worker(self, tmp_path: Path):
        store = SessionStore(tmp_path / "tui_pattern.db")
        sid_holder: list[str] = []
        exc_holder: list[Exception] = []

        worker_ready = threading.Event()

        def worker():
            worker_ready.set()
            try:
                sid = store.create_session("tui obj", "pilot", "/repo")
                sid_holder.append(sid)
                store.append_event(sid, "agent_turn", {"step": 1})
                store.add_task(sid, "criterion", weight=10, critical=True)
                store.set_status(sid, "working")
            except Exception as exc:
                exc_holder.append(exc)

        t = threading.Thread(target=worker)
        t.start()
        worker_ready.wait(timeout=2)
        t.join(timeout=5)

        assert exc_holder == []
        assert sid_holder
        assert store.get_session(sid_holder[0])["status"] == "working"
