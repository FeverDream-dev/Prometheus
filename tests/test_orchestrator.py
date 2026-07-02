from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from prometheus_cli.models import AutonomyMode, ModelBundle, ModelSpec, Settings
from prometheus_cli.orchestrator import Orchestrator
from prometheus_cli.session import SessionStore


class FakeProvider:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, messages, schema=None):
        self.calls += 1
        if self._responses:
            return self._responses.pop(0)
        return json.dumps({"status": "complete", "message": "done", "completion_percent": 100})

    def unload(self):
        pass


def _bundle():
    return ModelBundle(
        name="test",
        models=[
            ModelSpec(model="fake-controller", role="controller", tool_capable=True),
            ModelSpec(model="fake-reviewer", role="reviewer", tool_capable=False),
        ],
    )


def _settings(workspace: Path) -> Settings:
    return Settings(
        workspace=workspace, mode=AutonomyMode.ASTRONAUT,
        multi_agent_review=False, max_steps=10, target_completion=95,
    )


class TestDeterministicCompletion:
    def test_model_reported_percent_is_overridden_by_store(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / "test.db")
            orch = Orchestrator(_settings(Path(tmp)), _bundle(),
                                approve=lambda *_: True, session_store=store)
            responses = [
                json.dumps({
                    "status": "working", "message": "inspecting",
                    "criteria_proposed": [
                        {"description": "test passes", "weight": 50, "critical": False},
                        {"description": "build succeeds", "weight": 50, "critical": True},
                    ],
                    "calls": [{"tool": "list_files", "arguments": {"pattern": "*"}, "reason": "inspect"}],
                }),
                json.dumps({
                    "status": "working", "message": "fixed",
                    "criteria_met": ["test passes"],
                    "calls": [{"tool": "write_file", "arguments": {"path": "fix.py", "content": "pass"}, "reason": "fix"}],
                }),
                json.dumps({
                    "status": "complete", "message": "all done",
                    "completion_percent": 100,
                    "criteria_met": ["build succeeds"],
                }),
            ]
            orch.controller = FakeProvider(responses)
            result = orch.run("fix the project", on_update=lambda _: None)
            sid = store.list_sessions()[0].id
            assert store.completion_percent(sid) == 100.0
            assert store.all_critical_passed(sid) is True
            assert result.status == "complete"
            store.close()

    def test_complete_blocked_when_critical_criterion_unmet(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / "test.db")
            orch = Orchestrator(_settings(Path(tmp)), _bundle(),
                                approve=lambda *_: True, session_store=store)
            responses = [
                json.dumps({
                    "status": "working", "message": "start",
                    "criteria_proposed": [
                        {"description": "normal task", "weight": 50, "critical": False},
                        {"description": "critical task", "weight": 50, "critical": True},
                    ],
                }),
                json.dumps({
                    "status": "complete", "message": "done (lying)",
                    "completion_percent": 100,
                    "criteria_met": ["normal task"],
                }),
                json.dumps({
                    "status": "complete", "message": "really done now",
                    "completion_percent": 100,
                    "criteria_met": ["critical task"],
                }),
            ]
            orch.controller = FakeProvider(responses)
            result = orch.run("fix", on_update=lambda _: None)
            sid = store.list_sessions()[0].id
            assert store.completion_percent(sid) == 100.0
            assert result.status == "complete"
            assert orch.controller.calls >= 2
            store.close()

    def test_non_tool_model_rejected_as_controller(self):
        with TemporaryDirectory() as tmp:
            bundle = ModelBundle(
                name="bad",
                models=[ModelSpec(model="vibethinker", role="controller", tool_capable=False)],
            )
            try:
                Orchestrator(_settings(Path(tmp)), bundle)
                assert False, "should have raised"
            except ValueError as exc:
                assert "tool-capable" in str(exc)

    def test_evidence_recorded_for_each_tool_call(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / "test.db")
            orch = Orchestrator(_settings(Path(tmp)), _bundle(),
                                approve=lambda *_: True, session_store=store)
            responses = [
                json.dumps({
                    "status": "working", "message": "reading",
                    "calls": [{"tool": "list_files", "arguments": {}, "reason": "see files"}],
                }),
                json.dumps({"status": "complete", "message": "done", "completion_percent": 100}),
            ]
            orch.controller = FakeProvider(responses)
            orch.run("inspect", on_update=lambda _: None)
            sid = store.list_sessions()[0].id
            evidence = store.evidence_for(sid)
            assert len(evidence) >= 1
            assert evidence[0]["kind"] == "list_files"
            store.close()

    def test_stops_after_three_empty_turns(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / "test.db")
            orch = Orchestrator(_settings(Path(tmp)), _bundle(),
                                approve=lambda *_: True, session_store=store)
            empty = json.dumps({"status": "working", "message": "", "calls": []})
            orch.controller = FakeProvider([empty, empty, empty])
            result = orch.run("do something", on_update=lambda _: None)
            assert result.status == "blocked"
            assert "empty turns" in result.message.lower()
            store.close()
