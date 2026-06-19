from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import ModelSpec


Message = dict[str, Any]


class Provider(ABC):
    def __init__(self, spec: ModelSpec):
        self.spec = spec

    @abstractmethod
    def complete(self, messages: list[Message], schema: dict[str, Any] | None = None) -> str:
        raise NotImplementedError

    def unload(self) -> None:
        """Backends may override this to release model memory."""

