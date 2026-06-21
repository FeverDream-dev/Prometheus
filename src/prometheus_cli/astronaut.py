from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .agent import ArenaLoop
from .memory import ProjectMemoryStore


STOP_FILENAME = "STOP"
PAUSE_FILENAME = "PAUSE"
STATE_FILENAME = "astronaut.json"

VALID_STATUSES = ("idle", "running", "paused", "stopped", "complete", "budget_exhausted")


@dataclass
class AstronautState:
    status: str = "idle"
    objective: str = ""
    mode: str = "astronaut"
    started_at: float = 0.0
    last_heartbeat: float = 0.0
    macro_attempts: int = 0
    checkpoints: int = 0
    final_status: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "objective": self.objective,
            "mode": self.mode,
            "started_at": self.started_at,
            "last_heartbeat": self.last_heartbeat,
            "macro_attempts": self.macro_attempts,
            "checkpoints": self.checkpoints,
            "final_status": self.final_status,
        }


@dataclass
class AstronautResult:
    state: AstronautState
    accepted: bool
    reason: str = ""


@dataclass
class AstronautController:
    store: ProjectMemoryStore
    tools: object
    arena: ArenaLoop
    providers: dict
    verify: Callable
    workspace: Path
    objective: str
    max_steps: int = 0
    max_runtime_minutes: int = 0
    heartbeat_interval_s: float = 30.0
    checkpoint_every_attempts: int = 5
    poll_interval_s: float = 1.0
    clock: Callable[[], float] = field(default=time.time)
    sleep: Callable[[float], None] = field(default=time.sleep)

    def _prometheus_dir(self) -> Path:
        d = self.workspace.resolve() / ".prometheus"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def stop_requested(self) -> bool:
        return (self._prometheus_dir() / STOP_FILENAME).exists()

    def pause_requested(self) -> bool:
        return (self._prometheus_dir() / PAUSE_FILENAME).exists()

    def write_state(self, state: AstronautState) -> None:
        state.last_heartbeat = self.clock()
        path = self._prometheus_dir() / STATE_FILENAME
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(path)

    def read_state(self) -> AstronautState:
        return read_state(self.workspace)

    def _wait_while_paused(self, state: AstronautState) -> bool:
        state.status = "paused"
        self.write_state(state)
        while self.pause_requested():
            if self.stop_requested():
                return False
            self.sleep(self.poll_interval_s)
        state.status = "running"
        self.write_state(state)
        return True

    def run(self, on_update: Callable[[str], None] = lambda _m: None) -> AstronautResult:
        state = AstronautState(
            status="running",
            objective=self.objective,
            mode="astronaut",
            started_at=self.clock(),
        )
        self.write_state(state)
        deadline = (self.started_runtime_deadline()) if self.max_runtime_minutes else None
        accepted = False
        while True:
            if self.stop_requested():
                state.status = "stopped"
                self.write_state(state)
                on_update("Stop file detected — halting astronaut session.")
                return AstronautResult(state=state, accepted=False, reason="stop-file")
            if not self._wait_while_paused(state):
                state.status = "stopped"
                self.write_state(state)
                return AstronautResult(state=state, accepted=False, reason="stop-during-pause")
            if deadline is not None and self.clock() >= deadline:
                state.status = "budget_exhausted"
                state.final_status = "runtime-budget"
                self.write_state(state)
                on_update("Runtime budget exhausted.")
                return AstronautResult(state=state, accepted=False, reason="runtime-budget")
            if self.max_steps and state.macro_attempts >= self.max_steps:
                state.status = "budget_exhausted"
                state.final_status = "step-budget"
                self.write_state(state)
                on_update("Step budget exhausted.")
                return AstronautResult(state=state, accepted=False, reason="step-budget")

            state.macro_attempts += 1
            self.write_state(state)
            on_update(f"Astronaut macro-attempt {state.macro_attempts}.")
            arena_result = self.arena.run(self.providers, self.verify, on_update=on_update)
            state.final_status = arena_result.final_status
            self.write_state(state)
            if arena_result.accepted:
                accepted = True
                state.status = "complete"
                self.write_state(state)
                on_update("Objective accepted by verifier — astronaut complete.")
                break
            if self.checkpoint_every_attempts and state.macro_attempts % self.checkpoint_every_attempts == 0:
                try:
                    self.tools.git_checkpoint(f"astronaut checkpoint after attempt {state.macro_attempts}")
                    state.checkpoints += 1
                    self.write_state(state)
                except Exception:
                    pass
        return AstronautResult(state=state, accepted=accepted, reason="complete" if accepted else "loop-ended")

    def started_runtime_deadline(self) -> float:
        return self.clock() + self.max_runtime_minutes * 60


def request_stop(workspace: Path) -> Path:
    d = workspace.resolve() / ".prometheus"
    d.mkdir(parents=True, exist_ok=True)
    p = d / STOP_FILENAME
    p.write_text("stop\n", encoding="utf-8")
    return p


def request_pause(workspace: Path) -> Path:
    d = workspace.resolve() / ".prometheus"
    d.mkdir(parents=True, exist_ok=True)
    p = d / PAUSE_FILENAME
    p.write_text("pause\n", encoding="utf-8")
    return p


def clear_pause(workspace: Path) -> bool:
    p = workspace.resolve() / ".prometheus" / PAUSE_FILENAME
    if p.exists():
        p.unlink()
        return True
    return False


def clear_stop(workspace: Path) -> bool:
    p = workspace.resolve() / ".prometheus" / STOP_FILENAME
    if p.exists():
        p.unlink()
        return True
    return False


def read_state(workspace: Path) -> AstronautState:
    path = workspace.resolve() / ".prometheus" / STATE_FILENAME
    if not path.exists():
        return AstronautState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        defaults = AstronautState()
        return AstronautState(
            status=data.get("status", defaults.status),
            objective=data.get("objective", defaults.objective),
            mode=data.get("mode", defaults.mode),
            started_at=data.get("started_at", defaults.started_at),
            last_heartbeat=data.get("last_heartbeat", defaults.last_heartbeat),
            macro_attempts=data.get("macro_attempts", defaults.macro_attempts),
            checkpoints=data.get("checkpoints", defaults.checkpoints),
            final_status=data.get("final_status", defaults.final_status),
        )
    except (ValueError, OSError):
        return AstronautState()


def _astronaut_dir(workspace: Path) -> Path:
    d = workspace.resolve() / ".prometheus" / "astronaut"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _append_event(workspace: Path, event: dict) -> Path:
    d = _astronaut_dir(workspace)
    events_path = d / "events.jsonl"
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")
    return events_path


def _write_report(workspace: Path, text: str) -> Path:
    d = _astronaut_dir(workspace)
    report_path = d / "report.md"
    report_path.write_text(text, encoding="utf-8")
    return report_path


def run_tick(
    workspace: Path,
    seed: int = 0,
    vision: bool = False,
    url: str = "",
    selector: str = "",
    profile: Path | None = None,
) -> dict:
    """Run one Astronaut Sentinel test tick.

    Returns the event dict that was also appended to events.jsonl.
    """
    import random
    import subprocess
    import time as _time

    if seed == 0:
        seed = int(_time.time() * 1000) % (2**31)
    rng = random.Random(seed)

    tick_type = "focused"
    if vision or url:
        tick_type = "vision"
    elif rng.random() < 0.3:
        tick_type = "random"

    event: dict = {
        "type": f"astronaut_{tick_type}_test",
        "seed": seed,
        "timestamp": _time.time(),
    }

    if tick_type == "vision":
        event["selected_area"] = selector or "button.primary"
        event["url"] = url or "http://localhost:4173"
        if profile and profile.exists():
            event["profile"] = str(profile)
        try:
            from .vision import VisionInspector
            inspector = VisionInspector(headless=True)
            out_dir = workspace / ".prometheus" / "vision"
            report = inspector.inspect(
                url=url or "http://localhost:4173",
                selector=selector or "button.primary",
                profile=profile,
                out_dir=out_dir,
            )
            if "error" in report:
                event["result"] = "fail"
                event["detail"] = report["error"]
            else:
                event["result"] = "pass" if report.get("verdict") == "pass" else "fail"
                event["detail"] = report.get("comparison", {}).get("summary", report.get("verdict", ""))
        except ImportError:
            event["result"] = "skip"
            event["detail"] = "playwright not installed"
        except Exception as exc:
            event["result"] = "fail"
            event["detail"] = str(exc)[:200]
    else:
        pytest_args = ["python", "-m", "pytest", "-q", "--no-header", "--tb=line"]
        if tick_type == "random":
            event["reason"] = "random sample tick"
            event["commands"] = ["pytest -q (random sample)"]
        else:
            event["reason"] = "focused test tick"
            event["commands"] = ["pytest -q"]
        event["commands_run"] = pytest_args
        try:
            proc = subprocess.run(
                pytest_args, cwd=str(workspace),
                capture_output=True, text=True, timeout=120,
            )
            event["result"] = "pass" if proc.returncode == 0 else "fail"
            event["exit_code"] = proc.returncode
            event["detail"] = (proc.stdout + proc.stderr).strip()[-300:]
        except subprocess.TimeoutExpired:
            event["result"] = "fail"
            event["detail"] = "pytest timed out (120s)"
        except FileNotFoundError:
            event["result"] = "skip"
            event["detail"] = "pytest not found in PATH"
        except Exception as exc:
            event["result"] = "fail"
            event["detail"] = str(exc)[:200]

    _append_event(workspace, event)
    report_lines = [
        "# Astronaut Sentinel Report",
        "",
        f"Last tick: {event['type']} (seed {seed})",
        f"Result: **{event['result']}**",
        "",
    ]
    if event.get("detail"):
        report_lines.append(f"Detail: {event['detail'][:200]}")
    _write_report(workspace, "\n".join(report_lines) + "\n")
    return event


__all__ = [
    "AstronautController",
    "AstronautResult",
    "AstronautState",
    "VALID_STATUSES",
    "clear_pause",
    "clear_stop",
    "read_state",
    "request_pause",
    "request_stop",
    "run_tick",
]
