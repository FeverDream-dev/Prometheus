from __future__ import annotations


from prometheus_cli.models import Settings
from prometheus_cli.ponytail import (
    DEFAULT_MODE,
    append_to_prompt,
    build_injected_context,
    normalize_mode,
    system_prompt_with_ponytail,
)


def test_normalize_mode_defaults():
    assert normalize_mode(None) == DEFAULT_MODE
    assert normalize_mode("FULL") == "full"
    assert normalize_mode("bogus") == DEFAULT_MODE


def test_off_mode_injects_nothing():
    assert build_injected_context("off") == ""


def test_full_mode_injects_ladder():
    ctx = build_injected_context("full")
    assert "PONYTAIL" in ctx
    assert "YAGNI" in ctx or "stdlib" in ctx.lower()


def test_lite_and_ultra_distinct():
    lite = build_injected_context("lite")
    ultra = build_injected_context("ultra")
    assert lite != ultra
    assert "lite" in lite.lower()
    assert "ultra" in ultra.lower()


def test_append_to_prompt_preserves_base():
    base = "You are a controller."
    out = append_to_prompt(base, "full")
    assert out.startswith(base)
    assert "PONYTAIL" in out


def test_system_prompt_with_ponytail_respects_settings():
    settings = Settings(ponytail_mode="off")
    out = system_prompt_with_ponytail("BASE", settings.ponytail_mode)
    assert out == "BASE"


def test_orchestrator_settings_field():
    s = Settings()
    assert s.ponytail_mode == "full"
