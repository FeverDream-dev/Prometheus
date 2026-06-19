from __future__ import annotations

import os

import httpx

from .base import Message, Provider, ProviderCapabilities


class OpenAICompatibleProvider(Provider):
    def _headers(self) -> dict[str, str]:
        key = os.environ.get(self.spec.api_key_env or "", "")
        return {"Authorization": f"Bearer {key}"} if key else {}

    def _endpoint(self) -> str:
        if not self.spec.base_url:
            raise ValueError("base_url is required for OpenAI-compatible providers")
        return self.spec.base_url.rstrip("/")

    def complete(self, messages: list[Message], schema: dict | None = None) -> str:
        self._cancelled = False
        payload = {"model": self.spec.model, "messages": messages, "stream": False}
        if schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "agent_turn", "schema": schema},
            }
        response = httpx.post(
            f"{self._endpoint()}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=600,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=self.spec.tool_capable,
            supports_streaming=True,
            supports_json_schema=True,
            max_context_window=self.spec.context_window,
            tags=["cloud"] if self.spec.api_key_env else ["local"],
        )

    def list_models(self) -> list[str]:
        try:
            response = httpx.get(
                f"{self._endpoint()}/models",
                headers=self._headers(),
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
            return [m.get("id", "") for m in data.get("data", [])]
        except (httpx.HTTPError, ValueError):
            return []

    def health(self) -> bool:
        try:
            response = httpx.get(
                f"{self._endpoint()}/models",
                headers=self._headers(),
                timeout=3.0,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False
