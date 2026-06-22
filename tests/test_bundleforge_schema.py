from __future__ import annotations

import pytest
import yaml

from prometheus_cli.bundleforge.schema import (
    ForgeBundle,
    ForgePermissions,
    ForgeRequirements,
    ForgeRoleSpec,
    load_forge_bundle,
)


def _valid_bundle_data():
    return {
        "id": "test-bundle",
        "name": "Test Bundle",
        "description": "A test bundle",
        "version": "0.1.0",
        "use_case": "testing",
        "roles": {
            "envoy": {"model": "gemma3n:e2b", "provider": "ollama"},
            "builder": {"model": "qwen2.5-coder:7b", "provider": "ollama"},
            "critic": {"model": "granite-code:3b", "provider": "ollama"},
        },
        "optional": {"image_generator": "black-forest-labs/FLUX.1-schnell"},
        "permissions": {
            "network": "ask",
            "package_install": "ask",
            "browser": "allow",
            "assets": "allow",
            "external_directory": "deny",
        },
        "requirements": {"min_ram_gb": 8, "min_vram_gb": 6, "min_disk_gb": 20},
        "license_notes": "All models Apache-2.0 or Gemma-Terms.",
        "commercial_safe": True,
    }


class TestForgeBundleSchema:
    def test_valid_bundle_loads(self):
        b = ForgeBundle.model_validate(_valid_bundle_data())
        assert b.id == "test-bundle"
        assert len(b.roles) == 3

    def test_rejects_invalid_id(self):
        data = _valid_bundle_data()
        data["id"] = "Invalid ID!"
        with pytest.raises(Exception):
            ForgeBundle.model_validate(data)

    def test_rejects_unknown_role(self):
        data = _valid_bundle_data()
        data["roles"]["unknown_role"] = {"model": "foo:bar"}
        with pytest.raises(Exception):
            ForgeBundle.model_validate(data)

    def test_rejects_empty_roles(self):
        data = _valid_bundle_data()
        data["roles"] = {}
        with pytest.raises(Exception):
            ForgeBundle.model_validate(data)

    def test_rejects_unknown_permission_level(self):
        data = _valid_bundle_data()
        data["permissions"]["network"] = "maybe"
        with pytest.raises(Exception):
            ForgeBundle.model_validate(data)

    def test_all_model_ids_includes_optional(self):
        b = ForgeBundle.model_validate(_valid_bundle_data())
        ids = b.all_model_ids
        assert "gemma3n:e2b" in ids
        assert "black-forest-labs/FLUX.1-schnell" in ids


class TestForgeBundleToV2:
    def test_to_v2_produces_valid_structure(self):
        b = ForgeBundle.model_validate(_valid_bundle_data())
        v2 = b.to_v2_dict()
        assert v2["schema_version"] == 2
        assert v2["id"] == "test-bundle"
        assert "controller" in v2["roles"]
        assert "coder" in v2["roles"]
        assert "reviewer" in v2["roles"]
        assert "hardware" in v2
        assert "runtime" in v2
        assert "licenses" in v2

    def test_to_v2_maps_envoy_to_controller(self):
        b = ForgeBundle.model_validate(_valid_bundle_data())
        v2 = b.to_v2_dict()
        assert v2["roles"]["controller"]["model"] == "gemma3n:e2b"

    def test_to_v2_maps_builder_to_coder(self):
        b = ForgeBundle.model_validate(_valid_bundle_data())
        v2 = b.to_v2_dict()
        assert v2["roles"]["coder"]["model"] == "qwen2.5-coder:7b"

    def test_to_v2_maps_critic_to_reviewer(self):
        b = ForgeBundle.model_validate(_valid_bundle_data())
        v2 = b.to_v2_dict()
        assert v2["roles"]["reviewer"]["model"] == "granite-code:3b"

    def test_to_v2_passes_v2_validation(self):
        from prometheus_cli.bundles import BundleV2
        b = ForgeBundle.model_validate(_valid_bundle_data())
        v2 = b.to_v2_dict()
        bundle_v2 = BundleV2.model_validate(v2)
        assert bundle_v2.id == "test-bundle"


class TestLoadForgeBundle:
    def test_load_from_file(self, tmp_path):
        path = tmp_path / "bundle.yaml"
        path.write_text(yaml.safe_dump(_valid_bundle_data()), encoding="utf-8")
        b = load_forge_bundle(path)
        assert b.id == "test-bundle"


class TestTemplateLoading:
    def test_all_packaged_templates_load(self):
        from prometheus_cli.bundleforge import list_templates, load_template

        for template_id in list_templates():
            bundle = load_template(template_id)
            assert bundle.id
            assert len(bundle.roles) >= 1
            assert bundle.requirements.min_ram_gb > 0
