"""Opt-in end-to-end repair test against a REAL Ollama model.

Skipped unless PROMETHEUS_E2E_OLLAMA=1. This is the real-model MVP proof the
recovery prompt requires beyond the deterministic ScriptedProvider coverage in
test_e2e_repair.py. Small local models may not reach 100% completion reliably,
so this test asserts honest behavior: the real provider is exercised, the
session is durable, and any completion claim is backed by a real file change.

Run it (requires Ollama running + at least one model):
    PROMETHEUS_E2E_OLLAMA=1 pytest tests/test_e2e_ollama.py -q -s

Pin a specific model:
    PROMETHEUS_E2E_OLLAMA=1 PROMETHEUS_E2E_MODEL=llama3.2:latest pytest tests/test_e2e_ollama.py -q -s
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from prometheus_cli.models import AutonomyMode, ModelBundle, ModelSpec, Settings
from prometheus_cli.onboarding import check_ollama
from prometheus_cli.orchestrator import Orchestrator
from prometheus_cli.session import SessionStore

FIXTURE = Path(__file__).parent / "fixtures" / "broken_repo"

_ENV = "PROMETHEUS_E2E_OLLAMA"


def _real_model() -> str | None:
    model = os.environ.get("PROMETHEUS_E2E_MODEL", "").strip()
    if model:
        return model
    status = check_ollama()
    if status.models:
        return status.models[0]
    return None


@pytest.fixture(autouse=True)
def _opt_in():
    if os.environ.get(_ENV) != "1":
        pytest.skip(f"set {_ENV}=1 to run the real-Ollama end-to-end test")
    if not check_ollama().running:
        pytest.skip("Ollama service is not running")


def _settings(workspace):
    return Settings(
        workspace=workspace,
        mode=AutonomyMode.ASTRONAUT,
        multi_agent_review=False,
        max_steps=8,
        target_completion=95,
    )


def _bundle(model: str) -> ModelBundle:
    return ModelBundle(
        name="real-ollama",
        models=[ModelSpec(model=model, provider="ollama", role="controller", tool_capable=True)],
    )


class TestRealOllamaE2E:
    def test_real_provider_drives_orchestrator_against_broken_repo(self):
        model = _real_model()
        if model is None:
            pytest.skip("no Ollama model available; pull one first")
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "repo"
            shutil.copytree(str(FIXTURE), str(workspace))
            subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=True)

            store = SessionStore(Path(tmp) / "sessions.db")
            orch = Orchestrator(_settings(workspace), _bundle(model),
                                approve=lambda *_: True, session_store=store)

            real_calls = {"n": 0}
            original_complete = orch.controller.complete

            def counting_complete(messages, schema=None):
                real_calls["n"] += 1
                return original_complete(messages, schema=schema)

            orch.controller.complete = counting_complete

            updates: list[str] = []
            result = orch.run("Fix the broken calculator: add() must add, and all tests must pass.",
                              on_update=updates.append)
            sid = store.list_sessions()[0].id

            assert real_calls["n"] >= 1, "real Ollama provider was never called"

            events = store.events_since(sid, 0)
            assert any(e["type"] == "session_created" for e in events)

            assert result.status in {"complete", "failed", "incomplete", "blocked"}

            fixed = (workspace / "calculator.py").read_text()
            if result.status == "complete":
                assert "return a + b" in fixed, "completion claimed but the file was not actually fixed"
                assert store.all_critical_passed(sid) is True
            store.close()

    def test_real_inference_smoke(self):
        model = _real_model()
        if model is None:
            pytest.skip("no Ollama model available")
        from prometheus_cli.onboarding import inference_smoke_test

        smoke = inference_smoke_test(model)
        assert smoke.success, f"real inference failed for {model}: {smoke.error}"
        assert smoke.response.strip(), "real inference returned an empty response"
