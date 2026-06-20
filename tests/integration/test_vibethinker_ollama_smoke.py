from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("PROMETHEUS_RUN_OLLAMA_TESTS"),
    reason="set PROMETHEUS_RUN_OLLAMA_TESTS=1 to run real Ollama tests",
)

MODEL = os.environ.get("PROMETHEUS_TEST_MODEL", "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K")
BASE_URL = "http://127.0.0.1:11434"


def test_vibethinker_is_pulled_and_infers():
    from prometheus_cli.onboarding import check_ollama, inference_smoke_test

    status = check_ollama(BASE_URL)
    assert status.running, "Ollama must be running"
    assert MODEL in status.models, f"pull first: prometheus models pull vibethinker-q2  ({MODEL})"
    smoke = inference_smoke_test(MODEL, BASE_URL)
    assert smoke.success, f"inference failed: {smoke.error}"
    assert smoke.response.strip(), "empty inference response"


def test_provider_smoke_via_cli():
    from typer.testing import CliRunner
    from prometheus_cli.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["provider", "smoke", "--provider", "ollama", "--model", MODEL])
    assert result.exit_code == 0, result.stdout
    assert "health: OK" in result.stdout


def test_sandbox_suite_includes_real_inference(tmp_path):
    from prometheus_cli.sandbox_test import PASS, run_suite

    report = run_suite(tmp_path, ollama_model=MODEL, base_url=BASE_URL, include_optional=True)
    infer = next(r for r in report.results if r.name == "ollama.vibethinker_inference")
    assert infer.status == PASS, f"inference test: {infer.detail}"
