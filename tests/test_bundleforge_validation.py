from __future__ import annotations


import yaml

from prometheus_cli.bundleforge.schema import ForgeBundle
from prometheus_cli.bundleforge.validate import validate_all_templates, validate_bundle, validate_file, validate_template
from prometheus_cli.hardware import HardwareReport


def _hw(ram=32, vram=8):
    return HardwareReport(
        os="Linux", architecture="x86_64", ram_gb=ram, vram_gb=vram,
        cpu_features=[], disk_free_gb=500, metal=False, unified_memory=False,
    )


def _make_bundle(overrides=None):
    data = {
        "id": "test-val",
        "name": "Test Val",
        "roles": {
            "envoy": {"model": "gemma3n:e2b"},
            "builder": {"model": "qwen2.5-coder:7b"},
        },
        "requirements": {"min_ram_gb": 8, "min_vram_gb": 0},
        "commercial_safe": True,
        "license_notes": "Apache-2.0",
    }
    if overrides:
        data.update(overrides)
    return ForgeBundle.model_validate(data)


class TestAllTemplatesValidate:
    def test_all_templates_pass_validation(self):
        results = validate_all_templates()
        for template_id, result in results.items():
            assert result.passed, f"{template_id} failed: {result.errors}"


class TestSchemaValidation:
    def test_valid_bundle_passes(self):
        bundle = _make_bundle()
        result = validate_bundle(bundle)
        assert result.passed

    def test_unsafe_model_id_fails(self):
        bundle = _make_bundle(overrides={
            "roles": {
                "envoy": {"model": "../../etc/passwd"},
                "builder": {"model": "qwen2.5-coder:7b"},
            }
        })
        result = validate_bundle(bundle)
        assert not result.passed
        assert any("unsafe" in e.lower() or "invalid" in e.lower() for e in result.errors)

    def test_command_injection_fails(self):
        bundle = _make_bundle(overrides={
            "roles": {
                "envoy": {"model": "qwen2.5-coder:7b; rm -rf /"},
                "builder": {"model": "qwen2.5-coder:7b"},
            }
        })
        result = validate_bundle(bundle)
        assert not result.passed

    def test_missing_license_notes_warns(self):
        bundle = _make_bundle(overrides={"license_notes": ""})
        result = validate_bundle(bundle)
        assert any("license" in w.lower() for w in result.warnings)


class TestLicenseValidation:
    def test_non_commercial_model_in_commercial_bundle_fails(self):
        bundle = _make_bundle(overrides={
            "roles": {
                "envoy": {"model": "gemma3n:e2b"},
                "builder": {"model": "stabilityai/sdxl-turbo"},
            },
            "optional": {},
            "commercial_safe": True,
        })
        result = validate_bundle(bundle)
        assert not result.passed
        assert any("non-commercial" in e.lower() or "commercial_safe" in e.lower() for e in result.errors)

    def test_non_commercial_model_allowed_when_not_commercial(self):
        bundle = _make_bundle(overrides={
            "roles": {
                "envoy": {"model": "gemma3n:e2b"},
                "builder": {"model": "stabilityai/sdxl-turbo"},
            },
            "optional": {},
            "commercial_safe": False,
        })
        result = validate_bundle(bundle)
        assert result.passed


class TestHardwareValidation:
    def test_insufficient_ram_fails(self):
        bundle = _make_bundle(overrides={
            "requirements": {"min_ram_gb": 64, "min_vram_gb": 0}
        })
        result = validate_bundle(bundle, hardware=_hw(ram=8))
        assert not result.passed
        assert any("ram" in e.lower() for e in result.errors)

    def test_insufficient_vram_fails(self):
        bundle = _make_bundle(overrides={
            "requirements": {"min_ram_gb": 8, "min_vram_gb": 20}
        })
        result = validate_bundle(bundle, hardware=_hw(ram=32, vram=4))
        assert not result.passed
        assert any("vram" in e.lower() for e in result.errors)


class TestValidateFile:
    def test_validate_file_passes_for_valid_yaml(self, tmp_path):
        bundle = _make_bundle()
        path = tmp_path / "bundle.yaml"
        path.write_text(yaml.safe_dump(bundle.model_dump(mode="json")), encoding="utf-8")
        result = validate_file(path)
        assert result.passed

    def test_validate_file_fails_for_invalid_yaml(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("id: bad\nroles: {}\n", encoding="utf-8")
        result = validate_file(path)
        assert not result.passed

    def test_validate_file_template_id(self):
        result = validate_template("game-dev-lite")
        assert result.passed


class TestUnknownModelWarning:
    def test_unknown_model_produces_warning(self):
        bundle = _make_bundle(overrides={
            "roles": {
                "envoy": {"model": "unknown-future-model:99b"},
                "builder": {"model": "qwen2.5-coder:7b"},
            }
        })
        result = validate_bundle(bundle)
        assert any("not found in catalog" in w.lower() for w in result.warnings)
