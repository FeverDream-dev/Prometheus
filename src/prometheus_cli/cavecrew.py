"""Cavecrew-style compressed context — fewer tokens on local models.

Inspired by caveman/cavecrew output contracts (investigator/builder/reviewer).
"""

from __future__ import annotations

import re
from typing import Literal

CavecrewMode = Literal["off", "lite", "full"]
DEFAULT_MODE: CavecrewMode = "lite"


def normalize_mode(mode: str | None) -> CavecrewMode:
    if not mode:
        return DEFAULT_MODE
    key = mode.strip().lower()
    if key in {"off", "lite", "full"}:
        return key  # type: ignore[return-value]
    return DEFAULT_MODE


def compress_text(text: str, *, max_chars: int = 1800, mode: str | None = "lite") -> str:
    """Shrink tool/log output for model context without dropping errors."""
    if normalize_mode(mode) == "off" or len(text) <= max_chars:
        return text
    lines = text.splitlines()
    keep: list[str] = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in ("error", "fail", "denied", "self-check", "exception", "traceback")):
            keep.append(line)
    if not keep:
        keep = [lines[0]] if lines else []
        if len(lines) > 1:
            keep.append("…")
            keep.append(lines[-1])
    out = "\n".join(keep)
    if len(out) > max_chars:
        out = out[: max_chars - 3] + "…"
    return out


def compress_tool_results(results: list[dict], *, mode: str | None = "lite") -> list[dict]:
    """Compress TOOL RESULTS payloads before the next model turn."""
    if normalize_mode(mode) == "off":
        return results
    out = []
    for item in results:
        copy = dict(item)
        if "result" in copy and isinstance(copy["result"], str):
            copy["result"] = compress_text(copy["result"], mode=mode)
        out.append(copy)
    return out


__all__ = ["compress_text", "compress_tool_results", "normalize_mode"]
