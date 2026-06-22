# TUI Visual QA Report

## Methodology

The PROMETHEUS TUI is tested via deterministic headless Textual test runs that
export SVG screenshots of every screen at multiple terminal sizes. All tests run
in `--demo` mode (no Ollama, no cloud keys, no model downloads). Raw Rich markup
fragments are grepped from every exported artifact.

## Artifact paths

All visual smoke artifacts are exported to:

```
artifacts/tui/
```

This directory is gitignored. Small golden text fixtures live in:

```
tests/golden/tui/
```

## Terminal sizes tested

| Size | Sidebar | Inspector | Notes |
|---|---|---|---|
| 80×24 | Hidden | Hidden | Minimum supported; main area gets full width |
| 100×30 | Visible | Hidden | Inspector collapses below 100 cols |
| 120×36 | Visible | Visible | Standard development terminal |
| 160×48 | Visible | Visible | Wide terminal; rich content verified |

## Screens tested

| Screen | Command | SVG size | Status |
|---|---|---|---|
| Startup dashboard | (default) | ~96 KB | ✅ Pass |
| Setup wizard (9 steps) | `/setup` | ~70 KB | ✅ Pass |
| Help / command palette | `/help` | ~68 KB | ✅ Pass |
| Models | `/models` | ~62 KB | ✅ Pass |
| Bundles | `/bundles` | ~62 KB | ✅ Pass |
| BundleForge | `/bundleforge` | ~60 KB | ✅ Pass |
| Sandbox | `/sandbox` | ~62 KB | ✅ Pass |
| Memory | `/memory` | ~60 KB | ✅ Pass |
| Vision | `/vision` | ~60 KB | ✅ Pass |
| Assets | `/assets` | ~60 KB | ✅ Pass |
| Astronaut | `/astronaut` | ~60 KB | ✅ Pass |
| Settings | `/settings` | ~71 KB | ✅ Pass |
| Doctor | `/doctor` | ~60 KB | ✅ Pass |
| MCP | `/mcp` | ~60 KB | ✅ Pass |
| Command palette | Ctrl+P | ~71 KB | ✅ Pass |

## Visual gates

The test suite fails if any of the following are detected:

| Gate | Test file | Status |
|---|---|---|
| Raw Rich markup in SVG export | `test_tui_raw_markup_export.py` | ✅ Enforced |
| Screen is mostly empty (< 50 chars) | `test_tui_no_empty_debug_panel.py` | ✅ Enforced |
| Required header missing | `test_tui_no_empty_debug_panel.py` | ✅ Enforced |
| Sidebar missing at normal size | `test_tui_no_empty_debug_panel.py` | ✅ Enforced |
| Status bar missing | `test_tui_no_empty_debug_panel.py` | ✅ Enforced |
| Input missing | `test_tui_no_empty_debug_panel.py` | ✅ Enforced |
| Inspector missing at wide size | `test_tui_responsive.py` | ✅ Enforced |
| Crash at 80×24 | `test_tui_responsive.py` | ✅ Enforced |

## Raw markup grep

```sh
grep -R "\[bold\|\[/bold\|\[yellow\|\[/yellow\|\[/\]" artifacts/tui/
# Result: no matches
```

The following markup tags are checked in every exported SVG:

```
[bold  [/bold]  [yellow  [/yellow]  [red  [/red]
[green  [/green]  [cyan  [/cyan]  [dim]  [/dim]
[/]  [section]  [gold]  [k]  [v]  [ok]  [warn]  [err]  [info]
```

## Content density heuristic

Every screen must produce at least 50 non-whitespace characters of plain text
and at least 3 non-empty lines. The dashboard SVG must have at least 200
non-whitespace visible characters.

## Known visual issues

- **Interactive wizard modal** (`/setup-wizard`): works in a real TTY but the
  headless test path uses `/setup` (static rendering of all 9 steps) for
  cross-mode reliability.
- **Sidebar entries**: non-clickable in the current MVP (mapped to slash commands
  but no mouse handler). Keyboard navigation via `/command` works.
- **Right inspector**: shows a system digest by default; per-screen contextual
  detail is set via `set_context()` on each command dispatch.

## Before/after summary

| Aspect | Before (original TUI) | After (current) |
|---|---|---|
| Raw markup | `[bold yellow]Welcome...[/bold yellow]` visible | Zero markup in any export |
| Layout | Single giant debug panel | 3-column shell (sidebar, main, inspector) |
| Screens | 3 commands | 24 screens + palette + 9-step wizard |
| Responsive | Crashed at < 100 cols | Graceful collapse at 80×24 |
| Empty panel | Main area mostly empty | Content density enforced (200+ chars) |
| SVG export | Not tested | 36 artifacts exported, all verified |
