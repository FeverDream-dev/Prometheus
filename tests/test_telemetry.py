from __future__ import annotations

import json

import pytest

from prometheus_cli.telemetry import (
    TelemetrySnapshot,
    collect_snapshot,
    parse_nvidia_smi,
    parse_rocm_smi,
    render_bar,
    render_telemetry_lines,
    sample_disk,
)


NVIDIA_FIXTURE = (
    "NVIDIA GeForce RTX 4070, 35, 4567, 8192, 42\n"
    "NVIDIA GeForce RTX 4070, 12, 1000, 8192, 38"
)

ROCM_FIXTURE = json.dumps({
    "card0": {
        "GPU use (%)": "35",
        "VRAM Total Memory (B)": "17163091968",
        "VRAM Total Used Memory (B)": "4567890123",
        "Card series": "AMD Radeon RX 7900",
    },
    "card1": {
        "GPU use (%)": "10",
        "VRAM Total Memory (B)": "17163091968",
        "VRAM Total Used Memory (B)": "1000000000",
    },
})


def test_parse_nvidia_smi_first_gpu_full_row():
    parsed = parse_nvidia_smi(NVIDIA_FIXTURE)
    assert parsed["available"] is True
    assert parsed["vendor"] == "NVIDIA"
    assert parsed["name"] == "NVIDIA GeForce RTX 4070"
    assert parsed["usage_percent"] == 35.0
    assert parsed["vram_used_gb"] == round(4567 / 1024, 2)
    assert parsed["vram_total_gb"] == round(8192 / 1024, 2)
    assert parsed["vram_percent"] == round(parsed["vram_used_gb"] / parsed["vram_total_gb"] * 100, 1)
    assert parsed["temperature_c"] == 42.0


def test_parse_nvidia_smi_empty_output_marks_unavailable():
    parsed = parse_nvidia_smi("")
    assert parsed["available"] is False
    assert parsed["name"] is None


def test_parse_nvidia_smi_tolerates_missing_columns():
    parsed = parse_nvidia_smi("NVIDIA GeForce RTX 3060")
    assert parsed["available"] is True
    assert parsed["name"] == "NVIDIA GeForce RTX 3060"
    assert parsed["usage_percent"] is None
    assert parsed["vram_total_gb"] is None


def test_parse_rocm_smi_full_json():
    parsed = parse_rocm_smi(ROCM_FIXTURE)
    assert parsed["available"] is True
    assert parsed["vendor"] == "AMD"
    assert parsed["name"] == "AMD Radeon RX 7900"
    assert parsed["usage_percent"] == 35.0
    assert parsed["vram_total_gb"] == round(17163091968 / (1024**3), 2)
    assert parsed["vram_used_gb"] == round(4567890123 / (1024**3), 2)
    assert parsed["vram_percent"] is not None
    assert 25.0 < parsed["vram_percent"] < 30.0


def test_parse_rocm_smi_invalid_json_returns_unavailable():
    parsed = parse_rocm_smi("not json at all")
    assert parsed["available"] is False


def test_parse_rocm_smi_empty_returns_unavailable():
    parsed = parse_rocm_smi("")
    assert parsed["available"] is False
    assert parsed["vendor"] == "AMD"


def test_render_bar_zero_to_hundred():
    assert render_bar(0, 10) == "░░░░░░░░░░"
    assert render_bar(100, 10) == "██████████"
    assert render_bar(50, 10) == "█████░░░░░"
    assert render_bar(25, 8) == "██░░░░░░"


def test_render_bar_none_fills_empty():
    assert render_bar(None, 6) == "░░░░░░"


def test_render_bar_clamps_overflow():
    assert render_bar(150, 10) == "██████████"
    assert render_bar(-20, 10) == "░░░░░░░░░░"


def test_sample_disk_returns_total_and_percent(tmp_path):
    result = sample_disk(str(tmp_path))
    assert result["path"] == str(tmp_path)
    assert result["total_gb"] > 0
    assert result["used_gb"] >= 0
    assert 0.0 <= result["percent"] <= 100.0


def test_collect_snapshot_returns_full_schema(tmp_path):
    snap = collect_snapshot(workspace=str(tmp_path), cpu_interval_s=0.0)
    assert isinstance(snap, TelemetrySnapshot)
    d = snap.as_dict()
    for required_key in (
        "timestamp", "cpu_percent", "ram", "disk", "gpu", "battery",
        "ollama", "git", "sandbox", "bundle", "notes",
    ):
        assert required_key in d, f"snapshot missing {required_key}"
    for ram_key in ("total_gb", "used_gb", "percent"):
        assert ram_key in d["ram"]
    for gpu_key in ("vendor", "name", "usage_percent", "vram_percent", "available"):
        assert gpu_key in d["gpu"]


def test_snapshot_json_is_valid_json(tmp_path):
    snap = collect_snapshot(workspace=str(tmp_path), cpu_interval_s=0.0)
    parsed = json.loads(snap.as_json())
    assert parsed["timestamp"]
    assert "ram" in parsed
    assert "gpu" in parsed


def test_render_telemetry_lines_includes_all_categories(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "init"], check=True,
    )
    snap = collect_snapshot(workspace=str(tmp_path), cpu_interval_s=0.0)
    rendered = "\n".join(render_telemetry_lines(snap))
    for label in ("CPU", "RAM", "DISK", "GPU", "VRAM", "Ollama", "Git", "Sandbox"):
        assert label in rendered, f"telemetry render missing {label}"


def test_render_telemetry_lines_shows_bar_glyphs(tmp_path):
    snap = collect_snapshot(workspace=str(tmp_path), cpu_interval_s=0.0)
    rendered = "\n".join(render_telemetry_lines(snap))
    assert "█" in rendered or "░" in rendered, "bar glyphs not rendered"


def test_gpu_unavailable_fallback_when_no_tools(monkeypatch):
    import prometheus_cli.telemetry as tele

    monkeypatch.setattr(tele.shutil, "which", lambda _name: None)
    monkeypatch.setattr(tele, "_gpu_cache", {})
    gpu = tele.sample_gpu(timeout_s=0.1)
    assert gpu["available"] is False
    assert "source" in gpu


@pytest.mark.parametrize("fixture,expected_vendor", [
    (NVIDIA_FIXTURE, "NVIDIA"),
    (ROCM_FIXTURE, "AMD"),
])
def test_parser_vendor_classification(fixture, expected_vendor):
    if expected_vendor == "NVIDIA":
        parsed = parse_nvidia_smi(fixture)
    else:
        parsed = parse_rocm_smi(fixture)
    assert parsed["vendor"] == expected_vendor
