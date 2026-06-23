"""Download-size policy for Ollama model pulls.

Models larger than ``LARGE_DOWNLOAD_GB`` require explicit confirmation unless
``--yes`` is passed or the caller is running in non-interactive CI.
"""
from __future__ import annotations

from typing import Callable

from .onboarding import _estimate_download_gb

LARGE_DOWNLOAD_GB = 2.0

ConfirmFn = Callable[[str, bool], bool]


def estimate_model_download_gb(model_id: str) -> float:
    """Best-effort download size in GB for a model tag."""
    try:
        from .bundleforge.catalog import load_catalog

        catalog = load_catalog()
        entry = catalog.by_id(model_id)
        if entry is not None:
            return entry.download_gb
    except Exception:
        pass
    return _estimate_download_gb(model_id)


def largest_download_gb(model_ids: list[str]) -> tuple[float, str]:
    largest = 0.0
    largest_id = ""
    for model_id in model_ids:
        size = estimate_model_download_gb(model_id)
        if size > largest:
            largest = size
            largest_id = model_id
    return largest, largest_id


def requires_pull_confirmation(model_ids: list[str]) -> tuple[bool, float, str]:
    """Return whether any model exceeds the large-download threshold."""
    size, model_id = largest_download_gb(model_ids)
    needs = size > LARGE_DOWNLOAD_GB
    return needs, size, model_id


def confirm_large_pull(
    model_ids: list[str],
    *,
    yes: bool = False,
    confirm_fn: ConfirmFn | None = None,
) -> bool:
    """Return True when the pull may proceed."""
    needs, size, model_id = requires_pull_confirmation(model_ids)
    if not needs:
        return True
    if yes:
        return True
    prompt = (
        f"Pull includes {model_id} (~{size:.1f} GB). "
        f"Downloads over {LARGE_DOWNLOAD_GB:.0f} GB require confirmation. Proceed?"
    )
    if confirm_fn is not None:
        return confirm_fn(prompt, False)
    try:
        from rich.prompt import Confirm

        return Confirm.ask(prompt, default=False)
    except Exception:
        return False


__all__ = [
    "LARGE_DOWNLOAD_GB",
    "confirm_large_pull",
    "estimate_model_download_gb",
    "largest_download_gb",
    "requires_pull_confirmation",
]
