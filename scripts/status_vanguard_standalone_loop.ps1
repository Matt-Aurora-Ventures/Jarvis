$ErrorActionPreference = "Stop"

$env:JARVIS_RALPH_RUNTIME_DIR = Join-Path $env:LOCALAPPDATA "Jarvis\vanguard-standalone"
& (Join-Path (Get-Location).Path "scripts\status_ralph_wiggum_parallel_loop.ps1")
