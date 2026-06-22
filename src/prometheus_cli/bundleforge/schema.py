from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

_BUNDLE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]+$")
_PERMISSION_LEVELS = {"allow", "ask", "deny"}
_KNOWN_ROLE_NAMES = {"envoy", "builder", "critic", "controller", "vision", "embedding", "reviewer", "guardian"}

V2_ROLE_MAP = {
    "envoy": "controller",
    "builder": "coder",
    "critic": "reviewer",
    "controller": "controller",
    "vision": "vision",
    "embedding": "embedding",
    "reviewer": "reviewer",
    "guardian": "guardian",
}


class ForgeRoleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str
    provider: str = "ollama"


class ForgePermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    network: Literal["allow", "ask", "deny"] = "ask"
    package_install: Literal["allow", "ask", "deny"] = "ask"
    browser: Literal["allow", "ask", "deny"] = "ask"
    assets: Literal["allow", "ask", "deny"] = "ask"
    external_directory: Literal["allow", "ask", "deny"] = "deny"


class ForgeRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_ram_gb: int = Field(ge=0)
    min_vram_gb: int = Field(default=0, ge=0)
    min_disk_gb: int = Field(default=10, ge=0)


class ForgeBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str = ""
    version: str = "0.1.0"
    use_case: str = ""
    roles: dict[str, ForgeRoleSpec] = Field(default_factory=dict)
    optional: dict[str, str] = Field(default_factory=dict)
    mcp: dict[str, Any] | None = None
    permissions: ForgePermissions = Field(default_factory=ForgePermissions)
    requirements: ForgeRequirements = Field(default_factory=ForgeRequirements)
    license_notes: str = ""
    commercial_safe: bool = True

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not _BUNDLE_ID_RE.match(v):
            raise ValueError(f"invalid bundle id: {v!r}")
        return v

    @field_validator("roles")
    @classmethod
    def _known_role_names(cls, v: dict) -> dict:
        unknown = [r for r in v if r not in _KNOWN_ROLE_NAMES]
        if unknown:
            raise ValueError(f"unknown role names: {unknown}. Known: {sorted(_KNOWN_ROLE_NAMES)}")
        if not v:
            raise ValueError("bundle must define at least one role")
        return v

    @property
    def all_model_ids(self) -> list[str]:
        ids = [r.model for r in self.roles.values()]
        ids.extend(self.optional.values())
        return ids

    def to_v2_dict(self) -> dict:
        roles_v2: dict[str, dict] = {}
        for forge_role, spec in self.roles.items():
            v2_role = V2_ROLE_MAP.get(forge_role, forge_role)
            roles_v2[v2_role] = {
                "model": spec.model,
                "approximate_download_gb": 1.0,
                "capabilities": [],
                "keep_alive": "5m",
            }
        for opt_key, opt_model in self.optional.items():
            if opt_key in ("image_generator", "background_removal"):
                continue
            v2_role = V2_ROLE_MAP.get(opt_key, opt_key)
            if v2_role not in roles_v2:
                roles_v2[v2_role] = {
                    "model": opt_model,
                    "approximate_download_gb": 1.0,
                    "capabilities": [],
                    "keep_alive": "5m",
                    "optional": True,
                }

        return {
            "schema_version": 2,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "hardware": {
                "minimum_ram_gb": self.requirements.min_ram_gb,
                "minimum_vram_gb": self.requirements.min_vram_gb,
                "minimum_free_disk_gb": self.requirements.min_disk_gb,
            },
            "runtime": {
                "provider": "ollama",
                "sequential_loading": True,
                "maximum_loaded_models": 1,
                "default_context": 8192,
                "unlimited_local_sessions": True,
            },
            "roles": roles_v2,
            "licenses": [
                {"model": mid, "license": "check_upstream", "source": "https://ollama.com"}
                for mid in {r.model for r in self.roles.values()}
            ],
            "qualification": {"required": []},
            "experimental": False,
        }


def load_forge_bundle(path: Path) -> ForgeBundle:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ForgeBundle.model_validate(data)
