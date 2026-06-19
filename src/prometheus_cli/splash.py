from __future__ import annotations

import os
import sys
import time
from typing import IO

from .splash_frames import FRAMES

_LABEL = "PROMETHEUS"
_ANSI = {
    " ": "",
    "·": "\033[2;37m",
    "░": "\033[38;5;130m",
    "▒": "\033[38;5;166m",
    "▓": "\033[38;5;202m",
    "█": "\033[38;5;214m",
}
_RESET = "\033[0m"
_ALL_SIZES = ("compact", "normal", "wide")


def sizes() -> list[str]:
    return list(_ALL_SIZES)


def _resolve_size(size: str) -> str:
    key = size.strip().lower()
    for cand in _ALL_SIZES:
        if cand == key:
            return cand
    return "normal"


def frame_count(size: str = "normal") -> int:
    return len(FRAMES[_resolve_size(size)])


def _colorize(line: str) -> str:
    out: list[str] = []
    prev = ""
    for ch in line:
        code = _ANSI.get(ch, "")
        if code != prev:
            if prev:
                out.append(_RESET)
            if code:
                out.append(code)
            prev = code
        out.append(ch if ch != " " else " ")
    if prev:
        out.append(_RESET)
    return "".join(out)


def _art(frame_index: int, size: str = "normal", color: bool = False) -> list[str]:
    frames = FRAMES[_resolve_size(size)]
    idx = frame_index % len(frames)
    frame = frames[idx]
    if color:
        return [_colorize(line) for line in frame]
    return list(frame)


def _centered(lines: list[str], width: int) -> list[str]:
    return [line.center(width) for line in lines]


def render_frame(frame_index: int, size: str = "normal", color: bool = False) -> str:
    size = _resolve_size(size)
    art = _art(frame_index, size, color=color)
    width = max(len(line) for line in art) if art else 0
    label_width = len(_LABEL)
    total_width = max(width, label_width)
    lines = _centered(art, total_width)
    lines.append("")
    lines.append(_LABEL.center(total_width))
    return "\n".join(lines)


def static_mark(size: str = "compact") -> str:
    return render_frame(0, size=size, color=False)


def _env_truthy(name: str) -> bool:
    val = os.environ.get(name, "").strip().lower()
    return val in ("1", "true", "yes", "on")


def should_animate(
    no_animation: bool = False,
    stream: IO | None = None,
    reduced_motion: bool = False,
) -> bool:
    if no_animation or reduced_motion:
        return False
    if _env_truthy("PROMETHEUS_NO_ANIMATION") or _env_truthy("NO_COLOR"):
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    target = stream if stream is not None else sys.stdout
    is_tty = getattr(target, "isatty", None)
    return bool(is_tty and is_tty())


def _terminal_width(default: int = 80) -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return default


def pick_size_for_terminal(width: int | None = None) -> str:
    w = width if width is not None else _terminal_width()
    if w >= 60:
        return "wide"
    if w >= 36:
        return "normal"
    return "compact"


def play(
    size: str = "normal",
    duration_s: float = 1.6,
    fps: int = 12,
    color: bool = True,
    reduced_motion: bool = False,
    stream: IO | None = None,
    no_animation: bool = False,
) -> None:
    out = stream if stream is not None else sys.stdout
    size = _resolve_size(size)
    animate = should_animate(
        no_animation=no_animation, stream=out, reduced_motion=reduced_motion
    )
    if not animate:
        if getattr(out, "isatty", lambda: False)() or stream is not None:
            out.write(static_mark(size) + "\n")
            out.flush()
        return
    use_color = color and not _env_truthy("NO_COLOR")
    interval = 1.0 / fps if fps > 0 else 0.08
    frames_to_show = max(1, int(duration_s * fps))
    try:
        for i in range(frames_to_show):
            block = render_frame(i, size=size, color=use_color)
            out.write("\033[H\033[J")
            out.write(block + "\n")
            out.flush()
            time.sleep(interval)
    except (KeyboardInterrupt, BrokenPipeError):
        out.write(_RESET)
        out.flush()
        return
    out.write(_RESET)
    out.flush()


__all__ = [
    "frame_count",
    "pick_size_for_terminal",
    "play",
    "render_frame",
    "should_animate",
    "sizes",
    "static_mark",
]
