from .base import Provider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatibleProvider


def create_provider(spec) -> Provider:
    if spec.provider == "ollama":
        return OllamaProvider(spec)
    return OpenAICompatibleProvider(spec)


__all__ = ["Provider", "create_provider"]

