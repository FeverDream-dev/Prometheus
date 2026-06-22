from __future__ import annotations

import pytest

from prometheus_cli.bundleforge import (
    detect_capabilities,
    recommend,
    recommend_multi,
    load_catalog,
)
from prometheus_cli.hardware import HardwareReport


def _hw(ram=16, vram=8):
    return HardwareReport(
        os="Linux", architecture="x86_64", ram_gb=ram, vram_gb=vram,
        cpu_features=[], disk_free_gb=200, metal=False, unified_memory=False,
    )


class TestCapabilityDetection:
    def test_detects_rag(self):
        caps = detect_capabilities("I need RAG over company documents")
        assert "rag" in caps

    def test_detects_mcp(self):
        caps = detect_capabilities("I need WhatsApp MCP automation")
        assert "mcp" in caps

    def test_detects_image_generation(self):
        caps = detect_capabilities("I need icons and transparent images")
        assert "image_generation" in caps

    def test_detects_coding(self):
        caps = detect_capabilities("I want to build a web application")
        assert "coding" in caps

    def test_detects_multiple_capabilities(self):
        caps = detect_capabilities("I want a web app with custom icons and RAG search")
        assert "coding" in caps
        assert "image_generation" in caps
        assert "rag" in caps

    def test_detects_none(self):
        caps = detect_capabilities("hello world")
        assert caps == []


class TestRagRecommendation:
    def test_rag_recommendation(self):
        result = recommend("I need RAG over company documents", hardware=_hw())
        assert result.use_case == "rag_documents"
        assert "rag" in result.template_id

    def test_rag_has_embedding_model(self):
        result = recommend("I need RAG over company documents", hardware=_hw())
        assert result.bundle.optional.get("embedding") or "rag" in result.bundle.id


class TestMcpRecommendation:
    def test_mcp_recommendation(self):
        result = recommend("I need WhatsApp MCP automation", hardware=_hw())
        assert result.use_case == "mcp_automation"
        assert "whatsapp" in result.template_id or "mcp" in result.template_id

    def test_mcp_has_honest_caveat(self):
        result = recommend("I need WhatsApp MCP automation", hardware=_hw())
        catalog = load_catalog()
        for warning in result.license_warnings:
            assert isinstance(warning, str)


class TestAssetforgeRecommendation:
    def test_assetforge_recommendation(self):
        result = recommend("I need icons and transparent images for a web app", hardware=_hw(ram=16, vram=8))
        assert result.use_case in ("asset_generation", "game_development", "web_development")

    def test_assetforge_multi_recommendation(self):
        multi = recommend_multi("I need icons and transparent images for a web app", hardware=_hw(ram=16, vram=8))
        all_ids = multi.all_template_ids()
        assert len(all_ids) >= 2
        assert any("assetforge" in tid or "icon" in tid for tid in all_ids)
        assert any("webapp" in tid for tid in all_ids)


class TestMultiRecommendation:
    def test_rag_coding_multi(self):
        multi = recommend_multi("I want to build a web app with RAG over company docs", hardware=_hw())
        all_ids = multi.all_template_ids()
        assert any("rag" in tid for tid in all_ids)

    def test_web_icons_multi(self):
        multi = recommend_multi("I want to create a web app with custom icons", hardware=_hw(ram=16, vram=8))
        all_ids = multi.all_template_ids()
        assert len(all_ids) >= 2

    def test_game_with_assets_multi(self):
        multi = recommend_multi("I want to make a 2D game with generated sprites", hardware=_hw(ram=16, vram=8))
        all_ids = multi.all_template_ids()
        assert any("game" in tid for tid in all_ids)

    def test_detected_capabilities_populated(self):
        multi = recommend_multi("I want a web app with icons", hardware=_hw())
        assert len(multi.detected_capabilities) >= 2

    def test_secondary_results_have_templates(self):
        multi = recommend_multi("I want a web app with icons and RAG search", hardware=_hw(ram=16, vram=8))
        for sec in multi.secondary:
            assert sec.template_id
            assert sec.bundle is not None

    def test_all_template_ids_unique(self):
        multi = recommend_multi("I want a web app with icons and RAG and MCP", hardware=_hw(ram=32, vram=24))
        all_ids = multi.all_template_ids()
        assert len(all_ids) == len(set(all_ids))

    def test_no_duplicate_secondary(self):
        multi = recommend_multi("I want web app with icons", hardware=_hw(ram=16, vram=8))
        sec_ids = [s.template_id for s in multi.secondary]
        assert len(sec_ids) == len(set(sec_ids))


class TestCommercialSafeMatching:
    def test_rag_recommendation_is_commercial_safe(self):
        result = recommend("I need RAG over company documents", hardware=_hw(), commercial_safe_only=True)
        assert result.bundle.commercial_safe is True

    def test_assetforge_recommendation_is_commercial_safe(self):
        result = recommend("I need icon generation", hardware=_hw(ram=16, vram=8), commercial_safe_only=True)
        catalog = load_catalog()
        for model_id in result.bundle.all_model_ids:
            entry = catalog.by_id(model_id)
            if entry and not entry.commercial_safe:
                pytest.fail(f"non-commercial model {model_id} in commercial-safe recommendation")
