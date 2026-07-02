"""Combine Ponytail + Caveman + Cavecrew + low-VRAM budgets."""

from __future__ import annotations

from .cavecrew import compress_tool_results
from .caveman import append_to_prompt as append_caveman
from .models import Settings
from .ponytail import append_to_prompt as append_ponytail

LOW_VRAM_BUNDLE_IDS = frozenset({
    "spark-cpu-8gb", "spark-cpu", "ember-8gb-gpu", "ember-8gb",
    "assetforge-lite-8gb",
})

FORGE_TOOL_RETRY_HINT = (
    "RETRY REQUIRED: Your last turn had NO calls[] but described tools in message. "
    "Return valid AgentTurn JSON with write_file in calls[]. "
    "Put full file content in arguments.content — not in message."
)


def build_seat_contract(base: str, settings: Settings, *, seat: str = "forge") -> str:
    is_forge = seat == "forge"
    out = append_ponytail(base, settings.ponytail_mode) if is_forge else base
    out = append_caveman(out, settings.caveman_mode, forge=is_forge)
    return out


def build_controller_system(base: str, settings: Settings) -> str:
    out = append_ponytail(base, settings.ponytail_mode)
    out = append_caveman(out, settings.caveman_mode, forge=True)
    return out


def effective_arena_char_budget(settings: Settings) -> int:
    if settings.arena_char_budget > 0:
        return settings.arena_char_budget
    bundle = (settings.active_bundle_id or "").lower()
    if any(b in bundle for b in LOW_VRAM_BUNDLE_IDS):
        return 12_000
    return 24_000


def narrates_tools_without_calls(message: str, calls: list) -> bool:
    if calls:
        return False
    msg = (message or "").lower()
    return any(tok in msg for tok in ("write_file", "run_command", "read_file", "git_checkpoint"))


def compress_results(results: list[dict], settings: Settings) -> list[dict]:
    return compress_tool_results(results, mode=settings.cavecrew_mode)


__all__ = [
    "FORGE_TOOL_RETRY_HINT",
    "LOW_VRAM_BUNDLE_IDS",
    "build_controller_system",
    "build_seat_contract",
    "compress_results",
    "effective_arena_char_budget",
    "narrates_tools_without_calls",
]
