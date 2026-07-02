"""Ponytail efficiency ladder — minimal-code discipline for local agents.

Inspired by https://github.com/DietrichGebert/ponytail (MIT). PROMETHEUS injects
the ladder into controller/builder system prompts so 8–12 GB models spend tokens
on diffs, not boilerplate.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

PonytailMode = Literal["off", "lite", "full", "ultra"]
RUNTIME_MODES: frozenset[str] = frozenset({"off", "lite", "full", "ultra"})
DEFAULT_MODE: PonytailMode = "full"

_PROMPT_PATH = Path(__file__).resolve().parent / "resources" / "prompts" / "ponytail.md"

_FALLBACK = (
    "PONYTAIL (full): Before coding, climb YAGNI → reuse → stdlib → native → "
    "installed dep → one line → minimum. Never cut validation, security, or "
    "sandbox gates. Shortest working diff after reading the code."
)

_LITE = (
    "PONYTAIL (lite): Build what was asked; name the lazier alternative in one line."
)

_ULTRA = (
    "PONYTAIL (ultra): YAGNI extremist. Deletion before addition. Challenge "
    "unrequested scope in the same breath. One-liner when it holds."
)


def normalize_mode(mode: str | None) -> PonytailMode:
    if not mode:
        return DEFAULT_MODE
    key = mode.strip().lower()
    if key in RUNTIME_MODES:
        return key  # type: ignore[return-value]
    return DEFAULT_MODE


def default_mode() -> PonytailMode:
    env = os.environ.get("PONYTAIL_MODE") or os.environ.get("PROMETHEUS_PONYTAIL_MODE")
    return normalize_mode(env)


@lru_cache(maxsize=1)
def _load_prompt_body() -> str:
    try:
        text = _PROMPT_PATH.read_text(encoding="utf-8")
        return re.sub(r"^---[\s\S]*?---\s*", "", text, count=1).strip()
    except OSError:
        return _FALLBACK


def build_injected_context(mode: str | None = None) -> str:
    """Return system-prompt addon for the active Ponytail level."""
    effective = normalize_mode(mode or default_mode())
    if effective == "off":
        return ""
    if effective == "lite":
        return _LITE
    if effective == "ultra":
        return f"PONYTAIL MODE: ultra\n\n{_ULTRA}\n\n{_load_prompt_body()}"
    return f"PONYTAIL MODE: full\n\n{_load_prompt_body()}"


def append_to_prompt(base: str, mode: str | None = None) -> str:
    addon = build_injected_context(mode)
    if not addon:
        return base
    return f"{base.rstrip()}\n\n{addon}"


def system_prompt_with_ponytail(base: str, mode: str | None = None) -> str:
    """Alias used by orchestrator and arena seats."""
    return append_to_prompt(base, mode)


__all__ = [
    "DEFAULT_MODE",
    "PonytailMode",
    "RUNTIME_MODES",
    "append_to_prompt",
    "build_injected_context",
    "default_mode",
    "normalize_mode",
    "system_prompt_with_ponytail",
]
