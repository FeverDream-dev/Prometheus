from __future__ import annotations

from pathlib import Path

import pytest

from prometheus_cli.tui_screens import (
    WIZARD_STEPS,
    _setup_wizard_step_text,
    strip_markup,
)
from prometheus_cli.tui_state import collect_demo_snapshot


@pytest.fixture(scope="module")
def snap():
    return collect_demo_snapshot(Path("/tmp"))


class TestWizardStepsConfig:
    def test_wizard_has_9_steps(self):
        assert len(WIZARD_STEPS) == 9

    def test_step_names_match_spec(self):
        assert WIZARD_STEPS[0] == "Welcome"
        assert WIZARD_STEPS[1] == "Project folder"
        assert WIZARD_STEPS[2] == "Hardware scan"
        assert WIZARD_STEPS[3] == "Ollama status"
        assert WIZARD_STEPS[4] == "Bundle recommendation"
        assert WIZARD_STEPS[5] == "Bundle choice"
        assert WIZARD_STEPS[6] == "Model pull / validate"
        assert WIZARD_STEPS[7] == "Git & memory setup"
        assert WIZARD_STEPS[8] == "Ready to code"


class TestStepContent:
    @pytest.mark.parametrize("step", range(9))
    def test_every_step_produces_content(self, step, snap):
        lines = _setup_wizard_step_text(step, snap)
        assert len(lines) >= 3, f"Step {step} ({WIZARD_STEPS[step]}) produced only {len(lines)} lines"

    def test_welcome_mentions_prometheus(self, snap):
        lines = _setup_wizard_step_text(0, snap)
        joined = " ".join(lines).lower()
        assert "prometheus" in joined

    def test_project_folder_shows_path(self, snap):
        lines = _setup_wizard_step_text(1, snap)
        joined = strip_markup(" ".join(str(line) for line in lines))
        assert "path" in joined.lower()

    def test_hardware_shows_ram(self, snap):
        lines = _setup_wizard_step_text(2, snap)
        joined = strip_markup(" ".join(str(line) for line in lines))
        assert "ram" in joined.lower()

    def test_ollama_shows_status(self, snap):
        lines = _setup_wizard_step_text(3, snap)
        joined = strip_markup(" ".join(str(line) for line in lines))
        assert "ollama" in joined.lower()

    def test_recommendation_shows_bundle(self, snap):
        lines = _setup_wizard_step_text(4, snap)
        joined = strip_markup(" ".join(str(line) for line in lines))
        assert "bundle" in joined.lower() or "recommended" in joined.lower()

    def test_bundle_choice_shows_available(self, snap):
        lines = _setup_wizard_step_text(5, snap)
        joined = strip_markup(" ".join(str(line) for line in lines))
        assert "bundle" in joined.lower()

    def test_pull_step_mentions_confirmation(self, snap):
        lines = _setup_wizard_step_text(6, snap)
        joined = strip_markup(" ".join(str(line) for line in lines)).lower()
        assert "confirm" in joined or "pull" in joined or "download" in joined

    def test_git_memory_step_shows_git(self, snap):
        lines = _setup_wizard_step_text(7, snap)
        joined = strip_markup(" ".join(str(line) for line in lines)).lower()
        assert "git" in joined

    def test_git_memory_step_shows_memory(self, snap):
        lines = _setup_wizard_step_text(7, snap)
        joined = strip_markup(" ".join(str(line) for line in lines)).lower()
        assert "memory" in joined

    def test_ready_step_mentions_coding(self, snap):
        lines = _setup_wizard_step_text(8, snap)
        joined = strip_markup(" ".join(str(line) for line in lines)).lower()
        assert "code" in joined or "objective" in joined or "enter" in joined


class TestSetupScreenRendersAllSteps:
    def test_setup_screen_renders_all_9_steps(self, snap):
        from prometheus_cli.tui_screens import render_screen_text
        text = render_screen_text("/setup", snap)
        for i, name in enumerate(WIZARD_STEPS):
            clean = strip_markup(name).lower()
            assert clean in text.lower(), f"Step {i} '{name}' not found in /setup screen text"

    def test_setup_screen_has_step_numbers(self, snap):
        from prometheus_cli.tui_screens import render_screen_text
        text = render_screen_text("/setup", snap)
        for i in range(1, 10):
            assert f"Step {i}" in text or f"step {i}" in text.lower()
