#!/usr/bin/env sh
# PROMETHEUS public POSIX installer (Linux / macOS / WSL).
#
# Public one-liner:
#   curl -fsSL https://feverdream-dev.github.io/Prometheus/install.sh | sh
#
# This is a small, auditable bootstrap. It does NOT run arbitrary remote code
# beyond the PROMETHEUS source archive from the official GitHub repository. It
# creates an isolated, versioned virtual environment so PROMETHEUS never touches
# system Python. It never depends on PyPI: it installs PROMETHEUS from a verified
# GitHub source archive.
#
# Flags: --dry-run  --version VER  --prefix PATH  --no-ollama  --no-tui
#        --yes (noninteractive/CI)  --no-color  --help
#
# Environment overrides:
#   PROMETHEUS_VERSION     pin a version tag (e.g. v0.1.0) or "main"
#   PROMETHEUS_INSTALL_ROOT install root (default ~/.local/share/prometheus)
#   PROMETHEUS_BIN         wrapper dir    (default ~/.local/bin)
#   PROMETHEUS_REPO        owner/repo     (default FeverDream-dev/Prometheus)
#
# User data (config, sessions, bundles) lives separately under PROMETHEUS_HOME
# (default ~/.prometheus) and is preserved by 'prometheus uninstall' unless --purge.
set -eu

REPO="FeverDream-dev/Prometheus"
VERSION="${PROMETHEUS_VERSION:-}"
PREFIX="${PROMETHEUS_INSTALL_ROOT:-$HOME/.local/share/prometheus}"
BIN_DIR="${PROMETHEUS_BIN:-$HOME/.local/bin}"
INSTALL_TUI=1
RUN_OLLAMA_DOC=1
DRY_RUN=0
ASSUME_YES=0
USE_COLOR=1
LOG_FILE=""

usage() {
  cat <<'EOF'
PROMETHEUS installer — Linux / macOS / WSL

Usage: curl -fsSL .../install.sh | sh [-- FLAGS]

Flags (must follow `--` when piping):
  --version VER   install a specific release tag (e.g. v0.1.0) or "main"
  --prefix PATH   install root (default ~/.local/share/prometheus)
  --bin PATH      wrapper directory (default ~/.local/bin)
  --no-tui        do not install the Textual TUI extra
  --no-ollama     skip the post-install Ollama/doctor model check
  --yes           noninteractive (CI) mode: accept defaults, no prompts
  --dry-run       show what would happen, change nothing
  --no-color      disable color output
  --log PATH      write a diagnostic log to PATH
  -h, --help      show this help

Environment:
  PROMETHEUS_VERSION, PROMETHEUS_INSTALL_ROOT, PROMETHEUS_BIN, PROMETHEUS_REPO
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION="${2:-}"; shift 2 ;;
    --version=*) VERSION="${1#*=}"; shift ;;
    --prefix) PREFIX="${2:-}"; shift 2 ;;
    --prefix=*) PREFIX="${1#*=}"; shift ;;
    --bin) BIN_DIR="${2:-}"; shift 2 ;;
    --bin=*) BIN_DIR="${1#*=}"; shift ;;
    --no-tui) INSTALL_TUI=0; shift ;;
    --no-ollama) RUN_OLLAMA_DOC=0; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --no-color) USE_COLOR=0; shift ;;
    --log) LOG_FILE="${2:-}"; shift 2 ;;
    --log=*) LOG_FILE="${1#*=}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'prometheus install: unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done
REPO="${PROMETHEUS_REPO:-$REPO}"

if [ "$USE_COLOR" = 1 ] && [ -t 1 ]; then
  C_BOLD="\033[1m"; C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"; C_DIM="\033[2m"; C_RESET="\033[0m"
else
  C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_DIM=""; C_RESET=""
fi
say()  { printf '%b\n' "$1"; }
info() { printf '%b\n' "${C_DIM}$*${C_RESET}"; }
warn() { printf '%b\n' "${C_YELLOW}! $*${C_RESET}" >&2; }
err()  { printf '%b\n' "${C_RED}prometheus install: $*${C_RESET}" >&2; }
bold() { printf '%b%s%b' "$C_BOLD" "$*" "$C_RESET"; }

log_init() {
  [ -z "$LOG_FILE" ] && return 0
  {
    printf '=== PROMETHEUS install log %s ===\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date)"
    printf 'repo=%s version_env=%s prefix=%s bin=%s dry_run=%s\n' "$REPO" "$VERSION" "$PREFIX" "$BIN_DIR" "$DRY_RUN"
  } >>"$LOG_FILE" 2>/dev/null || warn "could not write log $LOG_FILE (continuing)"
}
log() { [ -z "$LOG_FILE" ] && return 0; printf '[%s] %s\n' "$(date -u +%H:%M:%SZ 2>/dev/null)" "$*" >>"$LOG_FILE" 2>/dev/null || true; }
fail() { err "$*"; log "FAIL: $*"; exit 1; }

os_name() {
  uname_s="$(uname -s 2>/dev/null || echo unknown)"
  case "$uname_s" in
    Linux*) printf linux ;;
    Darwin*) printf macos ;;
    MINGW*|MSYS*|CYGWIN*) printf windows-git-bash ;;
    *) printf '%s' "$(printf '%s' "$uname_s" | tr '[:upper:]' '[:lower:]')" ;;
  esac
}
arch_name() {
  u="$(uname -m 2>/dev/null || echo unknown)"
  case "$u" in
    x86_64|amd64) printf x86_64 ;;
    arm64|aarch64) printf arm64 ;;
    *) printf '%s' "$u" ;;
  esac
}
in_wsl() { [ -e /proc/version ] && grep -qi microsoft /proc/version 2>/dev/null; }

OS="$(os_name)"; ARCH="$(arch_name)"
WSL=0; in_wsl && WSL=1
case "$OS" in
  linux|macos) : ;;
  windows-git-bash) warn "Detected Git Bash on Windows. Native Windows is not supported yet; use WSL. Proceeding in this shell best-effort." ;;
  *) warn "Unrecognized OS '$OS'. Proceeding, but PROMETHEUS is tested on Linux/macOS/WSL." ;;
esac

have() { command -v "$1" >/dev/null 2>&1; }

DOWNLOADER=""
if have curl; then DOWNLOADER=curl
elif have wget; then DOWNLOADER=wget
else fail "Neither curl nor wget found. Install one to continue." ;fi

if ! have uname; then fail "uname is required."; fi
have tar || fail "tar is required but not found."

SHA256_CMD=""
if have sha256sum; then SHA256_CMD=sha256sum
elif have shasum; then SHA256_CMD=shasum
else warn "No sha256sum/shasum found; cannot verify checksums. Releases will not be verified."; fi

PY_BIN=""
py_version_ok() {
  # $1 = python binary. Returns 0 if it is 3.11+.
  "$1" - <<'PY' >/dev/null 2>&1 || return 1
import sys
ok = sys.version_info[:2] >= (3, 11)
sys.exit(0 if ok else 1)
PY
}
find_system_python() {
  for cand in python3 python3.11 python3.12 python3.13; do
    if have "$cand" && py_version_ok "$cand"; then PY_BIN="$cand"; return 0; fi
  done
  return 1
}
bootstrap_uv() {
  # Installs uv into BIN_DIR, then uses it to provision Python 3.11.
  warn "Python 3.11+ not found. Bootstrapping 'uv' to provision an isolated runtime."
  mkdir -p "$BIN_DIR"
  uv_url="https://astral.sh/uv/install.sh"
  if [ "$DOWNLOADER" = curl ]; then
    curl -fsSL "$uv_url" | UV_INSTALL_DIR="$BIN_DIR" sh >/dev/null 2>&1 || return 1
  else
    wget -qO- "$uv_url" | UV_INSTALL_DIR="$BIN_DIR" sh >/dev/null 2>&1 || return 1
  fi
  UV="$BIN_DIR/uv"
  have "$UV" || return 1
  "$UV" python install 3.11 >/dev/null 2>&1 || return 1
  UV_PY="$("$UV" python find 3.11 2>/dev/null || true)"
  [ -n "$UV_PY" ] && [ -x "$UV_PY" ] || return 1
  PY_BIN="$UV_PY"
  info "Provisioned Python via uv: $PY_BIN"
}

if ! find_system_python; then
  if [ "$DRY_RUN" = 1 ]; then
    warn "Python 3.11+ not found; would bootstrap uv (dry run, skipping)."
    PY_BIN="python3-from-uv"
  else
    bootstrap_uv || fail "Could not find or provision Python 3.11+. Install Python 3.11+ or ensure curl works to bootstrap uv."
  fi
fi
log "python=$PY_BIN downloader=$DOWNLOADER sha256=$SHA256_CMD os=$OS arch=$ARCH wsl=$WSL"

GH_API="https://api.github.com/repos/$REPO/releases/latest"
GH_TAG_BASE="https://github.com/$REPO/archive/refs/tags"
GH_BRANCH_BASE="https://github.com/$REPO/archive/refs/heads"

# Extract tag_name from the GitHub API JSON without jq/python (best-effort grep).
api_latest_tag() {
  body=""
  if [ "$DOWNLOADER" = curl ]; then
    body=$(curl -fsSL -H "Accept: application/vnd.github+json" "$GH_API" 2>/dev/null || true)
  else
    body=$(wget -qO- --header="Accept: application/vnd.github+json" "$GH_API" 2>/dev/null || true)
  fi
  printf '%s' "$body" | grep -o '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n1 | sed 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/'
}
# Fallback: list tags via git if git is present.
git_latest_tag() {
  have git || return 1
  git ls-remote --tags --refs "https://github.com/$REPO.git" 'refs/tags/v*' 2>/dev/null \
    | sed 's#.*/##' | sort -V | tail -n1
}

resolve_version() {
  if [ -n "$VERSION" ]; then printf '%s' "$VERSION"; return; fi
  t="$(api_latest_tag)"
  if [ -n "$t" ]; then printf '%s' "$t"; return; fi
  t="$(git_latest_tag)"
  if [ -n "$t" ]; then printf '%s' "$t"; return; fi
  printf main
}

RESOLVED="$(resolve_version)"
IS_RELEASE=0
case "$RESOLVED" in
  v*) IS_RELEASE=1 ;;
  main|master) IS_RELEASE=0 ;;
  *) IS_RELEASE=1 ;;
esac

VERSIONS_DIR="$PREFIX/versions"
INSTALL_DIR="$VERSIONS_DIR/$RESOLVED"
VENV_DIR="$INSTALL_DIR/venv"
WRAPPER="$BIN_DIR/prometheus"

# Track whether we are installing from a checksum-verifiable release artifact.
# 0 = source archive (cannot verify), 1 = release sdist (must verify).
VERIFY_CHECKSUM=0

if [ "$RESOLVED" = main ] || [ "$RESOLVED" = master ]; then
  TARBALL_URL="$GH_BRANCH_BASE/$RESOLVED.tar.gz"
  ARCHIVE="$INSTALL_DIR/source.tar.gz"
  SRC_SUB="Prometheus-$RESOLVED"
  SHA_URL=""
elif [ "$IS_RELEASE" = 1 ]; then
  # For releases, prefer the GitHub Release sdist (has a .sha256 sidecar
  # published by release.yml).  This is a python -m build artifact with a
  # stable, published checksum — unlike GitHub source archives which are
  # generated dynamically and cannot be checksum-verified.
  VER_NUM="${RESOLVED#v}"
  PKG_NAME="prometheus_local_agent"
  GH_RELEASE_BASE="https://github.com/$REPO/releases/download/$RESOLVED"
  TARBALL_URL="$GH_RELEASE_BASE/${PKG_NAME}-${VER_NUM}.tar.gz"
  SHA_URL="$GH_RELEASE_BASE/${PKG_NAME}-${VER_NUM}.tar.gz.sha256"
  ARCHIVE="$INSTALL_DIR/${PKG_NAME}-${VER_NUM}.tar.gz"
  SRC_SUB="${PKG_NAME}-${VER_NUM}"
  VERIFY_CHECKSUM=1
  # Fallback: GitHub source archive (not checksum-verifiable).
  SOURCE_FALLBACK_URL="$GH_TAG_BASE/$RESOLVED.tar.gz"
else
  TARBALL_URL="$GH_TAG_BASE/$RESOLVED.tar.gz"
  ARCHIVE="$INSTALL_DIR/source.tar.gz"
  SRC_SUB="Prometheus-${RESOLVED#v}"
  SHA_URL=""
fi

say "${C_BOLD}=== PROMETHEUS installer ===${C_RESET}"
info "repository : $REPO"
info "version    : $RESOLVED${C_DIM:-}$( [ "$IS_RELEASE" = 0 ] && printf '  (unreleased)' )"
info "python     : $PY_BIN"
info "install to : $INSTALL_DIR"
info "launcher   : $WRAPPER"
[ "$WSL" = 1 ] && info "environment: WSL"
[ "$INSTALL_TUI" = 0 ] && info "tui extra  : skipped (--no-tui)"
[ "$RUN_OLLAMA_DOC" = 0 ] && info "doctor     : skipping Ollama check (--no-ollama)"

if [ "$DRY_RUN" = 1 ]; then
  say "${C_YELLOW}DRY RUN${C_RESET} — no changes will be made."
  info "would download: $TARBALL_URL"
  if [ -n "$SHA_URL" ]; then
    info "would verify  : $SHA_URL"
  else
    info "would verify  : (source archive — no checksum sidecar)"
  fi
  info "would create  : $VENV_DIR"
  info "would install : PROMETHEUS$( [ "$INSTALL_TUI" = 1 ] && printf '[tui]' )"
  info "would write   : $WRAPPER"
  exit 0
fi

mkdir -p "$INSTALL_DIR" "$BIN_DIR" || fail "cannot create install directories (permission denied?)."

fetch() {
  # $1 url  $2 dest
  if [ "$DOWNLOADER" = curl ]; then curl -fsSL "$1" -o "$2"
  else wget -qO "$2" "$1"; fi
}

log "downloading $TARBALL_URL"
if ! fetch "$TARBALL_URL" "$ARCHIVE"; then
  if [ -n "${SOURCE_FALLBACK_URL:-}" ]; then
    warn "Release artifact not found: $TARBALL_URL"
    warn "Falling back to GitHub source archive (not checksum-verifiable)."
    TARBALL_URL="$SOURCE_FALLBACK_URL"
    ARCHIVE="$INSTALL_DIR/source.tar.gz"
    SRC_SUB="Prometheus-${RESOLVED#v}"
    SHA_URL=""
    VERIFY_CHECKSUM=0
    if ! fetch "$TARBALL_URL" "$ARCHIVE"; then
      rm -f "$ARCHIVE"
      fail "download failed: $TARBALL_URL\nCheck connectivity, or pin PROMETHEUS_VERSION, or check the repo is public."
    fi
  else
    rm -f "$ARCHIVE"
    fail "download failed: $TARBALL_URL\nCheck connectivity, or pin PROMETHEUS_VERSION, or check the repo is public."
  fi
fi

# Checksum verification.
compute_sha256() {
  [ -n "$SHA256_CMD" ] || return 1
  if [ "$SHA256_CMD" = sha256sum ]; then sha256sum "$1" | awk '{print $1}'
  else shasum -a 256 "$1" | awk '{print $1}'; fi
}
verify_checksum() {
  [ -n "$SHA256_CMD" ] || { warn "No sha256 tool; skipping verification."; return 0; }
  local_expected=""
  if [ -n "$SHA_URL" ] && fetch "$SHA_URL" "$ARCHIVE.sha256" 2>/dev/null && [ -s "$ARCHIVE.sha256" ]; then
    local_expected="$(awk '{print $1}' "$ARCHIVE.sha256" | tr -d '[:space:]' | head -n1 | tr '[:upper:]' '[:lower:]')"
  fi
  actual="$(compute_sha256 "$ARCHIVE" | tr -d '[:upper:]' | tr '[:upper:]' '[:lower:]')"
  if [ -n "$local_expected" ]; then
    if [ "$actual" != "$local_expected" ]; then
      rm -f "$ARCHIVE" "$ARCHIVE.sha256"
      fail "checksum mismatch for $TARBALL_URL\n  expected $local_expected\n  got      $actual"
    fi
    info "checksum verified: $actual"
    log "checksum verified: $actual"
  elif [ "$VERIFY_CHECKSUM" = 1 ]; then
    rm -f "$ARCHIVE" "$ARCHIVE.sha256"
    fail "release checksum missing ($SHA_URL).\nThe release is incomplete. Refusing to install unverified release artifact."
  else
    warn "Source archive: no stable checksum to verify against."
    warn "Computed sha256: $actual"
    if [ "$IS_RELEASE" = 1 ]; then
      warn "Release $RESOLVED: release artifacts not yet available; using source archive."
      warn "Re-run after the release workflow completes for a verified install."
    else
      warn "For a verified install, pin a version:  PROMETHEUS_VERSION=v0.1.0 sh install.sh"
    fi
    log "checksum unverified (source archive): $actual"
  fi
}
verify_checksum

log "extracting archive"
tar -xzf "$ARCHIVE" -C "$INSTALL_DIR" || fail "extraction failed."
SRC_DIR="$INSTALL_DIR/$SRC_SUB"
if [ ! -d "$SRC_DIR" ]; then
  # The archive may have a different top-level name; fall back to the only subdir.
  found=""
  for d in "$INSTALL_DIR"/*/; do
    if [ -f "${d}pyproject.toml" ]; then found="${d%/}"; break; fi
  done
  [ -n "$found" ] || fail "extracted archive has no recognizable source directory."
  SRC_DIR="$found"
fi

log "creating venv at $VENV_DIR"
"$PY_BIN" -m venv "$VENV_DIR" || fail "venv creation failed ($PY_BIN)."
. "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip --quiet >/dev/null

INSTALL_SPEC="$SRC_DIR"
if [ "$INSTALL_TUI" = 1 ]; then
  log "pip install -e $INSTALL_SPEC[tui]"
  python -m pip install "$INSTALL_SPEC[tui]" --quiet || \
    fail "pip install failed. Re-run with --no-tui if the TUI extra is unavailable offline."
else
  log "pip install -e $INSTALL_SPEC"
  python -m pip install "$INSTALL_SPEC" --quiet || fail "pip install failed."
fi

write_wrapper() {
  tmp="$WRAPPER.tmp.$$"
  cat > "$tmp" <<EOF
#!/usr/bin/env sh
# PROMETHEUS launcher (auto-generated by install.sh). Version: $RESOLVED
exec "$VENV_DIR/bin/prometheus" "\$@"
EOF
  chmod +x "$tmp"
  mv -f "$tmp" "$WRAPPER"
}
write_wrapper
log "wrote wrapper $WRAPPER"

ln -sfn "$INSTALL_DIR" "$VERSIONS_DIR/current" 2>/dev/null || true

path_has_bindir() { echo ":$PATH:" | grep -q ":$BIN_DIR:"; }
if ! path_has_bindir; then
  shell_rc=""
  case "$(basename "${SHELL:-sh}")" in
    zsh)  shell_rc="$HOME/.zshrc" ;;
    bash) shell_rc="$HOME/.bashrc" ;;
    fish) shell_rc="$HOME/.config/fish/config.fish" ;;
    *)    shell_rc="$HOME/.profile" ;;
  esac
  warn "$BIN_DIR is not on your PATH."
  say "  Add this line to ${shell_rc}:"
  if [ "$(basename "${SHELL:-sh}")" = fish ]; then
    say "    set -gx PATH $BIN_DIR \$PATH"
  else
    say "    export PATH=\"$BIN_DIR:\$PATH\""
  fi
  say "  Then start a new terminal, or run:  export PATH=\"$BIN_DIR:\$PATH\""
fi

PROM="$VENV_DIR/bin/prometheus"
if [ "$RUN_OLLAMA_DOC" = 1 ]; then
  say "${C_DIM}Running hardware check...${C_RESET}"
  "$PROM" doctor || warn "'prometheus doctor' returned non-zero (non-fatal). See output above."
fi

if [ "$ASSUME_YES" = 1 ]; then
  say "${C_DIM}Running first-run setup (noninteractive)...${C_RESET}"
  "$PROM" setup --yes >/dev/null 2>&1 || warn "'prometheus setup --yes' could not complete (non-fatal). Run it manually."
fi

say "${C_GREEN}${C_BOLD}=== Installation complete ===${C_RESET}"
info "version  : $RESOLVED"
info "launcher : $WRAPPER"
info "uninstall: prometheus uninstall      (update: prometheus update --check)"
if [ "$ASSUME_YES" = 0 ]; then
  say "Next: ${C_BOLD}prometheus setup${C_RESET}   then   ${C_BOLD}prometheus tui${C_RESET}"
fi
log "install complete: $RESOLVED at $WRAPPER"
