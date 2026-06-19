#!/usr/bin/env sh
set -eu

# Development bootstrap. The production one-liner must download a signed, versioned installer.
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required" >&2; exit 1; }
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,tui]'
prometheus doctor
echo "Run: . .venv/bin/activate && prometheus init . --mode pilot"

