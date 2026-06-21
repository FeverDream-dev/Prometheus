from __future__ import annotations

import json
from pathlib import Path

from prometheus_cli.assets.manifest import AssetManifest, KNOWN_LICENSES, can_use_commercially
from prometheus_cli.assets.generator import generate, is_image_gen_enabled, doctor


def test_non_commercial_model_cannot_use_commercially():
    assert can_use_commercially("stabilityai/sdxl-turbo") is False


def test_apache_model_can_use_commercially():
    assert can_use_commercially("black-forest-labs/FLUX.1-schnell") is True


def test_bria_is_marked_non_commercial():
    assert KNOWN_LICENSES["briaai/RMBG-1.4"]["commercial"] == "restricted"


def test_generate_without_image_tests_writes_manifest_only(tmp_path: Path):
    import os
    assert os.environ.get("PROMETHEUS_RUN_IMAGE_TESTS", "") != "1"
    result = generate(name="test-asset", kind="icon", size="512x512",
                      output_dir=tmp_path, model="stabilityai/sdxl-turbo")
    assert result["image_generated"] is False
    assert "skip_reason" in result
    mp = Path(result["manifest_path"])
    assert mp.exists()
    data = json.loads(mp.read_text())
    assert data["name"] == "test-asset"
    assert data["kind"] == "icon"


def test_generate_rejects_invalid_kind(tmp_path: Path):
    result = generate(name="x", kind="invalid", output_dir=tmp_path)
    assert "error" in result
    assert "invalid kind" in result["error"]


def test_generate_rejects_invalid_size(tmp_path: Path):
    result = generate(name="x", kind="icon", size="99x99", output_dir=tmp_path)
    assert "error" in result
    assert "invalid size" in result["error"]


def test_generate_creates_readme(tmp_path: Path):
    result = generate(name="my-icon", kind="icon", output_dir=tmp_path)
    rp = Path(result["readme_path"])
    assert rp.exists()
    content = rp.read_text()
    assert "my-icon" in content


def test_doctor_returns_capabilities():
    info = doctor()
    assert "rembg_available" in info
    assert "diffusers_available" in info
    assert "torch_available" in info
    assert "image_tests_enabled" in info


def test_manifest_with_bria_bg_removal_warns_on_commercial():
    m = AssetManifest(
        name="x", kind="icon", model="stabilityai/sdxl-turbo",
        background_removal_model="briaai/RMBG-1.4",
        commercial_use="allowed",
    )
    assert any("BRIA" in w for w in m.warnings)


def test_image_tests_disabled_by_default():
    assert is_image_gen_enabled() is False
