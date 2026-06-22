#!/usr/bin/env python3
"""Sync approved default resources from the repository into the installable package.

Source layout (repo root)                    Destination (package)
========================================     ================================================
config/bundles-v2/*.yaml                ->   src/prometheus_cli/resources/bundles_v2/*.yaml
config/bundles/*.yaml                   ->   src/prometheus_cli/resources/bundles_v1/*.yaml
config/bundle-v2.schema.json            ->   src/prometheus_cli/resources/schemas/bundle-v2.schema.json
config/default.yaml                     ->   src/prometheus_cli/resources/default_config.yaml
prompts/**                              ->   src/prometheus_cli/resources/prompts/**
schemas/**                              ->   src/prometheus_cli/resources/schemas/**
i18n/**                                 ->   src/prometheus_cli/resources/i18n/**

    python scripts/sync_package_resources.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_RESOURCES = REPO_ROOT / "src" / "prometheus_cli" / "resources"

FORBIDDEN_EXTS = {".bin", ".gguf", ".pt", ".pth", ".onnx", ".safetensors", ".zip", ".tar", ".gz"}

DIR_SYNCS: list[tuple[Path, str]] = [
    (REPO_ROOT / "config" / "bundles-v2", "bundles_v2"),
    (REPO_ROOT / "config" / "bundles", "bundles_v1"),
    (REPO_ROOT / "prompts", "prompts"),
    (REPO_ROOT / "schemas", "schemas"),
    (REPO_ROOT / "i18n", "i18n"),
]

FILE_SYNCS: list[tuple[Path, str]] = [
    (REPO_ROOT / "config" / "bundle-v2.schema.json", "schemas/bundle-v2.schema.json"),
    (REPO_ROOT / "config" / "bundle.schema.json", "schemas/bundle.schema.json"),
    (REPO_ROOT / "config" / "default.yaml", "default_config.yaml"),
]


def _reset_dir(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)


def _copy_dir(src: Path, name: str) -> int:
    dest = PKG_RESOURCES / name
    _reset_dir(dest)
    if not src.is_dir():
        return 0
    count = 0
    for entry in sorted(src.rglob("*")):
        if not entry.is_file():
            continue
        rel = entry.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, target)
        count += 1
    return count


def _copy_file(src: Path, dest_rel: str) -> bool:
    if not src.is_file():
        return False
    dest = PKG_RESOURCES / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def _ensure_init() -> None:
    init_file = PKG_RESOURCES / "__init__.py"
    PKG_RESOURCES.mkdir(parents=True, exist_ok=True)
    if not init_file.exists():
        init_file.write_text(
            '"""Packaged default resources for PROMETHEUS (bundles, prompts, schemas, i18n)."""\n',
            encoding="utf-8",
        )


def _check_no_weights() -> list[Path]:
    return [
        f for f in PKG_RESOURCES.rglob("*")
        if f.is_file() and f.suffix.lower() in FORBIDDEN_EXTS
    ]


def main() -> int:
    if not PKG_RESOURCES.parent.is_dir():
        print(f"ERROR: package dir not found: {PKG_RESOURCES.parent}", file=sys.stderr)
        return 1

    _ensure_init()

    total = 0
    for src, name in DIR_SYNCS:
        count = _copy_dir(src, name)
        if count == 0:
            print(f"  [skip] {name}/ - source not found or empty ({src})")
        else:
            print(f"  [ok]   {name}/ - {count} files")
            total += count

    for src, dest_rel in FILE_SYNCS:
        if _copy_file(src, dest_rel):
            print(f"  [ok]   {dest_rel}")
            total += 1
        else:
            print(f"  [skip] {dest_rel} - source not found ({src})")

    leaked = _check_no_weights()
    if leaked:
        print(f"\nERROR: {len(leaked)} forbidden binary/weight files leaked into resources:", file=sys.stderr)
        for f in leaked:
            print(f"  {f.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 2

    print(f"\nSynced {total} resource files into {PKG_RESOURCES.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
