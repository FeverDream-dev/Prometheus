from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

from prometheus_cli.sandbox import SandboxBroker


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path / "repo"


class TestSandboxDetection:
    def test_detects_bwrap_on_linux(self, workspace: Path):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("shutil.which", return_value="/usr/bin/bwrap"):
            broker = SandboxBroker(workspace, enabled=True)
            assert broker.tool == "bwrap"
            assert broker.active is True

    def test_detects_sandbox_exec_on_macos(self, workspace: Path):
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("shutil.which", return_value="/usr/bin/sandbox-exec"):
            broker = SandboxBroker(workspace, enabled=True)
            assert broker.tool == "sandbox-exec"
            assert broker.active is True

    def test_no_tool_returns_none(self, workspace: Path):
        with mock.patch("shutil.which", return_value=None):
            broker = SandboxBroker(workspace, enabled=True)
            assert broker.tool is None
            assert broker.active is False

    def test_disabled_is_not_active(self, workspace: Path):
        with mock.patch("shutil.which", return_value="/usr/bin/bwrap"):
            broker = SandboxBroker(workspace, enabled=False)
            assert broker.active is False


class TestSandboxWarning:
    def test_warning_when_no_tool_found(self, workspace: Path):
        with mock.patch("shutil.which", return_value=None):
            broker = SandboxBroker(workspace, enabled=True)
            assert broker.warning is not None
            assert broker.tier == "unsandboxed-warning"

    def test_no_warning_when_disabled(self, workspace: Path):
        with mock.patch("shutil.which", return_value=None):
            broker = SandboxBroker(workspace, enabled=False)
            assert broker.warning is None
            assert broker.tier == "unsandboxed"

    def test_no_warning_when_tool_active(self, workspace: Path):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("shutil.which", return_value="/usr/bin/bwrap"):
            broker = SandboxBroker(workspace, enabled=True)
            assert broker.warning is None
            assert "bwrap" in broker.tier


class TestBwrapWrapper:
    def test_wrap_adds_bwrap_prefix(self, workspace: Path):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("shutil.which", return_value="/usr/bin/bwrap"):
            broker = SandboxBroker(workspace, enabled=True)
            wrapped = broker.wrap(["python", "-m", "pytest"])
            assert wrapped[0] == "bwrap"
            assert "python" in wrapped
            assert "-m" in wrapped
            assert "pytest" in wrapped

    def test_wrap_includes_workspace_bind(self, workspace: Path):
        workspace.mkdir(parents=True)
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("shutil.which", return_value="/usr/bin/bwrap"):
            broker = SandboxBroker(workspace, enabled=True)
            wrapped = broker.wrap(["ls"])
            ws_str = str(workspace)
            bind_indices = [i for i, v in enumerate(wrapped) if v == "--bind"]
            assert any(wrapped[i + 1] == ws_str for i in bind_indices)

    def test_wrap_unshares_net_when_disallowed(self, workspace: Path):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("shutil.which", return_value="/usr/bin/bwrap"):
            broker = SandboxBroker(workspace, enabled=True, allow_network=False)
            wrapped = broker.wrap(["curl", "http://evil.com"])
            assert "--unshare-net" in wrapped

    def test_wrap_shares_net_when_allowed(self, workspace: Path):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("shutil.which", return_value="/usr/bin/bwrap"):
            broker = SandboxBroker(workspace, enabled=True, allow_network=True)
            wrapped = broker.wrap(["curl", "http://example.com"])
            assert "--unshare-net" not in wrapped


class TestSandboxExecWrapper:
    def test_wrap_adds_sandbox_exec_prefix(self, workspace: Path):
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("shutil.which", return_value="/usr/bin/sandbox-exec"):
            broker = SandboxBroker(workspace, enabled=True)
            wrapped = broker.wrap(["python", "test.py"])
            assert wrapped[0] == "sandbox-exec"
            assert "test.py" in wrapped


class TestWrapPassthrough:
    def test_disabled_returns_command_unchanged(self, workspace: Path):
        broker = SandboxBroker(workspace, enabled=False)
        cmd = ["echo", "hello"]
        assert broker.wrap(cmd) == cmd

    def test_no_tool_returns_command_unchanged(self, workspace: Path):
        with mock.patch("shutil.which", return_value=None):
            broker = SandboxBroker(workspace, enabled=True)
            cmd = ["echo", "hello"]
            assert broker.wrap(cmd) == cmd


class TestWorkspaceIntegration:
    def test_run_command_uses_sandbox_when_active(self, workspace: Path, tmp_path: Path):
        workspace.mkdir(parents=True)
        (workspace / "test.py").write_text("print('ok')")
        from prometheus_cli.tools.workspace import WorkspaceTools
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("shutil.which", return_value="/usr/bin/bwrap"):
            broker = SandboxBroker(workspace, enabled=True)
            tools = WorkspaceTools(workspace, sandbox=broker)
            result = tools.run_command(["echo", "hello"])
            assert "exit_code=0" in result

    def test_run_command_works_without_sandbox(self, workspace: Path):
        workspace.mkdir(parents=True)
        from prometheus_cli.tools.workspace import WorkspaceTools
        tools = WorkspaceTools(workspace)
        result = tools.run_command(["echo", "hello"])
        assert "exit_code=0" in result
        assert "sandbox" not in result.lower()
