"""Failure-signature tracking for PROMETHEUS escalation.

Groups failures by a canonical signature so five failures with the *same* root
cause trigger escalation (different persona/hypothesis), while five failures
with *different* causes do not. This implements the ACCEPTANCE_TESTS rule:
"Five identical failure signatures trigger a different persona/model and
hypothesis."

The signature normalizes file paths, line numbers, and quoted strings so that
the same error in different files or at different lines still groups together.
"""

from __future__ import annotations

import hashlib
import re


def failure_signature(tool: str, error: str) -> str:
    tool_part = tool or "unknown"
    error_type = "Unknown"
    message = error

    if error.startswith("ERROR "):
        rest = error[6:]
        if ":" in rest:
            error_type, message = rest.split(":", 1)
            error_type = error_type.strip()
            message = message.strip()
        else:
            error_type = rest.strip()
            message = ""

    normalized = re.sub(r"[/\w][/\w.-]+\.\w+", "PATH", message)
    normalized = re.sub(r"\d+", "N", normalized)
    normalized = re.sub(r"'[^']*'", "STR", normalized)
    normalized = re.sub(r'"[^"]*"', "STR", normalized)
    normalized = normalized.strip()[:120]

    digest = hashlib.sha256(normalized.encode()).hexdigest()[:12]
    return f"{tool_part}:{error_type}:{digest}"


class FailureTracker:
    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self._counts: dict[str, int] = {}

    def record(self, tool: str, error: str) -> str | None:
        sig = failure_signature(tool, error)
        self._counts[sig] = self._counts.get(sig, 0) + 1
        if self._counts[sig] >= self.threshold:
            return sig
        return None

    def reset(self, signature: str) -> None:
        self._counts.pop(signature, None)

    def count_for(self, tool: str, error: str) -> int:
        return self._counts.get(failure_signature(tool, error), 0)

    def total(self) -> int:
        return sum(self._counts.values())

    def distinct_signatures(self) -> int:
        return len(self._counts)
