from __future__ import annotations

import json

import pytest

from prometheus_cli.sandbox_test import FAIL, PASS, SKIP, run_suite, SuiteReport


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


def test_suite_runs_required_tests_and_writes_report(workspace):
    report = run_suite(workspace, include_optional=False)
    names = {r.name for r in report.results}
    assert "basic.workspace_write_allowed" in names
    assert "basic.rm_root_blocked" in names
    assert "mcp.permission_bypass_blocked" in names
    assert "memory.updated" in names
    assert "git.checkpoint_rollback" in names
    report_file = workspace / ".prometheus" / "sandbox-test-report.json"
    assert report_file.exists()
    data = json.loads(report_file.read_text())
    assert "summary" in data


def test_suite_blocks_catastrophic_and_path_escape(workspace):
    report = run_suite(workspace, include_optional=False)
    by_name = {r.name: r for r in report.results}
    assert by_name["basic.rm_root_blocked"].status == PASS
    assert by_name["basic.sudo_blocked"].status == PASS
    assert by_name["basic.outside_write_blocked"].status == PASS
    assert by_name["basic.symlink_escape_blocked"].status == PASS
    assert by_name["basic.path_traversal_blocked"].status == PASS
    assert by_name["basic.package_install_policy"].status == PASS
    assert by_name["basic.network_policy"].status == PASS
    assert by_name["mcp.permission_bypass_blocked"].status == PASS
    assert report.ok is True


def test_suite_writes_evidence_jsonl(workspace):
    run_suite(workspace, include_optional=False)
    evidence = (workspace / ".prometheus" / "evidence.jsonl").read_text()
    lines = [line for line in evidence.strip().split("\n") if line]
    assert len(lines) >= 10
    first = json.loads(lines[0])
    assert {"ts", "test", "status", "detail"} <= set(first)


def test_suite_updates_memory_md(workspace):
    run_suite(workspace, include_optional=False)
    mem = (workspace / ".prometheus" / "memory.md").read_text()
    assert "sandbox" in mem.lower()
    assert "passed" in mem


def test_optional_tests_skip_when_dependency_missing(workspace):
    report = run_suite(workspace, include_optional=True, ollama_model="hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K")
    statuses = {r.name: r.status for r in report.results}
    assert "docker.workspace_mount_readonly" in statuses
    assert "native.broker_active" in statuses
    assert "ollama.vibethinker_inference" in statuses


def test_report_ok_false_when_required_fails():
    report = SuiteReport(results=[], workspace="x")
    report.results = [
        type("R", (), {"name": "basic.x", "status": FAIL, "detail": "", "required": True})(),
    ]
    assert report.ok is False
    assert len(report.required_failed) == 1


def test_secret_redaction_test_passes(workspace):
    report = run_suite(workspace, include_optional=False)
    red = next(r for r in report.results if r.name == "basic.secret_redaction")
    assert red.status == PASS


def test_git_checkpoint_rollback_passes(workspace):
    report = run_suite(workspace, include_optional=False)
    git = next(r for r in report.results if r.name == "git.checkpoint_rollback")
    assert git.status in (PASS, SKIP)
