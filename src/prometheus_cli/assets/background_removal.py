from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from rembg import remove as _rembg_remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    _rembg_remove = None


def is_available() -> bool:
    return REMBG_AVAILABLE


def remove_background(input_path: str | Path, output_path: str | Path,
                      model: str = "u2netp") -> dict[str, Any]:
    if not REMBG_AVAILABLE:
        return {
            "success": False,
            "error": "rembg not installed",
            "hint": "pip install rembg",
        }
    input_p = Path(input_path)
    output_p = Path(output_path)
    if not input_p.exists():
        return {"success": False, "error": f"input not found: {input_p}"}
    try:
        input_data = input_p.read_bytes()
        output_data = _rembg_remove(input_data)
        output_p.parent.mkdir(parents=True, exist_ok=True)
        output_p.write_bytes(output_data)
        return {
            "success": True,
            "input": str(input_p),
            "output": str(output_p),
            "input_bytes": len(input_data),
            "output_bytes": len(output_data),
            "model": model,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


__all__ = ["is_available", "remove_background"]
