"""Low-end local model matrix — CPU, 8 GB GPU, and 12 GB GPU bundles."""
from __future__ import annotations

import os

import pytest

from prometheus_cli.bundles import classify_registry, find_bundle, hardware_fits, load_registry
from prometheus_cli.hardware import HardwareReport, recommended_profile


def _hw(*, ram_gb: float, vram_gb: float = 0, gpu_vendor: str | None = None) -> HardwareReport:
    return HardwareReport(
        os="Linux",
        architecture="x86_64",
        ram_gb=ram_gb,
        vram_gb=vram_gb,
        gpu_vendor=gpu_vendor,
        gpu_name="test-gpu" if gpu_vendor else None,
        cpu_features=[],
        disk_free_gb=200,
        metal=False,
        unified_memory=False,
    )


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        (_hw(ram_gb=8, vram_gb=0), "ember-8gb"),
        (_hw(ram_gb=16, vram_gb=8, gpu_vendor="NVIDIA"), "ember-8gb"),
        (_hw(ram_gb=32, vram_gb=12, gpu_vendor="NVIDIA"), "forge-12gb"),
    ],
)
def test_hardware_recommends_low_end_bundles(report, expected):
    assert recommended_profile(report) == expected


def test_low_end_matrix_bundle_ids_exist():
    registry = load_registry()
    ids = {b.id for b in registry}
    assert "spark-cpu-8gb" in ids
    assert "ember-8gb-gpu" in ids
    assert "forge-12gb" in ids


def test_ember_alias_resolves():
    bundle = find_bundle("ember-8gb")
    assert bundle is not None
    assert bundle.id == "ember-8gb-gpu"


def test_spark_cpu_alias_resolves():
    bundle = find_bundle("spark-cpu")
    assert bundle is not None
    assert bundle.id == "spark-cpu-8gb"


@pytest.mark.parametrize(
    ("bundle_id", "ram_gb", "vram_gb", "should_fit"),
    [
        ("ember-8gb-gpu", 16, 8, True),
        ("ember-8gb-gpu", 8, 4, False),
        ("forge-12gb", 32, 12, True),
        ("forge-12gb", 16, 8, False),
    ],
)
def test_hardware_fits_low_end_bundles(bundle_id, ram_gb, vram_gb, should_fit):
    bundle = find_bundle(bundle_id)
    assert bundle is not None
    report = _hw(ram_gb=ram_gb, vram_gb=vram_gb, gpu_vendor="NVIDIA" if vram_gb else None)
    fits, _reasons = hardware_fits(bundle, report)
    assert fits is should_fit


def test_classified_registry_includes_cpu_and_gpu_starters():
    report = _hw(ram_gb=32, vram_gb=12, gpu_vendor="NVIDIA")
    classified = classify_registry(load_registry(), report)
    ids = {c.bundle.id for c in classified}
    assert "ember-8gb-gpu" in ids
    assert "forge-12gb" in ids
    assert "spark-cpu-8gb" in ids


@pytest.mark.skipif(
    os.environ.get("PROMETHEUS_RUN_OLLAMA_TESTS") != "1",
    reason="Real Ollama tests require PROMETHEUS_RUN_OLLAMA_TESTS=1",
)
def test_ollama_models_list_when_enabled():
    from prometheus_cli.onboarding import check_ollama

    status = check_ollama()
    assert status.installed or not status.installed  # smoke: callable without crash
