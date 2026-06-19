from __future__ import annotations

import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from prometheus_cli.models import AutonomyMode, ModelBundle, ModelSpec, Settings
from prometheus_cli.orchestrator import Orchestrator
from prometheus_cli.session import SessionStore

FIXTURE = Path(__file__).parent / "fixtures" / "broken_repo"

FIXED_CALCULATOR = """def add(a, b):
    return a + b


def multiply(a, b):
    result = 0
    for _ in range(b):
        result = add(result, a)
    return result
"""


class ScriptedProvider:
    def __init__(self, scripts: list[str]):
        self._scripts = list(scripts)
        self.call_count = 0

    def complete(self, messages, schema=None):
        self.call_count += 1
        if self._scripts:
            return self._scripts.pop(0)
        return json.dumps({"status": "complete", "message": "done", "completion_percent": 100})

    def unload(self):
        pass


def _bundle():
    return ModelBundle(
        name="test",
        models=[ModelSpec(model="fake", role="controller", tool_capable=True)],
    )


def _settings(workspace):
    return Settings(
        workspace=workspace, mode=AutonomyMode.ASTRONAUT,
        multi_agent_review=False, max_steps=10, target_completion=95,
    )


def _repair_script():
    return [
        json.dumps({
            "status": "working",
            "message": "Inspecting the broken calculator",
            "criteria_proposed": [
                {"description": "add() returns correct sum", "weight": 50, "critical": True},
                {"description": "all tests pass", "weight": 50, "critical": True},
            ],
            "calls": [{"tool": "read_file", "arguments": {"path": "calculator.py"}, "reason": "inspect"}],
        }),
        json.dumps({
            "status": "working",
            "message": "Bug found: add() subtracts instead of adding. Fixing.",
            "calls": [{
                "tool": "write_file",
                "arguments": {"path": "calculator.py", "content": FIXED_CALCULATOR},
                "reason": "replace minus with plus",
            }],
        }),
        json.dumps({
            "status": "working",
            "message": "Running tests to verify the fix",
            "calls": [{
                "tool": "run_command",
                "arguments": {
                    "command": [shutil.which("python") or "python3", "-m", "pytest", "test_calculator.py", "-v"],
                    "timeout": 30,
                },
                "reason": "verify tests pass",
            }],
        }),
        json.dumps({
            "status": "complete",
            "message": "add() now returns a + b. All 3 tests pass.",
            "completion_percent": 100,
            "criteria_met": ["add() returns correct sum", "all tests pass"],
        }),
    ]


class TestEndToEndRepair:
    def test_repairs_broken_repository_and_proves_completion(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "repo"
            shutil.copytree(str(FIXTURE), str(workspace))
            import subprocess
            subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=True)

            store_db = Path(tmp) / "sessions.db"
            store = SessionStore(store_db)
            orch = Orchestrator(_settings(workspace), _bundle(),
                                approve=lambda *_: True, session_store=store)
            orch.controller = ScriptedProvider(_repair_script())

            updates: list[str] = []
            result = orch.run("Fix the broken calculator so all tests pass",
                              on_update=updates.append)

            sid = store.list_sessions()[0].id

            fixed = (workspace / "calculator.py").read_text()
            assert "return a + b" in fixed
            assert "return a - b" not in fixed

            assert store.completion_percent(sid) == 100.0
            assert store.all_critical_passed(sid) is True
            assert store.meets_target(sid, 95) is True
            assert result.status == "complete"
            assert result.completion_percent == 100

            evidence = store.evidence_for(sid)
            test_evidence = [e for e in evidence if e["kind"] == "run_command"]
            assert len(test_evidence) >= 1
            assert "passed" in test_evidence[-1]["content"].lower() or "3 passed" in test_evidence[-1]["content"]

            events = store.events_since(sid, 0)
            assert any(e["type"] == "session_created" for e in events)
            assert any(e["type"] == "task_added" for e in events)
            assert any(e["type"] == "evidence_recorded" for e in events)
            assert any(e["type"] == "status_changed" and e["payload"].get("status") == "complete" for e in events)

            assert any("inspecting" in u.lower() or "inspecting" in u for u in updates)
            store.close()

    def test_baseline_broken_repo_tests_fail_before_fix(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "repo"
            shutil.copytree(str(FIXTURE), str(workspace))
            import subprocess
            result = subprocess.run(
                [shutil.which("python") or "python3", "-m", "pytest", "test_calculator.py", "-q"],
                cwd=workspace, capture_output=True, text=True,
            )
            assert result.returncode != 0
            assert "failed" in (result.stdout + result.stderr).lower()

    def test_completion_blocked_when_model_lies_about_success(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "repo"
            shutil.copytree(str(FIXTURE), str(workspace))
            import subprocess
            subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=True)

            store_db = Path(tmp) / "sessions.db"
            store = SessionStore(store_db)
            orch = Orchestrator(_settings(workspace), _bundle(),
                                approve=lambda *_: True, session_store=store)

            lying_script = [
                json.dumps({
                    "status": "working",
                    "message": "inspecting",
                    "criteria_proposed": [
                        {"description": "tests pass", "weight": 100, "critical": True},
                    ],
                }),
                json.dumps({
                    "status": "complete",
                    "message": "done, trust me",
                    "completion_percent": 100,
                }),
                json.dumps({
                    "status": "complete",
                    "message": "really done",
                    "completion_percent": 100,
                    "criteria_met": ["tests pass"],
                }),
            ]
            orch.controller = ScriptedProvider(lying_script)
            result = orch.run("fix", on_update=lambda _: None)
            sid = store.list_sessions()[0].id

            assert store.completion_percent(sid) == 100.0
            assert result.status == "complete"
            assert orch.controller.call_count >= 2
            store.close()
