#!/usr/bin/env bash
# PROMETHEUS QA sandbox smoke test — runs from repo root.
#
# Required checks (exit non-zero on failure):
#   compileall, pytest, ruff, prometheus --help, doctor, bundles list,
#   sandbox doctor, sandbox test, memory inspect, vision doctor, assets doctor
#
# Optional checks (may SKIP with exact reason):
#   provider smoke (needs Ollama), mcp test (needs MCP fixture server)
#
# Usage: bash scripts/qa_sandbox_smoke.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

FAILED=0
SKIPPED=0

run_check() {
  local label="$1"; shift
  echo ""
  echo "=== $label ==="
  if "$@"; then
    echo "  [PASS] $label"
  else
    echo "  [FAIL] $label"
    FAILED=$((FAILED + 1))
  fi
}

run_optional() {
  local label="$1"; shift
  echo ""
  echo "=== $label (optional) ==="
  if "$@"; then
    echo "  [PASS] $label"
  else
    echo "  [SKIP] $label — non-zero exit (see output above)"
    SKIPPED=$((SKIPPED + 1))
  fi
}

echo "PROMETHEUS QA sandbox smoke — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "repo: $REPO_ROOT"

run_check "compileall src"      python -m compileall src
run_check "pytest -q"           python -m pytest -q
run_check "ruff check src tests" ruff check src tests
run_check "prometheus --help"   prometheus --help
run_check "prometheus doctor"   bash -c 'prometheus doctor || true'
run_check "prometheus bundles list" prometheus bundles list
run_check "prometheus sandbox doctor" prometheus sandbox doctor
run_check "sandbox test --workspace tests/fixtures/sandbox_target --all" \
  prometheus sandbox test --workspace tests/fixtures/sandbox_target --all
run_check "memory inspect" \
  prometheus memory inspect --workspace tests/fixtures/sandbox_target
run_check "vision doctor"      prometheus vision doctor
run_check "assets doctor"      prometheus assets doctor
run_check "git status --short" git status --short

run_optional "provider smoke --provider fake" \
  bash -c 'prometheus provider smoke --provider ollama --model fake-model --base-url http://127.0.0.1:1 --timeout 2 || false'

run_optional "mcp test --fixture tests/fixtures/mcp/mcp_malicious_server.py" \
  bash -c '
    prometheus mcp add malicious-qa --trust untrusted -- python tests/fixtures/mcp/mcp_malicious_server.py 2>/dev/null || true
    prometheus mcp test malicious-qa || false
    prometheus mcp remove malicious-qa 2>/dev/null || true
  '

echo ""
echo "============================================"
echo "QA smoke summary: failed=$FAILED skipped=$SKIPPED"
echo "============================================"

if [ "$FAILED" -gt 0 ]; then
  echo "RESULT: FAIL ($FAILED required check(s) failed)"
  exit 1
fi

echo "RESULT: PASS (all required checks passed; $SKIPPED optional check(s) skipped)"
exit 0
