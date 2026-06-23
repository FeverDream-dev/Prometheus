#!/usr/bin/env bash
# Smoke-test TUI objective flow in an isolated test project folder.
# Verifies no-bundle blocking and no SQLite thread errors.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="${1:-/tmp/prometheus_tui_test_project}"
CLEAN_HOME="$(mktemp -d)"

cleanup() {
    rm -rf "$CLEAN_HOME"
}
trap cleanup EXIT

mkdir -p "$TEST_DIR"
cd "$REPO_ROOT"

if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

export HOME="$CLEAN_HOME"
export PROMETHEUS_HOME="$CLEAN_HOME/.prometheus"

echo "=== TUI test-folder smoke ==="
echo "TEST_DIR=$TEST_DIR"
echo "HOME=$HOME"
echo ""

echo "[1/3] Submit objective with no bundle (must block, no crash)..."
OUT="$(python - <<'PY'
import asyncio
from pathlib import Path
from prometheus_cli.tui import PrometheusApp

TEST_DIR = Path(__import__("os").environ.get("TEST_DIR_OVERRIDE", "/tmp/prometheus_tui_test_project"))

class CaptureApp(PrometheusApp):
  lines: list[str] = []

  def _log(self, message: str) -> None:
    self.lines.append(message)

async def main():
    app = CaptureApp(workspace=TEST_DIR, demo=False)
    app._log_user = lambda t: app._log(f"USER:{t}")
    app._run_objective("please craft a website for me")
    return "\n".join(app.lines)

print(asyncio.run(main()))
PY
)"
echo "$OUT" | head -20
if echo "$OUT" | grep -qi "sqlite"; then
    echo "FAIL: SQLite error in transcript"
    exit 1
fi
if ! echo "$OUT" | grep -q "No active bundle configured"; then
    echo "FAIL: expected no-bundle guidance"
    exit 1
fi
echo "  OK — blocked without SQLite error"

echo "[2/3] SessionStore thread-safety repro..."
python scripts/repro_tui_sqlite_thread_bug.py

echo "[3/3] Headless TUI demo render..."
cd "$TEST_DIR"
prometheus tui --demo --exit-after-render

echo ""
echo "=== PASS: test-folder smoke ==="
