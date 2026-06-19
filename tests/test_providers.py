from __future__ import annotations

from unittest import mock

import httpx

from prometheus_cli.models import ModelSpec
from prometheus_cli.providers.ollama import OllamaProvider
from prometheus_cli.providers.openai_compat import OpenAICompatibleProvider


def _ollama_spec():
    return ModelSpec(
        provider="ollama", model="gemma3:4b", role="controller",
        context_window=16384, tool_capable=True,
    )


def _cloud_spec():
    return ModelSpec(
        provider="openrouter", model="claude-sonnet-4", role="controller",
        base_url="https://openrouter.ai/api/v1", api_key_env="OPENROUTER_API_KEY",
        context_window=200000, tool_capable=True,
    )


def _response(status_code=200, json_data=None):
    request = httpx.Request("GET", "http://localhost")
    return httpx.Response(status_code, json=json_data or {}, request=request)


class TestProviderCapabilities:
    def test_ollama_capabilities(self):
        provider = OllamaProvider(_ollama_spec())
        caps = provider.capabilities()
        assert caps.supports_tools is True
        assert caps.supports_streaming is True
        assert caps.supports_json_schema is True
        assert caps.max_context_window == 16384
        assert "local" in caps.tags

    def test_cloud_capabilities(self):
        provider = OpenAICompatibleProvider(_cloud_spec())
        caps = provider.capabilities()
        assert caps.supports_tools is True
        assert "cloud" in caps.tags

    def test_non_tool_model_capabilities(self):
        spec = ModelSpec(provider="ollama", model="vibethinker", role="reviewer", tool_capable=False)
        provider = OllamaProvider(spec)
        caps = provider.capabilities()
        assert caps.supports_tools is False


class TestOllamaHealth:
    def test_health_true_when_reachable(self):
        provider = OllamaProvider(_ollama_spec())
        with mock.patch("httpx.get", return_value=_response(200)):
            assert provider.health() is True

    def test_health_false_when_unreachable(self):
        provider = OllamaProvider(_ollama_spec())
        with mock.patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            assert provider.health() is False


class TestOllamaListModels:
    def test_returns_model_names(self):
        provider = OllamaProvider(_ollama_spec())
        payload = {"models": [{"name": "gemma3:4b"}, {"name": "qwen3:8b"}]}
        with mock.patch("httpx.get", return_value=_response(200, payload)):
            models = provider.list_models()
            assert models == ["gemma3:4b", "qwen3:8b"]

    def test_returns_empty_on_error(self):
        provider = OllamaProvider(_ollama_spec())
        with mock.patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            assert provider.list_models() == []


class TestOllamaLoadUnload:
    def test_load_sends_keep_alive(self):
        provider = OllamaProvider(_ollama_spec())
        with mock.patch("httpx.post", return_value=_response(200)) as mock_post:
            provider.load()
            assert mock_post.called
            call_args = mock_post.call_args
            assert call_args[1]["json"]["keep_alive"] == "5m"

    def test_unload_sends_zero_keep_alive(self):
        provider = OllamaProvider(_ollama_spec())
        with mock.patch("httpx.post", return_value=_response(200)) as mock_post:
            provider.unload()
            call_args = mock_post.call_args
            assert call_args[1]["json"]["keep_alive"] == 0

    def test_load_swallows_errors(self):
        provider = OllamaProvider(_ollama_spec())
        with mock.patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            provider.load()


class TestCloudHealth:
    def test_health_true_with_valid_key(self):
        provider = OpenAICompatibleProvider(_cloud_spec())
        with mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-test"}), \
             mock.patch("httpx.get", return_value=_response(200)):
            assert provider.health() is True

    def test_health_false_on_connection_error(self):
        provider = OpenAICompatibleProvider(_cloud_spec())
        with mock.patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            assert provider.health() is False


class TestCloudListModels:
    def test_returns_model_ids(self):
        provider = OpenAICompatibleProvider(_cloud_spec())
        payload = {"data": [{"id": "claude-sonnet-4"}, {"id": "gpt-4o"}]}
        with mock.patch("httpx.get", return_value=_response(200, payload)):
            models = provider.list_models()
            assert models == ["claude-sonnet-4", "gpt-4o"]


class TestCancel:
    def test_cancel_sets_flag(self):
        provider = OllamaProvider(_ollama_spec())
        assert provider._cancelled is False
        provider.cancel()
        assert provider._cancelled is True


class TestEstimateCost:
    def test_local_cost_is_zero(self):
        provider = OllamaProvider(_ollama_spec())
        assert provider.estimate_cost(input_tokens=1000, output_tokens=500) == 0.0
