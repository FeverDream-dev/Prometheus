# PROMETHEUS installer for Windows (PowerShell) and WSL.
# Usage from a cloned repo:  pwsh scripts/install.ps1
#
# Windows MVP runs inside WSL. If WSL is available, this script delegates to
# install.sh inside it. If WSL is not installed, it prints setup instructions.
# Native Windows support is a later phase gate per docs/INSTALLATION.md.
$ErrorActionPreference = "Stop"

$PrometheusHome = if ($env:PROMETHEUS_HOME) { $env:PROMETHEUS_HOME } else { "$env:USERPROFILE\.prometheus" }
Write-Host "=== PROMETHEUS installer ===" -ForegroundColor Cyan
Write-Host "Install location: $PrometheusHome"

if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
    Write-Host "WSL detected. Installing inside WSL for Linux-native operation." -ForegroundColor Green
    $repoPath = (Get-Location).Path
    $wslPath = (wsl.exe wslpath -a "$repoPath" 2>$null).Trim()
    if (-not $wslPath) {
        Write-Host "Could not translate path. Running install.sh from WSL home." -ForegroundColor Yellow
        wsl.exe bash -lc "cd ~ && curl -fsSL https://raw.githubusercontent.com/prometheus/local-agent/main/scripts/install.sh | sh"
    } else {
        wsl.exe bash -lc "cd '$wslPath' && sh scripts/install.sh"
    }
} else {
    Write-Host "WSL is not installed." -ForegroundColor Yellow
    Write-Host "PROMETHEUS on Windows requires WSL for the current MVP." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Install WSL first:" -ForegroundColor White
    Write-Host "  wsl --install" -ForegroundColor White
    Write-Host ""
    Write-Host "Then restart your terminal and run this installer again." -ForegroundColor White
    Write-Host "Or open WSL and run:" -ForegroundColor White
    Write-Host "  curl -fsSL https://raw.githubusercontent.com/prometheus/local-agent/main/scripts/install.sh | sh" -ForegroundColor White
    exit 1
}
