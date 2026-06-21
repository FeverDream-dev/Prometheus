# TUI polish + live telemetry slice

This document covers the TUI polish vertical slice on the `completion` branch:
what changed, how to manually smoke-test it, telemetry limitations by GPU
vendor, how to disable animation, and the test surface.

## What changed

| Area | Before | After |
|---|---|---|
| Markup rendering | Textual `Log` widget wrote `[bold yellow]Welcome...[/bold yellow]` as literal text | `RichLog` widget parses markup; 18 regression tests pin this |
| Layout | Sparse single-column (header, log, input, footer) | Three columns: command sidebar · main RichLog · live telemetry; dark theme; responsive collapse |
| Telemetry | None | New `prometheus_cli/telemetry.py`; `prometheus telemetry [--json]`; TUI right-panel live bars every 1.5 s |
| Logo | Placeholder ember squares; `TEMPORARY_ASCII_LOGO = True` | Brand-derived circular ring + eye + name + tagline; 12-frame rotating palette-cycle animation; `TEMPORARY_ASCII_LOGO = False` |
| Onboarding | Plain banner text | Boxed PROMETHEUS header + system summary + recommended bundle + provider + Ollama status + next-action commands |
| Command palette | Flat alphabetical list | Grouped (`Setup` / `Models & Coding` / `Safety` / `Browser & Vision` / `System`); fuzzy typo suggestions |
| Diagnostics | None | `prometheus_cli/diagnostics.py`; `prometheus diagnose [--since 1h] [--export diag.zip]`; recursive secret redaction |
| Settings | No reduced-motion field | `Settings.reduced_motion`, `Settings.tui_telemetry_panel` added |

New CLI commands: `prometheus telemetry`, `prometheus diagnose`, `prometheus logo preview`, `prometheus logo generate`.

New slash commands: `/telemetry`, `/logo`, `/diagnose`, `/provider`.

## Manual smoke test (run in order)

```sh
# 1. Baseline still green
python -m compileall src
python -m pytest -q
ruff check src tests

# 2. Help surface shows the new commands
prometheus --help                        # should list telemetry, diagnose, logo
prometheus telemetry --help
prometheus diagnose --help
prometheus logo preview --help
prometheus logo generate --help

# 3. Live telemetry (this machine)
prometheus telemetry                     # human-readable bars
prometheus telemetry --json              # machine-readable snapshot
prometheus telemetry --no-color          # ANSI stripped

# 4. Brand logo
prometheus logo preview --width 64       # static circular ring + eye + name
prometheus logo preview --width 80 --animated    # rotating highlight (needs TTY)
prometheus logo generate --source assets/branding/feverducation.png --out /tmp/gen.py

# 5. Diagnostics + secret redaction
prometheus diagnose                      # versions, config, git, ollama, test hints
prometheus diagnose --since 1h           # last-hour window
prometheus diagnose --export /tmp/diag.zip
unzip -p /tmp/diag.zip diagnostics.json | head

# 6. Doctor and sandbox (unchanged but verified)
prometheus doctor
prometheus sandbox test --workspace tests/fixtures/sandbox_target --all

# 7. TUI (interactive — needs a real TTY)
prometheus tui --help
prometheus tui                           # three-column layout + live telemetry
prometheus tui --no-animation            # skip splash animation
```

Inside the TUI, type `/help` for the grouped palette, `/telemetry` for a
one-shot snapshot, `/logo` for the brand mark, `/diagnose` for a quick
sanitized report, and `/modles` (intentional typo) to see the
`Did you mean "/models"?` suggestion.

## Telemetry limitations by GPU vendor

The telemetry module prefers `nvidia-smi`, then `rocm-smi`, then falls back to
the static `hardware.py` probe (vendor + VRAM, but no live usage). All probes
run with a strict 1.5 s timeout (configurable via `--gpu-timeout`) and never
crash the TUI if the tool is missing or hangs.

| Vendor | Live usage % | Live VRAM | Source | Notes |
|---|---|---|---|---|
| NVIDIA | ✅ | ✅ | `nvidia-smi --query-gpu=...` | Works on Linux/macOS/WSL with the binary on PATH |
| AMD | ✅ | ✅ | `rocm-smi --showuse --showmeminfo vram --json` | Linux only; on macOS/Windows AMD GPUs fall back to hardware-detect |
| Intel | ❌ | ❌ (Linux sysfs reports total only) | `hardware.py` | Live usage unavailable; vendor + total VRAM shown |
| Apple Silicon | ❌ | ❌ | `hardware.py` | Metal/unified memory reported; live usage unavailable without psutil |
| Unknown / CPU-only | ❌ | ❌ | — | Shown as "CPU-only mode" |

CPU percent uses `psutil.cpu_percent` when available; otherwise it samples
`/proc/stat` twice with a short interval (Linux only). On macOS/Windows
without psutil, CPU percent returns `None` and a note is added.

The right-hand TUI panel auto-hides on terminals narrower than 110 columns;
the left sidebar auto-hides below 90 columns. The telemetry polling interval
is 1.5 s and can be disabled by setting `tui_telemetry_panel: false` in
`~/.prometheus/config.yaml`.

## How to disable animation

Three ways, in increasing scope:

1. **One-shot**: `prometheus tui --no-animation` (skips splash, TUI still works)
2. **Persistent**: `prometheus init` then edit `~/.prometheus/config.yaml` and
   set `reduced_motion: true` — splash AND any in-TUI animation are disabled
3. **Environment**: `PROMETHEUS_NO_ANIMATION=1` (same effect as `--no-animation`)
   or `NO_COLOR=1` (also strips ANSI from the logo colorize path)

`prometheus logo preview --no-animation` and `--no-color` give the equivalent
controls for the standalone logo preview command.

## Test surface

| File | Count | Purpose |
|---|---|---|
| `tests/test_tui_markup_regression.py` | 18 | Source-level + render-level markup leak coverage |
| `tests/test_telemetry.py` | 17 | nvidia-smi/rocm-smi parsers, bar renderer, snapshot schema, JSON output |
| `tests/test_logo.py` | 22 | Brand art, animation, color/no-color, generate-with-Pillow, fallback |
| `tests/test_tui_layout.py` | 10 | Three-column CSS, dark theme, sidebar/telemetry methods, responsive kwargs |
| `tests/test_diagnostics.py` | 21 | Secret redaction (parametrized), `_safe` filename guard, zip export, schema |

Total: **+82 tests** over the 648-test baseline → 730 passing, 8 skipped.

## Files changed

```
src/prometheus_cli/tui.py              Log→RichLog; three-column layout; sidebar; live telemetry polling
src/prometheus_cli/tui_commands.py     Grouped help; fuzzy suggest; onboarding/telemetry/logo/diagnose lines
src/prometheus_cli/cli.py              +telemetry +diagnose +logo preview/generate commands
src/prometheus_cli/models.py           +reduced_motion +tui_telemetry_panel Settings fields
src/prometheus_cli/telemetry.py        NEW: psutil-optional CPU/RAM + subprocess-timeout GPU probes
src/prometheus_cli/logo.py             REWRITE: brand ring + rotating-palette animation + Pillow-optional generate
src/prometheus_cli/diagnostics.py      NEW: sanitized diagnostics + recursive secret redaction + zip export
assets/branding/feverducation.png      NEW: company logo source (committed; .gitignore allows png under assets/)
tests/test_tui_markup_regression.py    NEW
tests/test_telemetry.py                NEW
tests/test_tui_layout.py               NEW
tests/test_diagnostics.py              NEW
tests/test_logo.py                     REWRITE for the new brand-art API
docs/IMPLEMENTATION_STATUS.md          Slice section appended
docs/TUI_POLISH.md                     NEW (this file)
docs/RC_TESTING.md                     NEW
assets/branding/README.md              NEW
```
