"""Packaged default resources for PROMETHEUS.

Exposes the bundled defaults (bundles, prompts, schemas, i18n) so that
``prometheus setup``, ``prometheus bundles list``, and the TUI work without a
repository checkout. User overrides in ``~/.prometheus`` take precedence.

Bundle directory precedence (highest first)::

    1. explicit --bundles-dir
    2. ./.prometheus/bundles
    3. ~/.prometheus/bundles
    4. packaged defaults (this directory)
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

_RESOLVED_ROOT: Path | None = None


def get_resource_root() -> Path:
    global _RESOLVED_ROOT
    if _RESOLVED_ROOT is not None:
        return _RESOLVED_ROOT
    pkg_root = Path(__file__).resolve().parent
    if pkg_root.is_dir():
        _RESOLVED_ROOT = pkg_root
        return pkg_root
    repo_fallback = Path(__file__).resolve().parent.parent.parent.parent / "config"
    _RESOLVED_ROOT = repo_fallback
    return repo_fallback


def _subdir(name: str) -> Path:
    candidate = get_resource_root() / name
    return candidate if candidate.is_dir() else get_resource_root()


def get_default_bundles_dir() -> Path:
    return _subdir("bundles_v2")


def get_default_bundles_v1_dir() -> Path:
    return _subdir("bundles_v1")


def get_default_agents_dir() -> Path:
    return _subdir("agents")


def get_default_prompts_dir() -> Path:
    return _subdir("prompts")


def get_default_schemas_dir() -> Path:
    return _subdir("schemas")


def get_default_i18n_dir() -> Path:
    return _subdir("i18n")


def get_default_config_path() -> Path:
    candidate = get_resource_root() / "default_config.yaml"
    return candidate if candidate.is_file() else get_resource_root() / "default.yaml"


def _user_config_home() -> Path:
    return Path(os.environ.get("PROMETHEUS_HOME", Path.home() / ".prometheus"))


def resolve_bundles_dir(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    cwd_project = Path.cwd() / ".prometheus" / "bundles"
    if cwd_project.is_dir() and any(cwd_project.glob("*.yaml")):
        return cwd_project
    user_bundles = _user_config_home() / "bundles"
    if user_bundles.is_dir() and any(user_bundles.glob("*.yaml")):
        return user_bundles
    return get_default_bundles_dir()


def resolve_bundles_v1_dir(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    cwd_project = Path.cwd() / ".prometheus" / "bundles_v1"
    if cwd_project.is_dir() and any(cwd_project.glob("*.yaml")):
        return cwd_project
    user_v1 = _user_config_home() / "bundles_v1"
    if user_v1.is_dir() and any(user_v1.glob("*.yaml")):
        return user_v1
    return get_default_bundles_v1_dir()


def copy_default_user_config(target: Path, overwrite: bool = False) -> list[Path]:
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    source_pairs = [
        (get_default_bundles_dir(), target / "bundles_v2"),
        (get_default_bundles_v1_dir(), target / "bundles_v1"),
        (get_default_prompts_dir(), target / "prompts"),
    ]
    for src, dest in source_pairs:
        if not src.is_dir():
            continue
        dest.mkdir(parents=True, exist_ok=True)
        for entry in sorted(src.rglob("*")):
            if not entry.is_file():
                continue
            rel = entry.relative_to(src)
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists() and not overwrite:
                continue
            shutil.copy2(entry, out)
            copied.append(out)
    return copied


def list_packaged_bundles() -> list[Path]:
    root = get_default_bundles_dir()
    if not root.is_dir():
        return []
    return sorted(root.glob("*.yaml"))


def list_packaged_bundles_v1() -> list[Path]:
    root = get_default_bundles_v1_dir()
    if not root.is_dir():
        return []
    return sorted(root.glob("*.yaml"))


__all__ = [
    "copy_default_user_config",
    "get_default_agents_dir",
    "get_default_bundles_dir",
    "get_default_bundles_v1_dir",
    "get_default_config_path",
    "get_default_i18n_dir",
    "get_default_prompts_dir",
    "get_default_schemas_dir",
    "get_resource_root",
    "list_packaged_bundles",
    "list_packaged_bundles_v1",
    "resolve_bundles_dir",
    "resolve_bundles_v1_dir",
]
