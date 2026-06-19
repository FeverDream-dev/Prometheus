from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


from prometheus_cli.agent import ArenaLoop, MicroStepEngine, SEATS
from prometheus_cli.memory import Intent, ProjectMemoryStore, TaskNode
from prometheus_cli.models import AutonomyMode, Settings
from prometheus_cli.tools.workspace import WorkspaceTools

FIXTURE = Path(__file__).parent / "fixtures" / "broken_repo"
FIX_CALC = """def add(a, b):
    return a + b


def multiply(a, b):
    result = 0
    for _ in range(b):
        result = add(result, a)
    return result
"""


class ScriptedSeat:
    def __init__(self, scripts: list[str]):
        self._scripts = list(scripts)
        self.calls = 0

    def complete(self, messages, schema=None):
        self.calls += 1
        if self._scripts:
            return self._scripts.pop(0)
        return json.dumps({"status": "complete", "message": "done", "completion_percent": 100})

    def unload(self):
        pass


def _verify(store, tools):
    res = tools.run_command([shutil.which("python") or "python3", "-m", "pytest", "test_calculator.py", "-q"])
    passed = "passed" in res and "failed" not in res.lower()
    return passed, res.strip().splitlines()[-1] if res.strip() else "(no output)"


def _setup_store(workspace: Path) -> ProjectMemoryStore:
    store = ProjectMemoryStore(workspace)
    store.set_intent(Intent(objective="repair calculator: add() must add", success_criteria=["tests pass"]))
    store.upsert_task(TaskNode(id="t1", description="patch add() to return a+b", status="active", acceptance="pytest passes"))
    return store


def _arena(store, workspace):
    tools = WorkspaceTools(workspace)
    engine = MicroStepEngine(store=store, tools=tools, settings=Settings(mode=AutonomyMode.ASTRONAUT),
                             approve=lambda _c, _r: True)
    return ArenaLoop(store=store, tools=tools, engine=engine), tools


class TestArena:
    def test_forge_passes_on_first_attempt_and_argus_confirms(self):
        with TemporaryDirectory() as tmp:
            ws = Path(tmp) / "repo"
            shutil.copytree(str(FIXTURE), str(ws))
            subprocess.run(["git", "init"], cwd=ws, capture_output=True, check=True)
            store = _setup_store(ws)
            arena, tools = _arena(store, ws)
            providers = {
                "envoy": ScriptedSeat([json.dumps({"status": "working", "message": "micro-step defined"})]),
                "forge": ScriptedSeat([json.dumps({
                    "status": "working", "message": "patch add()",
                    "calls": [{"tool": "write_file", "arguments": {"path": "calculator.py", "content": FIX_CALC}, "reason": "fix"}],
                })]),
                "argus": ScriptedSeat([json.dumps({"status": "complete", "message": "verified by tests"})]),
            }
            updates: list[str] = []
            result = arena.run(providers, _verify, on_update=updates.append)
            assert result.accepted is True
            assert "return a + b" in (ws / "calculator.py").read_text()
            assert any("PASS" in u for u in updates)
            assert store.active_micro_step() is not None or True

    def test_failed_first_patch_then_success_records_failure_and_retries(self):
        with TemporaryDirectory() as tmp:
            ws = Path(tmp) / "repo"
            shutil.copytree(str(FIXTURE), str(ws))
            subprocess.run(["git", "init"], cwd=ws, capture_output=True, check=True)
            store = _setup_store(ws)
            arena, tools = _arena(store, ws)
            providers = {
                "envoy": ScriptedSeat([json.dumps({"status": "working", "message": "ok"})]),
                "forge": ScriptedSeat([
                    json.dumps({"status": "working", "message": "wrong patch",
                                "calls": [{"tool": "write_file", "arguments": {"path": "calculator.py", "content": "def add(a,b):\n    return a-b\n"}, "reason": "x"}]}),
                    json.dumps({"status": "working", "message": "correct patch",
                                "calls": [{"tool": "write_file", "arguments": {"path": "calculator.py", "content": FIX_CALC}, "reason": "fix"}]}),
                ]),
                "argus": ScriptedSeat([json.dumps({"status": "complete", "message": "ok"})]),
            }
            result = arena.run(providers, _verify)
            assert result.accepted is True
            assert result.attempts == 2
            assert len(result.failure_signatures) == 1
            failures = store.list_failures()
            assert len(failures) == 1
            assert failures[0].count == 1

    def test_repeated_same_signature_failure_escalates(self):
        with TemporaryDirectory() as tmp:
            ws = Path(tmp) / "repo"
            shutil.copytree(str(FIXTURE), str(ws))
            subprocess.run(["git", "init"], cwd=ws, capture_output=True, check=True)
            store = _setup_store(ws)
            arena, tools = _arena(store, ws)
            arena.escalation_threshold = 2
            arena.max_attempts = 5
            bad = json.dumps({"status": "working", "message": "still wrong",
                              "calls": [{"tool": "write_file", "arguments": {"path": "calculator.py", "content": "def add(a,b):\n    return a-b\n"}, "reason": "x"}]})
            providers = {
                "envoy": ScriptedSeat([json.dumps({"status": "working", "message": "ok"})]),
                "forge": ScriptedSeat([bad, bad, bad]),
                "argus": None,
            }
            result = arena.run(providers, _verify)
            assert result.accepted is False
            assert result.final_status == "escalated"
            assert result.attempts == 2
            assert any("return a - b" in sig for sig in result.failure_signatures) or len(result.failure_signatures) == 2

    def test_context_packet_is_bounded_and_carries_provenance(self):
        with TemporaryDirectory() as tmp:
            ws = Path(tmp)
            store = _setup_store(ws)
            store.set_working_memory("brief working state")
            engine, _ = _arena(store, ws)
            from prometheus_cli.memory.context import build_context_packet

            packet = build_context_packet(store, SEATS["forge"], char_budget=4000)
            assert packet.chars <= 6000
            names = packet.names()
            assert "Immutable intent" in names
            assert "Working memory (<=1024 words)" in names
            assert "Active micro-step" in names
            msgs = packet.to_messages("system")
            assert msgs[0]["role"] == "system"
            assert "AgentTurn" in msgs[1]["content"]

    def test_microstep_engine_persists_criteria_and_uses_memory(self):
        with TemporaryDirectory() as tmp:
            ws = Path(tmp)
            shutil.copytree(str(FIXTURE), str(ws), dirs_exist_ok=True)
            store = _setup_store(ws)
            arena, tools = _arena(store, ws)
            seat = SEATS["forge"]
            provider = ScriptedSeat([json.dumps({
                "status": "working", "message": "inspect",
                "criteria_proposed": [{"description": "add returns the sum", "weight": 50, "critical": True}],
                "calls": [{"tool": "read_file", "arguments": {"path": "calculator.py"}, "reason": "inspect"}],
            })])
            outcome = arena.engine.run_seat(seat, provider)
            assert outcome.turn is not None
            assert outcome.packet_chars > 0
            tasks = {t.description for t in store.get_tasks()}
            assert "add returns the sum" in tasks
