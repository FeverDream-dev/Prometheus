from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..agent.seats import SEATS, Seat, SeatName
from ..memory import FailureSignature, ProjectMemoryStore
from ..memory.context import build_context_packet
from ..models import AgentTurn, Risk, Settings, ToolCall
from ..policy import requires_approval

TOOL_RISK: dict[str, Risk] = {
    "read_file": Risk.READ,
    "list_files": Risk.READ,
    "write_file": Risk.WRITE,
    "run_command": Risk.EXECUTE,
    "git_checkpoint": Risk.EXECUTE,
    "git_diff": Risk.READ,
    "git_log": Risk.READ,
}


@dataclass
class StepOutcome:
    seat: SeatName
    turn: AgentTurn | None
    tool_outputs: list[str] = field(default_factory=list)
    error: str = ""
    packet_chars: int = 0


@dataclass
class MicroStepEngine:
    store: ProjectMemoryStore
    tools: object
    settings: Settings = field(default_factory=Settings)
    approve: Callable[[ToolCall, Risk], bool] = lambda _c, _r: False
    char_budget: int = 24000

    def run_seat(self, seat: Seat, provider) -> StepOutcome:
        active = self.store.active_micro_step()
        packet = build_context_packet(self.store, seat, active, char_budget=self.char_budget)
        schema = AgentTurn.model_json_schema()
        raw = provider.complete(packet.to_messages(seat.system_contract), schema=schema)
        try:
            turn = AgentTurn.model_validate_json(raw)
        except Exception as exc:
            return StepOutcome(seat=seat.name, turn=None, error=f"invalid AgentTurn: {exc}", packet_chars=packet.chars)
        self._sync_ledger(turn)
        outputs = self._execute_calls(turn)
        return StepOutcome(seat=seat.name, turn=turn, tool_outputs=outputs, packet_chars=packet.chars)

    def _sync_ledger(self, turn: AgentTurn) -> None:
        from ..memory import TaskNode

        if turn.criteria_proposed:
            for c in turn.criteria_proposed:
                tid = c.description[:40].strip().replace(" ", "-").lower() or f"crit-{len(self.store.get_tasks())}"
                self.store.upsert_task(TaskNode(id=tid, description=c.description, acceptance=c.description, status="active"))
        intent = self.store.get_intent()
        if intent and not intent.success_criteria and turn.criteria_proposed:
            intent.success_criteria = [c.description for c in turn.criteria_proposed]
            self.store.set_intent(intent)

    def _execute_calls(self, turn: AgentTurn) -> list[str]:
        out: list[str] = []
        for call in turn.calls:
            risk = TOOL_RISK.get(call.tool, Risk.EXECUTE)
            if requires_approval(self.settings, risk) and not self.approve(call, risk):
                out.append(f"{call.tool}: denied by policy")
                continue
            out.append(f"{call.tool}: " + self._dispatch(call))
        return out

    def _dispatch(self, call: ToolCall) -> str:
        a = call.arguments
        name = call.tool
        if name == "read_file":
            return self.tools.read_file(a.get("path", ""))
        if name == "list_files":
            return self.tools.list_files(a.get("pattern", "*"))
        if name == "write_file":
            return self.tools.write_file(a.get("path", ""), a.get("content", ""))
        if name == "run_command":
            return self.tools.run_command(list(a.get("command", [])), int(a.get("timeout", 120)))
        if name == "git_checkpoint":
            return self.tools.git_checkpoint(a.get("message", "checkpoint"))
        if name == "git_diff":
            return self.tools.git_diff(a.get("path"))
        if name == "git_log":
            return self.tools.git_log(int(a.get("limit", 10)))
        return f"unknown tool: {name}"


@dataclass
class ArenaResult:
    accepted: bool
    attempts: int
    failure_signatures: list[str] = field(default_factory=list)
    transcript: list[str] = field(default_factory=list)
    final_status: str = "blocked"


@dataclass
class ArenaLoop:
    store: ProjectMemoryStore
    tools: object
    engine: MicroStepEngine
    max_attempts: int = 5
    escalation_threshold: int = 3

    def run(
        self,
        providers: dict[SeatName, object],
        verify: Callable[[ProjectMemoryStore, object], tuple[bool, str]],
        on_update: Callable[[str], None] = lambda _m: None,
    ) -> ArenaResult:
        forge = providers["forge"]
        argus = providers.get("argus")
        attempts = 0
        seen_signatures: dict[str, int] = {}
        result = ArenaResult(accepted=False, attempts=0)
        self.engine.run_seat(SEATS["envoy"], providers["envoy"])
        on_update("Envoy framed the micro-step.")
        while attempts < self.max_attempts:
            attempts += 1
            result.attempts = attempts
            forge_out = self.engine.run_seat(SEATS["forge"], forge)
            self.store.set_working_memory(self._note(f"forge attempt {attempts}", forge_out.tool_outputs))
            on_update(f"Forge attempt {attempts}: {forge_out.turn.message if forge_out.turn else forge_out.error}")
            if forge_out.error:
                self._record_failure("invalid-agent-turn", forge_out.error)
                continue
            passed, evidence = verify(self.store, self.tools)
            on_update(f"Verification: {'PASS' if passed else 'FAIL'} — {evidence[:80]}")
            if passed and argus is not None:
                review = self.engine.run_seat(SEATS["argus"], argus)
                on_update(f"Argus: {review.turn.message if review.turn else review.error}")
            if passed:
                self.store.record_fact(_fact("micro-step verified", "test", evidence))
                self.store.set_working_memory(self._note("verified", [evidence]))
                result.accepted = True
                result.final_status = "complete"
                return result
            sig = _normalize_signature(evidence)
            seen_signatures[sig] = seen_signatures.get(sig, 0) + 1
            self._record_failure(sig, evidence)
            result.failure_signatures.append(sig)
            if seen_signatures[sig] >= self.escalation_threshold:
                on_update(f"Repeated failure signature '{sig}' — escalating (alternate hypothesis).")
                result.final_status = "escalated"
                self.store.set_working_memory(self._note("escalated", [f"repeated: {sig}"]))
                return result
        result.final_status = "exhausted"
        return result

    def _record_failure(self, signature: str, detail: str) -> None:
        self.store.record_failure(FailureSignature(
            id=signature[:40], signature=signature, hypothesis=detail[:160],
        ))

    def _note(self, tag: str, lines: list[str]) -> str:
        body = "\n".join(f"- {line}" for line in lines) if lines else "(no detail)"
        intent = self.store.get_intent()
        head = f"# Working memory\n\n## Objective\n{intent.objective if intent else '(none)'}\n\n## Last\n[{tag}]\n{body}\n"
        return head[:8000]


def _normalize_signature(evidence: str) -> str:
    text = " ".join(evidence.lower().split())
    return text[:80] or "unknown-failure"


def detect_test_command(workspace) -> list[str] | None:
    import shutil
    import sys
    from pathlib import Path

    root = Path(workspace)
    py = shutil.which("python") or shutil.which("python3") or sys.executable
    has_tests = any(root.glob("test_*.py")) or any(root.glob("*_test.py")) or any(root.glob("tests/test_*.py"))
    if has_tests or (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
        return [py, "-m", "pytest", "-q"]
    return None


def make_default_verify(workspace):
    from pathlib import Path

    root = Path(workspace)
    test_cmd = detect_test_command(root)

    def verify(store, tools):
        if test_cmd:
            out = tools.run_command(test_cmd, timeout=180)
            passed = "passed" in out and ("failed" not in out.lower() or " failed" not in out.lower())
            return passed, _meaningful_pytest_line(out)
        diff = tools.git_diff() if hasattr(tools, "git_diff") else ""
        changed = bool(diff and diff.strip() and "fatal" not in diff.lower())
        return changed, ("patch applied (no test suite to verify)" if changed else "no change made")

    return verify


def _meaningful_pytest_line(output: str) -> str:
    import re

    for line in output.splitlines():
        if re.search(r"FAILED|AssertionError|assert\b|Error:|Exception", line):
            return line.strip()[:160]
    summary = [s.strip() for s in output.splitlines() if s.strip()]
    return summary[-1] if summary else "(no output)"


def _fact(summary: str, source: str, ref: str):
    from ..memory import Fact, FactConfidence, Provenance

    return Fact(
        id=f"f-{abs(hash(summary)) % 10**9}",
        summary=f"{summary}: {ref[:80]}", confidence=FactConfidence.OBSERVED,
        provenance=Provenance(source=source),
    )


__all__ = ["ArenaLoop", "ArenaResult", "MicroStepEngine", "StepOutcome", "TOOL_RISK"]
