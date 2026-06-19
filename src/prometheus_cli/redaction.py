"""Secret redaction for PROMETHEUS.

Applies before tool output becomes evidence, before results are sent to the
model, and before anything is printed. Catches common token forms rather than
specific provider keys so it remains useful as providers evolve.

The patterns are intentionally broad: a false positive (redacting something
that is not a secret) is safe; a false negative (leaking a real secret) is
not. The replacement token [REDACTED] is always the same so it is easy to
grep for in audit logs.
"""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(sk-[a-zA-Z0-9]{20,})"), REDACTED),
    (re.compile(r"(AIza[a-zA-Z0-9_-]{35,})"), REDACTED),
    (re.compile(r"(AKIA[A-Z0-9]{16})"), REDACTED),
    (re.compile(r"(gh[pousr]_[A-Za-z0-9]{36})"), REDACTED),
    (re.compile(r"(xox[baprs]-[A-Za-z0-9-]{10,})"), REDACTED),
    (re.compile(r"(Bearer\s+[A-Za-z0-9._~+/=-]{20,})", re.IGNORECASE), "Bearer " + REDACTED),
    (
        re.compile(
            r"(-----BEGIN\s+[A-Z\s]*PRIVATE\s+KEY-----.*?-----END\s+[A-Z\s]*PRIVATE\s+KEY-----)",
            re.DOTALL,
        ),
        REDACTED,
    ),
    (re.compile(r"(?i)(password|passwd|pwd|secret|token|api[_-]?key)\s*[=:]\s*(['\"]?)([^\s'\"]{8,})\2"),
     r"\1=\2" + REDACTED + r"\2"),
    (re.compile(r"(?i)(Authorization)\s*:\s*([^\r\n]{8,})", re.IGNORECASE),
     r"\1: " + REDACTED),
    (re.compile(r"([a-f0-9]{64})"), REDACTED),
]


def redact(text: str) -> str:
    if not text:
        return text
    result = text
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    return result
