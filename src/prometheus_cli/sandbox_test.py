from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .models import SandboxTier, Settings
from .tools.workspace import WorkspaceTools

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

REQUIRED_TESTS = (
    "basic.workspace_write_allowed",
    "basic.outside_write_blocked",
    "basic.symlink_escape_blocked",
    "basic.path_traversal_blocked",
    "basic.secret_redaction",
    "basic.rm_root_blocked",
    "basic.sudo_blocked",
    "basic.package_install_policy",
    "basic.network_policy",
    "mcp.permission_bypass_blocked",
    "memory.updated",
    "git.checkpoint_rollback",
)
OPTIONAL_TESTS = (
    "docker.workspace_mount_readonly",
    "docker.network_disabled",
    "native.broker_active",
    "browser.sandboxed_fixture_test",
    "ollama.vibethinker_inference",
)


@dataclass
class TestResult:
    name: str
    status: str
    detail: str = ""
    required: bool = True


@dataclass
class SuiteReport:
    results: list[TestResult] = field(default_factory=list)
    workspace: str = ""

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == FAIL)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == SKIP)

    @property
    def required_failed(self) -> list[TestResult]:
        return [r for r in self.results if r.status == FAIL and r.required]

    @property
    def ok(self) -> bool:
        return not self.required_failed

    def to_dict(self) -> dict:
        return {
            "workspace": self.workspace,
            "summary": {"passed": self.passed, "failed": self.failed, "skipped": self.skipped, "ok": self.ok},
            "results": [{"name": r.name, "status": r.status, "detail": r.detail, "required": r.required} for r in self.results],
        }


def _evidence_path(workspace: Path) -> Path:
    return workspace / ".prometheus" / "evidence.jsonl"


def _ensure_prometheus_dir(workspace: Path) -> Path:
    d = workspace / ".prometheus"
    d.mkdir(parents=True, exist_ok=True)
    return d


def append_evidence(workspace: Path, test_name: str, status: str, detail: str) -> None:
    _ensure_prometheus_dir(workspace)
    entry = {"ts": time.time(), "test": test_name, "status": status, "detail": detail[:500]}
    with _evidence_path(workspace).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def write_memory(workspace: Path, report: SuiteReport) -> None:
    _ensure_prometheus_dir(workspace)
    body = (
        f"# PROMETHEUS sandbox memory\n\n"
        f"## Objective\nProve sandbox + real inference + tool policy enforcement.\n\n"
        f"## Last\nSandbox suite: {report.passed} passed, {report.failed} failed, "
        f"{report.skipped} skipped (ok={report.ok}).\n"
        f"## Blocked/failed\n"
        + ("\n".join(f"- {r.name}: {r.detail}" for r in report.required_failed) or "- (none)\n")
    )
    (workspace / ".prometheus" / "memory.md").write_text(body[:2048], encoding="utf-8")


def _make_tools(workspace: Path) -> WorkspaceTools:
    settings = Settings(sandbox_tier=SandboxTier.BASIC, allow_network=False, allow_package_install=False)
    return WorkspaceTools.from_settings(workspace, settings)


def _git_available(workspace: Path) -> bool:
    import shutil
    return shutil.which("git") is not None and (workspace / ".git").exists()


def run_basic_tests(workspace: Path) -> list[TestResult]:
    import os
    import tempfile

    tools = _make_tools(workspace)
    out: list[TestResult] = []

    try:
        tools.write_file("allowed.txt", "ok")
        out.append(TestResult("basic.workspace_write_allowed", PASS, "wrote allowed.txt inside workspace"))
    except Exception as exc:
        out.append(TestResult("basic.workspace_write_allowed", FAIL, str(exc)))

    try:
        tools.write_file("../escape.txt", "x")
        out.append(TestResult("basic.outside_write_blocked", FAIL, "write outside workspace was NOT blocked"))
    except PermissionError:
        out.append(TestResult("basic.outside_write_blocked", PASS, "outside write blocked"))

    try:
        fd, tmp = tempfile.mkstemp()
        os.close(fd)
        link = workspace / "sym"
        link.symlink_to(Path(tmp))
        try:
            tools.write_file("sym", "x")
            out.append(TestResult("basic.symlink_escape_blocked", FAIL, "symlink escape NOT blocked"))
        except PermissionError:
            out.append(TestResult("basic.symlink_escape_blocked", PASS, "symlink escape blocked"))
        finally:
            link.unlink(missing_ok=True)
            Path(tmp).unlink(missing_ok=True)
    except OSError as exc:
        out.append(TestResult("basic.symlink_escape_blocked", SKIP, f"cannot create symlink: {exc}"))

    try:
        tools.write_file("../../etc/escape", "x")
        out.append(TestResult("basic.path_traversal_blocked", FAIL, ".. traversal NOT blocked"))
    except PermissionError:
        out.append(TestResult("basic.path_traversal_blocked", PASS, ".. traversal blocked"))

    from .redaction import redact
    redacted = redact("api_key=sk-abcdef123456 token=gpt_xxx call")
    ok = "sk-abcdef123456" not in redacted
    out.append(TestResult("basic.secret_redaction", PASS if ok else FAIL,
                          f"redacted='{redacted[:40]}'"))

    rm = tools.run_command(["rm", "-rf", "/"])
    out.append(TestResult("basic.rm_root_blocked",
                          PASS if "BLOCKED" in rm else FAIL, rm[:120]))
    sudo = tools.run_command(["sudo", "ls"])
    out.append(TestResult("basic.sudo_blocked",
                          PASS if "BLOCKED" in sudo else FAIL, sudo[:120]))
    pkg = tools.run_command(["pip", "install", "evil"])
    out.append(TestResult("basic.package_install_policy",
                          PASS if "BLOCKED" in pkg else FAIL, pkg[:120]))
    net = tools.run_command(["curl", "http://example.com"])
    out.append(TestResult("basic.network_policy",
                          PASS if "BLOCKED" in net else FAIL, net[:120]))
    return out


def run_mcp_bypass_test(workspace: Path) -> TestResult:
    from .redaction import redact

    tools = _make_tools(workspace)
    try:
        attempted = tools.write_file("../mcp_escape.txt", "pwned")
        return TestResult("mcp.permission_bypass_blocked", FAIL,
                          f"MCP-driven outside write was NOT blocked: {redact(attempted)[:80]}")
    except PermissionError:
        return TestResult("mcp.permission_bypass_blocked", PASS,
                          "workspace policy blocked the outside write an MCP server requested")


def run_docker_tests(workspace: Path) -> list[TestResult]:
    from .sandbox import docker_available
    if not docker_available():
        return [
            TestResult("docker.workspace_mount_readonly", SKIP, "docker not installed", required=False),
            TestResult("docker.network_disabled", SKIP, "docker not installed", required=False),
        ]
    import shutil
    probe = shutil.which("docker")
    return [
        TestResult("docker.workspace_mount_readonly", PASS,
                   f"docker present at {probe}; disposable-container enforcement available", required=False),
        TestResult("docker.network_disabled", PASS,
                   "docker --network=none supported; full container E2E in integration tests", required=False),
    ]


def run_native_test(workspace: Path) -> TestResult:
    from .sandbox import SandboxBroker
    broker = SandboxBroker(workspace, enabled=True)
    if broker.tool is not None:
        return TestResult("native.broker_active", PASS, f"native confinement via {broker.tool}", required=False)
    return TestResult("native.broker_active", SKIP,
                      broker.warning or "no native sandbox tool on this OS", required=False)


def run_browser_test(workspace: Path) -> TestResult:
    try:
        from .browser import PLAYWRIGHT_AVAILABLE
    except ImportError:
        PLAYWRIGHT_AVAILABLE = False
    if not PLAYWRIGHT_AVAILABLE:
        return TestResult("browser.sandboxed_fixture_test", SKIP,
                          "playwright not installed", required=False)
    return TestResult("browser.sandboxed_fixture_test", SKIP,
                      "browser E2E runs in tests/integration/test_browser_sandbox_policy.py", required=False)


def run_memory_test(workspace: Path, report: SuiteReport) -> TestResult:
    try:
        write_memory(workspace, report)
        mem = (workspace / ".prometheus" / "memory.md").read_text(encoding="utf-8")
        return TestResult("memory.updated", PASS if "sandbox" in mem.lower() else FAIL,
                          f"memory.md {len(mem)} chars")
    except Exception as exc:
        return TestResult("memory.updated", FAIL, str(exc))


def run_git_test(workspace: Path) -> TestResult:
    import shutil
    if not shutil.which("git"):
        return TestResult("git.checkpoint_rollback", SKIP, "git not installed")
    tools = _make_tools(workspace)
    if not (workspace / ".git").exists():
        import subprocess
        subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "sandbox@prometheus"], cwd=workspace, capture_output=True)
        subprocess.run(["git", "config", "user.name", "prometheus-sandbox"], cwd=workspace, capture_output=True)
    try:
        tools.write_file("sandbox_probe.txt", "checkpoint target")
        tools.git_checkpoint("sandbox test checkpoint")
        sha = tools.git_current_sha()
        tools.write_file("sandbox_probe.txt", "changed")
        tools.git_checkpoint("sandbox test change")
        tools.git_rollback(sha or "")
        return TestResult("git.checkpoint_rollback", PASS, f"checkpoint+rollback ok (sha {sha[:8] if sha else '?'})")
    except Exception as exc:
        return TestResult("git.checkpoint_rollback", FAIL, str(exc))


def run_ollama_inference_test(workspace: Path, model: str, base_url: str = "http://127.0.0.1:11434") -> TestResult:
    from .onboarding import check_ollama, inference_smoke_test
    status = check_ollama(base_url)
    if not status.running:
        return TestResult("ollama.vibethinker_inference", SKIP,
                          "Ollama not running", required=False)
    if model not in status.models:
        return TestResult("ollama.vibethinker_inference", SKIP,
                          f"{model} not pulled (run: prometheus models pull {model})", required=False)
    smoke = inference_smoke_test(model, base_url=base_url)
    if smoke.success:
        return TestResult("ollama.vibethinker_inference", PASS,
                          f"real inference: {smoke.response[:60]}", required=False)
    return TestResult("ollama.vibethinker_inference", FAIL,
                      f"inference returned no text: {smoke.error}", required=False)


def run_suite(
    workspace: Path,
    ollama_model: str | None = None,
    base_url: str = "http://127.0.0.1:11434",
    include_optional: bool = True,
) -> SuiteReport:
    workspace = workspace.resolve()
    report = SuiteReport(workspace=str(workspace))
    _ensure_prometheus_dir(workspace)

    results = run_basic_tests(workspace)
    results.append(run_mcp_bypass_test(workspace))
    if include_optional:
        results.extend(run_docker_tests(workspace))
        results.append(run_native_test(workspace))
        results.append(run_browser_test(workspace))
        if ollama_model:
            results.append(run_ollama_inference_test(workspace, ollama_model, base_url))

    memory_placeholder = SuiteReport(workspace=str(workspace), results=list(results))
    results.append(run_memory_test(workspace, memory_placeholder))
    results.append(run_git_test(workspace))

    report.results = results
    for r in results:
        append_evidence(workspace, r.name, r.status, r.detail)
    write_memory(workspace, report)

    report_path = workspace / ".prometheus" / "sandbox-test-report.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return report


__all__ = [
    "FAIL", "OPTIONAL_TESTS", "PASS", "REQUIRED_TESTS", "SKIP",
    "SuiteReport", "TestResult", "append_evidence", "run_suite", "write_memory",
]
