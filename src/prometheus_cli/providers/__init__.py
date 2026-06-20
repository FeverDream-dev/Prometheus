from .base import Provider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatibleProvider
from .presets import PRESETS, create_provider_from_preset


def create_provider(spec) -> Provider:
    if spec.provider == "ollama":
        return OllamaProvider(spec)
    return OpenAICompatibleProvider(spec)


__all__ = ["PRESETS", "Provider", "create_provider", "create_provider_from_preset"]

