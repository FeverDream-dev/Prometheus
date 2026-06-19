from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

import httpx

from prometheus_cli.onboarding import (
    InstallPlan,
    format_pull_progress,
    inference_smoke_test,
    ollama_install_plan,
    pull_model,
    run_ollama_install,
    start_ollama_service,
)


class FakeStreamResponse:
    def __init__(self, lines: Iterable[bytes], status: int = 200):
        self._lines = list(lines)
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad", request=httpx.Request("POST", "x"))

    def iter_lines(self):
        for line in self._lines:
            if isinstance(line, str):
                yield line
            else:
                yield line.decode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeStreamClient:
    def __init__(self, lines: Iterable[bytes], status: int = 200):
        self._lines = list(lines)
        self._status = status
        self.posts: list[tuple[str, dict]] = []

    def stream(self, method, url, **kw):
        self.last_url = url
        return FakeStreamResponse(self._lines, self._status)

    def post(self, url, json=None, **kw):
        self.posts.append((url, json or {}))
        return self._post_response

    def set_post_response(self, status: int, body: dict):
        class R:
            status_code = status

            def json(self_inner):
                return body
        self._post_response = R()

    def close(self):
        pass


class FakePostClient:
    def __init__(self, status: int, body: dict):
        self.status = status
        self.body = body
        self.posted: list[tuple[str, dict]] = []

    def post(self, url, json=None, **kw):
        self.posted.append((url, json or {}))

        class R:
            status_code = self.status

            def json(self_inner):
                return self.body

        return R()

    def close(self):
        pass


def test_ollama_install_plan_linux_returns_curl_pipe(monkeypatch):
    monkeypatch.setattr("prometheus_cli.onboarding.platform.system", lambda: "Linux")
    monkeypatch.setattr("prometheus_cli.onboarding.shutil.which", lambda _: None)
    plan = ollama_install_plan()
    assert plan.command == "curl -fsSL https://ollama.com/install.sh | sh"
    assert plan.needs_shell is True


def test_ollama_install_plan_macos_prefers_brew(monkeypatch):
    monkeypatch.setattr("prometheus_cli.onboarding.platform.system", lambda: "Darwin")
    monkeypatch.setattr("prometheus_cli.onboarding.shutil.which", lambda x: "/usr/local/bin/brew" if x == "brew" else None)
    plan = ollama_install_plan()
    assert plan.command == "brew install ollama"


def test_ollama_install_plan_macos_falls_back_without_brew(monkeypatch):
    monkeypatch.setattr("prometheus_cli.onboarding.platform.system", lambda: "Darwin")
    monkeypatch.setattr("prometheus_cli.onboarding.shutil.which", lambda _: None)
    plan = ollama_install_plan()
    assert "ollama.com/install.sh" in plan.command


def test_ollama_install_plan_unknown_returns_none_command(monkeypatch):
    monkeypatch.setattr("prometheus_cli.onboarding.platform.system", lambda: "Plan9")
    plan = ollama_install_plan()
    assert plan.command is None


def test_run_ollama_install_success(monkeypatch):
    @dataclass
    class C:
        returncode = 0
        stdout = "installed"
        stderr = ""

    monkeypatch.setattr("prometheus_cli.onboarding.subprocess.run", lambda *a, **k: C())
    result = run_ollama_install(InstallPlan("echo hi", "test", needs_shell=True))
    assert result.success is True
    assert "installed" in result.output


def test_run_ollama_install_failure(monkeypatch):
    @dataclass
    class C:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr("prometheus_cli.onboarding.subprocess.run", lambda *a, **k: C())
    result = run_ollama_install(InstallPlan("false", "test", needs_shell=True))
    assert result.success is False
    assert result.returncode == 1


def test_run_ollama_install_no_command_returns_failure():
    result = run_ollama_install(InstallPlan(None, "no method", False))
    assert result.success is False


def test_pull_model_streams_progress_until_success():
    lines = [
        json.dumps({"status": "pulling manifest"}),
        json.dumps({"status": "downloading", "completed": 50, "total": 100, "digest": "abc"}),
        json.dumps({"status": "success"}),
    ]
    progress: list[dict] = []
    client = FakeStreamClient(lines)
    ok = pull_model("qwen3:8b", on_progress=progress.append, client=client)
    assert ok is True
    assert any(d.get("status") == "success" for d in progress)
    assert any(d.get("completed") == 50 for d in progress)


def test_pull_model_returns_false_on_error_field():
    lines = [json.dumps({"status": "error", "error": "disk full"})]
    client = FakeStreamClient(lines)
    assert pull_model("x", client=client) is False


def test_pull_model_honours_cancel_check():
    lines = [
        json.dumps({"status": "downloading", "completed": 1, "total": 100}),
        json.dumps({"status": "downloading", "completed": 2, "total": 100}),
        json.dumps({"status": "success"}),
    ]
    client = FakeStreamClient(lines)
    ok = pull_model("x", cancel_check=lambda: True, client=client)
    assert ok is False


def test_format_pull_progress_with_totals():
    out = format_pull_progress({"status": "downloading", "completed": 5242880, "total": 10485760})
    assert "50%" in out
    assert "5/10 MB" in out


def test_format_pull_progress_without_totals():
    assert format_pull_progress({"status": "pulling manifest"}) == "pulling manifest"


def test_inference_smoke_test_success():
    client = FakePostClient(200, {"response": " ready "})
    result = inference_smoke_test("qwen3:8b", client=client)
    assert result.success is True
    assert result.response == "ready"
    assert client.posted[0][0].endswith("/api/generate")
    assert client.posted[0][1]["model"] == "qwen3:8b"


def test_inference_smoke_test_empty_response_is_failure():
    client = FakePostClient(200, {"response": "   "})
    result = inference_smoke_test("x", client=client)
    assert result.success is False
    assert "empty" in result.error


def test_inference_smoke_test_http_error():
    client = FakePostClient(500, {})
    result = inference_smoke_test("x", client=client)
    assert result.success is False
    assert "500" in result.error


def test_inference_smoke_test_network_exception():
    class ExplodingClient:
        def post(self, *a, **k):
            raise httpx.ConnectError("no", request=httpx.Request("POST", "x"))

        def close(self):
            pass

    result = inference_smoke_test("x", client=ExplodingClient())
    assert result.success is False
    assert "no" in result.error


def test_start_ollama_service_when_already_running(monkeypatch):
    from prometheus_cli import onboarding

    monkeypatch.setattr(onboarding, "check_ollama", lambda url="x": type("S", (), {"running": True})())
    assert start_ollama_service() is True


def test_start_ollama_service_no_binary(monkeypatch):
    from prometheus_cli import onboarding

    seq = [type("S", (), {"running": False})()]

    def fake_check(url="x"):
        return seq[0]

    monkeypatch.setattr(onboarding, "check_ollama", fake_check)
    monkeypatch.setattr(onboarding.shutil, "which", lambda _: None)
    assert start_ollama_service() is False
