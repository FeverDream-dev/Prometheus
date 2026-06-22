from __future__ import annotations



from prometheus_cli.bundleforge.wizard import WizardAnswers, run_wizard, save_bundle
from prometheus_cli.hardware import HardwareReport


def _hw(ram=16, vram=0):
    return HardwareReport(
        os="Linux", architecture="x86_64", ram_gb=ram, vram_gb=vram,
        cpu_features=[], disk_free_gb=200, metal=False, unified_memory=False,
    )


class TestWizardNonInteractive:
    def test_wizard_with_defaults_returns_bundle(self):
        defaults = WizardAnswers(use_case="web development")
        answers, bundle = run_wizard(defaults=defaults, hardware=_hw(ram=16))
        assert bundle.id
        assert len(bundle.roles) >= 1

    def test_wizard_game_dev(self):
        defaults = WizardAnswers(use_case="I want to build a 2D game")
        answers, bundle = run_wizard(defaults=defaults, hardware=_hw(ram=16, vram=8))
        assert "game" in bundle.use_case or "game" in bundle.id

    def test_wizard_rag(self):
        defaults = WizardAnswers(use_case="I want a RAG assistant for my docs")
        answers, bundle = run_wizard(defaults=defaults, hardware=_hw(ram=16))
        assert "rag" in bundle.id or "rag" in bundle.use_case

    def test_wizard_cpu_only(self):
        defaults = WizardAnswers(use_case="cpu only laptop no gpu")
        answers, bundle = run_wizard(defaults=defaults, hardware=_hw(ram=4, vram=0))
        assert bundle.requirements.min_vram_gb == 0
        assert bundle.requirements.min_ram_gb <= 8


class TestWizardWithCallbacks:
    def test_wizard_uses_prompt_fn(self):
        calls = []

        def prompt_fn(msg, default):
            calls.append(msg)
            return "I want to make a video game"

        def confirm_fn(msg, default):
            return default

        answers, bundle = run_wizard(
            prompt_fn=prompt_fn,
            confirm_fn=confirm_fn,
            hardware=_hw(ram=16, vram=8),
        )
        assert len(calls) >= 1
        assert "game" in bundle.use_case or "game" in bundle.id

    def test_wizard_uses_choice_fn(self):
        def prompt_fn(msg, default):
            return "web development"

        def confirm_fn(msg, default):
            return default

        def choice_fn(msg, options, default_idx):
            return 0

        answers, bundle = run_wizard(
            prompt_fn=prompt_fn,
            confirm_fn=confirm_fn,
            choice_fn=choice_fn,
            hardware=_hw(ram=16, vram=0),
        )
        assert bundle.id


class TestSaveBundle:
    def test_save_creates_bundle_yaml(self, tmp_path):
        defaults = WizardAnswers(use_case="web development")
        _, bundle = run_wizard(defaults=defaults, hardware=_hw())
        path = save_bundle(bundle, tmp_path / "out")
        assert path.is_file()
        assert path.name == "bundle.yaml"

    def test_save_creates_readme(self, tmp_path):
        defaults = WizardAnswers(use_case="web development")
        _, bundle = run_wizard(defaults=defaults, hardware=_hw())
        save_bundle(bundle, tmp_path / "out")
        readme = tmp_path / "out" / "README.md"
        assert readme.is_file()
        assert bundle.name in readme.read_text(encoding="utf-8")

    def test_save_creates_license_notes(self, tmp_path):
        defaults = WizardAnswers(use_case="web development")
        _, bundle = run_wizard(defaults=defaults, hardware=_hw())
        save_bundle(bundle, tmp_path / "out")
        license_file = tmp_path / "out" / "LICENSE_NOTES.md"
        assert license_file.is_file()

    def test_saved_bundle_roundtrips(self, tmp_path):
        from prometheus_cli.bundleforge import load_forge_bundle

        defaults = WizardAnswers(use_case="web development")
        _, bundle = run_wizard(defaults=defaults, hardware=_hw())
        path = save_bundle(bundle, tmp_path / "out")
        loaded = load_forge_bundle(path)
        assert loaded.id == bundle.id
        assert len(loaded.roles) == len(bundle.roles)
