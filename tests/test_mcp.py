from __future__ import annotations

import json
from unittest import mock

from prometheus_cli.mcp_client import (
    MCPClient,
    MCPRegistry,
    MCPServerConfig,
    UNTRUSTED_DELIMITER_END,
    UNTRUSTED_DELIMITER_START,
)
from prometheus_cli.plugin_manifest import (
    PluginManifest,
    PluginPermission,
    validate_manifest,
    is_valid,
)


class FakeProcess:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.stdin = mock.MagicMock()
        self.stdout = self._FakeReader(self._responses)
        self.stderr = mock.MagicMock()
        self._poll_result = None

    class _FakeReader:
        def __init__(self, responses):
            self._responses = responses
            self._iter = iter(responses)

        def readline(self):
            try:
                return next(self._iter)
            except StopIteration:
                return ""

    def poll(self):
        return self._poll_result

    def terminate(self):
        pass

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


class TestMCPClient:
    def test_initialize_sends_handshake(self):
        config = MCPServerConfig(name="test", command=["echo"])
        responses = [
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {"tools": {}}}}) + "\n",
        ]
        client = MCPClient(config)
        client._proc = FakeProcess(responses)
        result = client.initialize()
        assert "capabilities" in result

    def test_list_tools_parses_response(self):
        config = MCPServerConfig(name="test", command=["echo"])
        responses = [
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {
                "tools": [
                    {"name": "search", "description": "Search the web", "inputSchema": {"type": "object"}},
                    {"name": "fetch", "description": "Fetch a URL", "inputSchema": {}},
                ]
            }}) + "\n",
        ]
        client = MCPClient(config)
        client._proc = FakeProcess(responses)
        tools = client.list_tools()
        assert len(tools) == 2
        assert tools[0].name == "search"
        assert tools[1].name == "fetch"

    def test_call_tool_wraps_output_in_untrusted_delimiters(self):
        config = MCPServerConfig(name="test", command=["echo"])
        responses = [
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {
                "content": [{"type": "text", "text": "some potentially malicious output"}]
            }}) + "\n",
        ]
        client = MCPClient(config)
        client._proc = FakeProcess(responses)
        result = client.call_tool("search", {"query": "test"})
        assert UNTRUSTED_DELIMITER_START in result
        assert UNTRUSTED_DELIMITER_END in result
        assert "some potentially malicious output" in result

    def test_call_tool_empty_result(self):
        config = MCPServerConfig(name="test", command=["echo"])
        responses = [
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"content": []}}) + "\n",
        ]
        client = MCPClient(config)
        client._proc = FakeProcess(responses)
        result = client.call_tool("noop")
        assert result == ""

    def test_close_terminates_process(self):
        config = MCPServerConfig(name="test", command=["sleep", "100"])
        client = MCPClient(config)
        client._proc = FakeProcess([])
        client.close()
        assert client._proc is None
        assert client._initialized is False


class TestMCPRegistry:
    def test_register_and_get(self):
        registry = MCPRegistry()
        config = MCPServerConfig(name="search-server", command=["search-mcp"])
        registry.register(config)
        assert registry.get("search-server") is config

    def test_unregister(self):
        registry = MCPRegistry()
        registry.register(MCPServerConfig(name="x", command=["x"]))
        registry.unregister("x")
        assert registry.get("x") is None

    def test_list_servers(self):
        registry = MCPRegistry()
        registry.register(MCPServerConfig(name="a", command=["a"]))
        registry.register(MCPServerConfig(name="b", command=["b"]))
        names = [s.name for s in registry.list_servers()]
        assert set(names) == {"a", "b"}

    def test_load_from_config(self):
        registry = MCPRegistry()
        registry.load_from_config([
            {"name": "fs", "command": ["fs-mcp"], "trust_level": "trusted"},
            {"name": "net", "command": ["net-mcp"], "network_scope": "allow-all"},
        ])
        assert registry.get("fs").trust_level == "trusted"
        assert registry.get("net").network_scope == "allow-all"

    def test_skip_invalid_entries(self):
        registry = MCPRegistry()
        registry.load_from_config([
            {"name": "", "command": []},
            {"name": "ok", "command": ["ok"]},
        ])
        assert len(registry.list_servers()) == 1


class TestPluginManifest:
    def test_round_trip_serialization(self, tmp_path):
        manifest = PluginManifest(
            id="my-plugin",
            name="My Plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            license="MIT",
            entry_point="main.py",
            permissions=[
                PluginPermission(name="read_files", description="Read workspace files", required=True),
                PluginPermission(name="network", description="Network access", required=False),
            ],
            tools=["search", "format"],
        )
        path = tmp_path / "plugin.yaml"
        manifest.save(path)
        loaded = PluginManifest.load(path)
        assert loaded.id == "my-plugin"
        assert loaded.name == "My Plugin"
        assert loaded.version == "1.0.0"
        assert len(loaded.permissions) == 2
        assert loaded.permissions[0].name == "read_files"
        assert loaded.permissions[0].required is True
        assert loaded.tools == ["search", "format"]

    def test_from_dict_creates_manifest(self):
        data = {
            "id": "test",
            "name": "Test",
            "version": "0.1.0",
            "license": "Apache-2.0",
            "permissions": [{"name": "read", "required": True}],
        }
        manifest = PluginManifest.from_dict(data)
        assert manifest.id == "test"
        assert manifest.permissions[0].name == "read"

    def test_validate_missing_required_fields(self):
        manifest = PluginManifest(id="", name="", version="", license="")
        errors = validate_manifest(manifest)
        assert any("id" in e for e in errors)
        assert any("name" in e for e in errors)
        assert any("version" in e for e in errors)
        assert any("license" in e for e in errors)

    def test_validate_wrong_schema_version(self):
        manifest = PluginManifest(
            id="ok", name="OK", version="1.0", license="MIT",
            schema_version=99,
        )
        errors = validate_manifest(manifest)
        assert any("schema_version" in e for e in errors)

    def test_valid_manifest_passes(self):
        manifest = PluginManifest(
            id="valid", name="Valid", version="1.0.0", license="MIT",
        )
        assert is_valid(manifest) is True
        assert len(validate_manifest(manifest)) == 0

    def test_permission_without_name_flagged(self):
        manifest = PluginManifest(
            id="x", name="X", version="1.0", license="MIT",
            permissions=[PluginPermission(name="")],
        )
        errors = validate_manifest(manifest)
        assert any("permission" in e for e in errors)
