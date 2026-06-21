from __future__ import annotations

import json
from pathlib import Path

from prometheus_cli.assets.manifest import (
    AssetManifest,
    KNOWN_LICENSES,
    VALID_KINDS,
    VALID_SIZES,
    can_use_commercially,
    write_manifest,
)


def test_manifest_basic_fields():
    m = AssetManifest(name="test-icon", kind="icon", model="stabilityai/sdxl-turbo")
    assert m.name == "test-icon"
    assert m.kind == "icon"
    assert m.model == "stabilityai/sdxl-turbo"
    assert m.generated_at != ""


def test_manifest_auto_fills_license_from_model():
    m = AssetManifest(name="x", kind="icon", model="black-forest-labs/FLUX.1-schnell")
    assert m.license_id == "Apache-2.0"
    assert m.commercial_use == "allowed"


def test_manifest_flags_stability_non_commercial():
    m = AssetManifest(name="x", kind="icon", model="stabilityai/sdxl-turbo",
                      commercial_use="allowed")
    assert any("Stability AI" in w for w in m.warnings)


def test_manifest_flags_bria_non_commercial():
    m = AssetManifest(name="x", kind="icon", model="stabilityai/sdxl-turbo",
                      background_removal_model="briaai/RMBG-1.4",
                      commercial_use="allowed")
    assert any("BRIA" in w for w in m.warnings)


def test_valid_kinds_contains_expected():
    assert "icon" in VALID_KINDS
    assert "hero" in VALID_KINDS
    assert "illustration" in VALID_KINDS


def test_valid_sizes_contains_expected():
    assert "512x512" in VALID_SIZES
    assert "1536x864" in VALID_SIZES


def test_write_manifest_creates_files(tmp_path: Path):
    m = AssetManifest(name="my-icon", kind="icon", model="stabilityai/sdxl-turbo",
                      prompt="a blue icon", seed=42, size="512x512")
    mp, rp = write_manifest(tmp_path / "my-icon", m)
    assert mp.exists()
    assert rp.exists()
    data = json.loads(mp.read_text())
    assert data["name"] == "my-icon"
    assert data["seed"] == 42
    readme = rp.read_text()
    assert "my-icon" in readme
    assert "stabilityai/sdxl-turbo" in readme


def test_manifest_roundtrip_from_dict():
    m1 = AssetManifest(name="x", kind="hero", model="black-forest-labs/FLUX.1-schnell", seed=99)
    d = m1.to_dict()
    m2 = AssetManifest.from_dict(d)
    assert m2.name == "x"
    assert m2.seed == 99


def test_can_use_commercially():
    assert can_use_commercially("black-forest-labs/FLUX.1-schnell") is True
    assert can_use_commercially("stabilityai/sdxl-turbo") is False
    assert can_use_commercially("unknown/model") is False


def test_known_licenses_has_all_expected_models():
    expected = {"stabilityai/sdxl-turbo", "black-forest-labs/FLUX.1-schnell",
                "rembg/u2netp", "rembg/silueta", "briaai/RMBG-1.4"}
    assert expected.issubset(set(KNOWN_LICENSES))
