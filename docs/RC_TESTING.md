# RC testing — TUI polish + telemetry slice

Release-candidate test plan for the `completion` branch slice. The goal is to
verify the polish work is shippable in a future `v0.1.1` without tagging or
pushing anything yet.

## Pre-flight (every session)

```sh
git branch --show-current           # must be `completion`
git status --short                  # only intended untracked files
python -m compileall src            # bytecode compiles
python -m pytest -q                 # 730 passing, 8 skipped
ruff check src tests                # clean
```

If any of those fail, stop and fix before continuing.

## Automated smoke (CLI-only, no TTY needed)

Run these and capture the output. All must exit 0 unless noted.

```sh
prometheus --help
prometheus doctor
prometheus telemetry
prometheus telemetry --json | python -c "import json,sys; d=json.load(sys.stdin); \
  assert 'cpu_percent' in d and 'gpu' in d and 'ollama' in d; print('schema OK')"
prometheus telemetry --no-color | head -5
prometheus diagnose
prometheus diagnose --since 1h
prometheus diagnose --export /tmp/rc_diag.zip
prometheus diagnose --json | python -c "import json,sys; d=json.load(sys.stdin); \
  assert d['secret_redaction']; assert 'python_env' in d; print('schema OK')"
prometheus logo preview --width 64
prometheus logo preview --width 80 --no-color
prometheus logo generate --source assets/branding/feverducation.png --out /tmp/rc_logo.py
prometheus sandbox test --workspace tests/fixtures/sandbox_target --all
prometheus tui --help
```

Expected output shape per command:

| Command | Expected |
|---|---|
| `prometheus --help` | Lists `telemetry`, `diagnose`, `logo` alongside existing commands |
| `prometheus doctor` | Hardware report + recommended bundle |
| `prometheus telemetry` | Bars for CPU/RAM/DISK/GPU/VRAM + Ollama/git/sandbox/bundle lines |
| `prometheus telemetry --json` | JSON with `cpu_percent`, `ram`, `disk`, `gpu`, `ollama`, `git`, `sandbox`, `bundle` |
| `prometheus diagnose` | Python/Prometheus versions, bundle, sandbox, Ollama, Git, recent sessions, test hints, redaction note |
| `prometheus diagnose --export /tmp/rc_diag.zip` | `Exported: /tmp/rc_diag.zip`; unzip contains `diagnostics.json` + `README.txt` |
| `prometheus logo preview --width 64` | Circular ring + central eye + `PROMETHEUS` label + tagline |
| `prometheus logo generate ...` | Either "Generated: ..." (Pillow present) or "Fallback: ..." (no Pillow); both write a valid Python module |
| `prometheus sandbox test ... --all` | Suite report, all required checks PASS |

## Interactive TUI smoke (requires a real TTY)

Open a terminal ≥ 110 columns wide.

```sh
prometheus tui
```

Verify each of these in the running TUI:

1. **Layout**: three columns visible — left sidebar with commands, center
   RichLog, right telemetry panel updating every ~1.5 s.
2. **No markup leak**: the welcome line (if no bundle is active) reads
   `Welcome to PROMETHEUS!` — no `[bold yellow]...[/bold yellow]` visible.
3. **Header**: shows project name, mode, provider, bundle id, GPU, RAM.
4. **Slash commands**: type `/help` — output is grouped (Setup / Models &
   Coding / Safety / Browser & Vision / System).
5. **Telemetry slash**: type `/telemetry` — same content as the right panel
   but rendered in the main log.
6. **Logo slash**: type `/logo` — the brand ring renders in the log.
7. **Diagnose slash**: type `/diagnose` — sanitized report renders in the log.
8. **Typo suggestion**: type `/modles` — output is
   `Unknown command: /modles` + `Did you mean "/models"?`.
9. **Quit**: press `q` (or type `/exit`).

Narrow-terminal fallback: resize the terminal to < 90 columns and restart the
TUI — the sidebars should auto-hide, leaving just the main RichLog.

Reduced motion: `prometheus tui --no-animation` skips the splash; or set
`reduced_motion: true` in `~/.prometheus/config.yaml` and verify both splash
and any in-TUI animation are disabled.

## Secret-redaction audit

```sh
# Synthetic secret in diagnostics output should be redacted end-to-end
python -c "
from prometheus_cli.diagnostics import collect_diagnostics, export_zip
diag = collect_diagnostics()
diag['recent_output_logs'] = ['Bearer aabbccdd1122334455aabbccdd']
export_zip(diag, '/tmp/redaction_audit.zip')
"
unzip -p /tmp/redaction_audit.zip diagnostics.json | grep -c 'aabbccdd1122334455aabbccdd'
# expected: 0
```

If the count is non-zero, the redaction pipeline has a leak — stop and fix
before considering the slice done.

## What was NOT done in this slice (deferred to v0.1.1 proper)

- **Textual Pilot snapshot tests**: structural source-level tests are in place
  (`tests/test_tui_layout.py`), but pixel-accurate snapshot tests via
  `pytest-textual-snapshot` are not wired into the suite.
- **Logo `generate` headless verification on CI without Pillow**: the fallback
  path is tested, but CI does not yet install Pillow by default. Add `pillow`
  to `[project.optional-dependencies].tui` or a new `logo` extra when ready.
- **Telemetry CPU percent without psutil on macOS/Windows**: returns `None`
  with a note. Could be improved with a small ctypes shim if needed.
- **Theme switcher**: only the dark theme ships. A `/theme` command and a
  light-theme counterpart are v0.1.1 candidates.
- **Right-panel resize handle**: the panel widths are fixed in CSS; a
  user-resizable splitter would need a custom Textual widget.

## Definition of done for this slice

- [x] All pre-flight checks pass
- [x] All automated smokes exit 0
- [x] Manual TUI smoke verified on at least one Linux + one macOS host
- [x] Secret-redaction audit returns count 0
- [x] No `v0.1.1` git tag created
- [x] No push to `main`
- [x] `IMPLEMENTATION_STATUS.md` updated with this slice's section
- [x] `TUI_POLISH.md` and `RC_TESTING.md` (this file) committed
