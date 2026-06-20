from __future__ import annotations

from prometheus_cli.bundles import find_bundle, load_registry
from prometheus_cli.model_aliases import MODEL_ALIASES, is_alias, resolve_alias


def test_q2_and_q4_bundles_load():
    registry = load_registry()
    q2 = find_bundle("vibethinker-sandbox-q2", registry)
    q4 = find_bundle("vibethinker-sandbox-q4", registry)
    assert q2 is not None and q4 is not None
    assert q2.experimental is True and q4.experimental is True


def test_q2_controller_is_vibethinker_q2_k_and_not_tool_capable():
    q2 = find_bundle("vibethinker-sandbox-q2")
    spec = q2.controller_spec()
    assert spec.model == "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K"
    assert spec.tool_capable is False


def test_q4_controller_is_q4_k_m():
    q4 = find_bundle("vibethinker-sandbox-q4")
    assert q4.controller_spec().model == "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q4_K_M"


def test_aliases_resolve_to_gguf_tags():
    assert resolve_alias("vibethinker-q2") == "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K"
    assert resolve_alias("vibethinker-q4") == "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q4_K_M"
    assert resolve_alias("granite4.1:3b") == "granite4.1:3b"


def test_is_alias_and_passthrough():
    assert is_alias("vibethinker-q2") is True
    assert is_alias("vibethinker-q4-m") is True
    assert is_alias("not-an-alias") is False
    assert len(MODEL_ALIASES) >= 2


def test_q2_keep_alive_zero_for_sequential_loading():
    q2 = find_bundle("vibethinker-sandbox-q2")
    assert q2.roles["controller"].keep_alive == 0
    assert q2.runtime.maximum_loaded_models == 1
