from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any


MCP_PROTOCOL_VERSION = "2024-11-05"

UNTRUSTED_DELIMITER_START = "--- UNTRUSTED MCP OUTPUT START ---"
UNTRUSTED_DELIMITER_END = "--- UNTRUSTED MCP OUTPUT END ---"


@dataclass
class MCPServerConfig:
    name: str
    command: list[str]
    trust_level: str = "untrusted"
    network_scope: str = "none"
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class MCPTool:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


class MCPClient:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._proc: subprocess.Popen[str] | None = None
        self._id_counter = 0
        self._lock = threading.Lock()
        self._initialized = False

    def _next_id(self) -> int:
        with self._lock:
            self._id_counter += 1
            return self._id_counter

    def _ensure_process(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._proc = subprocess.Popen(
            self.config.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**self.config.env},
        )

    def _send(self, method: str, params: dict | None = None) -> dict:
        self._ensure_process()
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("MCP server process not available")
        msg = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params:
            msg["params"] = params
        line = json.dumps(msg) + "\n"
        self._proc.stdin.write(line)
        self._proc.stdin.flush()
        response_line = self._proc.stdout.readline()
        if not response_line:
            raise RuntimeError("MCP server closed the connection")
        return json.loads(response_line)

    def _notify(self, method: str, params: dict | None = None) -> None:
        self._ensure_process()
        if self._proc is None or self._proc.stdin is None:
            return
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def initialize(self) -> dict:
        response = self._send("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "prometheus", "version": "0.1.0"},
        })
        self._notify("notifications/initialized")
        self._initialized = True
        return response.get("result", {})

    def list_tools(self) -> list[MCPTool]:
        response = self._send("tools/list")
        result = response.get("result", {})
        tools_data = result.get("tools", [])
        return [
            MCPTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in tools_data
        ]

    def call_tool(self, name: str, arguments: dict | None = None) -> str:
        response = self._send("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        result = response.get("result", {})
        content_parts = result.get("content", [])
        text_parts = [p.get("text", "") for p in content_parts if p.get("type") == "text"]
        raw_output = "\n".join(text_parts)
        return self._delimit_untrusted(raw_output)

    def _delimit_untrusted(self, text: str) -> str:
        if not text:
            return ""
        return f"{UNTRUSTED_DELIMITER_START}\n{text}\n{UNTRUSTED_DELIMITER_END}"

    def close(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
        self._initialized = False


class MCPRegistry:
    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {}

    def register(self, config: MCPServerConfig) -> None:
        self._servers[config.name] = config

    def unregister(self, name: str) -> None:
        self._servers.pop(name, None)

    def get(self, name: str) -> MCPServerConfig | None:
        return self._servers.get(name)

    def list_servers(self) -> list[MCPServerConfig]:
        return list(self._servers.values())

    def load_from_config(self, servers: list[dict]) -> None:
        for entry in servers:
            config = MCPServerConfig(
                name=entry.get("name", ""),
                command=entry.get("command", []),
                trust_level=entry.get("trust_level", "untrusted"),
                network_scope=entry.get("network_scope", "none"),
                env=entry.get("env", {}),
            )
            if config.name and config.command:
                self.register(config)
