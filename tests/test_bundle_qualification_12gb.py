"""12 GB class bundle qualification (mocked — no Ollama required)."""
from __future__ import annotations

import json

from prometheus_cli.bundles import find_bundle
from prometheus_cli.qualification import qualify_bundle


class FakeClient:
    def __init__(self, response_overrides):
        self._overrides = response_overrides

    def post(self, url, json=None, **_):
        key = self._match(json or {})
        value = self._overrides.get(key, {})

        class R:
            status_code = 200

            def json(self_inner):
                return value

        return R()

    def close(self):
        pass

    @staticmethod
    def _match(payload):
        msgs = payload.get("messages", [])
        text = " ".join(m.get("content", "") for m in msgs).lower()
        if "json" in payload.get("format", "") or "json" in text and "value" in text:
            return "json"
        if payload.get("tools"):
            return "tool"
        if "def add" in text:
            return "code"
        return "chat"


def _resp(content: str, tool_calls=None) -> dict:
    msg = {"role": "assistant", "content": content}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return {"message": msg}


def test_forge_12gb_bundle_exists():
    bundle = find_bundle("forge-12gb")
    assert bundle is not None
    assert bundle.id == "forge-12gb"


def test_forge_12gb_qualifies_with_mock_client():
    bundle = find_bundle("forge-12gb")
    assert bundle is not None
    client = FakeClient({
        "chat": _resp("hello"),
        "json": _resp(json.dumps({"status": "ok", "value": 42})),
        "tool": _resp("", tool_calls=[{"function": {"name": "get_weather", "arguments": "{}"}}]),
        "code": _resp("def add(a, b):\n    return a + b\n"),
    })
    report = qualify_bundle(bundle, "http://u", client=client)
    assert report.passed_count >= 1


def test_forge_12gb_targets_12gb_vram_class():
    bundle = find_bundle("forge-12gb")
    assert bundle is not None
    assert bundle.hardware.minimum_vram_gb >= 8
    assert bundle.hardware.recommended_vram_gb is None or bundle.hardware.recommended_vram_gb <= 16
