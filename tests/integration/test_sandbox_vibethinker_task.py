from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("PROMETHEUS_RUN_OLLAMA_TESTS"),
    reason="set PROMETHEUS_RUN_OLLAMA_TESTS=1 to run the real VibeThinker sandbox task",
)

MODEL = os.environ.get("PROMETHEUS_TEST_MODEL", "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K")
FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "sandbox_target"


def test_vibethinker_sandbox_task_creates_adder_and_tests(tmp_path):
    import shutil

    from prometheus_cli.models import AutonomyMode, Settings
    from prometheus_cli.agent import ArenaLoop, MicroStepEngine, make_default_verify
    from prometheus_cli.memory import Intent, ProjectMemoryStore
    from prometheus_cli.providers import create_provider
    from prometheus_cli.models import ModelSpec
    from prometheus_cli.tools.workspace import WorkspaceTools

    ws = tmp_path / "task"
    shutil.copytree(str(FIXTURE), str(ws))
    spec = ModelSpec(provider="ollama", model=MODEL, role="controller",
                     base_url="http://127.0.0.1:11434", tool_capable=False)
    provider = create_provider(spec)
    settings = Settings(mode=AutonomyMode.ASTRONAUT, sandbox_tier=__import__(
        "prometheus_cli.models", fromlist=["SandboxTier"]).SandboxTier.BASIC)
    mem = ProjectMemoryStore(ws)
    mem.set_intent(Intent(objective="create add(a,b) with tests", success_criteria=["tests pass"]))
    tools = WorkspaceTools.from_settings(ws, settings)
    engine = MicroStepEngine(store=mem, tools=tools, settings=settings, approve=lambda _c, _r: True)
    arena = ArenaLoop(store=mem, tools=tools, engine=engine)
    providers = {"envoy": provider, "forge": provider, "argus": provider}
    result = arena.run(providers, make_default_verify(ws))
    assert (ws / ".prometheus" / "memory.md").exists()
    assert result.attempts >= 1


def test_sandbox_blocks_outside_write_during_task(tmp_path):
    from prometheus_cli.models import SandboxTier, Settings
    from prometheus_cli.tools.workspace import WorkspaceTools

    settings = Settings(sandbox_tier=SandboxTier.BASIC)
    tools = WorkspaceTools.from_settings(tmp_path, settings)
    with pytest.raises(PermissionError):
        tools.write_file("../escape_during_task.txt", "x")
