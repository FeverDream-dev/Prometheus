$ErrorActionPreference = "Stop"

# WSL is the supported Windows MVP path. Native Windows support is a later phase gate.
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
  throw "WSL is required for the current MVP. Install WSL, then run scripts/bootstrap.sh inside it."
}
$wslPath = (wsl.exe wslpath -a "$($PWD.Path)").Trim()
if (-not $wslPath) { throw "Could not translate the current directory into a WSL path." }
wsl.exe sh -lc "cd '$wslPath' && sh scripts/bootstrap.sh"
