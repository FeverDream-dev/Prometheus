from __future__ import annotations

import httpx

from .base import Message, Provider, ProviderCapabilities


class OllamaProvider(Provider):
    def _base(self) -> str:
        return (self.spec.base_url or "http://127.0.0.1:11434").rstrip("/")

    def complete(self, messages: list[Message], schema: dict | None = None) -> str:
        self._cancelled = False
        payload = {
            "model": self.spec.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.spec.keep_alive,
            "options": self.spec.options,
        }
        if schema:
            payload["format"] = schema
        response = httpx.post(f"{self._base()}/api/chat", json=payload, timeout=600)
        response.raise_for_status()
        return response.json()["message"]["content"]

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=self.spec.tool_capable,
            supports_streaming=True,
            supports_json_schema=True,
            max_context_window=self.spec.context_window,
            tags=["local", "ollama"],
        )

    def list_models(self) -> list[str]:
        try:
            response = httpx.get(f"{self._base()}/api/tags", timeout=5.0)
            response.raise_for_status()
            data = response.json()
            return [m.get("name", "") for m in data.get("models", [])]
        except (httpx.HTTPError, ValueError):
            return []

    def health(self) -> bool:
        try:
            response = httpx.get(f"{self._base()}/api/tags", timeout=3.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def load(self) -> None:
        try:
            httpx.post(
                f"{self._base()}/api/generate",
                json={"model": self.spec.model, "keep_alive": self.spec.keep_alive, "prompt": ""},
                timeout=60,
            )
        except httpx.HTTPError:
            pass

    def unload(self) -> None:
        try:
            httpx.post(
                f"{self._base()}/api/generate",
                json={"model": self.spec.model, "keep_alive": 0},
                timeout=30,
            )
        except httpx.HTTPError:
            pass
