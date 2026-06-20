from __future__ import annotations

import json
from pathlib import Path

import pytest

from prometheus_cli.astronaut import (
    AstronautController,
    AstronautState,
    clear_pause,
    clear_stop,
    read_state,
    request_pause,
    request_stop,
)


class FakeArena:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    def run(self, providers, verify, on_update=lambda _m: None):
        self.calls += 1
        return self._outcomes.pop(0) if self._outcomes else _result(False, "exhausted")


class _Result:
    def __init__(self, accepted, final_status):
        self.accepted = accepted
        self.final_status = final_status


def _result(accepted, final_status):
    return _Result(accepted, final_status)


class FakeTools:
    def __init__(self):
        self.checkpoints = []

    def git_checkpoint(self, msg):
        self.checkpoints.append(msg)
        return "ok"


@pytest.fixture
def workspace(tmp_path):
    return tmp_path


def test_request_stop_creates_file(workspace):
    p = request_stop(workspace)
    assert p.exists()
    assert p.name == "STOP"
    assert clear_stop(workspace) is True
    assert not p.exists()


def test_request_pause_creates_file(workspace):
    p = request_pause(workspace)
    assert p.exists()
    assert p.name == "PAUSE"
    assert clear_pause(workspace) is True
    assert not p.exists()


def test_state_roundtrip(workspace):
    state = AstronautState(status="running", objective="fix tests", macro_attempts=3)
    ctrl = AstronautController(
        store=None, tools=None, arena=None, providers={}, verify=lambda *_: (True, ""),
        workspace=workspace, objective="fix tests",
    )
    ctrl.write_state(state)
    loaded = read_state(workspace)
    assert loaded.status == "running"
    assert loaded.objective == "fix tests"
    assert loaded.macro_attempts == 3


def test_read_state_missing_returns_idle(workspace):
    state = read_state(workspace)
    assert state.status == "idle"
    assert state.macro_attempts == 0


def test_controller_completes_when_arena_accepts(workspace):
    arena = FakeArena([_result(True, "complete")])
    ctrl = AstronautController(
        store=None, tools=FakeTools(), arena=arena, providers={}, verify=lambda *_: (True, ""),
        workspace=workspace, objective="x", clock=lambda: 1000.0, sleep=lambda _s: None,
    )
    result = ctrl.run()
    assert result.accepted is True
    assert result.state.status == "complete"
    assert arena.calls == 1


def test_controller_stops_on_stop_file(workspace):
    request_stop(workspace)
    arena = FakeArena([_result(True, "complete")])
    ctrl = AstronautController(
        store=None, tools=FakeTools(), arena=arena, providers={}, verify=lambda *_: (True, ""),
        workspace=workspace, objective="x", sleep=lambda _s: None,
    )
    result = ctrl.run()
    assert result.accepted is False
    assert result.reason == "stop-file"
    assert result.state.status == "stopped"
    assert arena.calls == 0


def test_controller_step_budget_exhausted(workspace):
    arena = FakeArena([_result(False, "exhausted")])
    ctrl = AstronautController(
        store=None, tools=FakeTools(), arena=arena, providers={}, verify=lambda *_: (False, ""),
        workspace=workspace, objective="x", max_steps=2, sleep=lambda _s: None,
    )
    result = ctrl.run()
    assert result.accepted is False
    assert result.reason == "step-budget"
    assert result.state.status == "budget_exhausted"
    assert arena.calls == 2


def test_controller_runtime_budget_exhausted(workspace):
    arena = FakeArena([_result(False, "exhausted")])

    class Clock:
        def __init__(self):
            self.n = 0

        def __call__(self):
            self.n += 1
            return 1000.0 if self.n <= 6 else 9999.0

    clock = Clock()
    ctrl = AstronautController(
        store=None, tools=FakeTools(), arena=arena, providers={}, verify=lambda *_: (False, ""),
        workspace=workspace, objective="x", max_runtime_minutes=1,
        clock=clock, sleep=lambda _s: None,
    )
    result = ctrl.run()
    assert result.reason == "runtime-budget"
    assert result.state.status == "budget_exhausted"


def test_controller_periodic_checkpoint(workspace):
    arena = FakeArena([_result(False, "exhausted"), _result(True, "complete")])
    tools = FakeTools()
    ctrl = AstronautController(
        store=None, tools=tools, arena=arena, providers={}, verify=lambda *_: (False, ""),
        workspace=workspace, objective="x", max_steps=2, checkpoint_every_attempts=1,
        sleep=lambda _s: None,
    )
    ctrl.run()
    assert len(tools.checkpoints) >= 1


def test_pause_blocks_until_cleared(workspace, monkeypatch):
    request_pause(workspace)
    pause_calls = [0]

    def fake_sleep(s):
        pause_calls[0] += 1
        if pause_calls[0] >= 2:
            clear_pause(workspace)
        if pause_calls[0] >= 10:
            raise RuntimeError("infinite pause")

    arena = FakeArena([_result(True, "complete")])
    ctrl = AstronautController(
        store=None, tools=FakeTools(), arena=arena, providers={}, verify=lambda *_: (True, ""),
        workspace=workspace, objective="x", poll_interval_s=0, sleep=fake_sleep,
    )
    result = ctrl.run()
    assert result.accepted is True
    assert result.state.status == "complete"
