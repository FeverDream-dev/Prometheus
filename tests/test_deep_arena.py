from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from prometheus_cli.agent import deep_arena
from prometheus_cli.agent.arena import MicroStepEngine
from prometheus_cli.memory import Intent, ProjectMemoryStore, TaskNode
from prometheus_cli.models import AutonomyMode, Settings
from prometheus_cli.tools.workspace import WorkspaceTools

FIXTURE = Path(__file__).parent / "fixtures" / "broken_repo"
GOOD = "def add(a, b):\n    return a + b\n\n\ndef multiply(a, b):\n    result = 0\n    for _ in range(b):\n        result = add(result, a)\n    return result\n"
BAD = "def add(a, b):\n    return a - b\n"


class Scripted:
    def __init__(self, script):
        self._script = script
        self.calls = 0

    def complete(self, messages, schema=None):
        self.calls += 1
        return self._script

    def unload(self):
        pass


def _verify_in(tools):
    res = tools.run_command([shutil.which("python") or "python3", "-m", "pytest", "test_calculator.py", "-q"])
    passed = "passed" in res and "failed" not in res.lower()
    return passed, (res.strip().splitlines()[-1] if res.strip() else "")


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


def _repo(tmp: Path) -> Path:
    ws = tmp / "repo"
    shutil.copytree(str(FIXTURE), str(ws))
    _git(["init"], ws)
    _git(["add", "."], ws)
    _git(["commit", "-m", "init"], ws)
    _git(["config", "user.email", "t@t"], ws)
    _git(["config", "user.name", "t"], ws)
    return ws


def _patch_script(content: str) -> str:
    return json.dumps({
        "status": "working", "message": "patch",
        "calls": [{"tool": "write_file", "arguments": {"path": "calculator.py", "content": content}, "reason": "fix"}],
    })


def test_deep_arena_picks_passing_candidate_and_applies_to_workspace():
    with TemporaryDirectory() as tmp:
        ws = _repo(Path(tmp))
        store = ProjectMemoryStore(ws)
        store.set_intent(Intent(objective="fix add", success_criteria=["tests pass"]))
        store.upsert_task(TaskNode(id="t1", description="fix add", status="active", acceptance="tests pass"))
        engine = MicroStepEngine(store=store, tools=WorkspaceTools(ws),
                                 settings=Settings(mode=AutonomyMode.ASTRONAUT), approve=lambda _c, _r: True)

        def factory(i, _wt):
            return Scripted(_patch_script(BAD if i == 0 else GOOD))

        result = deep_arena(store, ws, factory, _verify_in, engine, n=2,
                            on_update=lambda _m: None)
        assert result.applied is True
        assert result.winner is not None
        assert result.winner.passed is True
        assert result.winner.label == "cand-1"
        assert "return a + b" in (ws / "calculator.py").read_text()
        passed, _ = _verify_in(WorkspaceTools(ws))
        assert passed is True


def test_deep_arena_discards_all_when_none_pass():
    with TemporaryDirectory() as tmp:
        ws = _repo(Path(tmp))
        store = ProjectMemoryStore(ws)
        store.set_intent(Intent(objective="fix add"))
        store.upsert_task(TaskNode(id="t1", description="fix add", status="active", acceptance="tests"))
        engine = MicroStepEngine(store=store, tools=WorkspaceTools(ws),
                                 settings=Settings(mode=AutonomyMode.ASTRONAUT), approve=lambda _c, _r: True)
        def factory(i, _wt):
            return Scripted(_patch_script(BAD))
        result = deep_arena(store, ws, factory, _verify_in, engine, n=2)
        assert result.applied is False
        assert all(not c.passed for c in result.candidates)
        assert "discarded" in result.reason


def test_deep_arena_cleans_up_worktrees():
    with TemporaryDirectory() as tmp:
        ws = _repo(Path(tmp))
        store = ProjectMemoryStore(ws)
        store.set_intent(Intent(objective="fix add"))
        store.upsert_task(TaskNode(id="t1", description="fix add", status="active", acceptance="tests"))
        engine = MicroStepEngine(store=store, tools=WorkspaceTools(ws),
                                 settings=Settings(mode=AutonomyMode.ASTRONAUT), approve=lambda _c, _r: True)
        def factory(i, _wt):
            return Scripted(_patch_script(GOOD if i == 0 else BAD))
        deep_arena(store, ws, factory, _verify_in, engine, n=2)
        wt_root = ws / ".prometheus" / "worktrees"
        remaining = [p for p in wt_root.glob("cand-*") if p.is_dir()]
        assert remaining == [], f"worktrees not cleaned: {remaining}"
        listing = _git(["worktree", "list"], ws).stdout
        assert "cand-" not in listing


def test_deep_arena_candidates_cannot_contaminate_each_other():
    with TemporaryDirectory() as tmp:
        ws = _repo(Path(tmp))
        store = ProjectMemoryStore(ws)
        store.set_intent(Intent(objective="fix add"))
        store.upsert_task(TaskNode(id="t1", description="fix add", status="active", acceptance="tests"))
        engine = MicroStepEngine(store=store, tools=WorkspaceTools(ws),
                                 settings=Settings(mode=AutonomyMode.ASTRONAUT), approve=lambda _c, _r: True)
        def factory(i, _wt):
            return Scripted(_patch_script(GOOD if i == 0 else BAD))
        result = deep_arena(store, ws, factory, _verify_in, engine, n=2)
        cand0, cand1 = result.candidates[0], result.candidates[1]
        assert cand0.passed is True and cand1.passed is False
