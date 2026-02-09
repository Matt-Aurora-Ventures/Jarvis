param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Escape-ForBash([string]$s) {
  # Wrap in single quotes; escape embedded single quotes safely.
  return "'" + ($s -replace "'", "'\"'\"'") + "'"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$wslRoot = (wsl wslpath -a $repoRoot).Trim()

$activate = "$wslRoot/.venv-telegram/bin/activate"
$bashArgs = ($Args | ForEach-Object { Escape-ForBash $_ }) -join " "

$cmd = @(
  "set -euo pipefail",
  "cd " + (Escape-ForBash $wslRoot),
  "if [ -f " + (Escape-ForBash $activate) + " ]; then source " + (Escape-ForBash $activate) + "; fi",
  "python scripts/telegram_bot_e2e.py " + $bashArgs
) -join "; "

wsl -e bash -lc $cmd
exit $LASTEXITCODE

