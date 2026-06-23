#!/usr/bin/env bash
# Full installed-product smoke — clean HOME, install from public installer, verify.
#
# Unreleased main: PROMETHEUS_REF=main bash scripts/full_installed_product_smoke.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLEAN_HOME="$(mktemp -d)"
BIN_DIR="$CLEAN_HOME/.local/bin"
PREFIX="$CLEAN_HOME/.local/share/prometheus"
ARTIFACTS="$REPO_ROOT/artifacts/full_install_smoke"
PROMETHEUS_REF="${PROMETHEUS_REF:-}"
INSTALL_URL="https://feverdream-dev.github.io/Prometheus/install.sh"

cleanup() {
    rm -rf "$CLEAN_HOME"
}
trap cleanup EXIT

mkdir -p "$ARTIFACTS"
cd "$REPO_ROOT"

echo "=== PROMETHEUS full installed-product smoke ==="
echo "CLEAN_HOME=$CLEAN_HOME"
echo ""

echo "[1/8] Installing from public installer..."
INSTALL_ENV=(HOME="$CLEAN_HOME")
if [ -n "$PROMETHEUS_REF" ]; then
    INSTALL_ENV+=(PROMETHEUS_REF="$PROMETHEUS_REF")
    echo "  PROMETHEUS_REF=$PROMETHEUS_REF"
fi
if ! curl -fsSL "$INSTALL_URL" | env "${INSTALL_ENV[@]}" sh -s -- --yes --no-ollama \
    --bin "$BIN_DIR" --prefix "$PREFIX" > "$ARTIFACTS/install.log" 2>&1; then
    echo "FAIL: public installer failed"
    tail -40 "$ARTIFACTS/install.log"
    exit 1
fi
echo "  install OK"

export PATH="$BIN_DIR:$PATH"
export HOME="$CLEAN_HOME"
export PROMETHEUS_HOME="$CLEAN_HOME/.prometheus"

echo "[2/8] prometheus doctor"
if ! prometheus doctor > "$ARTIFACTS/doctor.txt" 2>&1; then
    echo "FAIL: doctor"
    cat "$ARTIFACTS/doctor.txt"
    exit 1
fi
echo "  doctor OK"

echo "[3/8] prometheus bundles list"
if ! prometheus bundles list --json > "$ARTIFACTS/bundles.json" 2>"$ARTIFACTS/bundles.err"; then
    echo "FAIL: bundles list"
    cat "$ARTIFACTS/bundles.err"
    exit 1
fi
BUNDLE_COUNT=$(python -c "import json; print(len(json.load(open('$ARTIFACTS/bundles.json'))))")
if [ "$BUNDLE_COUNT" -lt 8 ]; then
    echo "FAIL: expected >= 8 bundles, got $BUNDLE_COUNT"
    exit 1
fi
if grep -q "No bundles found" "$ARTIFACTS/bundles.err" 2>/dev/null; then
    echo "FAIL: No bundles found in bundles list"
    exit 1
fi
echo "  found $BUNDLE_COUNT bundles"

echo "[4/8] prometheus setup --dry-run"
if ! prometheus setup --dry-run > "$ARTIFACTS/setup.txt" 2>&1; then
    echo "FAIL: setup --dry-run"
    cat "$ARTIFACTS/setup.txt"
    exit 1
fi
if grep -q "No bundles found" "$ARTIFACTS/setup.txt"; then
    echo "FAIL: setup says No bundles found"
    cat "$ARTIFACTS/setup.txt"
    exit 1
fi
echo "  setup --dry-run OK"

echo "[5/8] prometheus tui --demo --exit-after-render"
if ! prometheus tui --demo --exit-after-render > "$ARTIFACTS/tui_demo.txt" 2>&1; then
    echo "FAIL: tui demo"
    cat "$ARTIFACTS/tui_demo.txt"
    exit 1
fi
echo "  tui demo OK"

echo "[6/8] bundleforge recommend"
if ! prometheus bundleforge recommend "I want to build a portfolio website" > "$ARTIFACTS/bundleforge.txt" 2>&1; then
    echo "FAIL: bundleforge recommend"
    cat "$ARTIFACTS/bundleforge.txt"
    exit 1
fi
echo "  bundleforge OK"

echo "[7/8] sandbox test"
SANDBOX_WS="$REPO_ROOT/tests/fixtures/sandbox_target"
if [ -d "$SANDBOX_WS" ]; then
    if ! prometheus sandbox test --workspace "$SANDBOX_WS" --all > "$ARTIFACTS/sandbox.txt" 2>&1; then
        echo "FAIL: sandbox test"
        tail -30 "$ARTIFACTS/sandbox.txt"
        exit 1
    fi
    echo "  sandbox OK"
else
    echo "  SKIP: sandbox fixture missing"
fi

echo "[8/8] raw markup check on TUI artifacts"
mkdir -p "$REPO_ROOT/artifacts/tui"
if [ -f "$REPO_ROOT/scripts/tui_visual_smoke.sh" ]; then
    bash "$REPO_ROOT/scripts/tui_visual_smoke.sh" > "$ARTIFACTS/tui_visual.log" 2>&1 || true
fi
if [ -d "$REPO_ROOT/artifacts/tui" ] && grep -R "\\[bold\\|\\[/bold\\|\\[yellow\\|\\[/yellow\\|\\[/\\]" "$REPO_ROOT/artifacts/tui" 2>/dev/null; then
    echo "FAIL: raw Rich markup found in TUI artifacts"
    exit 1
fi
echo "  no raw markup in artifacts/tui"

echo ""
echo "=== PASS: full installed-product smoke ==="
echo "  bundles: $BUNDLE_COUNT"
echo "  logs: $ARTIFACTS/"
