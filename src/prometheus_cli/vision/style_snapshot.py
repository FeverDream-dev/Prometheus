"""Deterministic computed-CSS snapshot for UI elements.

The CSS snapshot is the first judge; a vision model is a second reviewer,
never the source of truth (per the recovery prompt section 3.8).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

# Properties captured for every element inspection.
# Ordered for deterministic output.
SNAPSHOT_PROPERTIES: tuple[str, ...] = (
    "background-color",
    "color",
    "border-color",
    "border-width",
    "border-style",
    "border-radius",
    "font-family",
    "font-size",
    "font-weight",
    "line-height",
    "padding",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "margin",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "width",
    "height",
    "box-shadow",
    "opacity",
    "cursor",
    "display",
    "position",
    "text-align",
    "text-decoration",
    "letter-spacing",
    "text-transform",
)

# State-variant properties captured for hover/focus/disabled.
STATE_PROPERTIES: tuple[str, ...] = (
    "background-color",
    "color",
    "border-color",
    "box-shadow",
    "opacity",
    "cursor",
    "outline",
)


@dataclass
class BoundingBox:
    """Element bounding box in CSS pixels."""
    x: float
    y: float
    width: float
    height: float
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class StyleSnapshot:
    """Deterministic computed-CSS snapshot of a single element state."""
    properties: dict[str, str] = field(default_factory=dict)
    bounding_box: BoundingBox | None = None
    contrast_ratio: float | None = None
    state: str = "normal"  # normal | hover | focus | disabled

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"state": self.state, "properties": dict(self.properties)}
        if self.bounding_box:
            d["bounding_box"] = self.bounding_box.to_dict()
        if self.contrast_ratio is not None:
            d["contrast_ratio"] = round(self.contrast_ratio, 2)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


# --- JavaScript snippets executed inside Playwright to extract CSS ---

JS_GET_COMPUTED_STYLE = """
(properties) => {
    const el = this;
    const cs = window.getComputedStyle(el);
    const result = {};
    for (const prop of properties) {
        result[prop] = cs.getPropertyValue(prop);
    }
    const rect = el.getBoundingClientRect();
    result['bounding_box'] = {
        x: rect.x, y: rect.y, width: rect.width, height: rect.height,
        top: rect.top, right: rect.right, bottom: rect.bottom, left: rect.left,
    };
    return result;
}
"""

JS_GET_ACCESSIBILITY = """
() => {
    const el = this;
    const role = el.getAttribute('role');
    const ariaLabel = el.getAttribute('aria-label');
    const tagName = el.tagName.toLowerCase();
    const textContent = (el.textContent || '').trim().slice(0, 200);
    const disabled = el.disabled === true || el.getAttribute('aria-disabled') === 'true';
    const hidden = el.getAttribute('aria-hidden') === 'true'
        || cs_displayNone(el)
        || el.offsetParent === null;
    function cs_displayNone(node) {
        return window.getComputedStyle(node).display === 'none';
    }
    const focused = document.activeElement === el;
    return {
        role: role || (tagName === 'button' ? 'button'
                       : tagName === 'a' ? 'link'
                       : tagName === 'input' ? 'textbox'
                       : ''),
        name: ariaLabel || textContent || el.title || '',
        tagName: tagName,
        text: textContent,
        disabled: disabled,
        hidden: hidden,
        focused: focused,
    };
}
"""


def compute_contrast_ratio(fg: str, bg: str) -> float | None:
    """Approximate WCAG contrast ratio from two CSS color strings.

    Returns None if either color cannot be parsed.
    """
    fg_rgb = _parse_color(fg)
    bg_rgb = _parse_color(bg)
    if fg_rgb is None or bg_rgb is None:
        return None
    l1 = _relative_luminance(fg_rgb)
    l2 = _relative_luminance(bg_rgb)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _parse_color(css_color: str) -> tuple[float, float, float] | None:
    """Parse common CSS color formats to (r, g, b) in 0..255."""
    css_color = css_color.strip()
    if not css_color or css_color == "none":
        return None
    # rgb(r, g, b) or rgba(r, g, b, a)
    if css_color.startswith("rgb"):
        parts = css_color.replace("rgba", "").replace("rgb", "").strip("() ").split(",")
        try:
            return (float(parts[0]), float(parts[1]), float(parts[2]))
        except (ValueError, IndexError):
            return None
    # hex #rgb or #rrggbb
    if css_color.startswith("#"):
        hex_str = css_color[1:]
        if len(hex_str) == 3:
            hex_str = "".join(c * 2 for c in hex_str)
        if len(hex_str) == 6:
            try:
                r = int(hex_str[0:2], 16)
                g = int(hex_str[2:4], 16)
                b = int(hex_str[4:6], 16)
                return (float(r), float(g), float(b))
            except ValueError:
                return None
    # Named colors (common subset)
    named = {
        "white": (255, 255, 255), "black": (0, 0, 0), "red": (255, 0, 0),
        "green": (0, 128, 0), "blue": (0, 0, 255), "transparent": (0, 0, 0),
        "inherit": (0, 0, 0), "initial": (0, 0, 0),
    }
    return named.get(css_color.lower())


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG 2.x relative luminance."""
    def _channel(v: float) -> float:
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def build_snapshot(
    raw_props: dict[str, Any],
    state: str = "normal",
) -> StyleSnapshot:
    bbox_data = raw_props.pop("bounding_box", None)
    bbox = None
    if bbox_data and isinstance(bbox_data, dict):
        bbox = BoundingBox(
            x=bbox_data.get("x", 0), y=bbox_data.get("y", 0),
            width=bbox_data.get("width", 0), height=bbox_data.get("height", 0),
            top=bbox_data.get("top", 0), right=bbox_data.get("right", 0),
            bottom=bbox_data.get("bottom", 0), left=bbox_data.get("left", 0),
        )
    props = {k: str(v) for k, v in sorted(raw_props.items())}
    contrast = compute_contrast_ratio(
        props.get("color", ""),
        props.get("background-color", ""),
    )
    return StyleSnapshot(properties=props, bounding_box=bbox, contrast_ratio=contrast, state=state)


__all__ = [
    "BoundingBox",
    "SNAPSHOT_PROPERTIES",
    "STATE_PROPERTIES",
    "StyleSnapshot",
    "JS_GET_COMPUTED_STYLE",
    "JS_GET_ACCESSIBILITY",
    "build_snapshot",
    "compute_contrast_ratio",
]
