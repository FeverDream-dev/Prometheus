"""Decode agent/runtime errors into actionable fixes for users."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DecodedError:
    code: str
    summary: str
    likely_cause: str
    fix: str
    raw_excerpt: str


_RULES: list[tuple[str, str, str, str, re.Pattern[str]]] = [
    (
        "ollama_down",
        "Ollama not reachable",
        "ollama serve not running or wrong host",
        "Run: ollama serve   then: prometheus doctor",
        re.compile(r"could not connect to ollama|connection refused.*11434", re.I),
    ),
    (
        "empty_write",
        "Empty file write rejected",
        "Model sent write_file with no body",
        "Retry run; use spark-cpu-8gb. Objective must demand full HTML in write_file calls[]",
        re.compile(r"write_file rejected.*empty|SELF-CHECK FAIL.*only 0 chars", re.I),
    ),
    (
        "narrated_tools",
        "Model described tools instead of calling them",
        "Small model put write_file in message, not calls[]",
        "System will auto-retry. If persists: prometheus use spark-cpu-8gb && qualify",
        re.compile(r"no successful write_file|no tool writes|narrated tools", re.I),
    ),
    (
        "invalid_json",
        "Invalid AgentTurn JSON",
        "Model output not valid schema JSON",
        "Lower temperature; use granite4.1:3b or qualify bundle first",
        re.compile(r"invalid AgentTurn|Invalid AgentTurn JSON", re.I),
    ),
    (
        "verify_fail",
        "Verification failed — no real artifacts",
        "No non-empty .html/.css/.py files in workspace",
        "Check site/ exists with content; avoid git_rollback in same run",
        re.compile(r"no change made|verification failed|Cannot mark complete", re.I),
    ),
    (
        "empty_turns",
        "Model returned empty turns",
        "Ollama returned blank completion",
        "Restart ollama serve; prometheus provider smoke --model granite4.1:3b",
        re.compile(r"empty turns in a row|Stopped: model returned 3 empty", re.I),
    ),
    (
        "playwright_missing",
        "Playwright browsers missing",
        "pip install browser extra but chromium not installed",
        "pip install 'prometheus-local-agent[browser]' && playwright install chromium",
        re.compile(r"Executable doesn't exist.*playwright|Playwright not installed", re.I),
    ),
    (
        "no_bundle",
        "No model bundle configured",
        "prometheus use not run",
        "prometheus use spark-cpu-8gb",
        re.compile(r"No bundle specified|No package", re.I),
    ),
    (
        "self_check_fail",
        "Write self-check failed",
        "File on disk too small after write",
        "Model must send full file content in write_file arguments.content",
        re.compile(r"SELF-CHECK FAIL", re.I),
    ),
]


def decode_error(text: str) -> DecodedError | None:
    excerpt = (text or "").strip()[:500]
    if not excerpt:
        return None
    for code, summary, cause, fix, pattern in _RULES:
        if pattern.search(excerpt):
            return DecodedError(code, summary, cause, fix, excerpt[:200])
    return None


def format_decoded(err: DecodedError) -> str:
    return (
        f"[{err.code}] {err.summary}\n"
        f"  cause: {err.likely_cause}\n"
        f"  fix:   {err.fix}"
    )


def decode_and_format(text: str) -> str:
    decoded = decode_error(text)
    if decoded is None:
        return text
    return format_decoded(decoded)


__all__ = ["DecodedError", "decode_and_format", "decode_error", "format_decoded"]
