#!/usr/bin/env bash
# Local model smoke — detect Ollama, list models, qualify low-end bundles.
# Records results in docs/LOCAL_MODEL_TEST_REPORT.md.
#
# Real Ollama pulls are skipped unless PROMETHEUS_RUN_OLLAMA_TESTS=1.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
REPORT="$REPO_ROOT/docs/LOCAL_MODEL_TEST_REPORT.md"
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

PROM="${PROM:-prometheus}"
RUN_OLLAMA="${PROMETHEUS_RUN_OLLAMA_TESTS:-0}"

mkdir -p docs
{
    echo "# Local model test report"
    echo ""
    echo "Generated: $TS"
    echo ""
    echo "## Environment"
    echo ""
    echo "- PROMETHEUS_RUN_OLLAMA_TESTS: \`$RUN_OLLAMA\`"
    echo "- Python: \`$(python --version 2>&1)\`"
    echo ""
} > "$REPORT"

echo "=== PROMETHEUS local model smoke ==="

echo "[1/6] Detecting Ollama..."
if "$PROM" models list > /tmp/prometheus_local_models.txt 2>/tmp/prometheus_local_models.err; then
    echo "  Ollama reachable"
    echo "## Ollama status" >> "$REPORT"
    echo "" >> "$REPORT"
    echo "Ollama: **reachable**" >> "$REPORT"
    echo "" >> "$REPORT"
    echo '```' >> "$REPORT"
    cat /tmp/prometheus_local_models.txt >> "$REPORT"
    echo '```' >> "$REPORT"
else
    echo "  Ollama not running or not installed"
    echo "## Ollama status" >> "$REPORT"
    echo "" >> "$REPORT"
    echo "Ollama: **not reachable** (skipped live qualification)" >> "$REPORT"
    echo "" >> "$REPORT"
    echo '```' >> "$REPORT"
    cat /tmp/prometheus_local_models.err >> "$REPORT" || true
    echo '```' >> "$REPORT"
fi

echo "[2/6] Bundle list (packaged defaults)..."
BUNDLE_COUNT=$("$PROM" bundles list --json 2>/dev/null | python -c "import json,sys; print(len(json.load(sys.stdin)))")
echo "  $BUNDLE_COUNT bundles"
echo "" >> "$REPORT"
echo "## Packaged bundles" >> "$REPORT"
echo "" >> "$REPORT"
echo "Count: **$BUNDLE_COUNT**" >> "$REPORT"

echo "[3/6] Qualify ember-8gb (alias)..."
if "$PROM" bundles qualify ember-8gb > /tmp/prometheus_qualify_ember.txt 2>&1; then
    echo "  ember-8gb: PASS"
    EMBER_RESULT="PASS"
else
    echo "  ember-8gb: SKIP/FAIL (see report)"
    EMBER_RESULT="SKIP/FAIL"
fi
echo "" >> "$REPORT"
echo "## Bundle qualification" >> "$REPORT"
echo "" >> "$REPORT"
echo "### ember-8gb" >> "$REPORT"
echo "" >> "$REPORT"
echo "Result: **$EMBER_RESULT**" >> "$REPORT"
echo "" >> "$REPORT"
echo '```' >> "$REPORT"
cat /tmp/prometheus_qualify_ember.txt >> "$REPORT"
echo '```' >> "$REPORT"

echo "[4/6] Qualify forge-12gb..."
if "$PROM" bundles qualify forge-12gb > /tmp/prometheus_qualify_forge.txt 2>&1; then
    echo "  forge-12gb: PASS"
    FORGE_RESULT="PASS"
else
    echo "  forge-12gb: SKIP/FAIL (see report)"
    FORGE_RESULT="SKIP/FAIL"
fi
echo "" >> "$REPORT"
echo "### forge-12gb" >> "$REPORT"
echo "" >> "$REPORT"
echo "Result: **$FORGE_RESULT**" >> "$REPORT"
echo "" >> "$REPORT"
echo '```' >> "$REPORT"
cat /tmp/prometheus_qualify_forge.txt >> "$REPORT"
echo '```' >> "$REPORT"

echo "[5/6] Provider smoke..."
if "$PROM" provider smoke > /tmp/prometheus_provider_smoke.txt 2>&1; then
    echo "  provider smoke: PASS"
    PROVIDER_RESULT="PASS"
else
    echo "  provider smoke: SKIP/FAIL"
    PROVIDER_RESULT="SKIP/FAIL"
fi
echo "" >> "$REPORT"
echo "## Provider smoke" >> "$REPORT"
echo "" >> "$REPORT"
echo "Result: **$PROVIDER_RESULT**" >> "$REPORT"
echo "" >> "$REPORT"
echo '```' >> "$REPORT"
cat /tmp/prometheus_provider_smoke.txt >> "$REPORT"
echo '```' >> "$REPORT"

echo "[6/6] Optional tiny model pull..."
if [ "$RUN_OLLAMA" = "1" ]; then
    echo "  PROMETHEUS_RUN_OLLAMA_TESTS=1 — attempting tiny model pull with --yes"
    if "$PROM" models pull qwen2.5-coder:0.5b --yes --no-verify > /tmp/prometheus_tiny_pull.txt 2>&1; then
        PULL_RESULT="PASS"
    else
        PULL_RESULT="FAIL"
    fi
else
    echo "  Skipped (set PROMETHEUS_RUN_OLLAMA_TESTS=1 to enable)"
    PULL_RESULT="SKIPPED — PROMETHEUS_RUN_OLLAMA_TESTS not set"
    echo "(skipped)" > /tmp/prometheus_tiny_pull.txt
fi
echo "" >> "$REPORT"
echo "## Tiny model pull (qwen2.5-coder:0.5b)" >> "$REPORT"
echo "" >> "$REPORT"
echo "Result: **$PULL_RESULT**" >> "$REPORT"
echo "" >> "$REPORT"
echo '```' >> "$REPORT"
cat /tmp/prometheus_tiny_pull.txt >> "$REPORT"
echo '```' >> "$REPORT"

echo ""
echo "Report written to $REPORT"
echo "=== local model smoke complete ==="
