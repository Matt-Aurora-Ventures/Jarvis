#!/usr/bin/env pwsh
# Wrapper to run tvscreener's MCP server from an isolated venv without reading the repo's .env
# (python-dotenv will try to parse .env from the current working directory).

$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$venvDir = Join-Path $repoRoot '.venv-tvscreener'
$exe = Join-Path $venvDir 'Scripts' 'tvscreener-mcp.exe'

if (!(Test-Path $exe)) {
  Write-Error "tvscreener-mcp not found at: $exe"
  exit 1
}

Set-Location $venvDir
& $exe

