#!/usr/bin/env bash
# End-to-end: forge-12gb bundle, local models, website objective in test folder.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="${1:-/mnt/projects-ssd/test}"
CLEAN_HOME="$(mktemp -d)"
REPORT="$REPO_ROOT/docs/FORGE_12GB_E2E_REPORT.md"
ART="$REPO_ROOT/artifacts/forge_12gb_e2e"
PROM="/home/zarigata/.local/bin/prometheus"

cleanup() { rm -rf "$CLEAN_HOME"; }
trap cleanup EXIT

mkdir -p "$TEST_DIR" "$ART"
export HOME="$CLEAN_HOME"
export PROMETHEUS_HOME="$CLEAN_HOME/.prometheus"
export PATH="/home/zarigata/.local/share/prometheus/versions/v0.1.2/venv/bin:$PATH"

TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
{
  echo "# Forge-12GB end-to-end report"
  echo ""
  echo "Generated: $TS"
  echo "Test dir: \`$TEST_DIR\`"
  echo ""
} > "$REPORT"

log_section() {
  echo "" >> "$REPORT"
  echo "## $1" >> "$REPORT"
  echo "" >> "$REPORT"
  echo '```' >> "$REPORT"
}

end_section() { echo '```' >> "$REPORT"; }

echo "=== Forge-12GB E2E ==="

echo "[1/10] Reinstall check..."
log_section "Installed package features"
if grep -q "_log_user" "$(python -c 'import prometheus_cli.tui as t; print(t.__file__)')"; then
  echo "_log_user present in installed package" | tee -a "$REPORT"
else
  echo "FAIL: old package without _log_user" | tee -a "$REPORT"
  exit 1
fi
end_section

echo "[2/10] Ollama status..."
log_section "Ollama"
if ollama list > "$ART/ollama_list.txt" 2>&1; then
  cat "$ART/ollama_list.txt" >> "$REPORT"
  MODEL_COUNT=$(wc -l < "$ART/ollama_list.txt")
else
  echo "Ollama not reachable" >> "$REPORT"
  MODEL_COUNT=0
fi
end_section

echo "[3/10] Select forge-12gb..."
log_section "prometheus use forge-12gb"
cd "$TEST_DIR"
if $PROM use forge-12gb > "$ART/use_forge.txt" 2>&1; then
  cat "$ART/use_forge.txt" >> "$REPORT"
else
  cat "$ART/use_forge.txt" >> "$REPORT"
  echo "use forge-12gb failed" >> "$REPORT"
fi
end_section

echo "[4/10] Bundle inspect..."
log_section "prometheus bundles show forge-12gb"
$PROM bundles show forge-12gb > "$ART/bundle_show.txt" 2>&1 || true
cat "$ART/bundle_show.txt" >> "$REPORT"
end_section

echo "[5/10] Model pull (forge-12gb, --yes if Ollama up)..."
log_section "prometheus models pull --bundle forge-12gb --yes"
if ollama list >/dev/null 2>&1; then
  if timeout 600 $PROM models pull --bundle forge-12gb --yes --no-verify > "$ART/pull.txt" 2>&1; then
    echo "PULL OK" >> "$REPORT"
  else
    echo "PULL FAILED or timed out (600s cap)" >> "$REPORT"
  fi
  tail -30 "$ART/pull.txt" >> "$REPORT"
else
  echo "Skipped — Ollama not running" >> "$REPORT"
fi
end_section

echo "[6/10] bundles qualify forge-12gb..."
log_section "prometheus bundles qualify forge-12gb"
if $PROM bundles qualify forge-12gb > "$ART/qualify.txt" 2>&1; then
  echo "QUALIFY OK" >> "$REPORT"
else
  echo "QUALIFY SKIP/FAIL" >> "$REPORT"
fi
cat "$ART/qualify.txt" >> "$REPORT"
end_section

echo "[7/10] TUI objective thread test (forge-12gb active)..."
log_section "TUI orchestrate thread safety"
cd "$REPO_ROOT"
python - <<'PY' >> "$REPORT" 2>&1 || echo "TUI thread test FAILED" >> "$REPORT"
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
from prometheus_cli.models import AutonomyMode, Settings, ModelBundle, ModelSpec
from prometheus_cli.tui import PrometheusApp
from prometheus_cli.config import ensure_home

errors = []
lines = []
done = threading.Event()

app = PrometheusApp(workspace=Path("/mnt/projects-ssd/test"), demo=False)
app._log = lines.append
home = ensure_home()
settings = Settings(
    mode=AutonomyMode.PILOT,
    active_bundle_id="forge-12gb",
    bundle_file=home / "bundles" / "active-forge-12gb.yaml",
)
bundle = ModelBundle(
    name="Forge",
    models=[ModelSpec(model="test-model", role="controller")],
)

class FakeTurn:
    status = "complete"
    completion_percent = 100
    message = "done"

with patch("prometheus_cli.tui.load_settings", return_value=settings), \
     patch("prometheus_cli.tui.load_bundle", return_value=bundle), \
     patch("prometheus_cli.tui.Orchestrator") as orch:
    orch.return_value.run.return_value = FakeTurn()
    t = threading.Thread(target=app._orchestrate, args=("make gaming website", settings, bundle, home))
    t.start()
    t.join(timeout=30)
    assert not t.is_alive(), "orchestrate hung"
text = "\n".join(lines)
assert "sqlite" not in text.lower(), text
assert "Objective failed" not in text or "done" in text
print("TUI worker thread OK — no sqlite error")
print("Sample lines:", lines[:5])
PY
end_section

echo "[8/10] Website objective via prometheus run..."
log_section "prometheus run (gaming website)"
cd "$TEST_DIR"
mkdir -p site
if timeout 300 $PROM run "Create a simple static gaming website with index.html and style.css in ./site/" \
    --yes --max-steps 3 > "$ART/run_website.txt" 2>&1; then
  echo "RUN OK" >> "$REPORT"
else
  echo "RUN FAILED/TIMEOUT/SKIPPED" >> "$REPORT"
fi
tail -40 "$ART/run_website.txt" >> "$REPORT"
if [ -f "$TEST_DIR/site/index.html" ]; then
  echo "" >> "$REPORT"
  echo "Created files:" >> "$REPORT"
  ls -la "$TEST_DIR/site/" >> "$REPORT"
fi
end_section

echo "[9/10] Full TUI test suite..."
log_section "pytest TUI suite"
cd "$REPO_ROOT"
if .venv/bin/python -m pytest -q tests/test_tui_no_bundle_blocks_objective.py tests/test_sqlite_thread_safety.py tests/test_tui_worker_error_handling.py tests/test_tui_objective_submission_threadsafe.py 2>&1 | tee "$ART/pytest_tui.txt" >> "$REPORT"; then
  echo "pytest OK" >> "$REPORT"
else
  echo "pytest FAILED" >> "$REPORT"
fi
end_section

echo "[10/10] Project docs acceptance spot-check..."
log_section "Docs acceptance spot-check"
cd "$REPO_ROOT"
bash scripts/clean_install_defaults_smoke.sh > "$ART/clean_install.txt" 2>&1 && echo "clean_install: PASS" >> "$REPORT" || echo "clean_install: FAIL" >> "$REPORT"
bash scripts/test_folder_full_tui.sh "$TEST_DIR" > "$ART/full_tui.txt" 2>&1 && echo "full_tui: PASS" >> "$REPORT" || echo "full_tui: FAIL" >> "$REPORT"
grep -R "\[bold\|\[/bold\|\[yellow\|\[/yellow\|\[/\]" artifacts/tui >/dev/null 2>&1 && echo "markup leak: FAIL" >> "$REPORT" || echo "markup leak: PASS" >> "$REPORT"
end_section

echo ""
echo "Report: $REPORT"
echo "Artifacts: $ART/"
