from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from prometheus_cli.session import SessionStore


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    db = tmp_path / "test.db"
    s = SessionStore(db)
    yield s
    s.close()


class TestSessionLifecycle:
    def test_create_and_get_session(self, store: SessionStore):
        sid = store.create_session("fix the bug", "pilot", "/repo", "bundle.yaml")
        session = store.get_session(sid)
        assert session is not None
        assert session["objective"] == "fix the bug"
        assert session["mode"] == "pilot"
        assert session["status"] == "active"

    def test_missing_session_returns_none(self, store: SessionStore):
        assert store.get_session("nonexistent") is None

    def test_set_status_records_event(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        store.set_status(sid, "complete")
        assert store.get_session(sid)["status"] == "complete"
        events = store.events_since(sid, 0)
        assert any(e["type"] == "status_changed" for e in events)


class TestEventLog:
    def test_monotonic_sequence_numbers(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        seq1 = store.append_event(sid, "step", {"n": 1})
        seq2 = store.append_event(sid, "step", {"n": 2})
        seq3 = store.append_event(sid, "step", {"n": 3})
        assert seq1 < seq2 < seq3

    def test_events_since_returns_only_new(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        s1 = store.append_event(sid, "a", {})
        store.append_event(sid, "b", {})
        store.append_event(sid, "c", {})
        new = store.events_since(sid, s1)
        assert len(new) == 2
        assert new[0]["type"] == "b"
        assert new[1]["type"] == "c"

    def test_last_event_seq(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        store.append_event(sid, "a", {})
        last = store.append_event(sid, "b", {})
        assert store.last_event_seq(sid) == last

    def test_resume_from_checkpoint_reads_missed_events(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        checkpoint = store.append_event(sid, "checkpoint", {})
        store.append_event(sid, "step", {"after": True})
        missed = store.events_since(sid, checkpoint)
        assert len(missed) == 1
        assert missed[0]["payload"]["after"] is True


class TestCompletionCalculation:
    def test_empty_session_is_zero(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        assert store.completion_percent(sid) == 0.0

    def test_weighted_accepted_over_total(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        t1 = store.add_task(sid, "task A", weight=3)
        store.add_task(sid, "task B", weight=1)
        store.set_task_accepted(t1, True)
        assert store.completion_percent(sid) == 75.0

    def test_all_tasks_accepted_is_100(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        t1 = store.add_task(sid, "a", weight=2)
        t2 = store.add_task(sid, "b", weight=3)
        store.set_task_accepted(t1, True)
        store.set_task_accepted(t2, True)
        assert store.completion_percent(sid) == 100.0

    def test_critical_gate_blocks_meets_target(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        t1 = store.add_task(sid, "normal", weight=1)
        store.add_task(sid, "critical", weight=99, critical=True)
        store.set_task_accepted(t1, True)
        assert store.completion_percent(sid) == 1.0
        assert store.all_critical_passed(sid) is False
        assert store.meets_target(sid, target=95) is False

    def test_critical_passing_lifts_gate(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        t1 = store.add_task(sid, "critical", weight=100, critical=True)
        store.set_task_accepted(t1, True)
        assert store.all_critical_passed(sid) is True
        assert store.meets_target(sid, target=95) is True

    def test_below_target_does_not_meet(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        t1 = store.add_task(sid, "a", weight=10)
        store.add_task(sid, "b", weight=10)
        store.set_task_accepted(t1, True)
        assert store.meets_target(sid, target=95) is False


class TestEvidence:
    def test_record_and_retrieve_evidence(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        tid = store.add_task(sid, "task")
        store.add_evidence(sid, "test_output", "5 passed", task_id=tid)
        store.add_evidence(sid, "build_log", "exit 0")
        evidence = store.evidence_for(sid)
        assert len(evidence) == 2
        assert evidence[0]["kind"] == "test_output"
        assert evidence[1]["kind"] == "build_log"


class TestCheckpoints:
    def test_record_and_list_checkpoints(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        store.record_checkpoint(sid, "abc123", "initial checkpoint")
        store.record_checkpoint(sid, "def456", "after fix")
        checkpoints = store.list_checkpoints(sid)
        assert len(checkpoints) == 2
        assert checkpoints[0]["commit_sha"] == "def456"

    def test_rollback_target_is_most_recent(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        store.record_checkpoint(sid, "good", "stable")
        store.record_checkpoint(sid, "bad", "broke things")
        latest = store.list_checkpoints(sid)[0]
        assert latest["commit_sha"] == "bad"


class TestListingAndCounts:
    def test_list_sessions_ordered_by_recency(self, store: SessionStore):
        s1 = store.create_session("first", "pilot", "/a")
        s2 = store.create_session("second", "pilot", "/b")
        sessions = store.list_sessions()
        assert sessions[0].id == s2
        assert sessions[1].id == s1
        assert sessions[0].objective == "second"

    def test_task_count(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        store.add_task(sid, "a")
        store.add_task(sid, "b")
        store.add_task(sid, "c")
        assert store.task_count(sid) == 3


class TestDurability:
    def test_data_survives_reopen(self, tmp_path: Path):
        db = tmp_path / "persist.db"
        sid = SessionStore(db).create_session("obj", "pilot", "/repo")
        store2 = SessionStore(db)
        assert store2.get_session(sid) is not None
        store2.close()

    def test_wal_mode_enabled(self, store: SessionStore):
        with store._query() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"

    def test_transaction_rollback_on_error(self, store: SessionStore):
        sid = store.create_session("obj", "pilot", "/repo")
        try:
            with store._tx() as conn:
                conn.execute("INSERT INTO tasks (id, session_id, description, weight, critical, accepted, created_at) VALUES (?,?,?,?,?,?,?)",
                             ("dup", sid, "x", 1, 0, 0, "now"))
                conn.execute("INSERT INTO tasks (id, session_id, description, weight, critical, accepted, created_at) VALUES (?,?,?,?,?,?,?)",
                             ("dup", sid, "duplicate id should fail", 1, 0, 0, "now"))
        except sqlite3.IntegrityError:
            pass
        assert store.task_count(sid) == 0
