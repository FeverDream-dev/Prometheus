# PROMETHEUS public Windows entry point (delegates to WSL).
#
# Public one-liner:
#   irm https://raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.ps1 | iex
#
# PROMETHEUS on Windows runs inside WSL for the current MVP (native Windows is a
# later phase gate, per docs/INSTALLATION.md). If WSL is installed, this script
# runs the official POSIX installer inside it. If WSL is missing, it prints the
# exact steps to install WSL first. It never uses a placeholder owner/repo.
#
# Pass arguments after the pipe via iex, e.g.:
#   irm .../install.ps1 | iex -InstallArgs @("--yes","--no-tui")
[CmdletBinding()]
param(
    [string[]] $InstallArgs = @()
)

$ErrorActionPreference = "Stop"
$Repo = "FeverDream-dev/Prometheus"
$BootstrapUrl = "https://raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.sh"

function Write-Section($msg) { Write-Host "=== $msg ===" -ForegroundColor Cyan }
function Write-Ok($msg)      { Write-Host $msg -ForegroundColor Green }
function Write-Warn2($msg)   { Write-Host $msg -ForegroundColor Yellow }

Write-Section "PROMETHEUS installer (Windows -> WSL)"
Write-Host "Repository: $Repo"

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    Write-Warn2 "WSL is not installed."
    Write-Warn2 "PROMETHEUS on Windows requires WSL for the current MVP."
    Write-Host ""
    Write-Host "Install WSL first (run in an elevated PowerShell):" -ForegroundColor White
    Write-Host "  wsl --install" -ForegroundColor White
    Write-Host ""
    Write-Host "Then restart your computer, open a new terminal, and run:" -ForegroundColor White
    Write-Host "  irm $BootstrapUrl | iex" -ForegroundColor White
    Write-Host ""
    Write-Host "Or, inside WSL directly:" -ForegroundColor White
    Write-Host "  curl -fsSL $BootstrapUrl | sh" -ForegroundColor White
    exit 1
}

Write-Ok "WSL detected. Installing PROMETHEUS inside WSL (Linux-native)."

$argString = ($InstallArgs | ForEach-Object { $_ }) -join " "
$flags = if ($argString) { "-- $argString" } else { "" }

# Detect whether this script is running from inside a cloned repo (local install.sh).
$localSh = Join-Path (Get-Location) "install.sh"
$useLocal = (Test-Path $localSh) -and ($null -ne $env:CLONED_PROMETHEUS_REPO)

if ($useLocal) {
    $wslPath = (wsl.exe wslpath -a $localSh 2>$null)
    if ($wslPath) {
        Write-Host "Running local install.sh from WSL: $wslPath"
        wsl.exe bash -lc "sh '$wslPath' $argString"
        exit $LASTEXITCODE
    }
}

Write-Host "Fetching installer: $BootstrapUrl"
if ($flags) {
    wsl.exe bash -lc "curl -fsSL '$BootstrapUrl' | sh -s -- $argString"
} else {
    wsl.exe bash -lc "curl -fsSL '$BootstrapUrl' | sh"
}
exit $LASTEXITCODE
