"""Caveman terse communication — embedded token efficiency.

Inspired by https://github.com/JuliusBrussee/caveman (MIT).
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

CavemanMode = Literal["off", "lite", "full", "ultra"]
RUNTIME_MODES: frozenset[str] = frozenset({"off", "lite", "full", "ultra"})
DEFAULT_MODE: CavemanMode = "full"

_PROMPT_PATH = Path(__file__).resolve().parent / "resources" / "prompts" / "caveman.md"

_FORGE_TOOL_RULE = (
    "TOOL RULE: Every file change MUST be a JSON ToolCall in calls[]. "
    "Never narrate write_file/read_file/run_command only in message."
)

_LITE = "CAVEman (lite): Tight messages. Actions in calls[], not prose."

_ULTRA = (
    "CAVEman (ultra): Min tokens. calls[] only for actions. "
    "message ≤2 short lines. Errors: one quoted line."
)


def normalize_mode(mode: str | None) -> CavemanMode:
    if not mode:
        return DEFAULT_MODE
    key = mode.strip().lower()
    if key in RUNTIME_MODES:
        return key  # type: ignore[return-value]
    return DEFAULT_MODE


def default_mode() -> CavemanMode:
    env = os.environ.get("PROMETHEUS_CAVEMAN_MODE") or os.environ.get("CAVEman_MODE")
    return normalize_mode(env)


@lru_cache(maxsize=1)
def _load_prompt_body() -> str:
    try:
        text = _PROMPT_PATH.read_text(encoding="utf-8")
        return re.sub(r"^---[\s\S]*?---\s*", "", text, count=1).strip()
    except OSError:
        return _FORGE_TOOL_RULE


def build_injected_context(mode: str | None = None, *, forge: bool = False) -> str:
    effective = normalize_mode(mode or default_mode())
    if effective == "off":
        return _FORGE_TOOL_RULE if forge else ""
    if effective == "lite":
        base = _LITE
    elif effective == "ultra":
        base = _ULTRA
    else:
        base = f"CAVEman (full):\n\n{_load_prompt_body()}"
    if forge:
        base = f"{base}\n\n{_FORGE_TOOL_RULE}"
    return base


def append_to_prompt(base: str, mode: str | None = None, *, forge: bool = False) -> str:
    addon = build_injected_context(mode, forge=forge)
    if not addon:
        return base
    return f"{base.rstrip()}\n\n{addon}"


def compress_user_message(text: str, mode: str | None = None, *, max_chars: int = 400) -> str:
    """Compress status lines shown to user (not model file content)."""
    if normalize_mode(mode) == "off" or len(text) <= max_chars:
        return text
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) <= 3:
        return text[:max_chars]
    return "\n".join(lines[:2] + ["…"] + lines[-1:])[:max_chars]


__all__ = [
    "DEFAULT_MODE",
    "CavemanMode",
    "RUNTIME_MODES",
    "append_to_prompt",
    "build_injected_context",
    "compress_user_message",
    "default_mode",
    "normalize_mode",
]
