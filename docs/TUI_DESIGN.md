# PROMETHEUS TUI 2.0 — Design Document

The TUI is the primary user-facing surface of PROMETHEUS. This document captures
the architecture, visual identity, and testing strategy after the 2.0 rebuild.

## Goals

PROMETHEUS is an installable local-first TUI coding agent. A user installs it,
enters any project folder, runs `prometheus tui`, chooses or confirms a model
bundle, and starts vibe coding locally with safety, memory, Git checkpoints,
tools, sandboxing, browser/vision tests, and optional cloud providers.

The TUI must make that obvious immediately — not look like a debug box.

## Layout

Six regions compose the application shell:

```
┌────────────────────────────────────────────────────────────────────────────┐
│ #brand-header      🔥 PROMETHEUS · project /tmp · mode pilot · bundle ember │
├──────────────┬──────────────────────────────────────────────┬───────────────┤
│              │ OBJECTIVE                                     │ INSPECTOR     │
│  #sidebar    │ Ask PROMETHEUS to build, fix, test…          │ System        │
│  (rail)      │ ─────────────────────────────────────────    │   OS  Linux   │
│              │ PLAN                                          │   CPU AMD…    │
│  Chat        │ No active plan. Type an objective…           │   RAM 32 GB   │
│  Plan        │ ─────────────────────────────────────────    │ Backend       │
│  Files       │ ACTIVITY                                      │   Ollama run  │
│  Models      │ <RichLog transcript with markup rendering>   │ Policy        │
│  Tools       │ ─────────────────────────────────────────    │   mode pilot  │
│  MCP         │ RECENT FILES                                  │ Git           │
│  Sandbox     │ • src/foo.py                                  │   main clean  │
│  Memory      │ ┌────────────────────────────────────────┐   │               │
│  Vision      │ │ next: Type an objective, or /help      │   │               │
│  Assets      │ └────────────────────────────────────────┘   │               │
│  Astronaut   │                                              │               │
│  Settings    │                                              │               │
├──────────────┴──────────────────────────────────────────────┴───────────────┤
│ > Ask PROMETHEUS to build, fix, test, explain… (/ for cmds, Ctrl+P palette) │
├────────────────────────────────────────────────────────────────────────────┤
│ provider ollama · bundle ember-8gb · mode Pilot · sandbox basic · git clean │
└────────────────────────────────────────────────────────────────────────────┘
```

Responsive breakpoints (in `PrometheusApp._apply_responsive_layout`):

| Width | Sidebar | Inspector |
|---|---|---|
| `<= 80` cols | hidden | hidden |
| `<= 100` cols | visible | hidden |
| `> 100` cols | visible | visible |

## Visual identity

Ancient myth + serious developer tool + local AI workstation. Defined in
[`src/prometheus_cli/tui_theme.py`](../src/prometheus_cli/tui_theme.py) as the
single source of truth.

- Obsidian / near-black canvas: `#0b0c10`
- Warm gold accent: `#d4a02a` / `#f0c050`
- Bronze / sandstone borders: `#5b4a2a` / `#3a3530`
- Calm status colors: olive `#7a9a4a`, amber `#c08a3a`, brick `#a04a4a`
- No clown magenta, no generic purple gradient, no massive empty borders.

## State contract

`TuiSnapshot` (in [`tui_state.py`](../src/prometheus_cli/tui_state.py)) is the
single read-only dataclass for all displayed values. Widgets and screens never
call probes directly — they read from a snapshot.

- `collect_snapshot(workspace)` calls every probe (hardware, ollama, git,
  memory, sandbox, sessions). Each probe is individually guarded so a failure
  degrades to an "unknown" sentinel rather than crashing the TUI.
- `collect_demo_snapshot(workspace)` returns fully-mocked realistic data for
  `prometheus tui --demo`. No IO whatsoever.

## Slash command screens

23 display screens (in [`tui_screens.py`](../src/prometheus_cli/tui_screens.py))
extend a `RichCommandScreen` base that renders a title strip + scrollable body.
The `SLASH_SCREEN_MAP` dict routes `/cmd` → screen class. Display commands push
a screen; state-mutating commands (`/exit /clear /mode /use /qualify /resume
/memory <action> /build`) are handled inline by the App.

## Setup wizard

7-step wizard accessible via `/setup`:

1. Welcome — orientation
2. Hardware — detected OS/CPU/RAM/GPU/VRAM/Disk
3. Ollama — running state + model count
4. Recommended bundle — hardware-derived suggestion
5. Confirm bundle — browse alternatives
6. Pull / validate — qualification flow
7. Start coding — next-action hint

The default `/setup` dispatch renders all 7 steps as one scrollable
`SetupScreen` (works under both interactive and headless-export paths). An
interactive `SetupWizard` (Screen subclass with Back/Next buttons and
Ctrl+N/Ctrl+B bindings) is available via `/setup-wizard`.

## Command palette

`Ctrl+P` opens `CommandPaletteScreen` — a custom MVP richer than Textual's
builtin. Each row shows command name, description, shortcut, availability, and
source classification (`local` / `cloud` / `external`). Type to filter; Up/Down
to navigate; Enter to dispatch; Esc to cancel.

## SVG export

`App.export_screenshot(title=...)` returns an SVG string of the current screen.
CLI entry: `prometheus tui --screenshot PATH --screen NAME`. Drives the app
via `App.run_test(headless=True, size=(120, 36))`, composes, optionally pushes
a screen, exports, writes to disk, exits. Used by tests and the visual smoke
script.

## Responsiveness

`_apply_responsive_layout` is called from both `on_mount` and `watch_size` so
the initial size and every subsequent resize both apply the breakpoint logic.
Tested at 80x24, 100x30, 120x36, 160x48 in `test_tui_responsive.py`.

## Testing strategy

Seven test files covering layout, snapshot stability, first-run, command
dispatch, responsiveness, raw-markup elimination, and SVG visual regression:

| File | Coverage |
|---|---|
| `test_tui_layout.py` | chrome regions, sidebar sections, status bar segments, input copy |
| `test_tui_snapshot.py` | golden text fixtures for `/help`, `/setup`, dashboard; keyword presence per screen |
| `test_tui_first_run.py` | demo ribbon, 7 wizard steps reachable, demo hardware in step 2 |
| `test_tui_command_palette.py` | every `/cmd` dispatches, palette opens on Ctrl+P, filter narrows, `/clear` works |
| `test_tui_responsive.py` | 4 sizes render, panels collapse at correct thresholds, Ctrl+B/I toggle |
| `test_tui_no_raw_markup.py` | no `[bold]`/`[yellow]`/`[/]` in rendered text or SVG output |
| `test_tui_visual_regression.py` | SVG export of every screen + `launch_tui(screenshot_path=...)` CLI path |

Golden text fixtures live in [`tests/golden/tui/`](../tests/golden/tui/):
`startup.txt`, `help.txt`, `setup.txt`. They're deterministic plain-text dumps
from `render_screen_text(cmd, snapshot)` — regenerate via the one-liner
documented in the snapshot test if intentional drift occurs.

## File map

| File | Role |
|---|---|
| `tui.py` | `PrometheusApp` — compose, keybindings, slash dispatch, demo mode, SVG export, `launch_tui()` |
| `tui_state.py` | `TuiSnapshot` dataclass + `collect_snapshot` / `collect_demo_snapshot` |
| `tui_theme.py` | Color palette, `APP_CSS` stylesheet, `SIDEBAR_SECTIONS`, `COMMAND_PALETTE` registry |
| `tui_widgets.py` | `BrandHeader`, `BrandBadges`, `CommandRail`, `InspectorPanel`, `StatusBar`, `DemoRibbon` |
| `tui_screens.py` | 23 `RichCommandScreen` subclasses, `SetupScreen`, `SetupWizard`, `CommandPaletteScreen`, `dispatch_slash`, `render_screen_text` |
| `tui_commands.py` | Pure data helpers (`*_lines()`) that produce markup-bearing display strings |
