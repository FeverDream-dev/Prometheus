from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class McpTemplateServer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    command: list[str]
    trust_level: str = "untrusted"
    network_scope: str = "none"
    env: dict[str, str] = Field(default_factory=dict)


class McpTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str = ""
    warning: str = ""
    servers: list[McpTemplateServer] = Field(default_factory=list)
    permissions: dict[str, str] = Field(default_factory=dict)
    setup_steps: list[str] = Field(default_factory=list)


def _templates_dir() -> Path:
    from .resources import get_resource_root
    return get_resource_root() / "mcp_templates"


def list_templates() -> list[str]:
    d = _templates_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def load_template(template_id: str) -> McpTemplate:
    path = _templates_dir() / f"{template_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"template not found: {template_id} ({path})")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return McpTemplate.model_validate(data)


def get_template_server_configs(template_id: str) -> list[dict]:
    template = load_template(template_id)
    return [
        {
            "name": s.name,
            "command": s.command,
            "trust_level": s.trust_level,
            "network_scope": s.network_scope,
            "env": s.env,
        }
        for s in template.servers
    ]


def install_template(template_id: str, mcp_config_path: Path) -> Path:
    import json

    mcp_config_path = Path(mcp_config_path)
    servers = get_template_server_configs(template_id)

    data: dict = {"servers": []}
    if mcp_config_path.exists():
        try:
            data = json.loads(mcp_config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            pass
    if "servers" not in data:
        data["servers"] = []

    existing_names = {s.get("name") for s in data["servers"]}
    for server in servers:
        if server["name"] not in existing_names:
            data["servers"].append(server)

    mcp_config_path.parent.mkdir(parents=True, exist_ok=True)
    mcp_config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return mcp_config_path


__all__ = [
    "McpTemplate",
    "McpTemplateServer",
    "get_template_server_configs",
    "install_template",
    "list_templates",
    "load_template",
]
