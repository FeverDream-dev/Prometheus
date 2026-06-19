from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


MANIFEST_VERSION = 1


@dataclass
class PluginPermission:
    name: str
    description: str = ""
    required: bool = False


@dataclass
class PluginManifest:
    schema_version: int = MANIFEST_VERSION
    id: str = ""
    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    license: str = ""
    entry_point: str = ""
    permissions: list[PluginPermission] = field(default_factory=list)
    mcp_servers: list[dict] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    signature: dict | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "entry_point": self.entry_point,
            "permissions": [
                {"name": p.name, "description": p.description, "required": p.required}
                for p in self.permissions
            ],
            "mcp_servers": self.mcp_servers,
            "tools": self.tools,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PluginManifest":
        perms_data = data.get("permissions", [])
        permissions = [
            PluginPermission(
                name=p.get("name", ""),
                description=p.get("description", ""),
                required=p.get("required", False),
            )
            for p in perms_data
        ]
        return cls(
            schema_version=data.get("schema_version", MANIFEST_VERSION),
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            license=data.get("license", ""),
            entry_point=data.get("entry_point", ""),
            permissions=permissions,
            mcp_servers=data.get("mcp_servers", []),
            tools=data.get("tools", []),
            signature=data.get("signature"),
        )

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(self.to_dict(), sort_keys=False), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "PluginManifest":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data or {})


REQUIRED_FIELDS = {"id", "name", "version", "license"}


def validate_manifest(manifest: PluginManifest) -> list[str]:
    errors: list[str] = []
    if not manifest.id:
        errors.append("id is required")
    if not manifest.name:
        errors.append("name is required")
    if not manifest.version:
        errors.append("version is required")
    if not manifest.license:
        errors.append("license is required")
    if manifest.schema_version != MANIFEST_VERSION:
        errors.append(f"schema_version must be {MANIFEST_VERSION}")
    for perm in manifest.permissions:
        if not perm.name:
            errors.append("each permission must have a name")
    return errors


def is_valid(manifest: PluginManifest) -> bool:
    return len(validate_manifest(manifest)) == 0
