from __future__ import annotations

import pytest

from prometheus_cli.bundleforge.recommend import recommend, search_bundles
from prometheus_cli.bundleforge.catalog import load_catalog
from prometheus_cli.hardware import HardwareReport


def _hw(ram=32, vram=8):
    return HardwareReport(
        os="Linux", architecture="x86_64", ram_gb=ram, vram_gb=vram,
        cpu_features=[], disk_free_gb=500, metal=False, unified_memory=False,
    )


class TestVideoGameRecommendation:
    def test_game_dev_recommendation(self):
        result = recommend("I want to build a video game with local models and generated sprites", hardware=_hw(ram=16, vram=8))
        assert result.use_case == "game_development"
        assert "game" in result.template_id
        assert any("image" in opt or "generator" in opt for opt in result.bundle.optional) or "game" in result.template_id

    def test_game_dev_with_assetforge_on_quality(self):
        result = recommend(
            "I want to make a 2D game with sprites and assets",
            hardware=_hw(ram=16, vram=8),
            prefer_quality=True,
        )
        assert "game" in result.template_id

    def test_game_dev_matches_keywords(self):
        result = recommend("I want to build a video game with local models and generated sprites", hardware=_hw(ram=16, vram=8))
        assert "game" in result.matched_keywords


class TestWhatsAppMcpRecommendation:
    def test_whatsapp_recommendation(self):
        result = recommend("I want to use MCP to help with WhatsApp messages", hardware=_hw(ram=16))
        assert result.use_case == "mcp_automation"
        assert "whatsapp" in result.template_id or "mcp" in result.template_id

    def test_whatsapp_matches_keywords(self):
        result = recommend("I want to use MCP to help with WhatsApp messages", hardware=_hw(ram=16))
        assert "whatsapp" in result.matched_keywords
        assert "mcp" in result.matched_keywords


class TestRagRecommendation:
    def test_rag_recommendation(self):
        result = recommend("I want a RAG coding assistant for my company docs", hardware=_hw(ram=16))
        assert result.use_case == "rag_documents"
        assert "rag" in result.template_id or "rag" in result.bundle.id

    def test_rag_has_embedding(self):
        result = recommend("I want a RAG coding assistant for my company docs", hardware=_hw(ram=16))
        assert result.bundle.optional.get("embedding") or "rag" in result.bundle.id


class TestCpuOnlyRecommendation:
    def test_cpu_only_recommendation(self):
        result = recommend("I have an old laptop with no GPU, just CPU", hardware=_hw(ram=4, vram=0))
        assert "cpu" in result.template_id or result.bundle.requirements.min_vram_gb == 0

    def test_cpu_fallback_on_low_hardware(self):
        result = recommend("I want to build a video game", hardware=_hw(ram=4, vram=0))
        assert result.bundle.requirements.min_vram_gb == 0 or result.hardware_fit


class TestCommercialSafe:
    def test_commercial_safe_excludes_sdxl(self):
        result = recommend(
            "I want image generation with icons",
            hardware=_hw(ram=16, vram=8),
            commercial_safe_only=True,
        )
        catalog = load_catalog()
        for model_id in result.bundle.all_model_ids:
            entry = catalog.by_id(model_id)
            if entry and entry.id == "stabilityai/sdxl-turbo":
                pytest.fail(f"SDXL Turbo (non-commercial) was included in a commercial_safe bundle")


class TestSearchBundles:
    def test_search_game(self):
        results = search_bundles("game")
        assert len(results) >= 1
        assert any("game" in r["template_id"] for r in results)

    def test_search_rag(self):
        results = search_bundles("rag document")
        assert len(results) >= 1

    def test_search_empty_results(self):
        results = search_bundles("xyzzy_nothing_matches")
        assert len(results) == 0

    def test_search_sorted_by_score(self):
        results = search_bundles("game")
        if len(results) >= 2:
            assert results[0]["score"] >= results[1]["score"]


class TestAllTemplatesRecommendable:
    def test_every_template_can_be_loaded(self):
        from prometheus_cli.bundleforge import list_templates, load_template
        for tid in list_templates():
            bundle = load_template(tid)
            assert bundle.id
            assert len(bundle.roles) >= 1
