from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

FORBIDDEN_SUFFIXES = (
    ".gguf", ".safetensors", ".bin", ".pt", ".ckpt", ".onnx", ".weights",
    ".sqlite", ".sqlite3", ".trace", ".har", ".webm", ".mp4",
)
FORBIDDEN_NAMES = {".env", "prometheus.db"}
SECRET_PATTERNS = (
    "BEGIN RSA PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "BEGIN PGP PRIVATE KEY",
)
ALLOWED_LARGE = {"assets/audio/music.mp3"}


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def test_no_model_weights_or_dbs_tracked():
    bad = [f for f in _tracked_files() if f.endswith(FORBIDDEN_SUFFIXES) or Path(f).name in FORBIDDEN_NAMES]
    assert not bad, f"forbidden model/db files tracked: {bad}"


def test_no_secret_key_material_tracked():
    for f in _tracked_files():
        path = REPO / f
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat in SECRET_PATTERNS:
            assert pat not in text, f"secret material ({pat}) found in tracked file {f}"


def test_no_large_unexpected_binaries_tracked():
    large = []
    for f in _tracked_files():
        path = REPO / f
        if not path.is_file():
            continue
        if f in ALLOWED_LARGE:
            continue
        if path.stat().st_size > 5_000_000:
            large.append(f"{f} ({path.stat().st_size} bytes)")
    assert not large, f"unexpected large tracked files: {large}"


def test_artifact_directories_not_tracked():
    tracked = set(_tracked_files())
    for d in (".local-test", ".prometheus-test", ".artifacts", ".traces", "playwright-report", "test-results"):
        assert not any(p.startswith(d + "/") for p in tracked), f"artifact dir {d}/ has tracked files"


def test_completion_kit_not_tracked():
    tracked = set(_tracked_files())
    assert not any(p.startswith("PROMETHEUS-Completion-Kit/") for p in tracked)
