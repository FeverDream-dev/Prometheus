from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from prometheus_cli.agent import make_default_verify
from prometheus_cli.cavecrew import compress_text, compress_tool_results
from prometheus_cli.tools.workspace import WorkspaceTools
from prometheus_cli.verify import nonempty_artifact_count, self_check_write, verify_workspace_progress


def test_write_file_rejects_empty():
    with TemporaryDirectory() as tmp:
        tools = WorkspaceTools(Path(tmp))
        with pytest.raises(ValueError, match="empty"):
            tools.write_file("x.txt", "")


def test_nonempty_artifact_count_ignores_prometheus():
    with TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "site").mkdir()
        (ws / "site" / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        (ws / ".prometheus").mkdir()
        (ws / ".prometheus" / "x").write_text("meta", encoding="utf-8")
        assert nonempty_artifact_count(ws) == 1


def test_verify_passes_on_untracked_nonempty_files():
    with TemporaryDirectory() as tmp:
        ws = Path(tmp)
        subprocess.run(["git", "init"], cwd=ws, capture_output=True, check=True)
        (ws / "site").mkdir()
        (ws / "site" / "index.html").write_text("<!DOCTYPE html><title>x</title>", encoding="utf-8")
        tools = WorkspaceTools(ws)
        passed, msg = verify_workspace_progress(tools)
        assert passed is True
        assert "non-empty" in msg


def test_verify_fails_on_empty_untracked_files():
    with TemporaryDirectory() as tmp:
        ws = Path(tmp)
        subprocess.run(["git", "init"], cwd=ws, capture_output=True, check=True)
        (ws / "site").mkdir()
        (ws / "site" / "index.html").touch()
        tools = WorkspaceTools(ws)
        passed, msg = verify_workspace_progress(tools)
        assert passed is False


def test_self_check_write_ok_and_fail():
    with TemporaryDirectory() as tmp:
        tools = WorkspaceTools(Path(tmp))
        tools.write_file("a.html", "<html>hello world</html>")
        ok = self_check_write(tools, "a.html")
        assert "SELF-CHECK OK" in ok
        tools.write_file("b.html", "x")
        bad = self_check_write(tools, "b.html", min_bytes=10)
        assert "SELF-CHECK FAIL" in bad


def test_make_default_verify_uses_artifacts():
    with TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "hello.txt").write_text("hello prometheus", encoding="utf-8")
        tools = WorkspaceTools(ws)
        passed, _ = make_default_verify(ws)(None, tools)
        assert passed is True


def test_verify_ignores_log_files():
    with TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "native_e2e.log").write_text("x" * 100, encoding="utf-8")
        assert nonempty_artifact_count(ws) == 0


def test_cavecrew_compress_keeps_errors():
    blob = "ok\n" * 100 + "ERROR: disk full\n" + "tail\n" * 50
    out = compress_text(blob, max_chars=200, mode="lite")
    assert "ERROR" in out
    assert len(out) <= 200


def test_compress_tool_results():
    results = [{"tool": "write_file", "result": "ERROR: bad\n" + "x" * 5000}]
    out = compress_tool_results(results, mode="lite")
    assert "ERROR" in out[0]["result"]
    assert len(out[0]["result"]) < 5000
