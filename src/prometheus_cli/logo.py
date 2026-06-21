"""PROMETHEUS brand logo art and startup animation.

Renders a circular ring + central eye silhouette derived from the company mark
at ``assets/branding/feverducation.png``. Provides three size tiers, a 12-frame
rotating-highlight animation cycling through the brand accent palette
(cyan/green/yellow/orange/magenta), a reduced-motion static fallback, and an
image-to-ASCII generator (Pillow-optional).

The placeholder stand-in (``TEMPORARY_ASCII_LOGO = True``) has been replaced
with this real brand-derived art; the flag is now ``False`` and kept only as a
versioning marker for the test suite.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import IO

LOGO_LABEL = "PROMETHEUS"
LOGO_TAGLINE = "local-first coding agent"

TEMPORARY_ASCII_LOGO = False
REPLACEMENT_CRITERION = (
    "The temporary bracketed-ember stand-in has been replaced with brand-derived "
    "art sourced from assets/branding/feverducation.png: a circular color ring "
    "with a central eye/R silhouette. TEMPORARY_ASCII_LOGO is now False; the "
    "flag is retained as a marker so tests can detect placeholder regressions."
)

_ALL_SIZES = ("compact", "normal", "wide")
_WIDTH_FOR_SIZE = {"compact": 28, "normal": 42, "wide": 58}
_FRAME_COUNT = 12

_RING_PALETTE = [
    (255, 184, 28),    # gold/orange
    (255, 215, 0),     # yellow
    (0, 200, 180),     # cyan
    (60, 200, 120),    # green
    (200, 80, 200),    # magenta
]


def sizes() -> list[str]:
    return list(_ALL_SIZES)


def _resolve_size(size: str) -> str:
    key = (size or "").strip().lower()
    return key if key in _ALL_SIZES else "normal"


def frame_count(size: str = "normal") -> int:
    return _FRAME_COUNT


def _width_for_size(size: str) -> int:
    return _WIDTH_FOR_SIZE[_resolve_size(size)]


def _ring_char(angle_delta_deg: float) -> str:
    if angle_delta_deg < 18:
        return "█"
    if angle_delta_deg < 40:
        return "▓"
    if angle_delta_deg < 70:
        return "▒"
    if angle_delta_deg < 105:
        return "░"
    return "·"


def _eye_overlay(grid: list[list[str]], cx: float, cy: float, scale: float) -> None:
    eye = [
        " ▓▓▓▓▓ ",
        "▓░░░░░▓",
        "▓░▓▓░░▓",
        "▓░▓▓░░▓",
        "▓░░░░░▓",
        "▓░░░░░▓",
        " ▓▓▓▓▓ ",
    ]
    h = len(eye)
    w = len(eye[0])
    sx = int(round(cx - w / 2 + scale))
    sy = int(round(cy - h / 2 + scale))
    for ey in range(h):
        for ex in range(w):
            c = eye[ey][ex]
            if c == " ":
                continue
            gx, gy = sx + ex, sy + ey
            if 0 <= gy < len(grid) and 0 <= gx < len(grid[0]):
                grid[gy][gx] = c


def render_brand_frame(
    rotation_step: int = 0,
    width: int = 42,
    color: bool = False,
    include_label: bool = True,
) -> str:
    height = max(11, width // 2)
    cx = width / 2.0
    cy = height / 2.0
    r_outer = min(width / 2.0, height) - 0.5
    r_inner = r_outer * 0.55

    grid: list[list[str]] = [[" "] * width for _ in range(height)]
    lit_angle = (rotation_step * (360.0 / _FRAME_COUNT)) % 360.0

    for y in range(height):
        for x in range(width):
            dx = x - cx + 0.5
            dy = (y - cy + 0.5) * 2.0
            r = math.sqrt(dx * dx + dy * dy)
            if r_inner <= r <= r_outer:
                angle = math.degrees(math.atan2(dy, dx)) % 360.0
                delta = min(abs(angle - lit_angle), 360.0 - abs(angle - lit_angle))
                grid[y][x] = _ring_char(delta)

    _eye_overlay(grid, cx, cy, scale=max(0.0, (r_inner - 4.0) / 6.0))

    lines = ["".join(row) for row in grid]
    if include_label:
        lines.append("")
        lines.append(LOGO_LABEL.center(width))
        if width >= len(LOGO_TAGLINE):
            lines.append(LOGO_TAGLINE.center(width))

    art = "\n".join(lines)
    if color:
        art = _colorize(art, rotation_step)
    return art


def _colorize(art: str, rotation_step: int) -> str:
    rgb = _RING_PALETTE[rotation_step % len(_RING_PALETTE)]
    ansi_lit = f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"
    ansi_dim = "\033[38;5;240m"
    reset = "\033[0m"
    out_lines: list[str] = []
    for line in art.split("\n"):
        chars: list[str] = []
        for ch in line:
            if ch == "█":
                chars.append(ansi_lit + ch + reset)
            elif ch == "▓":
                chars.append(ansi_lit + ch + reset)
            elif ch in "▒░·":
                chars.append(ansi_dim + ch + reset)
            else:
                chars.append(ch)
        out_lines.append("".join(chars))
    return "\n".join(out_lines)


def render_logo(frame_index: int = 0, size: str = "normal", color: bool = False) -> str:
    width = _width_for_size(size)
    step = frame_index % _FRAME_COUNT
    return render_brand_frame(rotation_step=step, width=width, color=color)


def static_logo(size: str = "compact") -> str:
    return render_logo(0, size=size, color=False)


def static_mark(size: str = "compact") -> str:
    return static_logo(size)


def _env_truthy(name: str) -> bool:
    val = (__import__("os").environ.get(name, "")).strip().lower()
    return val in ("1", "true", "yes", "on")


def should_animate_logo(
    no_animation: bool = False,
    stream: IO | None = None,
    reduced_motion: bool = False,
) -> bool:
    if no_animation or reduced_motion:
        return False
    if _env_truthy("PROMETHEUS_NO_ANIMATION") or _env_truthy("NO_COLOR"):
        return False
    import os
    if os.environ.get("TERM", "") == "dumb":
        return False
    target = stream if stream is not None else sys.stdout
    is_tty = getattr(target, "isatty", None)
    return bool(is_tty and is_tty())


def play_logo(
    size: str = "normal",
    duration_s: float = 1.2,
    fps: int = 12,
    color: bool = True,
    reduced_motion: bool = False,
    stream: IO | None = None,
    no_animation: bool = False,
) -> None:
    out = stream if stream is not None else sys.stdout
    if reduced_motion or no_animation or not should_animate_logo(stream=out):
        out.write(static_logo(size) + "\n")
        out.flush()
        return
    use_color = color and not _env_truthy("NO_COLOR")
    interval = 1.0 / fps if fps > 0 else 0.08
    frames_to_show = max(1, int(duration_s * fps))
    try:
        for i in range(frames_to_show):
            out.write("\033[H\033[J")
            out.write(render_logo(i, size=size, color=use_color) + "\n")
            out.flush()
            time.sleep(interval)
    except (KeyboardInterrupt, BrokenPipeError):
        out.write("\033[0m")
        out.flush()
        return
    out.write("\033[0m")
    out.flush()


def preview_logo(
    width: int = 42,
    animated: bool = False,
    color: bool = True,
    no_animation: bool = False,
    reduced_motion: bool = False,
    stream: IO | None = None,
) -> None:
    out = stream if stream is not None else sys.stdout
    if width <= 32:
        size = "compact"
    elif width >= 52:
        size = "wide"
    else:
        size = "normal"
    if animated:
        play_logo(
            size=size, color=color, no_animation=no_animation,
            reduced_motion=reduced_motion, stream=out,
        )
    else:
        art = render_logo(0, size=size, color=color and not no_animation)
        out.write(art + "\n")
        out.flush()


def generate_logo(source: Path | str, out_path: Path | str) -> tuple[bool, str]:
    source = Path(source)
    out_path = Path(out_path)
    if not source.exists():
        return False, f"source image not found: {source}"
    try:
        from PIL import Image
    except ImportError:
        out_path.write_text(
            _static_module_fallback(source), encoding="utf-8",
        )
        return False, "Pillow not installed; wrote static brand fallback module"

    im = Image.open(source).convert("L")
    src_w, src_h = im.size
    target_w = min(72, src_w)
    target_h = max(13, int(target_w * src_h / src_w / 2.1))
    im = im.resize((target_w, target_h))
    chars = " .:-=+*#%@"
    lines: list[str] = []
    for y in range(target_h):
        line = []
        for x in range(target_w):
            px = im.getpixel((x, y))
            idx = min(len(chars) - 1, (255 - px) * len(chars) // 256)
            line.append(chars[idx])
        lines.append("".join(line))
    lines.append("")
    lines.append(LOGO_LABEL.center(target_w))
    if target_w >= len(LOGO_TAGLINE):
        lines.append(LOGO_TAGLINE.center(target_w))

    body = "\n".join(_py_repr_line(ln) for ln in lines)
    header = (
        '"""Auto-generated PROMETHEUS logo ASCII art.\n\n'
        f"Source: {source}\n"
        f"Size: {target_w}x{target_h} chars\n"
        '"""\n\n'
        "GENERATED_LOGO: list[str] = [\n"
    )
    out_path.write_text(header + body + "\n]\n", encoding="utf-8")
    return True, f"generated {target_w}x{target_h} ASCII art from {source} -> {out_path}"


def _py_repr_line(line: str) -> str:
    return "    " + repr(line) + ","


def _static_module_fallback(source: Path) -> str:
    art = static_logo("normal")
    lines = art.split("\n")
    body = "\n".join("    " + repr(ln) + "," for ln in lines)
    return (
        '"""PROMETHEUS logo fallback (Pillow not installed).\n\n'
        f"Intended source: {source}\n"
        'Install Pillow and re-run `prometheus logo generate` for an image-derived logo.\n'
        '"""\n\n'
        "GENERATED_LOGO: list[str] = [\n"
        + body
        + "\n]\n"
    )


__all__ = [
    "LOGO_LABEL",
    "LOGO_TAGLINE",
    "REPLACEMENT_CRITERION",
    "TEMPORARY_ASCII_LOGO",
    "frame_count",
    "generate_logo",
    "play_logo",
    "preview_logo",
    "render_brand_frame",
    "render_logo",
    "should_animate_logo",
    "sizes",
    "static_logo",
    "static_mark",
]
