#!/usr/bin/env sh
# PROMETHEUS installer for POSIX systems (Linux, macOS, WSL).
# Usage from a cloned repo:  sh scripts/install.sh
# Usage as one-liner:         curl -fsSL <url>/install.sh | sh
#
# This script is intentionally small and auditable. It does not run arbitrary
# remote code beyond pip installing this package. It creates an isolated
# virtual environment so PROMETHEUS never touches the system Python.
set -eu

PROMETHEUS_HOME="${PROMETHEUS_HOME:-$HOME/.prometheus}"
VENV_DIR="$PROMETHEUS_HOME/venv"
BIN_DIR="$HOME/.local/bin"
PACKAGE_NAME="prometheus-local-agent"

VERSION="${PROMETHEUS_VERSION:-}"
INSTALL_TUI="${PROMETHEUS_INSTALL_TUI:-1}"

err() { printf 'prometheus install: %s\n' "$*" >&2; exit 1; }

printf '=== PROMETHEUS installer ===\n'
printf 'Install location: %s\n' "$PROMETHEUS_HOME"

if ! command -v python3 >/dev/null 2>&1; then
    err "Python 3 is required but not found in PATH. Install Python 3.11+ from https://python.org"
fi

PY_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PY_MAJOR=$(printf '%s' "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(printf '%s' "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    err "Python 3.11+ required, found $PY_VERSION"
fi
printf 'Python: %s\n' "$PY_VERSION"

mkdir -p "$PROMETHEUS_HOME" "$BIN_DIR"

printf 'Creating virtual environment at %s...\n' "$VENV_DIR"
python3 -m venv "$VENV_DIR"

# shellcheck disable=SC1090
. "$VENV_DIR/bin/activate"

printf 'Upgrading pip...\n'
python -m pip install --upgrade pip --quiet

if [ -n "$VERSION" ]; then
    INSTALL_SPEC="$PACKAGE_NAME==$VERSION"
    printf 'Installing PROMETHEUS %s from PyPI...\n' "$VERSION"
elif [ -f "$(pwd)/pyproject.toml" ] && grep -q "$PACKAGE_NAME" "$(pwd)/pyproject.toml" 2>/dev/null; then
    INSTALL_SPEC="$(pwd)"
    printf 'Installing PROMETHEUS from local source...\n'
else
    INSTALL_SPEC="$PACKAGE_NAME"
    printf 'Installing PROMETHEUS from PyPI...\n'
fi

if [ "$INSTALL_TUI" = "1" ]; then
    python -m pip install "$INSTALL_SPEC[tui]" --quiet
else
    python -m pip install "$INSTALL_SPEC" --quiet
fi

WRAPPER="$BIN_DIR/prometheus"
cat > "$WRAPPER" << EOF
#!/usr/bin/env sh
exec "$VENV_DIR/bin/prometheus" "\$@"
EOF
chmod +x "$WRAPPER"
printf 'Wrapper script: %s\n' "$WRAPPER"

if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    printf '\nWARNING: %s is not in your PATH.\n' "$BIN_DIR"
    printf 'Add this line to your shell profile (~/.bashrc, ~/.zshrc):\n'
    printf '  export PATH="%s:$PATH"\n\n' "$BIN_DIR"
fi

printf '\nRunning hardware check...\n'
"$VENV_DIR/bin/prometheus" doctor || true

printf '\n=== Installation complete ===\n'
printf 'Run:  prometheus setup\n'
printf 'Then: prometheus tui\n'
printf 'Or:   prometheus run "your objective" --bundle ~/.prometheus/config.yaml --workspace .\n'
