"""Ollama model pull policy — large downloads require confirmation."""
from __future__ import annotations

from prometheus_cli.pull_policy import (
    LARGE_DOWNLOAD_GB,
    confirm_large_pull,
    estimate_model_download_gb,
    requires_pull_confirmation,
)


def test_large_download_threshold_is_2gb():
    assert LARGE_DOWNLOAD_GB == 2.0


def test_tiny_model_does_not_require_confirmation():
    needs, size, _ = requires_pull_confirmation(["qwen2.5-coder:0.5b"])
    assert needs is False
    assert size < LARGE_DOWNLOAD_GB


def test_large_model_requires_confirmation():
    needs, size, model_id = requires_pull_confirmation(["qwen2.5-coder:7b"])
    assert needs is True
    assert size > LARGE_DOWNLOAD_GB
    assert "qwen2.5-coder" in model_id


def test_confirm_large_pull_blocks_without_yes():
    allowed = confirm_large_pull(
        ["qwen2.5-coder:7b"],
        yes=False,
        confirm_fn=lambda _msg, _default: False,
    )
    assert allowed is False


def test_confirm_large_pull_allows_with_yes():
    allowed = confirm_large_pull(["qwen2.5-coder:7b"], yes=True)
    assert allowed is True


def test_confirm_small_pull_always_allowed():
    allowed = confirm_large_pull(
        ["qwen2.5-coder:0.5b"],
        yes=False,
        confirm_fn=lambda _msg, _default: False,
    )
    assert allowed is True


def test_estimate_uses_catalog_when_available():
    size = estimate_model_download_gb("qwen2.5-coder:0.5b")
    assert 0 < size < 1.0
