#!/usr/bin/env bash
# Full TUI + CLI verification in an isolated test project folder.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="${1:-/mnt/projects-ssd/test}"
CLEAN_HOME="$(mktemp -d)"
ARTIFACTS="$REPO_ROOT/artifacts/test_folder_run"
PROM="$REPO_ROOT/.venv/bin/prometheus"
PY="$REPO_ROOT/.venv/bin/python"

cleanup() { rm -rf "$CLEAN_HOME"; }
trap cleanup EXIT

mkdir -p "$TEST_DIR" "$ARTIFACTS"
cd "$TEST_DIR"

export HOME="$CLEAN_HOME"
export PROMETHEUS_HOME="$CLEAN_HOME/.prometheus"
export PATH="$REPO_ROOT/.venv/bin:$PATH"

PASS=0
FAIL=0

check() {
    local name="$1"
    shift
    echo ""
    echo "━━━ $name ━━━"
    if "$@"; then
        echo "✓ PASS: $name"
        PASS=$((PASS + 1))
    else
        echo "✗ FAIL: $name"
        FAIL=$((FAIL + 1))
    fi
}

echo "============================================================"
echo " PROMETHEUS full test-folder verification"
echo " TEST_DIR=$TEST_DIR"
echo " HOME=$HOME (clean)"
echo "============================================================"

check "prometheus doctor" "$PROM" doctor > "$ARTIFACTS/doctor.txt" 2>&1

check "bundles list (>=8)" bash -c \
    "count=\$($PROM bundles list --json | $PY -c 'import json,sys; print(len(json.load(sys.stdin)))'); test \"\$count\" -ge 8"

check "setup dry-run (no 'No bundles found')" bash -c \
    "$PROM setup --dry-run > '$ARTIFACTS/setup.txt' 2>&1 && ! grep -q 'No bundles found' '$ARTIFACTS/setup.txt'"

check "bundleforge recommend" bash -c \
    "$PROM bundleforge recommend 'build a portfolio website' > '$ARTIFACTS/bf.txt' 2>&1 && grep -q 'Recommended' '$ARTIFACTS/bf.txt'"

check "tui launches without bundle" bash -c \
    "$PROM tui --exit-after-render > '$ARTIFACTS/tui_nobundle.txt' 2>&1"

check "tui demo mode" bash -c \
    "$PROM tui --demo --exit-after-render > '$ARTIFACTS/tui_demo.txt' 2>&1"

check "tui visual screens export" bash -c \
    "cd '$REPO_ROOT' && bash scripts/tui_visual_smoke.sh > '$ARTIFACTS/tui_visual.log' 2>&1"

check "no raw markup in artifacts/tui" bash -c \
    "cd '$REPO_ROOT' && ! grep -R '\\[bold\\|\\[/bold\\|\\[yellow\\|\\[/yellow\\|\\[/\\]' artifacts/tui 2>/dev/null"

check "no-bundle blocks objective (no sqlite)" "$PY" - <<'PY'
import sys
from pathlib import Path
from unittest.mock import patch
from prometheus_cli.models import AutonomyMode, Settings
from prometheus_cli.tui import PrometheusApp

lines: list[str] = []
app = PrometheusApp(workspace=Path("/mnt/projects-ssd/test"), demo=False)
app._log = lines.append
settings = Settings(mode=AutonomyMode.PILOT, active_bundle_id=None, bundle_file=None)
with patch("prometheus_cli.tui.load_settings", return_value=settings):
    app._log_user("please craft a website for me")
    app._run_objective("please craft a website for me")
text = "\n".join(lines)
assert "You" in text, "missing user label"
assert "#5a8aa0" in text or "hello" in text.lower() or "craft" in text.lower(), "missing user styling/content"
assert "No active bundle configured" in text, "missing setup card"
assert "sqlite" not in text.lower(), f"sqlite error leaked: {text}"
print(text[:500])
PY

check "chat user vs agent distinction" "$PY" - <<'PY'
from prometheus_cli.tui import PrometheusApp
lines: list[str] = []
app = PrometheusApp(demo=True)
app._log = lines.append
app._log_user("build me a login page")
app._log_agent("step 1: drafting acceptance criteria (42%)")
app._log_agent("JWT auth added with tests.", prefix="Result")
text = "\n".join(lines)
assert "You" in text and "build me a login page" in text
assert "◆" in text and "PROMETHEUS" in text
assert "Result" in text
assert text.index("You") < text.index("PROMETHEUS"), "user should appear before agent"
print(text)
PY

check "all slash command screens render" "$PY" - <<'PY'
from pathlib import Path
from prometheus_cli.tui import PrometheusApp, _exit_after_render

SCREENS = [
    "setup", "help", "models", "bundles", "bundleforge", "sandbox",
    "memory", "vision", "assets", "astronaut", "settings", "mcp",
    "tools", "modes", "sessions", "telemetry", "doctor", "plan",
]
for screen in SCREENS:
    app = PrometheusApp(workspace=Path("/mnt/projects-ssd/test"), demo=True)
    _exit_after_render(app, initial_screen=screen)
print(f"rendered {len(SCREENS)} screens OK")
PY

check "sqlite thread repro" bash -c "cd '$REPO_ROOT' && $PY scripts/repro_tui_sqlite_thread_bug.py | grep -q 'BUG FIXED'"

check "bundle alias ember-8gb resolves" bash -c \
    "$PROM bundles inspect ember-8gb > '$ARTIFACTS/ember.txt' 2>&1 || $PROM bundles show ember-8gb > '$ARTIFACTS/ember.txt' 2>&1; grep -qi ember '$ARTIFACTS/ember.txt'"

echo ""
echo "============================================================"
echo " Results: $PASS passed, $FAIL failed"
echo " Logs: $ARTIFACTS/"
echo "============================================================"
test "$FAIL" -eq 0
