from __future__ import annotations

from typing import IO

from .splash import (
    frame_count,
    pick_size_for_terminal,
    play as _play,
    render_frame as _render_frame,
    should_animate as _should_animate,
    sizes,
    static_mark as _static_mark,
)

TEMPORARY_ASCII_LOGO = True
LOGO_LABEL = "PROMETHEUS"
REPLACEMENT_CRITERION = (
    "The official company-logo image has not been supplied. This fire-themed "
    "bracketed-ember art is the temporary stand-in. Replace TEMPORARY_ASCII_LOGO "
    "with the real frames (via tools/generate_splash.py against the supplied "
    "image) and flip this flag to False once rights are confirmed."
)


def render_logo(frame_index: int = 0, size: str = "normal", color: bool = False) -> str:
    return _render_frame(frame_index, size=size, color=color)


def static_logo(size: str = "compact") -> str:
    return _static_mark(size=size)


def should_animate_logo(no_animation: bool = False, stream: IO | None = None) -> bool:
    return _should_animate(no_animation=no_animation, stream=stream)


def play_logo(
    size: str = "normal",
    duration_s: float = 1.6,
    fps: int = 12,
    color: bool = True,
    reduced_motion: bool = False,
    stream: IO | None = None,
    no_animation: bool = False,
) -> None:
    _play(
        size=size, duration_s=duration_s, fps=fps, color=color,
        reduced_motion=reduced_motion, stream=stream, no_animation=no_animation,
    )


__all__ = [
    "LOGO_LABEL",
    "REPLACEMENT_CRITERION",
    "TEMPORARY_ASCII_LOGO",
    "frame_count",
    "pick_size_for_terminal",
    "play_logo",
    "render_logo",
    "should_animate_logo",
    "sizes",
    "static_logo",
]
