from __future__ import annotations

import httpx

from .base import Message, Provider


class OllamaProvider(Provider):
    def complete(self, messages: list[Message], schema: dict | None = None) -> str:
        base = (self.spec.base_url or "http://127.0.0.1:11434").rstrip("/")
        payload = {
            "model": self.spec.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.spec.keep_alive,
            "options": self.spec.options,
        }
        if schema:
            payload["format"] = schema
        response = httpx.post(f"{base}/api/chat", json=payload, timeout=600)
        response.raise_for_status()
        return response.json()["message"]["content"]

    def unload(self) -> None:
        base = (self.spec.base_url or "http://127.0.0.1:11434").rstrip("/")
        try:
            httpx.post(
                f"{base}/api/generate",
                json={"model": self.spec.model, "keep_alive": 0},
                timeout=30,
            ).raise_for_status()
        except httpx.HTTPError:
            pass

