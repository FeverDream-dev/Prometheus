from __future__ import annotations

import sys
from pathlib import Path

import pytest

from prometheus_cli.resources import (
    get_default_bundles_dir,
    get_default_bundles_v1_dir,
    get_default_prompts_dir,
    get_default_schemas_dir,
    get_resource_root,
    list_packaged_bundles,
    list_packaged_bundles_v1,
)


class TestInstalledPackageIntegrity:
    def test_resources_package_is_importable(self):
        import prometheus_cli.resources as res_pkg
        assert hasattr(res_pkg, "get_resource_root")

    def test_installed_package_path_exists(self):
        root = get_resource_root()
        assert root.exists(), f"installed resource root does not exist: {root}"

    def test_v2_bundles_loadable_after_install(self):
        bundles = list_packaged_bundles()
        assert len(bundles) >= 8
        import yaml
        for path in bundles:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert "id" in data
            assert "roles" in data

    def test_v1_bundles_loadable_after_install(self):
        bundles = list_packaged_bundles_v1()
        assert len(bundles) >= 4
        import yaml
        for path in bundles:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert "name" in data
            assert "models" in data or "roles" in data

    def test_prompts_present_after_install(self):
        d = get_default_prompts_dir()
        files = list(d.glob("*")) if d.is_dir() else []
        assert len(files) >= 2, f"expected >= 2 prompt files, got {len(files)}"

    def test_schemas_present_after_install(self):
        d = get_default_schemas_dir()
        files = list(d.glob("*")) if d.is_dir() else []
        assert len(files) >= 1, f"expected schemas, got {len(files)}"

    def test_all_v2_bundles_parse_via_bundle_v2_model(self):
        from prometheus_cli.bundles import load_bundle
        for path in list_packaged_bundles():
            bundle = load_bundle(path)
            assert bundle.id
            assert bundle.schema_version == 2


class TestBundleRegistryFromPackagedDefaults:
    def test_load_registry_returns_all_bundles(self):
        from prometheus_cli.bundles import load_registry
        registry = load_registry()
        ids = {b.id for b in registry}
        expected = {
            "spark-cpu-8gb", "ember-8gb-gpu", "forge-12gb",
            "cloud-hybrid", "vibethinker-sandbox-q2", "vibethinker-sandbox-q4",
        }
        assert expected <= ids, f"missing bundles: {expected - ids}"

    def test_load_registry_does_not_require_repo_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PROMETHEUS_HOME", str(tmp_path / "no_home"))
        from prometheus_cli.bundles import load_registry
        registry = load_registry()
        assert len(registry) >= 8


class TestNoForbiddenArtifacts:
    FORBIDDEN_EXTS = {".bin", ".gguf", ".pt", ".pth", ".onnx", ".safetensors", ".zip", ".tar", ".gz"}
    FORBIDDEN_NAMES = {".ollama", ".prometheus", ".git", "node_modules"}

    def test_no_weights_or_caches(self):
        root = get_resource_root()
        for f in root.rglob("*"):
            if f.is_file():
                assert f.suffix.lower() not in self.FORBIDDEN_EXTS, f"forbidden: {f}"
            if f.is_dir() and f.name not in ("__pycache__",):
                assert f.name not in self.FORBIDDEN_NAMES, f"forbidden dir: {f}"
