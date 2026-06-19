from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..models import ModelSpec

Message = dict[str, Any]


@dataclass
class ProviderCapabilities:
    supports_tools: bool = False
    supports_streaming: bool = False
    supports_vision: bool = False
    supports_json_schema: bool = False
    max_context_window: int = 32768
    tags: list[str] = field(default_factory=list)


class Provider(ABC):
    def __init__(self, spec: ModelSpec):
        self.spec = spec
        self._cancelled = False

    @abstractmethod
    def complete(self, messages: list[Message], schema: dict[str, Any] | None = None) -> str:
        raise NotImplementedError

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(max_context_window=self.spec.context_window)

    def list_models(self) -> list[str]:
        return []

    def health(self) -> bool:
        return False

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0

    def cancel(self) -> None:
        self._cancelled = True

    def load(self) -> None:
        pass

    def unload(self) -> None:
        pass
