from __future__ import annotations

import json

import httpx

from prometheus_cli.bundles import load_registry
from prometheus_cli.qualification import qualify_bundle, qualify_model


class FakeClient:
    def __init__(self, response_overrides):
        self._overrides = response_overrides
        self.calls: list[dict] = []

    def post(self, url, json=None, **_):
        self.calls.append(json or {})
        key = self._match(json or {})
        value = self._overrides.get(key, {})
        if isinstance(value, Exception):
            raise value

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
        if "get_weather" in text or payload.get("tools"):
            return "tool"
        if "def add" in text or "add(a" in text:
            return "code"
        return "chat"


def _resp(content: str, tool_calls=None) -> dict:
    msg = {"role": "assistant", "content": content}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return {"message": msg}


def test_qualify_model_all_pass():
    client = FakeClient({
        "chat": _resp("hello"),
        "json": _resp(json.dumps({"status": "ok", "value": 42})),
        "tool": _resp("", tool_calls=[{"function": {"name": "get_weather", "arguments": '{"city":"Paris"}'}}]),
        "code": _resp("def add(a, b):\n    return a + b\n"),
    })
    report = qualify_model("x", "http://u", client=client)
    assert report.passed is True
    assert report.passed_count == 4
    assert {r.name for r in report.results} == {"chat", "structured_output", "single_tool", "code_patch"}


def test_qualify_model_structured_output_fail_on_non_json():
    client = FakeClient({"chat": _resp("hi"), "json": _resp("not json at all"), "tool": _resp(""), "code": _resp("")})
    report = qualify_model("x", "http://u", client=client)
    json_result = next(r for r in report.results if r.name == "structured_output")
    assert json_result.passed is False
    assert report.passed is False


def test_qualify_model_tool_fail_without_tool_calls():
    client = FakeClient({"chat": _resp("hi"), "json": _resp('{"status":"ok"}'), "tool": _resp("The weather in Paris is sunny"), "code": _resp("")})
    report = qualify_model("x", "http://u", client=client)
    tool_result = next(r for r in report.results if r.name == "single_tool")
    assert tool_result.passed is False


def test_qualify_model_handles_http_error():
    client = FakeClient({})
    client.post = lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("no", request=httpx.Request("POST", "x")))
    report = qualify_model("x", "http://u", client=client)
    assert report.passed is False
    assert all(not r.passed for r in report.results)


def test_qualify_bundle_skips_add_on():
    vt = next(b for b in load_registry() if b.id == "vibethinker-review-addon")
    report = qualify_bundle(vt, "http://u", client=FakeClient({}))
    assert report.passed is True
    assert report.results[0].name == "skip"


def test_qualify_bundle_uses_controller_model():
    spark = next(b for b in load_registry() if b.id == "spark-cpu-8gb")
    client = FakeClient({
        "chat": _resp("hello"),
        "json": _resp('{"status":"ok"}'),
        "code": _resp("def add(a, b):\n    return a + b\n"),
    })
    report = qualify_bundle(spark, "http://u", client=client)
    assert report.model == "granite4.1:3b"
    assert all(c["model"] == "granite4.1:3b" for c in client.calls)


def test_as_dict_shape():
    client = FakeClient({"chat": _resp("hi"), "json": _resp('{"status":"ok"}'), "tool": _resp(""), "code": _resp("")})
    d = qualify_model("m", "http://u", client=client).as_dict()
    assert d["model"] == "m"
    assert "passed" in d and "results" in d
