from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .style_snapshot import StyleSnapshot, STATE_PROPERTIES


@dataclass
class ElementCapture:
    selector: str
    screenshot_b64: str = ""
    variants: dict[str, str] = field(default_factory=dict)
    snapshots: dict[str, StyleSnapshot] = field(default_factory=dict)
    accessibility: dict[str, Any] = field(default_factory=dict)
    full_page_screenshot_b64: str = ""
    error: str = ""

    def save_to(self, out_dir: Path) -> dict[str, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        written: dict[str, Path] = {}
        if self.screenshot_b64:
            p = out_dir / "element.png"
            p.write_bytes(base64.b64decode(self.screenshot_b64))
            written["element"] = p
        for state, b64 in self.variants.items():
            p = out_dir / f"element-{state}.png"
            p.write_bytes(base64.b64decode(b64))
            written[f"element-{state}"] = p
        style_data = {s: snap.to_dict() for s, snap in self.snapshots.items()}
        sp = out_dir / "style.json"
        sp.write_text(json.dumps(style_data, indent=2, sort_keys=True), encoding="utf-8")
        written["style"] = sp
        ap = out_dir / "accessibility.json"
        ap.write_text(json.dumps(self.accessibility, indent=2, sort_keys=True), encoding="utf-8")
        written["accessibility"] = ap
        if self.full_page_screenshot_b64:
            fp = out_dir / "page.png"
            fp.write_bytes(base64.b64decode(self.full_page_screenshot_b64))
            written["page"] = fp
        return written

    def to_dict(self) -> dict[str, Any]:
        return {
            "selector": self.selector,
            "has_screenshot": bool(self.screenshot_b64),
            "variants": {k: f"{len(v)} chars" for k, v in self.variants.items()},
            "snapshots": {s: snap.to_dict() for s, snap in self.snapshots.items()},
            "accessibility": self.accessibility,
            "has_full_page": bool(self.full_page_screenshot_b64),
            "error": self.error,
        }


def _b64(png_bytes: bytes) -> str:
    return base64.b64encode(png_bytes).decode("ascii")


def capture_element(
    page,
    selector: str,
    variants: tuple[str, ...] = ("hover", "focus", "disabled"),
    include_full_page: bool = False,
) -> ElementCapture:
    """Capture element-only screenshot + CSS + accessibility from a Playwright page.

    ``page`` is a playwright.sync_api.Page. Playwright must already be started.
    """
    capture = ElementCapture(selector=selector)
    if page is None:
        capture.error = "page is None — Playwright must be started before calling capture_element"
        return capture
    loc = page.locator(selector).first
    try:
        loc.wait_for(state="visible", timeout=10000)
    except Exception as exc:
        capture.error = f"element not visible: {exc}"
        return capture

    from .style_snapshot import SNAPSHOT_PROPERTIES, JS_GET_COMPUTED_STYLE, JS_GET_ACCESSIBILITY, build_snapshot

    raw_normal = loc.evaluate(JS_GET_COMPUTED_STYLE, list(SNAPSHOT_PROPERTIES))
    capture.snapshots["normal"] = build_snapshot(raw_normal, state="normal")

    png = loc.screenshot()
    capture.screenshot_b64 = _b64(png)

    for variant in variants:
        try:
            if variant == "hover":
                loc.hover(timeout=3000)
            elif variant == "focus":
                loc.focus(timeout=3000)
            elif variant == "disabled":
                pass
            raw_v = loc.evaluate(JS_GET_COMPUTED_STYLE, list(STATE_PROPERTIES))
            snap_v = build_snapshot(raw_v, state=variant)
            capture.snapshots[variant] = snap_v
            png_v = loc.screenshot()
            capture.variants[variant] = _b64(png_v)
            loc.evaluate("() => { this.blur(); }")
        except Exception:
            pass

    try:
        capture.accessibility = loc.evaluate(JS_GET_ACCESSIBILITY) or {}
    except Exception:
        capture.accessibility = {}

    if include_full_page:
        try:
            capture.full_page_screenshot_b64 = _b64(page.screenshot(full_page=True))
        except Exception:
            pass

    return capture


__all__ = ["ElementCapture", "capture_element"]
