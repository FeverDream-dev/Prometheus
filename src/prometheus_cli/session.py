"""SQLite-backed durable session state for PROMETHEUS.

Stores sessions, weighted acceptance-criteria tasks, evidence, events, and Git
checkpoints. Every event carries a monotonic sequence number so a crashed run
can be replayed deterministically without re-executing side effects. Completion
is computed from weighted accepted criteria, never from a model's self-report.

Uses only the standard library (sqlite3) so it works on every platform without
extra dependencies. The database lives under PROMETHEUS_HOME/sessions/.

Thread-safety: connections are opened per-operation and closed immediately
after use. No ``sqlite3.Connection`` or cursor is stored as instance state.
This makes :class:`SessionStore` safe to call from any thread — including
Textual worker threads — without the ``SQLite objects created in a thread can
only be used in that same thread`` error that occurs when a long-lived
connection crosses threads. WAL mode + ``busy_timeout`` allow concurrent
readers and a single writer to coexist gracefully.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return uuid.uuid4().hex


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    objective TEXT NOT NULL,
    mode TEXT NOT NULL,
    bundle_file TEXT,
    workspace TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, seq);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    description TEXT NOT NULL,
    weight INTEGER NOT NULL DEFAULT 1,
    critical INTEGER NOT NULL DEFAULT 0,
    accepted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_id TEXT,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_session ON evidence(session_id);
CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON checkpoints(session_id);
"""


@dataclass
class SessionSummary:
    id: str
    objective: str
    status: str
    completion_percent: float
    created_at: str


class SessionStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_schema(self) -> None:
        with self._tx() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def _query(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    def close(self) -> None:
        pass

    def __enter__(self) -> "SessionStore":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def create_session(
        self,
        objective: str,
        mode: str,
        workspace: str,
        bundle_file: str | None = None,
    ) -> str:
        session_id = _uuid()
        now = _now()
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO sessions (id, objective, mode, bundle_file, workspace, "
                "created_at, updated_at, status) VALUES (?,?,?,?,?,?,?,?)",
                (session_id, objective, mode, bundle_file, workspace, now, now, "active"),
            )
            conn.execute(
                "INSERT INTO events (session_id, type, payload, created_at) VALUES (?,?,?,?)",
                (session_id, "session_created", json.dumps({"objective": objective}), now),
            )
        return session_id

    def append_event(self, session_id: str, event_type: str, payload: dict | None = None) -> int:
        now = _now()
        with self._tx() as conn:
            cursor = conn.execute(
                "INSERT INTO events (session_id, type, payload, created_at) VALUES (?,?,?,?)",
                (session_id, event_type, json.dumps(payload or {}), now),
            )
            conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
            return int(cursor.lastrowid)

    def events_since(self, session_id: str, last_seq: int = 0) -> list[dict]:
        with self._query() as conn:
            rows = conn.execute(
                "SELECT seq, type, payload, created_at FROM events "
                "WHERE session_id=? AND seq>? ORDER BY seq",
                (session_id, last_seq),
            ).fetchall()
        return [{"seq": r["seq"], "type": r["type"], "payload": json.loads(r["payload"]),
                 "created_at": r["created_at"]} for r in rows]

    def last_event_seq(self, session_id: str) -> int:
        with self._query() as conn:
            row = conn.execute(
                "SELECT MAX(seq) AS m FROM events WHERE session_id=?", (session_id,)
            ).fetchone()
        return int(row["m"] or 0)

    def add_task(
        self,
        session_id: str,
        description: str,
        weight: int = 1,
        critical: bool = False,
    ) -> str:
        task_id = _uuid()
        now = _now()
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO tasks (id, session_id, description, weight, critical, "
                "accepted, created_at) VALUES (?,?,?,?,?,?,?)",
                (task_id, session_id, description, weight, int(critical), 0, now),
            )
            conn.execute(
                "INSERT INTO events (session_id, type, payload, created_at) VALUES (?,?,?,?)",
                (session_id, "task_added",
                 json.dumps({"task_id": task_id, "description": description, "weight": weight}),
                 now),
            )
        return task_id

    def set_task_accepted(self, task_id: str, accepted: bool) -> None:
        now = _now()
        with self._tx() as conn:
            row = conn.execute("SELECT session_id FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"task {task_id} not found")
            conn.execute("UPDATE tasks SET accepted=? WHERE id=?", (int(accepted), task_id))
            conn.execute(
                "INSERT INTO events (session_id, type, payload, created_at) VALUES (?,?,?,?)",
                (row["session_id"], "task_accepted" if accepted else "task_rejected",
                 json.dumps({"task_id": task_id}), now),
            )

    def add_evidence(
        self, session_id: str, kind: str, content: str, task_id: str | None = None
    ) -> str:
        evidence_id = _uuid()
        now = _now()
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO evidence (id, session_id, task_id, kind, content, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (evidence_id, session_id, task_id, kind, content, now),
            )
            conn.execute(
                "INSERT INTO events (session_id, type, payload, created_at) VALUES (?,?,?,?)",
                (session_id, "evidence_recorded",
                 json.dumps({"evidence_id": evidence_id, "kind": kind, "task_id": task_id}), now),
            )
        return evidence_id

    def evidence_for(self, session_id: str) -> list[dict]:
        with self._query() as conn:
            rows = conn.execute(
                "SELECT kind, content, task_id, created_at FROM evidence WHERE session_id=? "
                "ORDER BY created_at",
                (session_id,),
            ).fetchall()
        return [{"kind": r["kind"], "content": r["content"], "task_id": r["task_id"],
                 "created_at": r["created_at"]} for r in rows]

    def record_checkpoint(self, session_id: str, commit_sha: str, message: str) -> str:
        checkpoint_id = _uuid()
        now = _now()
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO checkpoints (id, session_id, commit_sha, message, created_at) "
                "VALUES (?,?,?,?,?)",
                (checkpoint_id, session_id, commit_sha, message, now),
            )
            conn.execute(
                "INSERT INTO events (session_id, type, payload, created_at) VALUES (?,?,?,?)",
                (session_id, "checkpoint",
                 json.dumps({"checkpoint_id": checkpoint_id, "commit_sha": commit_sha}), now),
            )
        return checkpoint_id

    def list_checkpoints(self, session_id: str) -> list[dict]:
        with self._query() as conn:
            rows = conn.execute(
                "SELECT id, commit_sha, message, created_at FROM checkpoints "
                "WHERE session_id=? ORDER BY created_at DESC",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _completion_percent_conn(self, conn: sqlite3.Connection, session_id: str) -> float:
        row = conn.execute(
            "SELECT COALESCE(SUM(weight), 0) AS total, "
            "COALESCE(SUM(CASE WHEN accepted=1 THEN weight ELSE 0 END), 0) AS accepted "
            "FROM tasks WHERE session_id=?",
            (session_id,),
        ).fetchone()
        total = int(row["total"])
        if total == 0:
            return 0.0
        return round(int(row["accepted"]) / total * 100, 1)

    def completion_percent(self, session_id: str) -> float:
        with self._query() as conn:
            return self._completion_percent_conn(conn, session_id)

    def all_critical_passed(self, session_id: str) -> bool:
        with self._query() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS unmet FROM tasks WHERE session_id=? AND critical=1 AND accepted=0",
                (session_id,),
            ).fetchone()
        return int(row["unmet"]) == 0

    def meets_target(self, session_id: str, target: int = 95) -> bool:
        return (
            self.completion_percent(session_id) >= target
            and self.all_critical_passed(session_id)
        )

    def set_status(self, session_id: str, status: str) -> None:
        now = _now()
        with self._tx() as conn:
            conn.execute("UPDATE sessions SET status=?, updated_at=? WHERE id=?", (status, now, session_id))
            conn.execute(
                "INSERT INTO events (session_id, type, payload, created_at) VALUES (?,?,?,?)",
                (session_id, "status_changed", json.dumps({"status": status}), now),
            )

    def get_session(self, session_id: str) -> dict | None:
        with self._query() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, limit: int = 20) -> list[SessionSummary]:
        with self._query() as conn:
            rows = conn.execute(
                "SELECT id, objective, status, created_at FROM sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            summaries = [
                SessionSummary(
                    id=r["id"], objective=r["objective"], status=r["status"],
                    completion_percent=self._completion_percent_conn(conn, r["id"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        return summaries

    def task_count(self, session_id: str) -> int:
        with self._query() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM tasks WHERE session_id=?", (session_id,)
            ).fetchone()
        return int(row["c"])
