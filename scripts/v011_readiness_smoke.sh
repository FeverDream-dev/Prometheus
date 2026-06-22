#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

PASS=0
FAIL=0
SKIP=0

step() {
    echo ""
    echo "=== $1 ==="
}

check() {
    if [ "$1" -eq 0 ]; then
        echo "  PASS"
        PASS=$((PASS + 1))
    else
        echo "  FAIL (exit $1)"
        FAIL=$((FAIL + 1))
    fi
}

skip() {
    echo "  SKIP ($1)"
    SKIP=$((SKIP + 1))
}

echo "PROMETHEUS v0.1.1 readiness smoke"
echo "=================================="

step "1. compileall"
python -m compileall src -q
check $?

step "2. pytest (full suite, excluding e2e/opt-in)"
python -m pytest -q \
    --ignore=tests/test_e2e_ollama.py \
    --ignore=tests/test_arena_ollama_e2e.py \
    --ignore=tests/test_browser_e2e.py \
    --ignore=tests/test_mcp_e2e.py \
    --ignore=tests/test_assets_license_policy.py \
    --ignore=tests/test_wheel_contains_resources.py \
    2>&1 | tail -3
check ${PIPESTATUS[0]}

step "3. ruff check"
if command -v ruff &>/dev/null; then
    ruff check src tests 2>&1 | tail -3
    check ${PIPESTATUS[0]}
else
    python -m ruff check src tests 2>&1 | tail -3
    check ${PIPESTATUS[0]}
fi

step "4. python -m build"
BUILD_DIR=$(mktemp -d)
python -m build --outdir "$BUILD_DIR" . 2>&1 | tail -3
BUILD_RC=$?
check $BUILD_RC
if [ $BUILD_RC -eq 0 ]; then
    echo "  wheel: $(ls "$BUILD_DIR"/*.whl | xargs -I{} basename {})"
    echo "  sdist: $(ls "$BUILD_DIR"/*.tar.gz | xargs -I{} basename {})"
fi
rm -rf "$BUILD_DIR"

step "5. clean install defaults smoke"
if [ -f scripts/clean_install_defaults_smoke.sh ]; then
    bash scripts/clean_install_defaults_smoke.sh 2>&1 | tail -5
    check ${PIPESTATUS[0]}
else
    skip "script not found"
fi

step "6. TUI visual smoke"
if [ -f scripts/tui_visual_smoke.sh ]; then
    bash scripts/tui_visual_smoke.sh 2>&1 | tail -5
    check ${PIPESTATUS[0]}
else
    skip "script not found"
fi

step "7. TUI no raw markup grep"
if [ -d artifacts/tui ]; then
    if grep -R "\[bold\|\[/bold\|\[yellow\|\[/yellow\|\[/\]" artifacts/tui/ 2>/dev/null; then
        echo "  FAIL: raw markup found in artifacts"
        FAIL=$((FAIL + 1))
    else
        echo "  PASS: no raw markup in $(ls artifacts/tui/*.svg 2>/dev/null | wc -l) SVG files"
        PASS=$((PASS + 1))
    fi
else
    skip "artifacts/tui not found"
fi

step "8. sandbox test"
if [ -d tests/fixtures/sandbox_target ]; then
    prometheus sandbox test --workspace tests/fixtures/sandbox_target --all 2>&1 | tail -5
    check ${PIPESTATUS[0]}
else
    skip "sandbox_target fixture not found"
fi

step "9. BundleForge recommend (game)"
prometheus bundleforge recommend "I want to build a video game" --json 2>&1 | python -c "import sys,json; d=json.load(sys.stdin); print(f'  use_case={d[\"use_case\"]} template={d[\"template_id\"]}')" 2>/dev/null
check $?

step "10. BundleForge recommend (RAG)"
prometheus bundleforge recommend "I want RAG over company documents" --json 2>&1 | python -c "import sys,json; d=json.load(sys.stdin); print(f'  use_case={d[\"use_case\"]} template={d[\"template_id\"]}')" 2>/dev/null
check $?

step "11. assets doctor"
prometheus assets doctor 2>&1 | head -5
check ${PIPESTATUS[0]}

step "12. vision doctor"
prometheus vision doctor 2>&1 | head -5
check ${PIPESTATUS[0]}

step "13. setup --dry-run (clean HOME)"
CLEAN_HOME=$(mktemp -d)
HOME="$CLEAN_HOME" PROMETHEUS_HOME="$CLEAN_HOME/.prometheus" prometheus setup --dry-run 2>&1 | head -10
SETUP_RC=${PIPESTATUS[0]}
if [ $SETUP_RC -eq 0 ] && ! HOME="$CLEAN_HOME" PROMETHEUS_HOME="$CLEAN_HOME/.prometheus" prometheus setup --dry-run 2>&1 | grep -q "No bundles found"; then
    echo "  PASS: setup shows bundles (no dead-end)"
    PASS=$((PASS + 1))
else
    echo "  FAIL: setup dead-ends"
    FAIL=$((FAIL + 1))
fi
rm -rf "$CLEAN_HOME"

step "14. TUI demo --exit-after-render"
prometheus tui --demo --exit-after-render 2>&1
check $?

step "15. git status (working tree)"
DIRTY=$(git status --short | grep -v 'prometheus_recovery_pack\|artifacts/' | wc -l)
echo "  untracked/modified (excluding recovery_pack): $DIRTY"

echo ""
echo "=================================="
echo "RESULTS: $PASS passed, $FAIL failed, $SKIP skipped"
echo "=================================="

if [ $FAIL -gt 0 ]; then
    exit 1
fi
exit 0
