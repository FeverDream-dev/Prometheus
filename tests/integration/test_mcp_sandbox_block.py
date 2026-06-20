from __future__ import annotations

import sys
from pathlib import Path

from prometheus_cli.mcp_client import MCPClient, MCPServerConfig
from prometheus_cli.models import SandboxTier, Settings
from prometheus_cli.tools.workspace import WorkspaceTools

MALICIOUS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "mcp" / "mcp_malicious_server.py"


def test_mcp_server_returns_untrusted_payload_but_workspace_still_blocks_write(tmp_path):
    cfg = MCPServerConfig(name="malicious", command=[sys.executable, str(MALICIOUS)], trust_level="untrusted")
    client = MCPClient(cfg)
    try:
        info = client.initialize()
        assert info["serverInfo"]["name"] == "malicious-fixture"
        tools = client.list_tools()
        assert any(t.name == "exfiltrate" for t in tools)
        out = client.call_tool("exfiltrate", {"path": "../../etc/passwd"})
        assert "UNTRUSTED MCP OUTPUT" in out
        assert "rm -rf /" in out
    finally:
        client.close()

    ws = tmp_path / "ws"
    ws.mkdir()
    settings = Settings(sandbox_tier=SandboxTier.BASIC)
    tools = WorkspaceTools.from_settings(ws, settings)
    try:
        tools.write_file("../mcp_exfil.txt", "pwned")
        blocked = False
    except PermissionError:
        blocked = True
    assert blocked, "workspace policy must block the outside write the MCP server requested"


def test_mcp_output_cannot_alter_command_policy(tmp_path):
    cfg = MCPServerConfig(name="malicious", command=[sys.executable, str(MALICIOUS)])
    client = MCPClient(cfg)
    try:
        client.initialize()
        client.call_tool("exfiltrate", {})
    finally:
        client.close()
    settings = Settings(sandbox_tier=SandboxTier.BASIC)
    tools = WorkspaceTools.from_settings(tmp_path, settings)
    result = tools.run_command(["rm", "-rf", "/"])
    assert "BLOCKED" in result
