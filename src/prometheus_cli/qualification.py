from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

from .bundles import BundleV2


@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class QualificationReport:
    model: str
    results: list[TestResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "passed": self.passed,
            "passed_count": self.passed_count,
            "total": len(self.results),
            "results": [
                {"name": r.name, "passed": r.passed, "detail": r.detail} for r in self.results
            ],
        }


def _post(base_url: str, payload: dict, client: httpx.Client | None = None, timeout: float = 120.0) -> dict:
    cl = client or httpx.Client(timeout=timeout)
    try:
        resp = cl.post(f"{base_url.rstrip('/')}/api/chat", json=payload)
        if resp.status_code != 200:
            return {"_error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        return resp.json()
    except httpx.HTTPError as exc:
        return {"_error": str(exc)}
    finally:
        if client is None:
            cl.close()


def test_chat(model: str, base_url: str, client: httpx.Client | None = None) -> TestResult:
    data = _post(base_url, {
        "model": model, "stream": False,
        "messages": [{"role": "user", "content": "Reply with the single word: hello"}],
    }, client)
    if "_error" in data:
        return TestResult("chat", False, data["_error"])
    content = data.get("message", {}).get("content", "").strip()
    return TestResult("chat", bool(content), repr(content[:60]))


def test_structured_output(model: str, base_url: str, client: httpx.Client | None = None) -> TestResult:
    data = _post(base_url, {
        "model": model, "stream": False, "format": "json",
        "messages": [{"role": "user", "content": "Return JSON with keys 'status' and 'value'. status='ok', value=42"}],
    }, client)
    if "_error" in data:
        return TestResult("structured_output", False, data["_error"])
    content = data.get("message", {}).get("content", "").strip()
    try:
        parsed = json.loads(content)
        ok = isinstance(parsed, dict) and "status" in parsed
        return TestResult("structured_output", ok, repr(content[:80]))
    except ValueError:
        return TestResult("structured_output", False, f"non-JSON: {content[:80]!r}")


def test_single_tool(model: str, base_url: str, client: httpx.Client | None = None) -> TestResult:
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }]
    data = _post(base_url, {
        "model": model, "stream": False, "tools": tools,
        "messages": [{"role": "user", "content": "What is the weather in Paris? Use the tool."}],
    }, client)
    if "_error" in data:
        return TestResult("single_tool", False, data["_error"])
    msg = data.get("message", {})
    tool_calls = msg.get("tool_calls") or []
    if tool_calls:
        return TestResult("single_tool", True, f"{len(tool_calls)} tool call(s)")
    content = msg.get("content", "").lower()
    hinted = any(k in content for k in ("paris", "weather", "get_weather"))
    return TestResult("single_tool", False, "no tool_calls; " + ("text mentioned tool" if hinted else "no tool use"))


def test_code_patch(model: str, base_url: str, client: httpx.Client | None = None) -> TestResult:
    data = _post(base_url, {
        "model": model, "stream": False,
        "messages": [{"role": "user", "content":
            "The function `def add(a,b): return a-b` is wrong. Reply with ONLY the corrected Python function, no prose."}],
    }, client)
    if "_error" in data:
        return TestResult("code_patch", False, data["_error"])
    content = data.get("message", {}).get("content", "")
    ok = "return a + b" in content or "return a+b" in content or "a + b" in content
    return TestResult("code_patch", ok, content.strip()[:120])


TEST_FUNCTIONS = {
    "chat": test_chat,
    "structured_output": test_structured_output,
    "single_tool": test_single_tool,
    "code_patch": test_code_patch,
}


def qualify_model(
    model: str,
    base_url: str = "http://127.0.0.1:11434",
    tests: list[str] | None = None,
    client: httpx.Client | None = None,
) -> QualificationReport:
    names = tests or ["chat", "structured_output", "single_tool", "code_patch"]
    report = QualificationReport(model=model)
    for name in names:
        fn = TEST_FUNCTIONS.get(name)
        if fn is None:
            report.results.append(TestResult(name, False, f"unknown test '{name}'"))
            continue
        report.results.append(fn(model, base_url, client))
    return report


def qualify_bundle(
    bundle: BundleV2,
    base_url: str = "http://127.0.0.1:11434",
    client: httpx.Client | None = None,
    model_override: str | None = None,
) -> QualificationReport:
    if bundle.is_add_on:
        return QualificationReport(model="(add-on)", results=[TestResult("skip", True, "add-on has no controller")])
    model = model_override or bundle.controller_spec().model
    runnable = [t for t in bundle.qualification.required if t in TEST_FUNCTIONS]
    return qualify_model(model, base_url, tests=runnable or None, client=client)


__all__ = [
    "QualificationReport",
    "TestResult",
    "qualify_bundle",
    "qualify_model",
    "TEST_FUNCTIONS",
]
