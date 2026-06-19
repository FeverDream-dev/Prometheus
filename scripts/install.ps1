# Thin wrapper for clone-repo users. The PUBLIC Windows one-liner is the
# repo-root install.ps1:
#   irm https://raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.ps1 | iex
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$rootPs1 = Join-Path $root "install.ps1"
if (-not (Test-Path $rootPs1)) {
    throw "scripts/install.ps1: root install.ps1 not found at $rootPs1"
}
& $rootPs1 @args
exit $LASTEXITCODE
