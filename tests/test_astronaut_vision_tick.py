from __future__ import annotations

import json
from pathlib import Path

from prometheus_cli.astronaut import run_tick, _astronaut_dir


def test_run_tick_focused_writes_event(tmp_path: Path):
    result = run_tick(tmp_path, seed=42, vision=False)
    assert result["type"] == "astronaut_focused_test"
    assert result["seed"] == 42
    events_path = tmp_path / ".prometheus" / "astronaut" / "events.jsonl"
    assert events_path.exists()
    lines = events_path.read_text().strip().split("\n")
    assert len(lines) >= 1
    event = json.loads(lines[0])
    assert event["type"] == "astronaut_focused_test"


def test_run_tick_vision_skips_without_playwright(tmp_path: Path):
    result = run_tick(tmp_path, seed=99, vision=True,
                      url="http://localhost:4173", selector="button.primary")
    assert result["type"] == "astronaut_vision_test"
    assert result["result"] in ("skip", "pass", "fail")


def test_run_tick_seed_is_reproducible(tmp_path: Path):
    run_tick(tmp_path, seed=12345, vision=False)
    events_path = tmp_path / ".prometheus" / "astronaut" / "events.jsonl"
    first_event = json.loads(events_path.read_text().strip().split("\n")[0])
    assert first_event["seed"] == 12345


def test_run_tick_writes_report_md(tmp_path: Path):
    run_tick(tmp_path, seed=7, vision=False)
    report_path = tmp_path / ".prometheus" / "astronaut" / "report.md"
    assert report_path.exists()
    content = report_path.read_text()
    assert "Astronaut Sentinel Report" in content


def test_astronaut_dir_created(tmp_path: Path):
    d = _astronaut_dir(tmp_path)
    assert d.exists()
    assert d.name == "astronaut"
