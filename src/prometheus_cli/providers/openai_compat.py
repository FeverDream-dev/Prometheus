from __future__ import annotations

import os

import httpx

from .base import Message, Provider


class OpenAICompatibleProvider(Provider):
    def complete(self, messages: list[Message], schema: dict | None = None) -> str:
        if not self.spec.base_url:
            raise ValueError("base_url is required for OpenAI-compatible providers")
        key = os.environ.get(self.spec.api_key_env or "", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        payload = {"model": self.spec.model, "messages": messages, "stream": False}
        if schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "agent_turn", "schema": schema},
            }
        response = httpx.post(
            f"{self.spec.base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=600,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

