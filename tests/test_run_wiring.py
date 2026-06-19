from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


from prometheus_cli.agent import make_default_verify
from prometheus_cli.agent.arena import detect_test_command
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


class Scripted:
    def __init__(self, scripts):
        self._scripts = list(scripts)
        self.calls = 0

    def complete(self, messages, schema=None):
        self.calls += 1
        return self._scripts.pop(0) if self._scripts else json.dumps({"status": "complete", "message": "done"})

    def unload(self):
        pass


def test_detect_test_command_finds_pytest():
    with TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "test_app.py").write_text("def test_x(): pass", encoding="utf-8")
        cmd = detect_test_command(ws)
        assert cmd is not None
        assert "pytest" in cmd


def test_detect_test_command_none_without_tests():
    with TemporaryDirectory() as tmp:
        assert detect_test_command(Path(tmp)) is None


def test_default_verify_passes_when_tests_pass():
    with TemporaryDirectory() as tmp:
        ws = Path(tmp)
        shutil.copytree(str(FIXTURE), str(ws), dirs_exist_ok=True)
        (ws / "calculator.py").write_text(FIX_CALC, encoding="utf-8")
        tools = WorkspaceTools(ws)
        verify = make_default_verify(ws)
        passed, evidence = verify(None, tools)
        assert passed is True


def test_default_verify_fails_when_tests_fail():
    with TemporaryDirectory() as tmp:
        ws = Path(tmp)
        shutil.copytree(str(FIXTURE), str(ws), dirs_exist_ok=True)
        tools = WorkspaceTools(ws)
        verify = make_default_verify(ws)
        passed, _ = verify(None, tools)
        assert passed is False


def test_default_verify_falls_back_to_diff_when_no_tests():
    with TemporaryDirectory() as tmp:
        ws = Path(tmp)
        subprocess.run(["git", "init"], cwd=ws, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=ws, capture_output=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=ws, capture_output=True)
        (ws / "a.txt").write_text("init", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=ws, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "i"], cwd=ws, capture_output=True, check=True)
        (ws / "a.txt").write_text("changed", encoding="utf-8")
        tools = WorkspaceTools(ws)
        verify = make_default_verify(ws)
        passed, evidence = verify(None, tools)
        assert passed is True
        assert "patch applied" in evidence


def test_arena_loop_with_default_verify_completes_repair():
    from prometheus_cli.agent import ArenaLoop, MicroStepEngine

    with TemporaryDirectory() as tmp:
        ws = Path(tmp) / "repo"
        shutil.copytree(str(FIXTURE), str(ws))
        subprocess.run(["git", "init"], cwd=ws, capture_output=True, check=True)
        store = ProjectMemoryStore(ws)
        store.set_intent(Intent(objective="repair add()", success_criteria=["tests pass"]))
        store.upsert_task(TaskNode(id="t1", description="patch add()", status="active", acceptance="tests pass"))
        tools = WorkspaceTools(ws)
        engine = MicroStepEngine(store=store, tools=tools, settings=Settings(mode=AutonomyMode.ASTRONAUT), approve=lambda _c, _r: True)
        arena = ArenaLoop(store=store, tools=tools, engine=engine)
        providers = {
            "envoy": Scripted([json.dumps({"status": "working", "message": "frame step"})]),
            "forge": Scripted([json.dumps({
                "status": "working", "message": "patch add",
                "calls": [{"tool": "write_file", "arguments": {"path": "calculator.py", "content": FIX_CALC}, "reason": "fix"}],
            })]),
            "argus": Scripted([json.dumps({"status": "complete", "message": "verified"})]),
        }
        result = arena.run(providers, make_default_verify(ws))
        assert result.accepted is True
        assert "return a + b" in (ws / "calculator.py").read_text()
        assert store.get_intent().objective == "repair add()"
        assert store.get_working_memory()
