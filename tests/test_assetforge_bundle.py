from __future__ import annotations

import pytest

from prometheus_cli.bundleforge import load_template, validate_template
from prometheus_cli.bundleforge.catalog import load_catalog


class TestAssetforgeBundleExists:
    def test_assetforge_icon_factory_template(self):
        bundle = load_template("assetforge-icon-factory")
        assert bundle.id == "assetforge-icon-factory"
        assert bundle.name

    def test_assetforge_lite_v1_bundle(self):
        from prometheus_cli.resources import get_default_bundles_v1_dir
        d = get_default_bundles_v1_dir()
        files = list(d.glob("assetforge*.yaml"))
        assert len(files) >= 1


class TestAssetforgeCapabilities:
    def test_has_image_generator(self):
        bundle = load_template("assetforge-icon-factory")
        assert "image_generator" in bundle.optional
        assert "flux" in bundle.optional["image_generator"].lower() or "sdxl" in bundle.optional["image_generator"].lower()

    def test_has_background_removal(self):
        bundle = load_template("assetforge-icon-factory")
        assert "background_removal" in bundle.optional

    def test_permissions_allow_assets(self):
        bundle = load_template("assetforge-icon-factory")
        assert bundle.permissions.assets in ("allow", "ask")

    def test_commercial_safe(self):
        bundle = load_template("assetforge-icon-factory")
        assert bundle.commercial_safe is True


class TestAssetforgeValidation:
    def test_template_validates(self):
        result = validate_template("assetforge-icon-factory")
        assert result.passed, f"validation errors: {result.errors}"

    def test_models_in_catalog(self):
        bundle = load_template("assetforge-icon-factory")
        catalog = load_catalog()
        for model_id in bundle.all_model_ids:
            entry = catalog.by_id(model_id)
            assert entry is not None, f"model '{model_id}' not in catalog"


class TestAssetforgeLicenseCompliance:
    def test_flux_is_commercial_safe(self):
        catalog = load_catalog()
        flux = catalog.by_id("black-forest-labs/FLUX.1-schnell")
        assert flux is not None
        assert flux.commercial_safe is True
        assert flux.license == "apache-2.0"

    def test_rembg_is_commercial_safe(self):
        catalog = load_catalog()
        rembg = catalog.by_id("rembg/silueta")
        assert rembg is not None
        assert rembg.commercial_safe is True

    def test_assetforge_bundle_does_not_include_sdxl(self):
        bundle = load_template("assetforge-icon-factory")
        for model_id in bundle.all_model_ids:
            assert "sdxl-turbo" not in model_id, "SDXL Turbo is non-commercial but bundle claims commercial_safe"

    def test_license_notes_present(self):
        bundle = load_template("assetforge-icon-factory")
        assert bundle.license_notes
        assert len(bundle.license_notes) > 10


class TestAssetforgeHardwareRequirements:
    def test_has_vram_requirement(self):
        bundle = load_template("assetforge-icon-factory")
        assert bundle.requirements.min_vram_gb > 0

    def test_has_ram_requirement(self):
        bundle = load_template("assetforge-icon-factory")
        assert bundle.requirements.min_ram_gb >= 8

    def test_has_disk_requirement(self):
        bundle = load_template("assetforge-icon-factory")
        assert bundle.requirements.min_disk_gb >= 10


class TestAssetforgeBundleForgeIntegration:
    def test_recommend_for_icon_request(self):
        from prometheus_cli.bundleforge import recommend
        result = recommend("I need icons and transparent images")
        assert "assetforge" in result.template_id or "icon" in result.template_id

    def test_recommend_for_asset_generation(self):
        from prometheus_cli.bundleforge import recommend
        result = recommend("I want to generate game sprites and art assets")
        assert result.use_case in ("asset_generation", "game_development")
