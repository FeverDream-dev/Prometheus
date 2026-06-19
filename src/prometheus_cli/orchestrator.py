from __future__ import annotations

import json
import time
from collections.abc import Callable

from .escalation import FailureTracker
from .models import AgentTurn, ModelBundle, Risk, Settings, ToolCall
from .policy import requires_approval
from .providers import create_provider
from .redaction import redact
from .session import SessionStore
from .tools.workspace import WorkspaceTools


SYSTEM_PROMPT = """You are the controller of PROMETHEUS, a coding agent.
Return only an AgentTurn JSON object matching the provided schema.

First turn: propose acceptance criteria via criteria_proposed. Each criterion
has a description, weight (1-100), and critical flag. Completion is computed
deterministically from accepted criteria, not from your self-reported percentage.

When a criterion is satisfied with evidence (passing tests, successful build),
list its description in criteria_met. Do not claim a criterion is met without
tool-result evidence in the same or a prior turn.

Available tools: list_files(pattern), read_file(path), write_file(path, content),
run_command(command: string array, timeout), git_checkpoint(message),
git_log(limit), git_diff(path), git_current_sha(), git_rollback(commit_sha).
Browser tools (when available): browser_navigate(url), browser_screenshot(),
browser_click(selector), browser_fill(selector, value), browser_text(selector),
browser_evaluate(expression), browser_evidence().
git_rollback is destructive and always requires user approval.
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
    "git_log": Risk.READ,
    "git_diff": Risk.READ,
    "git_current_sha": Risk.READ,
    "git_rollback": Risk.DESTRUCTIVE,
    "browser_navigate": Risk.NETWORK,
    "browser_screenshot": Risk.READ,
    "browser_click": Risk.EXECUTE,
    "browser_fill": Risk.WRITE,
    "browser_text": Risk.READ,
    "browser_evaluate": Risk.EXECUTE,
    "browser_evidence": Risk.READ,
}


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        bundle: ModelBundle,
        approve: Callable[[ToolCall, Risk], bool] | None = None,
        session_store: SessionStore | None = None,
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
        self.store = session_store
        self._criterion_tasks: dict[str, str] = {}
        self._browser = None

    def _get_browser(self):
        if self._browser is None:
            try:
                from .browser import BrowserTools
                self._browser = BrowserTools()
            except ImportError:
                return None
        return self._browser

    def _execute(self, call: ToolCall) -> str:
        if call.tool not in TOOL_RISK:
            return f"ERROR: unknown tool {call.tool}"
        risk = TOOL_RISK[call.tool]
        if requires_approval(self.settings, risk) and not self.approve(call, risk):
            return "DENIED: user approval required"
        if call.tool.startswith("browser_"):
            browser = self._get_browser()
            if browser is None:
                return "ERROR: Playwright not installed. Install with: pip install 'prometheus-local-agent[browser]'"
            method_name = call.tool.replace("browser_", "")
            method = getattr(browser, method_name, None)
            if method_name == "evidence":
                return browser.collect_evidence().summary()
            if method is None:
                return f"ERROR: unknown browser tool {call.tool}"
        else:
            method = getattr(self.workspace, call.tool)
        try:
            return str(method(**call.arguments))
        except Exception as exc:
            return f"ERROR {type(exc).__name__}: {exc}"

    def _sync_criteria(self, turn: AgentTurn, session_id: str) -> None:
        if not self.store:
            return
        for criterion in turn.criteria_proposed:
            if criterion.description not in self._criterion_tasks:
                task_id = self.store.add_task(
                    session_id, criterion.description,
                    weight=criterion.weight, critical=criterion.critical,
                )
                self._criterion_tasks[criterion.description] = task_id
        for description in turn.criteria_met:
            task_id = self._criterion_tasks.get(description)
            if task_id:
                self.store.set_task_accepted(task_id, True)

    def _evaluated_completion(self, session_id: str, model_percent: int) -> int:
        if not self.store:
            return model_percent
        return int(self.store.completion_percent(session_id))

    def run(self, objective: str, on_update: Callable[[str], None] = print) -> AgentTurn:
        started = time.monotonic()
        session_id = None
        if self.store:
            session_id = self.store.create_session(
                objective, self.settings.mode.value, str(self.settings.workspace),
                str(self.settings.bundle_file) if self.settings.bundle_file else None,
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": objective},
        ]
        failures = FailureTracker(self.settings.attempts_before_escalation)
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

            if session_id:
                self.store.append_event(session_id, "agent_turn", {
                    "step": step, "message": turn.message, "status": turn.status,
                })
                self._sync_criteria(turn, session_id)

            evaluated = self._evaluated_completion(session_id, turn.completion_percent)
            turn.completion_percent = evaluated
            last_turn = turn
            on_update(f"step {step}: {turn.message} ({evaluated}%)")

            terminal = turn.status in {"complete", "needs_user", "blocked"} and not turn.calls
            if terminal:
                if turn.status == "complete" and session_id:
                    if not self.store.meets_target(session_id, self.settings.target_completion):
                        messages.append({
                            "role": "user",
                            "content": (
                                f"Completion claims {evaluated}% but the traceability matrix "
                                f"requires {self.settings.target_completion}% with all critical "
                                f"criteria accepted. List remaining criteria_met with evidence."
                            ),
                        })
                        continue
                    self.store.set_status(session_id, "complete")
                elif session_id:
                    self.store.set_status(session_id, turn.status)
                return turn

            results = []
            escalated_sig: str | None = None
            for call in turn.calls:
                result = self._execute(call)
                result = redact(result)
                results.append({"tool": call.tool, "result": result})
                if result.startswith("ERROR"):
                    sig = failures.record(call.tool, result)
                    if sig:
                        escalated_sig = sig
                if session_id:
                    self.store.add_evidence(session_id, call.tool, result[:5000])

            messages.extend(
                [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": "TOOL RESULTS:\n" + json.dumps(results)},
                ]
            )
            if escalated_sig and self.reviewer:
                review = self.reviewer.complete(
                    [
                        {"role": "system", "content": (
                            f"You have failed {self.settings.attempts_before_escalation} times "
                            f"with the same error signature. Diagnose the root cause and propose "
                            f"a materially different approach. Do not repeat the same fix."
                        )},
                        {"role": "user", "content": json.dumps(results)},
                    ]
                )
                messages.append({
                    "role": "user",
                    "content": (
                        f"ESCALATION: {failures.count_for(call.tool, result)} identical failures "
                        f"detected. Try a materially different approach.\n{review}"
                    ),
                })
                failures.reset(escalated_sig)
        if session_id:
            self.store.set_status(session_id, "blocked")
        return AgentTurn(
            status="blocked", message="Maximum steps reached",
            completion_percent=last_turn.completion_percent,
        )
