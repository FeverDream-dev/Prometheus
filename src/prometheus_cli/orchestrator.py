from __future__ import annotations

import json
import time
from collections.abc import Callable

from .models import AgentTurn, ModelBundle, Risk, Settings, ToolCall
from .policy import requires_approval
from .providers import create_provider
from .tools.workspace import WorkspaceTools


SYSTEM_PROMPT = """You are the controller of PROMETHEUS, a coding agent.
Return only an AgentTurn JSON object matching the provided schema.
Use small, evidence-driven steps. Never claim completion without build/test evidence.
Available tools: list_files(pattern), read_file(path), write_file(path, content),
run_command(command: string array, timeout), git_checkpoint(message).
Do not put shell syntax in command arrays. Do not escape the workspace.
Placeholders are allowed only for explicit prototypes, must be labeled PLACEHOLDER,
and must appear in the remaining-work report.
"""


TOOL_RISK = {
    "list_files": Risk.READ,
    "read_file": Risk.READ,
    "write_file": Risk.WRITE,
    "run_command": Risk.EXECUTE,
    "git_checkpoint": Risk.WRITE,
}


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        bundle: ModelBundle,
        approve: Callable[[ToolCall, Risk], bool] | None = None,
    ):
        self.settings = settings
        self.bundle = bundle
        self.workspace = WorkspaceTools(settings.workspace)
        controller_spec = bundle.for_role("controller")
        if not controller_spec.tool_capable:
            raise ValueError("The controller role requires a tool-capable model")
        self.controller = create_provider(controller_spec)
        self.reviewer = create_provider(bundle.for_role("reviewer")) if settings.multi_agent_review else None
        self.approve = approve or (lambda _call, _risk: False)

    def _execute(self, call: ToolCall) -> str:
        if call.tool not in TOOL_RISK:
            return f"ERROR: unknown tool {call.tool}"
        risk = TOOL_RISK[call.tool]
        if requires_approval(self.settings, risk) and not self.approve(call, risk):
            return "DENIED: user approval required"
        method = getattr(self.workspace, call.tool)
        try:
            return str(method(**call.arguments))
        except Exception as exc:  # tool errors become evidence for the repair loop
            return f"ERROR {type(exc).__name__}: {exc}"

    def run(self, objective: str, on_update: Callable[[str], None] = print) -> AgentTurn:
        started = time.monotonic()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": objective},
        ]
        failures = 0
        last_turn = AgentTurn(message="Not started")
        schema = AgentTurn.model_json_schema()

        for step in range(1, self.settings.max_steps + 1):
            if time.monotonic() - started > self.settings.max_runtime_minutes * 60:
                return AgentTurn(status="blocked", message="Runtime limit reached")
            raw = self.controller.complete(messages, schema=schema)
            try:
                turn = AgentTurn.model_validate_json(raw)
            except Exception as exc:
                failures += 1
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": f"Invalid AgentTurn JSON: {exc}"})
                continue
            last_turn = turn
            on_update(f"step {step}: {turn.message} ({turn.completion_percent}%)")
            if turn.status in {"complete", "needs_user", "blocked"} and not turn.calls:
                if turn.status == "complete" and turn.completion_percent < self.settings.target_completion:
                    messages.append({"role": "user", "content": "Completion is below required target."})
                    continue
                return turn
            results = []
            for call in turn.calls:
                result = self._execute(call)
                results.append({"tool": call.tool, "result": result})
                failures = failures + 1 if result.startswith("ERROR") else 0
            messages.extend(
                [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": "TOOL RESULTS:\n" + json.dumps(results)},
                ]
            )
            if failures >= self.settings.attempts_before_escalation and self.reviewer:
                review = self.reviewer.complete(
                    [
                        {"role": "system", "content": "Diagnose the repeated failure. Do not call tools."},
                        {"role": "user", "content": json.dumps(results)},
                    ]
                )
                messages.append({"role": "user", "content": f"REVIEWER ADVICE:\n{review}"})
                failures = 0
        return AgentTurn(status="blocked", message="Maximum steps reached", completion_percent=last_turn.completion_percent)
