from __future__ import annotations

from dataclasses import dataclass

from ..models import ModelSpec
from .base import Provider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatibleProvider


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    label: str
    base_url: str
    api_key_env: str | None
    kind: str
    notes: str


PRESETS: dict[str, ProviderPreset] = {
    "ollama": ProviderPreset(
        "ollama", "Ollama (local, quota-free)", "http://127.0.0.1:11434",
        None, "local", "Default backend. No API key. Cloud-untouched.",
    ),
    "openai": ProviderPreset(
        "openai", "OpenAI (cloud, metered)", "https://api.openai.com/v1",
        "OPENAI_API_KEY", "cloud", "GPT-class tool-capable models.",
    ),
    "anthropic": ProviderPreset(
        "anthropic", "Anthropic (cloud, metered)", "https://api.anthropic.com/v1",
        "ANTHROPIC_API_KEY", "cloud",
        "Claude-class. Native protocol differs; OpenAI-compat gateway required for this adapter.",
    ),
    "openrouter": ProviderPreset(
        "openrouter", "OpenRouter (cloud, metered)", "https://openrouter.ai/api/v1",
        "OPENROUTER_API_KEY", "cloud", "Aggregator; routes to many model families.",
    ),
    "zai-glm": ProviderPreset(
        "zai-glm", "Z.ai / GLM (cloud, metered)", "https://open.bigmodel.cn/api/paas/v4",
        "ZAI_API_KEY", "cloud", "GLM-class tool-capable models.",
    ),
    "grok": ProviderPreset(
        "grok", "Grok / xAI (cloud, metered)", "https://api.x.ai/v1",
        "XAI_API_KEY", "cloud", "Grok-class models.",
    ),
    "gemini": ProviderPreset(
        "gemini", "Google / Gemini (cloud, metered)",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "GEMINI_API_KEY", "cloud", "Gemini via Google's OpenAI-compat endpoint.",
    ),
    "mistral": ProviderPreset(
        "mistral", "Mistral (cloud, metered)", "https://api.mistral.ai/v1",
        "MISTRAL_API_KEY", "cloud", "Mistral-class tool-capable models.",
    ),
    "deepseek": ProviderPreset(
        "deepseek", "DeepSeek (cloud, metered)", "https://api.deepseek.com/v1",
        "DEEPSEEK_API_KEY", "cloud", "DeepSeek-class reasoning/coding models.",
    ),
    "llama-cpp": ProviderPreset(
        "llama-cpp", "llama.cpp / LM Studio (local)", "http://127.0.0.1:1234/v1",
        None, "local", "Any OpenAI-compat local server. No API key.",
    ),
}


def preset(preset_id: str) -> ProviderPreset | None:
    return PRESETS.get(preset_id)


def spec_from_preset(preset_id: str, model: str, role: str = "controller",
                     context_window: int = 32768, tool_capable: bool = True) -> ModelSpec:
    p = PRESETS[preset_id]
    return ModelSpec(
        provider="ollama" if p.kind == "local" and preset_id == "ollama" else "openai-compat",
        model=model, role=role, base_url=p.base_url,
        api_key_env=p.api_key_env, context_window=context_window,
        tool_capable=tool_capable,
    )


def create_provider_from_preset(preset_id: str, model: str, **kwargs) -> Provider:
    if preset_id == "ollama":
        return OllamaProvider(spec_from_preset("ollama", model, **kwargs))
    return OpenAICompatibleProvider(spec_from_preset(preset_id, model, **kwargs))


__all__ = ["PRESETS", "ProviderPreset", "create_provider_from_preset", "preset", "spec_from_preset"]
