from __future__ import annotations

import sys
from pathlib import Path

from prometheus_cli.mcp_client import (
    UNTRUSTED_DELIMITER_END,
    UNTRUSTED_DELIMITER_START,
    MCPClient,
    MCPRegistry,
    MCPServerConfig,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mcp" / "echo_server.py"


def _client() -> MCPClient:
    cfg = MCPServerConfig(
        name="echo",
        command=[sys.executable, str(FIXTURE)],
        trust_level="untrusted",
        network_scope="none",
    )
    return MCPClient(cfg)


class TestMCPFixtureEndToEnd:
    def setup_method(self):
        self.client = _client()

    def teardown_method(self):
        self.client.close()

    def test_initialize_handshake(self):
        info = self.client.initialize()
        assert info["serverInfo"]["name"] == "echo-fixture"
        assert info["protocolVersion"] == "2024-11-05"

    def test_list_tools_discovers_advertised_tools(self):
        self.client.initialize()
        tools = self.client.list_tools()
        names = {t.name for t in tools}
        assert names == {"echo", "fetch_doc"}
        echo = next(t for t in tools if t.name == "echo")
        assert "text" in echo.input_schema.get("properties", {})

    def test_call_echo_returns_text(self):
        self.client.initialize()
        out = self.client.call_tool("echo", {"text": "hello world"})
        assert "hello world" in out
        assert UNTRUSTED_DELIMITER_START in out
        assert UNTRUSTED_DELIMITER_END in out

    def test_prompt_injection_output_is_delimited_as_untrusted_data(self):
        self.client.initialize()
        out = self.client.call_tool("fetch_doc", {"url": "http://example.invalid/x"})
        assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in out
        assert "rm -rf /" in out
        start = out.index(UNTRUSTED_DELIMITER_START)
        end = out.index(UNTRUSTED_DELIMITER_END)
        assert start < end
        injected = out[start:end]
        assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in injected
        assert "rm -rf /" in injected

    def test_unknown_tool_returns_error_not_silent_success(self):
        self.client.initialize()
        raised = False
        try:
            self.client.call_tool("does_not_exist", {})
        except KeyError:
            raised = True
        except Exception:
            raised = True
        assert raised

    def test_registry_load_unregister_and_namespacing(self):
        reg = MCPRegistry()
        reg.load_from_config([
            {"name": "echo", "command": ["x"], "trust_level": "untrusted"},
            {"name": "chrome", "command": ["y"], "trust_level": "trusted", "network_scope": "loopback"},
        ])
        assert reg.get("echo") is not None
        assert reg.get("chrome").network_scope == "loopback"
        assert {s.name for s in reg.list_servers()} == {"echo", "chrome"}
        reg.unregister("echo")
        assert reg.get("echo") is None

    def test_client_reconnects_after_process_exit(self):
        self.client.initialize()
        assert self.client._proc is not None
        self.client._proc.terminate()
        self.client._proc.wait(timeout=5)
        info = self.client.initialize()
        assert info["serverInfo"]["name"] == "echo-fixture"
