"""Opt-in real-Ollama end-to-end test for the bounded-memory Arena.

Skipped unless PROMETHEUS_E2E_OLLAMA=1. Proves §15 'Builder and Tester complete a
real repair through the Arena loop' with a real local model driving bounded-context
micro-steps, deterministic verification, and persisted memory.

    PROMETHEUS_E2E_OLLAMA=1 PROMETHEUS_E2E_MODEL=granite4.1:3b \
        pytest tests/test_arena_ollama_e2e.py -q -s
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from prometheus_cli.agent import ArenaLoop, MicroStepEngine, make_default_verify
from prometheus_cli.memory import Intent, ProjectMemoryStore, TaskNode
from prometheus_cli.models import AutonomyMode, ModelSpec, Settings
from prometheus_cli.providers import create_provider
from prometheus_cli.tools.workspace import WorkspaceTools

FIXTURE = Path(__file__).parent / "fixtures" / "broken_repo"
_ENV = "PROMETHEUS_E2E_OLLAMA"


@pytest.fixture(autouse=True)
def _opt_in():
    if os.environ.get(_ENV) != "1":
        pytest.skip(f"set {_ENV}=1 to run the real-Ollama arena end-to-end test")


def _model() -> str:
    model = os.environ.get("PROMETHEUS_E2E_MODEL", "").strip()
    if model:
        return model
    from prometheus_cli.onboarding import check_ollama

    status = check_ollama()
    if status.models:
        return status.models[0]
    pytest.skip("no Ollama model available")


def test_real_arena_repairs_broken_repo_with_bounded_context():
    model = _model()
    with TemporaryDirectory() as tmp:
        ws = Path(tmp) / "repo"
        shutil.copytree(str(FIXTURE), str(ws))
        subprocess.run(["git", "init"], cwd=ws, capture_output=True, check=True)

        store = ProjectMemoryStore(ws)
        store.set_intent(Intent(objective="Fix calculator.py so add() returns a+b and all tests pass.",
                                success_criteria=["all tests pass"]))
        store.upsert_task(TaskNode(id="t1", description="patch add() to return a + b",
                                   status="active", acceptance="pytest test_calculator.py passes"))
        tools = WorkspaceTools(ws)
        spec = ModelSpec(model=model, provider="ollama", role="controller", tool_capable=True)
        engine = MicroStepEngine(store=store, tools=tools,
                                 settings=Settings(mode=AutonomyMode.ASTRONAUT),
                                 approve=lambda _c, _r: True)
        arena = ArenaLoop(store=store, tools=tools, engine=engine, max_attempts=4)
        providers = {
            "envoy": create_provider(spec),
            "forge": create_provider(spec),
            "argus": create_provider(spec),
        }
        result = arena.run(providers, make_default_verify(ws))
        assert result.attempts >= 1
        assert result.final_status in {"complete", "escalated", "exhausted"}
        assert store.get_intent().objective.startswith("Fix calculator.py")
        assert store.get_working_memory()
        if result.accepted:
            assert "return a + b" in (ws / "calculator.py").read_text()
            passed, _ = make_default_verify(ws)(store, tools)
            assert passed is True
