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


def test_v1_path_bundle_files_exist_and_load():
    """The user-facing command path config/bundles/vibethinker-sandbox-q2.yaml
    must resolve (not just the bundles-v2/ path)."""
    from pathlib import Path
    from prometheus_cli.bundles import load_bundle

    repo = Path(__file__).resolve().parent.parent
    q2 = repo / "config" / "bundles" / "vibethinker-sandbox-q2.yaml"
    q4 = repo / "config" / "bundles" / "vibethinker-sandbox-q4.yaml"
    assert q2.exists(), f"{q2} must exist for the documented sandbox command"
    assert q4.exists(), f"{q4} must exist"
    b2 = load_bundle(q2)
    b4 = load_bundle(q4)
    assert b2.controller_spec().model == "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K"
    assert b4.controller_spec().model == "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q4_K_M"


def test_v1_and_v2_path_bundles_match():
    from pathlib import Path
    from prometheus_cli.bundles import load_bundle

    repo = Path(__file__).resolve().parent.parent
    v1 = load_bundle(repo / "config" / "bundles" / "vibethinker-sandbox-q2.yaml")
    v2 = load_bundle(repo / "config" / "bundles-v2" / "09-vibethinker-sandbox-q2.yaml")
    assert v1.id == v2.id
    assert v1.controller_spec().model == v2.controller_spec().model


def test_pages_installer_files_exist_and_valid():
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    sh = repo / "website" / "install.sh"
    ps1 = repo / "website" / "install.ps1"
    assert sh.exists() and ps1.exists(), "Pages-served installers must exist in website/"
    assert b"FeverDream-dev/Prometheus" in sh.read_bytes()
    assert b"prometheus/local-agent" not in sh.read_bytes()
    assert b"prometheus/local-agent" not in ps1.read_bytes()
