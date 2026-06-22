#!/usr/bin/env bash
# PROMETHEUS TUI visual smoke test.
#
# Drives the TUI in deterministic --demo mode and exports an SVG screenshot
# of every required UI state to artifacts/tui/. Demo mode needs no Ollama,
# no cloud keys, no model downloads, no real project. Output is gitignored.
#
# Usage: bash scripts/tui_visual_smoke.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

mkdir -p artifacts/tui
OUT_DIR="artifacts/tui"

python - <<'PY'
import asyncio
from pathlib import Path
from prometheus_cli.tui import PrometheusApp

OUT_DIR = Path("artifacts/tui")

STATES = [
    ("startup",          None,           (120, 36), None),
    ("startup_80x24",    None,           (80, 24),  None),
    ("startup_100x30",   None,           (100, 30), None),
    ("startup_120x36",   None,           (120, 36), None),
    ("startup_160x48",   None,           (160, 48), None),
    ("setup",            "/setup",       (120, 36), None),
    ("help",             "/help",        (120, 36), None),
    ("models",           "/models",      (120, 36), None),
    ("bundles",          "/bundles",     (120, 36), None),
    ("sandbox",          "/sandbox",     (120, 36), None),
    ("memory",           "/memory",      (120, 36), None),
    ("vision",           "/vision",      (120, 36), None),
    ("assets",           "/assets",      (120, 36), None),
    ("astronaut",        "/astronaut",   (120, 36), None),
    ("doctor",           "/doctor",      (120, 36), None),
    ("settings",         "/settings",    (120, 36), None),
    ("mcp",              "/mcp",         (120, 36), None),
    ("tools",            "/tools",       (120, 36), None),
    ("modes",            "/modes",       (120, 36), None),
    ("sessions",         "/sessions",    (120, 36), None),
    ("telemetry",        "/telemetry",   (120, 36), None),
    ("logo",             "/logo",        (120, 36), None),
    ("diagnose",         "/diagnose",    (120, 36), None),
    ("plan",             "/plan",        (120, 36), None),
    ("permissions",      "/permissions", (120, 36), None),
    ("providers",        "/providers",   (120, 36), None),
    ("palette",          None,           (120, 36), "__palette__"),
]

async def main():
    ok = err = 0
    for name, cmd, size, special in STATES:
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        try:
            async with app.run_test(headless=True, size=size) as pilot:
                await pilot.pause(0.15)
                if special == "__palette__":
                    app.action_command_palette()
                    await pilot.pause(0.2)
                elif cmd:
                    app._dispatch_slash_text(cmd)
                    await pilot.pause(0.2)
                svg = app.export_screenshot(title=f"PROMETHEUS — {name}")
                (OUT_DIR / f"{name}.svg").write_text(svg, encoding="utf-8")
                ok += 1
                print(f"  OK   {name:<20} {len(svg):>7} bytes  ({size[0]}x{size[1]})")
        except Exception as exc:
            err += 1
            print(f"  ERR  {name:<20} {type(exc).__name__}: {str(exc)[:80]}")
    print(f"\nExported {ok} SVGs to {OUT_DIR}/  ({err} errors)")

asyncio.run(main())
PY

echo "---"
echo "Output directory:"
ls -la "$OUT_DIR" | head -32
echo "---"
echo "Total files: $(ls "$OUT_DIR"/*.svg 2>/dev/null | wc -l)"
exit 0
