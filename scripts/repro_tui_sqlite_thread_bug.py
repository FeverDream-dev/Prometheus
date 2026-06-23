#!/usr/bin/env python3
"""Reproduction script for the TUI SQLite thread-safety bug.

Before the fix, this script reproduced the exact crash that users saw::

    sqlite3.ProgrammingError: SQLite objects created in a thread can only be
    used in that same thread.

The bug occurred because SessionStore.__init__ created a long-lived
sqlite3.Connection bound to the constructing thread. When the TUI's worker
thread (spawned by run_worker) tried to use it, Python refused.

This script simulates the TUI objective-submission path:
  1. Create a SessionStore on the main thread (as on_mount / _run_objective does)
  2. Spawn a daemon worker thread (as run_worker does)
  3. Call store methods from the worker thread (as Orchestrator.run does)

Usage::

    python scripts/repro_tui_sqlite_thread_bug.py

Exit code 0 = bug is fixed (no thread error).
Exit code 1 = bug is present (thread error detected).
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import threading
import traceback
from pathlib import Path


def main() -> int:
    print("=" * 64)
    print("PROMETHEUS — TUI SQLite Thread-Safety Reproduction")
    print("=" * 64)
    print()

    try:
        from prometheus_cli.session import SessionStore
    except ImportError:
        print("ERROR: prometheus_cli is not installed.")
        print("Install with: pip install -e '.[dev,tui]'")
        return 2

    tmpdir = Path(tempfile.mkdtemp(prefix="prometheus_repro_"))
    db_path = tmpdir / "prometheus.db"

    print(f"[1/4] Creating SessionStore on main thread (id={threading.get_ident()})")
    print(f"      DB path: {db_path}")
    store = SessionStore(db_path)

    print(f"[2/4] Checking no long-lived connection is stored...")
    conn_attr = getattr(store, "_conn", "MISSING")
    if conn_attr == "MISSING":
        print("      OK: no _conn attribute (per-operation connections)")
    elif conn_attr is None:
        print("      OK: _conn is None (per-operation connections)")
    else:
        print("      WARNING: _conn is a live connection — this would be unsafe!")
        print("      (close() should be a no-op in the new architecture)")
    print()

    errors: list[Exception] = []
    results: dict = {}

    def worker():
        tid = threading.get_ident()
        print(f"[3/4] Worker thread started (id={tid})")
        try:
            sid = store.create_session(
                "develop for me a website that will host my personal portfolio",
                "pilot",
                "/mnt/projects-ssd/test",
            )
            results["session_id"] = sid
            print(f"      create_session OK → {sid[:8]}...")

            seq = store.append_event(sid, "agent_turn", {"step": 1, "msg": "planning"})
            results["event_seq"] = seq
            print(f"      append_event OK → seq={seq}")

            task_id = store.add_task(sid, "Site renders homepage", weight=10, critical=True)
            results["task_id"] = task_id
            print(f"      add_task OK → {task_id[:8]}...")

            store.set_task_accepted(task_id, True)
            print(f"      set_task_accepted OK")

            evidence_id = store.add_evidence(sid, "screenshot", "homepage.png captured")
            print(f"      add_evidence OK → {evidence_id[:8]}...")

            completion = store.completion_percent(sid)
            results["completion"] = completion
            print(f"      completion_percent OK → {completion}%")

            events = store.events_since(sid, 0)
            print(f"      events_since OK → {len(events)} events")

            store.set_status(sid, "complete")
            print(f"      set_status OK → complete")

        except sqlite3.ProgrammingError as exc:
            errors.append(exc)
            print(f"      FAILED: {exc}")
        except Exception as exc:
            errors.append(exc)
            print(f"      FAILED: {type(exc).__name__}: {exc}")

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=10)

    print()
    if errors:
        print("[4/4] RESULT: BUG PRESENT — thread error detected!")
        print()
        print("The SessionStore is NOT thread-safe. Details:")
        for exc in errors:
            traceback.print_exception(type(exc), exc, exc.__traceback__)
        return 1

    print("[4/4] RESULT: BUG FIXED — all operations succeeded from worker thread.")
    print()

    sessions = store.list_sessions()
    assert len(sessions) == 1, f"Expected 1 session, got {len(sessions)}"
    s = sessions[0]
    print(f"  Session:    {s.id[:8]}...")
    print(f"  Objective:  {s.objective}")
    print(f"  Status:     {s.status}")
    print(f"  Completion: {s.completion_percent}%")
    print()
    print("  All store methods called successfully from a foreign thread.")
    print("  The TUI SQLite thread bug is fixed.")
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
