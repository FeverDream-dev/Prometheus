from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

_CATALOG_CACHE: ModelCatalog | None = None


class ModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str = "ollama"
    family: str = ""
    roles: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)
    approx_download_size_mb: int = Field(ge=0)
    min_ram_gb: int = Field(ge=0)
    min_vram_gb: int = Field(ge=0)
    context_window: int = Field(default=0, ge=0)
    license: str = "check_upstream"
    commercial_safe: bool = False
    source_url: str = ""
    aliases: list[str] = Field(default_factory=list)

    @field_validator("source_url")
    @classmethod
    def _source_must_be_url_or_empty(cls, v: str) -> str:
        if v and not v.startswith(("https://", "http://")):
            raise ValueError(f"source_url must be an HTTPS URL: {v!r}")
        return v

    @property
    def download_gb(self) -> float:
        return self.approx_download_size_mb / 1024


class ModelCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version: int
    last_updated: str = ""
    models: list[ModelEntry]

    def by_id(self, model_id: str) -> ModelEntry | None:
        for m in self.models:
            if m.id == model_id or model_id in m.aliases:
                return m
        return None

    def by_role(self, role: str) -> list[ModelEntry]:
        return [m for m in self.models if role in m.roles]

    def by_strength(self, strength: str) -> list[ModelEntry]:
        return [m for m in self.models if strength in m.strengths]

    def by_family(self, family: str) -> list[ModelEntry]:
        return [m for m in self.models if m.family == family]

    def all_ids(self) -> list[str]:
        return [m.id for m in self.models]

    def commercial_safe_ids(self) -> list[str]:
        return [m.id for m in self.models if m.commercial_safe]

    def fits_hardware(self, ram_gb: float, vram_gb: float) -> list[ModelEntry]:
        return [
            m for m in self.models
            if m.min_ram_gb <= ram_gb and m.min_vram_gb <= vram_gb
        ]

    def recommend_for_role(self, role: str, ram_gb: float, vram_gb: float, prefer_quality: bool = False) -> ModelEntry | None:
        candidates = [
            m for m in self.by_role(role)
            if m.min_ram_gb <= ram_gb and m.min_vram_gb <= vram_gb
            and "embedding_only" not in m.limits
        ]
        if not candidates:
            return None
        if prefer_quality:
            candidates.sort(key=lambda m: (-m.approx_download_size_mb, m.id))
        else:
            candidates.sort(key=lambda m: (m.approx_download_size_mb, m.id))
        return candidates[0]


def _catalog_path() -> Path:
    from ..resources import get_resource_root
    return get_resource_root() / "model_catalog" / "catalog.yaml"


def load_catalog(path: Path | None = None) -> ModelCatalog:
    global _CATALOG_CACHE
    if path is None and _CATALOG_CACHE is not None:
        return _CATALOG_CACHE
    resolved = path or _catalog_path()
    if not resolved.is_file():
        raise FileNotFoundError(f"model catalog not found: {resolved}")
    data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    catalog = ModelCatalog.model_validate(data)
    if path is None:
        _CATALOG_CACHE = catalog
    return catalog


def reload_catalog() -> ModelCatalog:
    global _CATALOG_CACHE
    _CATALOG_CACHE = None
    return load_catalog()


__all__ = [
    "ModelCatalog",
    "ModelEntry",
    "load_catalog",
    "reload_catalog",
]
