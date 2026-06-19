from __future__ import annotations

import pytest
import yaml

from prometheus_cli.bundles import find_bundle, load_registry, sanitize_bundle


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def test_find_bundle_returns_match(registry):
    assert find_bundle("spark-cpu-8gb", registry).id == "spark-cpu-8gb"


def test_find_bundle_returns_none_for_unknown(registry):
    assert find_bundle("nope", registry) is None


def test_sanitize_strips_secret_named_fields(registry):
    bundle = find_bundle("spark-cpu-8gb", registry)
    data = sanitize_bundle(bundle)
    _assert_no_secret_keys(data)


def _assert_no_secret_keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            assert not any(s in k.lower() for s in ("api_key", "secret", "token", "password")), f"secret key leaked: {k}"
            _assert_no_secret_keys(v)
    elif isinstance(node, list):
        for item in node:
            _assert_no_secret_keys(item)


def test_sanitize_drops_absolute_personal_paths(registry):
    bundle = find_bundle("spark-cpu-8gb", registry)
    data = sanitize_bundle(bundle)
    _assert_no_absolute_paths(data)


def _assert_no_absolute_paths(node):
    if isinstance(node, dict):
        for v in node.values():
            _assert_no_absolute_paths(v)
    elif isinstance(node, list):
        for item in node:
            _assert_no_absolute_paths(item)
    elif isinstance(node, str):
        if "://" not in node:
            assert not node.startswith("/"), f"absolute path leaked: {node}"
            assert not node.startswith("../"), f"escape path leaked: {node}"


def test_sanitize_preserves_https_license_sources(registry):
    bundle = find_bundle("forge-12gb", registry)
    data = sanitize_bundle(bundle)
    sources = [lic["source"] for lic in data["licenses"]]
    assert all(s.startswith("https://") for s in sources)


def test_sanitize_output_is_valid_yaml_roundtrip(registry, tmp_path):
    bundle = find_bundle("spark-cpu-8gb", registry)
    out = tmp_path / "x.yaml"
    out.write_text(yaml.safe_dump(sanitize_bundle(bundle), sort_keys=False), encoding="utf-8")
    reloaded = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert reloaded["id"] == "spark-cpu-8gb"
    assert reloaded["schema_version"] == 2


def test_sanitize_strips_injected_secret_in_custom_dict():
    from prometheus_cli.bundles import _strip_unsafe

    nasty = {
        "id": "custom",
        "api_key": "sk-leak",
        "model": {"name": "x", "token": "t", "nested": {"password": "p"}},
        "path": "/home/user/secret",
        "safe_url": "https://ollama.com/library/x",
    }
    clean = _strip_unsafe(nasty)
    assert "api_key" not in clean
    assert "token" not in clean["model"]
    assert "password" not in clean["model"]["nested"]
    assert clean["path"] is None
    assert clean["safe_url"] == "https://ollama.com/library/x"


def test_use_materializes_active_bundle_and_sets_settings(tmp_path, monkeypatch):
    monkeypatch.setattr("prometheus_cli.config.CONFIG_HOME", tmp_path)
    monkeypatch.setattr("prometheus_cli.installer.user_data_home", lambda: tmp_path)
    import prometheus_cli.config as cfg

    monkeypatch.setattr(cfg, "CONFIG_HOME", tmp_path)
    monkeypatch.setattr(cfg, "ensure_home", lambda: tmp_path)
    from prometheus_cli.bundles import find_bundle, load_registry

    bundle = find_bundle("spark-cpu-8gb", load_registry())
    active_dir = tmp_path / "bundles"
    active_dir.mkdir()
    active_path = active_dir / f"active-{bundle.id}.yaml"
    v1 = bundle.to_v1_bundle()
    active_path.write_text(yaml.safe_dump(v1.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
    assert active_path.exists()
    reloaded = yaml.safe_load(active_path.read_text(encoding="utf-8"))
    assert reloaded["name"] == "spark-cpu-8gb"
    assert any(m["role"] == "controller" for m in reloaded["models"])
