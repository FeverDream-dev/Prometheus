from __future__ import annotations

from prometheus_cli.agent_efficiency import (
    FORGE_TOOL_RETRY_HINT,
    build_controller_system,
    build_seat_contract,
    effective_arena_char_budget,
    narrates_tools_without_calls,
)
from prometheus_cli.caveman import append_to_prompt, build_injected_context, normalize_mode
from prometheus_cli.errors_decode import decode_error, format_decoded
from prometheus_cli.models import Settings


def test_caveman_modes():
    assert "CAVEman" in build_injected_context("lite")
    assert build_injected_context("off") == ""
    assert "TOOL RULE" in build_injected_context("full", forge=True)


def test_build_seat_contract_includes_ponytail_and_caveman():
    s = Settings(ponytail_mode="full", caveman_mode="full")
    out = build_seat_contract("BASE", s, seat="forge")
    assert "BASE" in out
    assert "PONYTAIL" in out
    assert "CAVEman" in out or "TOOL RULE" in out


def test_low_vram_budget():
    s = Settings(active_bundle_id="spark-cpu-8gb")
    assert effective_arena_char_budget(s) == 12_000
    s2 = Settings(active_bundle_id="titan-24gb")
    assert effective_arena_char_budget(s2) == 24_000


def test_narrates_tools_detection():
    assert narrates_tools_without_calls("I will write_file('x')", []) is True
    assert narrates_tools_without_calls("done", [{"tool": "x"}]) is False  # type: ignore[arg-type]


def test_decode_ollama():
    d = decode_error("Error: could not connect to ollama server")
    assert d is not None
    assert d.code == "ollama_down"
    assert "ollama serve" in d.fix


def test_decode_empty_write():
    d = decode_error("SELF-CHECK FAIL: ./site/index.html has only 0 chars")
    assert d is not None
    assert d.code in {"empty_write", "self_check_fail"}


def test_format_decoded():
    d = decode_error("could not connect to ollama")
    assert d is not None
    text = format_decoded(d)
    assert "cause:" in text and "fix:" in text


def test_forge_retry_hint_present():
    assert "calls[]" in FORGE_TOOL_RETRY_HINT


def test_controller_system_combines_efficiency():
    s = Settings()
    out = build_controller_system("SYS", s)
    assert "SYS" in out
