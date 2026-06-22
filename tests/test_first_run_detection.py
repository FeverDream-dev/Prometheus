from __future__ import annotations

from unittest import mock


from prometheus_cli.first_run import FirstRunState, detect_first_run
from prometheus_cli.onboarding import OllamaStatus


def _ollama(running=True, models=None, installed=True):
    return OllamaStatus(installed=installed, running=running, models=models or [], install_hint="")


class TestFirstRunDetection:
    def test_fresh_install_is_first_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr("prometheus_cli.config.CONFIG_HOME", tmp_path / "home")
        monkeypatch.chdir(tmp_path)
        with mock.patch("prometheus_cli.onboarding.check_ollama", return_value=_ollama(running=False, models=[])):
            state = detect_first_run(home=tmp_path / "home", workspace=tmp_path)
        assert state.is_first_run is True
        assert state.has_config is False
        assert state.has_active_bundle is False

    def test_with_config_is_not_first_run(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        (home / "config.yaml").write_text(
            "mode: pilot\nactive_bundle_id: spark-cpu-8gb\n", encoding="utf-8"
        )
        monkeypatch.setattr("prometheus_cli.config.CONFIG_HOME", home)
        with mock.patch("prometheus_cli.onboarding.check_ollama", return_value=_ollama(models=["granite4.1:3b"])):
            state = detect_first_run(home=home, workspace=tmp_path)
        assert state.is_first_run is False
        assert state.has_config is True
        assert state.has_active_bundle is True

    def test_config_but_no_bundle_is_first_run(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        (home / "config.yaml").write_text("mode: pilot\n", encoding="utf-8")
        with mock.patch("prometheus_cli.onboarding.check_ollama", return_value=_ollama(models=[])):
            state = detect_first_run(home=home, workspace=tmp_path)
        assert state.is_first_run is True
        assert state.has_config is True
        assert state.has_active_bundle is False

    def test_detects_ollama_missing(self, tmp_path):
        state = detect_first_run(
            home=tmp_path / "home", workspace=tmp_path,
            ollama_status=_ollama(installed=False, running=False, models=[]),
        )
        assert state.ollama_installed is False
        assert state.ollama_running is False
        assert state.needs_ollama_setup is True

    def test_detects_ollama_stopped(self, tmp_path):
        state = detect_first_run(
            home=tmp_path / "home", workspace=tmp_path,
            ollama_status=_ollama(installed=True, running=False, models=[]),
        )
        assert state.ollama_installed is True
        assert state.ollama_running is False
        assert state.needs_ollama_setup is True

    def test_detects_no_models(self, tmp_path):
        state = detect_first_run(
            home=tmp_path / "home", workspace=tmp_path,
            ollama_status=_ollama(running=True, models=[]),
        )
        assert state.has_models is False
        assert state.model_count == 0
        assert state.needs_ollama_setup is True

    def test_detects_has_models(self, tmp_path):
        state = detect_first_run(
            home=tmp_path / "home", workspace=tmp_path,
            ollama_status=_ollama(running=True, models=["granite4.1:3b", "qwen2.5-coder:7b"]),
        )
        assert state.has_models is True
        assert state.model_count == 2
        assert state.needs_ollama_setup is False

    def test_detects_git_repo(self, tmp_path):
        (tmp_path / ".git").mkdir()
        state = detect_first_run(home=tmp_path / "home", workspace=tmp_path, ollama_status=_ollama())
        assert state.has_git_repo is True

    def test_detects_no_git_repo(self, tmp_path):
        state = detect_first_run(home=tmp_path / "home", workspace=tmp_path, ollama_status=_ollama())
        assert state.has_git_repo is False

    def test_detects_memory_file(self, tmp_path):
        mem_dir = tmp_path / ".prometheus"
        mem_dir.mkdir()
        (mem_dir / "memory.md").write_text("# Memory\n", encoding="utf-8")
        state = detect_first_run(home=tmp_path / "home", workspace=tmp_path, ollama_status=_ollama())
        assert state.has_memory is True

    def test_detects_no_memory(self, tmp_path):
        state = detect_first_run(home=tmp_path / "home", workspace=tmp_path, ollama_status=_ollama())
        assert state.has_memory is False


class TestGuidance:
    def test_fresh_install_guidance(self, tmp_path):
        state = FirstRunState(has_config=False, has_active_bundle=False, ollama_installed=False)
        assert state.guidance == "first_run_full"
        assert "setup" in state.next_action.lower()

    def test_no_config_guidance(self, tmp_path):
        state = FirstRunState(has_config=False, has_active_bundle=False, ollama_installed=True, ollama_running=True, has_models=True)
        assert state.guidance == "first_run_select_bundle"

    def test_no_models_guidance(self, tmp_path):
        state = FirstRunState(
            has_config=True, has_active_bundle=True,
            ollama_installed=True, ollama_running=True, has_models=False,
            recommended_bundle="ember-8gb", recommended_models=["qwen2.5-coder:7b"],
        )
        assert state.guidance == "no_models"
        assert "pull" in state.next_action.lower()

    def test_ollama_down_guidance(self, tmp_path):
        state = FirstRunState(
            has_config=True, has_active_bundle=True,
            ollama_installed=True, ollama_running=False, has_models=False,
        )
        assert state.guidance == "ollama_down"
        assert "ollama" in state.next_action.lower()

    def test_ready_guidance(self, tmp_path):
        state = FirstRunState(
            has_config=True, has_active_bundle=True,
            ollama_installed=True, ollama_running=True, has_models=True,
            has_git_repo=True, has_memory=True,
        )
        assert state.guidance == "ready"

    def test_no_model_message_not_deadend(self):
        state = FirstRunState(
            has_models=False,
            recommended_bundle="ember-8gb",
            recommended_models=["qwen2.5-coder:7b"],
        )
        msg = state.no_model_message
        assert "no models" in msg.lower()
        assert "ember-8gb" in msg
        assert "pull" in msg.lower()
