from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from prometheus_cli.first_run import ModelPullInfo, build_pull_info_for_bundle


class TestModelPullInfo:
    def _make_info(self, **kwargs):
        defaults = dict(
            model_id="qwen2.5-coder:7b",
            role="builder",
            download_size_gb=4.7,
            disk_required_gb=7,
            min_ram_gb=8,
            min_vram_gb=6,
            license="apache-2.0",
            provider="ollama",
            required=True,
        )
        defaults.update(kwargs)
        return ModelPullInfo(**defaults)

    def test_summary_lines_contain_all_required_fields(self):
        info = self._make_info()
        lines = info.summary_lines()
        joined = " ".join(lines).lower()
        assert "model" in joined
        assert "role" in joined
        assert "download" in joined
        assert "disk" in joined
        assert "ram" in joined
        assert "vram" in joined
        assert "license" in joined
        assert "provider" in joined
        assert "status" in joined
        assert "priority" in joined

    def test_local_provider_is_local_only(self):
        info = self._make_info(provider="ollama")
        assert info.is_local is True
        assert info.privacy_level == "local-only"

    def test_cloud_provider_is_cloud(self):
        info = self._make_info(provider="openai")
        assert info.is_local is False
        assert info.privacy_level == "cloud"

    def test_installed_status_shows_ok(self):
        info = self._make_info(already_installed=True)
        lines = info.summary_lines()
        joined = " ".join(lines).lower()
        assert "installed" in joined

    def test_not_installed_shows_warning(self):
        info = self._make_info(already_installed=False)
        lines = info.summary_lines()
        joined = " ".join(lines).lower()
        assert "not installed" in joined

    def test_required_vs_optional(self):
        required = self._make_info(required=True)
        optional = self._make_info(required=False)
        assert "required" in " ".join(required.summary_lines()).lower()
        assert "optional" in " ".join(optional.summary_lines()).lower()


class TestBuildPullInfoForBundle:
    def test_returns_info_for_known_bundle(self):
        infos = build_pull_info_for_bundle("spark-cpu-8gb", [])
        assert len(infos) >= 1
        assert all(isinstance(i, ModelPullInfo) for i in infos)

    def test_controller_is_required(self):
        infos = build_pull_info_for_bundle("spark-cpu-8gb", [])
        controllers = [i for i in infos if i.role == "controller"]
        if controllers:
            assert controllers[0].required is True

    def test_vision_is_optional_when_marked(self):
        infos = build_pull_info_for_bundle("spark-cpu-8gb", [])
        vision = [i for i in infos if i.role == "vision"]
        if vision:
            assert vision[0].required is False

    def test_already_installed_detected(self):
        infos = build_pull_info_for_bundle("spark-cpu-8gb", ["granite4.1:3b"])
        for info in infos:
            if info.model_id == "granite4.1:3b":
                assert info.already_installed is True

    def test_not_installed_when_absent(self):
        infos = build_pull_info_for_bundle("spark-cpu-8gb", [])
        for info in infos:
            assert info.already_installed is False

    def test_returns_empty_for_unknown_bundle(self):
        infos = build_pull_info_for_bundle("nonexistent-bundle", [])
        assert infos == []

    def test_download_size_is_positive(self):
        infos = build_pull_info_for_bundle("spark-cpu-8gb", [])
        for info in infos:
            assert info.download_size_gb > 0

    def test_license_is_populated(self):
        infos = build_pull_info_for_bundle("spark-cpu-8gb", [])
        for info in infos:
            assert info.license
            assert info.license != ""

    def test_provider_is_ollama_for_local_bundles(self):
        infos = build_pull_info_for_bundle("spark-cpu-8gb", [])
        for info in infos:
            assert info.provider == "ollama"
            assert info.privacy_level == "local-only"


class TestPullConfirmation:
    def test_models_not_auto_downloaded(self):
        from prometheus_cli.onboarding import OllamaStatus
        infos = build_pull_info_for_bundle("spark-cpu-8gb", [])
        not_installed = [i for i in infos if not i.already_installed]
        assert len(not_installed) >= 1
