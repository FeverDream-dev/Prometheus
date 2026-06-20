from __future__ import annotations

import pytest
import yaml

from prometheus_cli.bundles import (
    BUILT_IN_DIR,
    classify_bundle,
    classify_registry,
    hardware_fits,
    load_bundle,
    load_registry,
)
from prometheus_cli.hardware import HardwareReport


def _hw(ram=32, vram=0, disk=200, metal=False, unified=False) -> HardwareReport:
    return HardwareReport(
        os="Linux", architecture="x86_64", ram_gb=ram, vram_gb=vram,
        cpu_features=[], disk_free_gb=disk, metal=metal, unified_memory=unified,
    )


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def test_registry_loads_all_built_in_bundles(registry):
    ids = {b.id for b in registry}
    assert ids == {
        "spark-cpu-8gb", "ember-8gb-gpu", "forge-12gb", "oracle-gemma4-12gb",
        "titan-24gb", "hephaestus-code-24gb", "vibethinker-review-addon",
        "cloud-hybrid", "vibethinker-sandbox-q2", "vibethinker-sandbox-q4",
    }


def test_every_bundle_has_required_license(registry):
    for b in registry:
        assert b.licenses, f"{b.id} has no licenses"


def test_vibethinker_is_add_on_without_controller(registry):
    vt = next(b for b in registry if b.id == "vibethinker-review-addon")
    assert vt.is_add_on is True
    with pytest.raises(ValueError):
        vt.controller_spec()


def test_vibethinker_reviewer_cannot_call_tools(registry):
    vt = next(b for b in registry if b.id == "vibethinker-review-addon")
    reviewer = vt.for_role("reviewer")
    assert reviewer.tool_capable is False


def test_controller_adapter_is_tool_capable(registry):
    forge = next(b for b in registry if b.id == "forge-12gb")
    ctrl = forge.controller_spec()
    assert ctrl.role == "controller"
    assert ctrl.tool_capable is True
    assert ctrl.model == "qwen3.5:9b"


def test_to_v1_bundle_roundtrip(registry):
    forge = next(b for b in registry if b.id == "forge-12gb")
    v1 = forge.to_v1_bundle()
    assert v1.name == "forge-12gb"
    assert any(m.role == "controller" for m in v1.models)
    assert v1.for_role("controller").model == "qwen3.5:9b"


def test_hardware_fits_low_ram():
    b = next(b for b in load_registry() if b.id == "titan-24gb")
    fits, reasons = hardware_fits(b, _hw(ram=8, vram=24, disk=500))
    assert fits is False
    assert any("RAM" in r for r in reasons)


def test_hardware_fits_apple_silicon_unified_memory():
    b = next(b for b in load_registry() if b.id == "ember-8gb-gpu")
    fits, _ = hardware_fits(b, _hw(ram=16, vram=0, metal=True, unified=True))
    assert fits is True


def test_classify_recommends_cpu_bundle_on_cpu_host(registry):
    classified = classify_registry(registry, _hw(ram=8, vram=0, disk=200))
    rec = [c for c in classified if c.status == "recommended"]
    assert len(rec) == 1
    assert rec[0].id == "spark-cpu-8gb"


def test_classify_recommends_non_experimental_on_24gb_gpu(registry):
    classified = classify_registry(registry, _hw(ram=64, vram=24, disk=500))
    rec = [c for c in classified if c.status == "recommended"]
    assert len(rec) == 1
    assert rec[0].bundle.experimental is False
    by_id = {c.bundle.id: c for c in classified}
    assert by_id["titan-24gb"].status == "experimental"
    assert by_id["hephaestus-code-24gb"].status == "experimental"


def test_classify_installed_when_all_roles_present(registry):
    forge = next(b for b in registry if b.id == "forge-12gb")
    installed = ["qwen3.5:9b", "granite4.1:3b", "qwen3-embedding:0.6b"]
    c = classify_bundle(forge, _hw(ram=32, vram=12, disk=300), installed_models=installed)
    assert c.status == "installed"


def test_classify_incompatible_on_low_vram(registry):
    ember = next(b for b in registry if b.id == "ember-8gb-gpu")
    c = classify_bundle(ember, _hw(ram=16, vram=2, disk=200))
    assert c.status == "incompatible"
    assert c.fits_hardware is False


def test_classify_skips_addons_for_recommended(registry):
    classified = classify_registry(registry, _hw(ram=8, vram=0, disk=200))
    rec = [c for c in classified if c.status == "recommended"]
    assert all(not c.bundle.is_add_on for c in rec)


def test_load_rejects_unknown_top_level_field(tmp_path):
    bad = tmp_path / "bad.yaml"
    data = yaml.safe_load((BUILT_IN_DIR / "01-spark-cpu-8gb.yaml").read_text())
    data["hidden_shell_hook"] = "rm -rf /"
    bad.write_text(yaml.safe_dump(data))
    with pytest.raises(Exception):
        load_bundle(bad)


def test_load_rejects_missing_license(tmp_path):
    data = yaml.safe_load((BUILT_IN_DIR / "01-spark-cpu-8gb.yaml").read_text())
    data["licenses"] = data["licenses"][:1]
    controller_model = data["roles"]["controller"]["model"]
    data["licenses"] = [lic for lic in data["licenses"] if lic["model"] != controller_model]
    bad = tmp_path / "nolicense.yaml"
    bad.write_text(yaml.safe_dump(data))
    with pytest.raises(Exception):
        load_bundle(bad)


def test_load_rejects_unsafe_model_id(tmp_path):
    data = yaml.safe_load((BUILT_IN_DIR / "01-spark-cpu-8gb.yaml").read_text())
    data["roles"]["controller"]["model"] = "../../etc/passwd"
    data["licenses"].append({"model": "../../etc/passwd", "license": "x", "source": "https://x"})
    bad = tmp_path / "unsafe.yaml"
    bad.write_text(yaml.safe_dump(data))
    with pytest.raises(Exception):
        load_bundle(bad)


def test_load_rejects_license_non_https_source(tmp_path):
    data = yaml.safe_load((BUILT_IN_DIR / "01-spark-cpu-8gb.yaml").read_text())
    data["licenses"][0]["source"] = "http://insecure.example"
    bad = tmp_path / "insecure.yaml"
    bad.write_text(yaml.safe_dump(data))
    with pytest.raises(Exception):
        load_bundle(bad)


def test_total_download_gb(registry):
    forge = next(b for b in registry if b.id == "forge-12gb")
    assert forge.total_download_gb() == pytest.approx(6.6 + 2.1 + 0.7, rel=0.05)


def test_quota_free_local_sessions_default_true(registry):
    for b in registry:
        assert b.runtime.unlimited_local_sessions is True


def test_v2_built_in_dir_exists():
    assert BUILT_IN_DIR.is_dir()
    assert len(list(BUILT_IN_DIR.glob("*.yaml"))) >= 8


def test_cloud_hybrid_is_experimental_and_local_first(registry):
    ch = next(b for b in registry if b.id == "cloud-hybrid")
    assert ch.experimental is True
    assert ch.runtime.provider == "ollama"
    assert ch.runtime.unlimited_local_sessions is True
    assert "cloud" in ch.description.lower()


def test_bundles_inspect_cli_runs():
    from typer.testing import CliRunner

    from prometheus_cli.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["bundles", "inspect", "cloud-hybrid"])
    assert result.exit_code == 0, result.stdout
    assert "cloud-hybrid" in result.stdout
    assert "experimental: True" in result.stdout


def test_bundles_list_subcommand_runs():
    from typer.testing import CliRunner

    from prometheus_cli.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["bundles", "list", "--json"])
    assert result.exit_code == 0, result.stdout
    assert "cloud-hybrid" in result.stdout
