#!/usr/bin/env bash
set -euo pipefail

# Step 1 clean-install smoke: build wheel, install into clean venv, verify defaults.
# Exit codes: 0 = pass, 1 = fail.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$(mktemp -d)"
TMP_HOME="$(mktemp -d)"
TMP_VENV="$(mktemp -d)"

cleanup() {
    rm -rf "$BUILD_DIR" "$TMP_HOME" "$TMP_VENV"
}
trap cleanup EXIT

echo "=== PROMETHEUS clean-install defaults smoke ==="
echo ""

cd "$REPO_ROOT"

echo "[1/5] Building wheel + sdist..."
python -m build --outdir "$BUILD_DIR" .

WHEEL="$(ls "$BUILD_DIR"/*.whl | head -1)"
if [ -z "$WHEEL" ]; then
    echo "FAIL: no wheel built"
    exit 1
fi
echo "  wheel: $(basename "$WHEEL")"

echo "[2/5] Creating clean venv..."
python -m venv "$TMP_VENV"
"$TMP_VENV/bin/pip" install --quiet --upgrade pip
"$TMP_VENV/bin/pip" install --quiet "$WHEEL"
echo "  installed into: $TMP_VENV"

echo "[3/5] Testing: prometheus bundles list"
HOME="$TMP_HOME" "$TMP_VENV/bin/prometheus" bundles list --json > /tmp/prometheus_smoke_bundles.json 2>/tmp/prometheus_smoke_bundles.err || {
    echo "FAIL: bundles list failed"
    cat /tmp/prometheus_smoke_bundles.err
    exit 1
}
BUNDLE_COUNT=$(python -c "import json; print(len(json.load(open('/tmp/prometheus_smoke_bundles.json'))))")
if [ "$BUNDLE_COUNT" -lt 8 ]; then
    echo "FAIL: expected >= 8 bundles, got $BUNDLE_COUNT"
    exit 1
fi
echo "  found $BUNDLE_COUNT bundles"

echo "[4/5] Testing: prometheus setup --dry-run"
HOME="$TMP_HOME" "$TMP_VENV/bin/prometheus" setup --dry-run > /tmp/prometheus_smoke_setup.txt 2>&1 || {
    echo "FAIL: setup --dry-run failed"
    cat /tmp/prometheus_smoke_setup.txt
    exit 1
}
if grep -q "No bundles found" /tmp/prometheus_smoke_setup.txt; then
    echo "FAIL: setup --dry-run still says 'No bundles found'"
    cat /tmp/prometheus_smoke_setup.txt
    exit 1
fi
if ! grep -q "Available bundles" /tmp/prometheus_smoke_setup.txt; then
    echo "FAIL: setup --dry-run does not show 'Available bundles'"
    cat /tmp/prometheus_smoke_setup.txt
    exit 1
fi
echo "  setup --dry-run shows bundles (no 'No bundles found' error)"

echo "[5/5] Testing: prometheus doctor"
HOME="$TMP_HOME" "$TMP_VENV/bin/prometheus" doctor > /tmp/prometheus_smoke_doctor.txt 2>&1 || {
    echo "FAIL: doctor failed"
    cat /tmp/prometheus_smoke_doctor.txt
    exit 1
}
echo "  doctor runs successfully"

echo ""
echo "=== PASS: clean install includes defaults ==="
echo "  bundles: $BUNDLE_COUNT"
echo "  setup --dry-run: OK"
echo "  doctor: OK"
