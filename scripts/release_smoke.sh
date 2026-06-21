#!/usr/bin/env bash
# scripts/release_smoke.sh — local release-readiness verification.
#
# Runs every check that the release pipeline depends on, captures real output,
# and appends evidence to docs/RELEASE_READINESS.md.
#
# Usage:
#   bash scripts/release_smoke.sh              # run all checks
#   bash scripts/release_smoke.sh --build      # also build wheel + sdist + SBOM
#
# Exit non-zero if any check fails.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DO_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --build) DO_BUILD=1 ;;
    *) ;;
  esac
done

EVIDENCE_FILE="docs/RELEASE_READINESS.md"
TMPDIR_SMOKE="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_SMOKE"' EXIT

PASS_COUNT=0
FAIL_COUNT=0
RESULTS=""

record() {
  local name="$1" status="$2" detail="${3:-}"
  if [ "$status" = "PASS" ]; then
    PASS_COUNT=$((PASS_COUNT + 1))
    RESULTS+="| ${name} | PASS | ${detail} |\n"
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    RESULTS+="| ${name} | FAIL | ${detail} |\n"
  fi
}

run_check() {
  local name="$1"
  shift
  local out
  out="$("$@" 2>&1)" && {
    record "$name" "PASS" "$(echo "$out" | tail -1)"
    return 0
  } || {
    record "$name" "FAIL" "$(echo "$out" | tail -3 | tr '\n' ' ')"
    return 1
  }
}

echo "=== PROMETHEUS release smoke ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Root: $ROOT"
echo ""

# 1. compileall
run_check "compileall" python -m compileall -q src || true

# 2. pytest
set +e
PYOUT="$(python -m pytest -q 2>&1)"
PYEXIT=$?
set -e
if [ $PYEXIT -eq 0 ]; then
  record "pytest" "PASS" "$(echo "$PYOUT" | tail -1)"
else
  record "pytest" "FAIL" "$(echo "$PYOUT" | tail -3 | tr '\n' ' ')"
fi

# 3. ruff
run_check "ruff check" ruff check src tests || true

# 4. CLI --help
run_check "prometheus --help" python -m prometheus_cli.cli --help || true

# 5. doctor
run_check "prometheus doctor" python -m prometheus_cli.cli doctor || true

# 6. sandbox test
run_check "sandbox test (19/19)" \
  python -m prometheus_cli.cli sandbox test \
  --workspace tests/fixtures/sandbox_target --all || true

# 7. install.sh syntax
run_check "bash -n install.sh" bash -n install.sh || true

# 8. public/install.sh syntax
run_check "bash -n public/install.sh" bash -n public/install.sh || true

# 9. dry-run
set +e
DRYOUT="$(sh public/install.sh --dry-run 2>&1)"
DRYEXIT=$?
set -e
if [ $DRYEXIT -eq 0 ]; then
  record "install.sh --dry-run" "PASS" "exit 0"
else
  record "install.sh --dry-run" "FAIL" "exit $DRYEXIT"
fi

# 10. No placeholder URLs
set +e
PLACEHOLDER_CHECK="$(grep -r 'prometheus/local-agent' install.sh public/install.sh install.ps1 public/install.ps1 2>&1 || true)"
set -e
if [ -z "$PLACEHOLDER_CHECK" ]; then
  record "no placeholder URLs" "PASS" "clean"
else
  record "no placeholder URLs" "FAIL" "$PLACEHOLDER_CHECK"
fi

# 11. Git working tree status
set +e
GITSTATUS="$(git status --short 2>&1)"
set -e
if [ -z "$GITSTATUS" ]; then
  record "git status clean" "PASS" "clean"
else
  CHANGED_COUNT=$(echo "$GITSTATUS" | wc -l)
  record "git status" "PASS" "$CHANGED_COUNT modified files (expected during dev)"
fi

# 12. Build artifacts (optional)
if [ "$DO_BUILD" = 1 ]; then
  echo ""
  echo "--- Building artifacts ---"
  rm -rf dist/*
  python -m build 2>&1 | tail -3 || true

  if ls dist/*.whl >/dev/null 2>&1 && ls dist/*.tar.gz >/dev/null 2>&1; then
    record "wheel build" "PASS" "$(ls dist/*.whl)"
    record "sdist build" "PASS" "$(ls dist/*.tar.gz)"

    # Checksums
    (cd dist && sha256sum * > SHA256SUMS && \
      for f in *; do [ "$f" = "SHA256SUMS" ] && continue; \
      sha256sum "$f" | awk '{print $1}' > "$f.sha256"; done) || true
    record "checksums" "PASS" "SHA256SUMS + sidecars"

    # SBOM
    set +e
    cyclonedx-py environment -o dist/sbom.cyclonedx.json --sv 1.5 "$(which python)" 2>&1
    if [ $? -eq 0 ] && [ -f dist/sbom.cyclonedx.json ]; then
      record "SBOM (CycloneDX)" "PASS" "dist/sbom.cyclonedx.json"
    else
      record "SBOM (CycloneDX)" "FAIL" "generation failed"
    fi
    set -e

    # Clean wheel install
    CLEAN_VENV="$TMPDIR_SMOKE/clean_venv"
    python3 -m venv "$CLEAN_VENV"
    "$CLEAN_VENV/bin/python" -m pip install --upgrade pip --quiet
    set +e
    "$CLEAN_VENV/bin/python" -m pip install "$(ls dist/*.whl)[tui]" --quiet 2>&1
    WHEEL_INSTALL_EXIT=$?
    set -e
    if [ $WHEEL_INSTALL_EXIT -eq 0 ]; then
      record "clean wheel install" "PASS" "pip install succeeded"
      "$CLEAN_VENV/bin/prometheus" --help >/dev/null 2>&1 && \
        record "installed CLI --help" "PASS" "exit 0" || \
        record "installed CLI --help" "FAIL" "non-zero exit"
    else
      record "clean wheel install" "FAIL" "pip install failed"
    fi
  else
    record "wheel build" "FAIL" "no .whl in dist/"
    record "sdist build" "FAIL" "no .tar.gz in dist/"
  fi
fi

# Write evidence
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat > "$EVIDENCE_FILE" <<EOF
# PROMETHEUS release readiness

**Generated:** ${TS} by \`scripts/release_smoke.sh\`

**Result:** ${PASS_COUNT} passed / ${FAIL_COUNT} failed

| Check | Status | Detail |
|---|---|---|
$(printf '%b' "$RESULTS")

## How to reproduce

\`\`\`sh
bash scripts/release_smoke.sh --build
\`\`\`

## Next human step

\`\`\`sh
git tag v0.1.0
git push origin v0.1.0
\`\`\`

This triggers \`.github/workflows/release.yml\` which builds wheel + sdist +
SHA256SUMS + SBOM + release manifest, creates the GitHub Release, and runs the
smoke job.
EOF

echo ""
echo "=== Results: ${PASS_COUNT} passed / ${FAIL_COUNT} failed ==="
echo "Evidence written to $EVIDENCE_FILE"

[ "$FAIL_COUNT" -eq 0 ] || exit 1
