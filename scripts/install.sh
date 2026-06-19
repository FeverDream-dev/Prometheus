#!/usr/bin/env sh
# Thin wrapper for clone-repo users. The PUBLIC one-liner is the repo-root
# install.sh:
#   curl -fsSL https://raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.sh | sh
#
# From a clone, this runs the root bootstrap and forwards all flags. The root
# script defaults to a verified GitHub install; set PROMETHEUS_VERSION to pin.
set -eu
root_dir="$(cd "$(dirname "$0")/.." && pwd)"
root_sh="$root_dir/install.sh"
if [ ! -f "$root_sh" ]; then
  printf 'scripts/install.sh: root install.sh not found at %s\n' "$root_sh" >&2
  exit 1
fi
exec sh "$root_sh" "$@"
