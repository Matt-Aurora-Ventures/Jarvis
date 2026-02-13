param(
  [Parameter(Mandatory = $true)][string]$ManifestId,
  [Parameter(Mandatory = $true)][ValidateSet("memecoin","bags","bluechip","xstock","prestock","index","xstock_index")][string]$Family,
  [ValidateSet("fast","thorough")][string]$DataScale = "thorough",
  [ValidateSet("gecko_only","allow_birdeye_fallback")][string]$SourcePolicy = "gecko_only",
  [int]$LookbackHours = 2160,
  [int]$MaxTokens = 120
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

Set-Location "c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\jarvis-sniper"

function New-RunId {
  return "manifest-build-$Family-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
}

$familySeed = @{
  memecoin = "pump_fresh_tight"
  bags = "bags_fresh_snipe"
  bluechip = "bluechip_trend_follow"
  xstock = "xstock_intraday"
  prestock = "prestock_speculative"
  index = "index_intraday"
  xstock_index = "xstock_intraday"
}

$seed = [string]$familySeed[$Family]
$runId = New-RunId
$body = [ordered]@{
  strategyId = $seed
  strategyIds = @($seed)
  family = $Family
  mode = "quick"
  dataScale = $DataScale
  sourcePolicy = $SourcePolicy
  strictNoSynthetic = $true
  includeEvidence = $false
  includeReport = $false
  lookbackHours = $LookbackHours
  maxTokens = $MaxTokens
  datasetManifestId = $ManifestId
  runId = $runId
  manifestId = "manifest-$runId"
}

Write-Host "Building dataset manifest..."
Write-Host "  manifestId: $ManifestId"
Write-Host "  family: $Family"
Write-Host "  seed strategy: $seed"

$payload = $body | ConvertTo-Json -Depth 20 -Compress
$resp = Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:3001/api/backtest" -ContentType "application/json" -Body $payload -TimeoutSec 3600

$outDir = Join-Path (Get-Location) ".jarvis-cache\backtest-datasets\$ManifestId\$Family"
Write-Host "Done."
Write-Host "  runId: $($resp.runId)"
Write-Host "  datasetManifestId: $ManifestId"
Write-Host "  cacheDir: $outDir"
Write-Host "  datasetsSucceeded: $($resp.meta.datasetsSucceeded)"
Write-Host "  datasetsAttempted: $($resp.meta.datasetsAttempted)"

