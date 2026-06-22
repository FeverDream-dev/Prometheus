from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _has_build():
    return shutil.which("python") is not None and bool(importlib_util_find("build"))


def importlib_util_find(name):
    try:
        import importlib.util
        return importlib.util.find_spec(name)
    except ImportError:
        return None


def _build_wheel_and_sdist(tmp_path):
    dest = tmp_path / "dist_build"
    dest.mkdir()
    result = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(dest), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        pytest.skip(f"python -m build failed: {result.stderr[:500]}")
    wheels = list(dest.glob("*.whl"))
    sdists = list(dest.glob("*.tar.gz"))
    assert wheels, f"no wheel built in {dest}: {list(dest.iterdir())}"
    assert sdists, f"no sdist built in {dest}: {list(dest.iterdir())}"
    return wheels[0], sdists[0]


class TestWheelContainsResources:
    @pytest.fixture(scope="class")
    def built_artifacts(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("build")
        return _build_wheel_and_sdist(tmp)

    def test_wheel_contains_v2_bundle_yamls(self, built_artifacts):
        import zipfile
        wheel, _ = built_artifacts
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
        yaml_files = [n for n in names if "resources/bundles_v2/" in n and n.endswith(".yaml")]
        assert len(yaml_files) >= 8, (
            f"wheel has only {len(yaml_files)} v2 bundle YAML files; expected >= 8.\n"
            f"Wheel contents sample: {sorted(names)[:20]}"
        )

    def test_wheel_contains_v1_bundle_yamls(self, built_artifacts):
        import zipfile
        wheel, _ = built_artifacts
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
        yaml_files = [n for n in names if "resources/bundles_v1/" in n and n.endswith(".yaml")]
        assert len(yaml_files) >= 4, f"wheel has only {len(yaml_files)} v1 bundle YAML files"

    def test_wheel_contains_prompts(self, built_artifacts):
        import zipfile
        wheel, _ = built_artifacts
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
        prompt_files = [n for n in names if "resources/prompts/" in n]
        assert len(prompt_files) >= 2, f"wheel missing prompts: {prompt_files}"

    def test_wheel_contains_schemas(self, built_artifacts):
        import zipfile
        wheel, _ = built_artifacts
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
        schema_files = [n for n in names if "resources/schemas/" in n]
        assert len(schema_files) >= 1, f"wheel missing schemas: {schema_files}"

    def test_wheel_contains_i18n(self, built_artifacts):
        import zipfile
        wheel, _ = built_artifacts
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
        i18n_files = [n for n in names if "resources/i18n/" in n]
        assert len(i18n_files) >= 1, f"wheel missing i18n: {i18n_files}"

    def test_wheel_contains_default_config(self, built_artifacts):
        import zipfile
        wheel, _ = built_artifacts
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
        assert any("default_config.yaml" in n for n in names), \
            f"wheel missing default_config.yaml: {[n for n in names if 'default' in n.lower()]}"

    def test_wheel_has_no_model_weights(self, built_artifacts):
        import zipfile
        wheel, _ = built_artifacts
        forbidden = {".bin", ".gguf", ".pt", ".pth", ".onnx", ".safetensors"}
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
        leaked = [n for n in names if Path(n).suffix.lower() in forbidden]
        assert leaked == [], f"wheel contains weight files: {leaked}"


class TestSdistContainsResources:
    @pytest.fixture(scope="class")
    def built_artifacts(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("build")
        return _build_wheel_and_sdist(tmp)

    def test_sdist_contains_v2_bundle_yamls(self, built_artifacts):
        import tarfile
        _, sdist = built_artifacts
        with tarfile.open(sdist, "r:gz") as tf:
            names = tf.getnames()
        yaml_files = [n for n in names if "resources/bundles_v2/" in n and n.endswith(".yaml")]
        assert len(yaml_files) >= 8, f"sdist has only {len(yaml_files)} v2 bundle YAML files"

    def test_sdist_contains_no_weights(self, built_artifacts):
        import tarfile
        _, sdist = built_artifacts
        forbidden = {".bin", ".gguf", ".pt", ".pth", ".onnx", ".safetensors"}
        with tarfile.open(sdist, "r:gz") as tf:
            names = tf.getnames()
        leaked = [n for n in names if Path(n).suffix.lower() in forbidden]
        assert leaked == [], f"sdist contains weight files: {leaked}"


class TestCleanVenvInstall:
    @pytest.fixture(scope="class")
    def installed_venv(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("venv_install")
        wheel, _ = _build_wheel_and_sdist(tmp)
        venv = tmp / "venv"
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            pytest.skip(f"venv creation failed: {result.stderr}")
        pip = str(venv / "bin" / "pip")
        install = subprocess.run(
            [pip, "install", str(wheel), "--no-deps", "--no-build-isolation"],
            capture_output=True, text=True, timeout=120,
        )
        if install.returncode != 0:
            pytest.skip(f"pip install failed: {install.stderr[:500]}")
        deps = subprocess.run(
            [pip, "install", "httpx", "pydantic", "PyYAML", "rich", "typer"],
            capture_output=True, text=True, timeout=120,
        )
        if deps.returncode != 0:
            pytest.skip(f"deps install failed: {deps.stderr[:500]}")
        return venv

    def test_clean_install_can_list_bundles(self, installed_venv):
        prometheus = str(installed_venv / "bin" / "prometheus")
        result = subprocess.run(
            [prometheus, "bundles", "list", "--json"],
            capture_output=True, text=True, timeout=30,
            env={**__import__("os").environ, "HOME": str(installed_venv.parent)},
        )
        assert result.returncode == 0, f"bundles list failed: {result.stderr[:500]}"
        import json
        data = json.loads(result.stdout)
        assert len(data) >= 8

    def test_clean_install_can_dry_run_setup(self, installed_venv):
        prometheus = str(installed_venv / "bin" / "prometheus")
        result = subprocess.run(
            [prometheus, "setup", "--dry-run"],
            capture_output=True, text=True, timeout=30,
            env={**__import__("os").environ, "HOME": str(installed_venv.parent)},
        )
        assert result.returncode == 0, f"setup --dry-run failed: {result.stderr[:500]}"
        assert "No bundles found" not in result.stdout
        assert "Available bundles" in result.stdout
