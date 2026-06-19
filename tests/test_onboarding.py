from __future__ import annotations

from pathlib import Path
from unittest import mock

import httpx

from prometheus_cli.hardware import HardwareReport
from prometheus_cli.models import ModelBundle, ModelSpec
from prometheus_cli.onboarding import (
    BundleOption,
    _estimate_download_gb,
    classify_bundle_fit,
    explain_bundle,
    list_available_bundles,
    pick_default_bundle,
    check_ollama,
)

BUNDLES_DIR = Path(__file__).resolve().parent.parent / "config" / "bundles"


def _report(ram=16, vram=0, gpu_vendor=None, metal=False, unified=False, disk=100):
    return HardwareReport(
        os="Linux", architecture="x86_64", ram_gb=ram, vram_gb=vram,
        gpu_vendor=gpu_vendor, metal=metal, unified_memory=unified, disk_free_gb=disk,
    )


def _bundle(name="test", ram=8, vram=0, models=None):
    return ModelBundle(
        name=name, minimum_ram_gb=ram, minimum_vram_gb=vram,
        models=models or [ModelSpec(model="gemma3:4b", role="controller")],
    )


class TestListBundles:
    def test_finds_all_shipped_bundles(self):
        options = list_available_bundles(BUNDLES_DIR)
        names = {o.name for o in options}
        assert {"ember-8gb", "forge-12gb", "forge-24gb", "cloud-example"} <= names

    def test_empty_for_missing_dir(self, tmp_path):
        assert list_available_bundles(tmp_path / "nope") == []

    def test_skips_invalid_yaml(self, tmp_path):
        (tmp_path / "broken.yaml").write_text("not: [valid yaml")
        assert list_available_bundles(tmp_path) == []


class TestClassifyFit:
    def test_fits_when_within_limits(self):
        bundle = _bundle(ram=8, vram=0)
        fits, reason = classify_bundle_fit(bundle, _report(ram=16))
        assert fits is True

    def test_rejected_for_insufficient_ram(self):
        bundle = _bundle(ram=16)
        fits, reason = classify_bundle_fit(bundle, _report(ram=8))
        assert fits is False
        assert "16 GB RAM" in reason

    def test_rejected_for_insufficient_vram(self):
        bundle = _bundle(vram=12)
        fits, reason = classify_bundle_fit(bundle, _report(ram=32, vram=4, gpu_vendor="NVIDIA"))
        assert fits is False
        assert "12 GB VRAM" in reason

    def test_apple_unified_memory_skips_vram_check(self):
        bundle = _bundle(vram=12)
        fits, _ = classify_bundle_fit(bundle, _report(ram=32, metal=True, unified=True))
        assert fits is True

    def test_rejected_for_insufficient_disk(self):
        bundle = _bundle(models=[ModelSpec(model="qwen3:14b", role="controller")])
        fits, reason = classify_bundle_fit(bundle, _report(ram=32, disk=5))
        assert fits is False
        assert "disk" in reason.lower()


class TestPickDefault:
    def test_picks_ember_for_cpu_host(self):
        options = list_available_bundles(BUNDLES_DIR)
        chosen = pick_default_bundle(options, _report(ram=8, vram=0, gpu_vendor=None))
        assert chosen is not None
        assert chosen.name == "ember-8gb"

    def test_returns_none_when_profile_missing(self):
        options = [BundleOption(name="nonexistent", path=Path("x"), bundle=_bundle(), fits=False, reason="")]
        assert pick_default_bundle(options, _report()) is None


class TestExplainBundle:
    def test_includes_memory_and_download_estimate(self):
        bundle = _bundle(models=[
            ModelSpec(model="gemma3:4b", role="controller"),
            ModelSpec(model="qwen3:8b", role="coder"),
        ])
        text = explain_bundle(bundle, _report(ram=16, disk=200))
        assert "Memory floor" in text
        assert "Estimated downloads" in text
        assert "gemma3:4b" in text
        assert "tool-capable" in text


class TestEstimateDownload:
    def test_known_model(self):
        assert _estimate_download_gb("gemma3:4b") == 3.5

    def test_unknown_uses_default(self):
        assert _estimate_download_gb("future-model:99b") == 7.0

    def test_family_match(self):
        assert _estimate_download_gb("qwen3:8b-instruct") == 6.5


class TestCheckOllama:
    def test_not_installed_returns_false(self):
        with mock.patch("prometheus_cli.onboarding.shutil.which", return_value=None):
            status = check_ollama()
            assert status.installed is False
            assert status.running is False
            assert "ollama" in status.install_hint.lower() or "ollama.com" in status.install_hint

    def test_running_returns_model_list(self):
        payload = {"models": [{"name": "gemma3:4b"}, {"name": "qwen3:8b"}]}
        request = httpx.Request("GET", "http://127.0.0.1:11434/api/tags")
        response = httpx.Response(200, json=payload, request=request)
        with mock.patch("prometheus_cli.onboarding.shutil.which", return_value="/usr/bin/ollama"), \
             mock.patch("httpx.get", return_value=response):
            status = check_ollama()
            assert status.installed is True
            assert status.running is True
            assert status.models == ["gemma3:4b", "qwen3:8b"]

    def test_installed_but_not_running(self):
        with mock.patch("prometheus_cli.onboarding.shutil.which", return_value="/usr/bin/ollama"), \
             mock.patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            status = check_ollama()
            assert status.installed is True
            assert status.running is False
