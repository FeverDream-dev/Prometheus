from __future__ import annotations

import pytest

from prometheus_cli.bundleforge.catalog import ModelCatalog, ModelEntry, load_catalog


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


class TestCatalogLoads:
    def test_catalog_has_models(self, catalog):
        assert len(catalog.models) >= 15

    def test_catalog_version_is_set(self, catalog):
        assert catalog.catalog_version >= 1

    def test_every_entry_has_required_fields(self, catalog):
        for m in catalog.models:
            assert m.id
            assert m.provider
            assert m.min_ram_gb >= 0
            assert m.min_vram_gb >= 0
            assert m.approx_download_size_mb >= 0


class TestRequiredModelFamilies:
    def test_has_small_coding_models(self, catalog):
        ids = set(catalog.all_ids())
        assert "qwen2.5-coder:0.5b" in ids
        assert "qwen2.5-coder:7b" in ids

    def test_has_granite_code(self, catalog):
        ids = set(catalog.all_ids())
        assert "granite-code:3b" in ids
        assert "granite-code:8b" in ids

    def test_has_vibethinker(self, catalog):
        ids = set(catalog.all_ids())
        assert any("VibeThinker" in i for i in ids)

    def test_has_general_models(self, catalog):
        ids = set(catalog.all_ids())
        assert any("gemma3n" in i for i in ids)
        assert "llama3.2:3b" in ids

    def test_has_stronger_coding(self, catalog):
        ids = set(catalog.all_ids())
        assert "deepseek-coder-v2:16b" in ids
        assert "devstral:24b" in ids

    def test_has_embedding_models(self, catalog):
        ids = set(catalog.all_ids())
        assert "nomic-embed-text" in ids
        assert "mxbai-embed-large" in ids

    def test_has_image_models(self, catalog):
        ids = set(catalog.all_ids())
        assert "stabilityai/sdxl-turbo" in ids
        assert "black-forest-labs/FLUX.1-schnell" in ids

    def test_has_rembg(self, catalog):
        ids = set(catalog.all_ids())
        assert "rembg/u2netp" in ids
        assert "rembg/silueta" in ids


class TestCatalogQueries:
    def test_by_id(self, catalog):
        m = catalog.by_id("nomic-embed-text")
        assert m is not None
        assert m.id == "nomic-embed-text"

    def test_by_id_returns_none_for_unknown(self, catalog):
        assert catalog.by_id("nonexistent-model") is None

    def test_by_role(self, catalog):
        embeddings = catalog.by_role("embedding")
        assert len(embeddings) >= 2
        for m in embeddings:
            assert "embedding" in m.roles

    def test_by_strength(self, catalog):
        coders = catalog.by_strength("code")
        assert len(coders) >= 5

    def test_fits_hardware(self, catalog):
        fits = catalog.fits_hardware(ram_gb=8, vram_gb=0)
        for m in fits:
            assert m.min_ram_gb <= 8
            assert m.min_vram_gb <= 0

    def test_recommend_for_role_prefers_smaller_by_default(self, catalog):
        m = catalog.recommend_for_role("builder", ram_gb=32, vram_gb=12, prefer_quality=False)
        assert m is not None
        assert m.min_vram_gb <= 12

    def test_recommend_for_role_prefers_larger_for_quality(self, catalog):
        m = catalog.recommend_for_role("builder", ram_gb=32, vram_gb=24, prefer_quality=True)
        assert m is not None


class TestCommercialSafety:
    def test_sdxl_turbo_is_non_commercial(self, catalog):
        m = catalog.by_id("stabilityai/sdxl-turbo")
        assert m is not None
        assert m.commercial_safe is False

    def test_flux_schnell_is_commercial(self, catalog):
        m = catalog.by_id("black-forest-labs/FLUX.1-schnell")
        assert m is not None
        assert m.commercial_safe is True

    def test_commercial_safe_ids_excludes_non_commercial(self, catalog):
        safe = set(catalog.commercial_safe_ids())
        assert "stabilityai/sdxl-turbo" not in safe
        assert "black-forest-labs/FLUX.1-schnell" in safe


class TestNoWeights:
    def test_catalog_has_no_weight_entries(self, catalog):
        for m in catalog.models:
            assert ".gguf" not in m.id or "hf.co/" in m.id
            assert ".bin" not in m.id
            assert ".safetensors" not in m.id
