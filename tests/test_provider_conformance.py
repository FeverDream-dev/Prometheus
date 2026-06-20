from __future__ import annotations

from unittest import mock

import httpx
import pytest

from prometheus_cli.providers import create_provider_from_preset
from prometheus_cli.providers.base import ProviderCapabilities
from prometheus_cli.providers.presets import PRESETS, preset


REQUIRED_PRESETS = {
    "ollama", "openai", "anthropic", "openrouter", "zai-glm",
    "grok", "gemini", "mistral", "deepseek", "llama-cpp",
}


def test_all_eleven_required_presets_present():
    missing = REQUIRED_PRESETS - set(PRESETS)
    assert not missing, f"missing provider presets: {missing}"


def test_every_preset_has_label_and_endpoint():
    for pid, p in PRESETS.items():
        assert p.label, pid
        assert p.base_url.startswith("http"), pid
        assert p.kind in {"local", "cloud"}, pid


def test_local_presets_carry_no_api_key_env():
    assert PRESETS["ollama"].api_key_env is None
    assert PRESETS["llama-cpp"].api_key_env is None


@pytest.mark.parametrize("preset_id", sorted(REQUIRED_PRESETS - {"ollama"}))
def test_conformance_complete_returns_content(preset_id, monkeypatch):
    if PRESETS[preset_id].api_key_env:
        monkeypatch.setenv(PRESETS[preset_id].api_key_env, "fake-key")
    provider = create_provider_from_preset(preset_id, "test-model")
    fake = httpx.Response(
        200,
        json={"choices": [{"message": {"content": "{\"status\":\"working\"}"}}]},
        request=httpx.Request("POST", PRESETS[preset_id].base_url + "/chat/completions"),
    )
    with mock.patch("httpx.post", return_value=fake):
        out = provider.complete([{"role": "user", "content": "hi"}])
    assert "working" in out


@pytest.mark.parametrize("preset_id", sorted(REQUIRED_PRESETS - {"ollama"}))
def test_conformance_list_models(preset_id, monkeypatch):
    if PRESETS[preset_id].api_key_env:
        monkeypatch.setenv(PRESETS[preset_id].api_key_env, "fake-key")
    provider = create_provider_from_preset(preset_id, "test-model")
    fake = httpx.Response(
        200,
        json={"data": [{"id": "alpha"}, {"id": "beta"}]},
        request=httpx.Request("GET", PRESETS[preset_id].base_url + "/models"),
    )
    with mock.patch("httpx.get", return_value=fake):
        assert provider.list_models() == ["alpha", "beta"]


@pytest.mark.parametrize("preset_id", sorted(REQUIRED_PRESETS - {"ollama"}))
def test_conformance_health(preset_id, monkeypatch):
    if PRESETS[preset_id].api_key_env:
        monkeypatch.setenv(PRESETS[preset_id].api_key_env, "fake-key")
    provider = create_provider_from_preset(preset_id, "test-model")
    ok = httpx.Response(200, request=httpx.Request("GET", PRESETS[preset_id].base_url + "/models"))
    down = httpx.Response(503, request=httpx.Request("GET", PRESETS[preset_id].base_url + "/models"))
    with mock.patch("httpx.get", return_value=ok):
        assert provider.health() is True
    with mock.patch("httpx.get", return_value=down):
        assert provider.health() is False


@pytest.mark.parametrize("preset_id", sorted(REQUIRED_PRESETS - {"ollama"}))
def test_conformance_capabilities_and_metadata(preset_id, monkeypatch):
    if PRESETS[preset_id].api_key_env:
        monkeypatch.setenv(PRESETS[preset_id].api_key_env, "fake-key")
    provider = create_provider_from_preset(preset_id, "test-model", tool_capable=True)
    caps = provider.capabilities()
    assert isinstance(caps, ProviderCapabilities)
    assert caps.supports_json_schema is True
    assert caps.max_context_window > 0
    provider.cancel()
    provider.load()
    provider.unload()


@pytest.mark.parametrize("preset_id", sorted(REQUIRED_PRESETS - {"ollama"}))
def test_conformance_structured_json_passthrough(preset_id, monkeypatch):
    if PRESETS[preset_id].api_key_env:
        monkeypatch.setenv(PRESETS[preset_id].api_key_env, "fake-key")
    provider = create_provider_from_preset(preset_id, "test-model")

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json["response_format"]["type"] == "json_schema"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "{\"ok\":true}"}}]},
            request=httpx.Request("POST", url),
        )

    with mock.patch("httpx.post", side_effect=fake_post):
        out = provider.complete([{"role": "user", "content": "x"}], schema={"type": "object"})
    assert "ok" in out


def test_conformance_health_returns_false_on_network_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    provider = create_provider_from_preset("openai", "test-model")
    with mock.patch("httpx.get", side_effect=httpx.ConnectError("no")):
        assert provider.health() is False
        assert provider.list_models() == []


def test_preset_lookup_by_id():
    assert preset("openai").label.startswith("OpenAI")
    assert preset("nonexistent") is None
