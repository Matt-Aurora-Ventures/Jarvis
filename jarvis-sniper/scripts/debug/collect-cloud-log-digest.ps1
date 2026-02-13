param(
  [string]$ProjectId = "kr8tiv",
  [string]$ServiceName = "ssrkr8tiv",
  [int]$Hours = 6,
  [int]$SampleLimit = 80,
  [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"

function Get-JsonLogRows {
  param(
    [string]$Filter,
    [int]$Limit = 50
  )

  try {
    $raw = gcloud logging read $Filter --project $ProjectId --limit $Limit --format json 2>$null
    if (-not $raw) { return @() }
    $rows = $raw | ConvertFrom-Json
    if ($rows -is [System.Array]) { return $rows }
    if ($rows) { return @($rows) }
    return @()
  } catch {
    return @()
  }
}

function Format-RowLine {
  param($Row)
  $ts = if ($null -ne $Row.timestamp) { [string]$Row.timestamp } else { "" }
  $severity = if ($null -ne $Row.severity) { [string]$Row.severity } else { "INFO" }
  $url = if ($null -ne $Row.httpRequest -and $null -ne $Row.httpRequest.requestUrl) { [string]$Row.httpRequest.requestUrl } else { "" }
  $status = if ($null -ne $Row.httpRequest -and $null -ne $Row.httpRequest.status) { [string]$Row.httpRequest.status } else { "" }
  $text = if ($null -ne $Row.textPayload) { [string]$Row.textPayload } else { "" }
  if (-not $text -and $Row.jsonPayload) {
    $text = ($Row.jsonPayload | ConvertTo-Json -Compress -Depth 6)
  }
  $shortText = if ($text.Length -gt 240) { $text.Substring(0, 240) + "..." } else { $text }
  return "- [$ts] $severity status=$status url=$url :: $shortText"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $OutFile) {
  $OutFile = "debug/cloud-log-digest-$timestamp.md"
}

$sinceIso = (Get-Date).ToUniversalTime().AddHours(-1 * [math]::Abs($Hours)).ToString("yyyy-MM-ddTHH:mm:ssZ")
$baseFilter = "resource.type=""cloud_run_revision"" resource.labels.service_name=""$ServiceName"" timestamp>=""$sinceIso"""

$allErrors = Get-JsonLogRows -Filter "$baseFilter severity>=ERROR" -Limit $SampleLimit
$swapFailures = Get-JsonLogRows -Filter "$baseFilter (textPayload:""/api/bags/swap"" OR jsonPayload.message:""/api/bags/swap"") severity>=WARNING" -Limit $SampleLimit
$insufficientSol = Get-JsonLogRows -Filter "$baseFilter (textPayload:""INSUFFICIENT_SIGNER_SOL"" OR jsonPayload.message:""INSUFFICIENT_SIGNER_SOL"")" -Limit $SampleLimit
$backtestApi = Get-JsonLogRows -Filter "$baseFilter (textPayload:""/api/backtest"" OR jsonPayload.message:""/api/backtest"")" -Limit $SampleLimit
$backtest5xx = @($backtestApi | Where-Object {
  $status = if ($null -ne $_.httpRequest -and $null -ne $_.httpRequest.status) { [int]$_.httpRequest.status } else { 0 }
  $status -ge 500
})
$monitorUnavailable = Get-JsonLogRows -Filter "$baseFilter (textPayload:""Run monitor unavailable"" OR jsonPayload.error:""Run monitor unavailable"")" -Limit $SampleLimit

$lines = @()
$lines += "# Cloud Log Digest"
$lines += ""
$lines += "- Project: $ProjectId"
$lines += "- Service: $ServiceName"
$lines += "- Window start (UTC): $sinceIso"
$lines += "- Generated at: $(Get-Date -Format "yyyy-MM-ddTHH:mm:ssK")"
$lines += ""
$lines += "## Counts"
$lines += ""
$lines += "- Total severity>=ERROR: $($allErrors.Count)"
$lines += "- `/api/bags/swap` warnings/errors: $($swapFailures.Count)"
$lines += "- `INSUFFICIENT_SIGNER_SOL` entries: $($insufficientSol.Count)"
$lines += "- `/api/backtest` 5xx entries: $($backtest5xx.Count)"
$lines += "- Run monitor unavailable entries: $($monitorUnavailable.Count)"
$lines += ""

$lines += "## Sample: Errors"
$lines += ""
if ($allErrors.Count -eq 0) {
  $lines += "- none"
} else {
  $allErrors | Select-Object -First 20 | ForEach-Object { $lines += (Format-RowLine -Row $_) }
}
$lines += ""

$lines += "## Sample: Swap Failures"
$lines += ""
if ($swapFailures.Count -eq 0) {
  $lines += "- none"
} else {
  $swapFailures | Select-Object -First 20 | ForEach-Object { $lines += (Format-RowLine -Row $_) }
}
$lines += ""

$lines += "## Sample: Backtest 5xx"
$lines += ""
if ($backtest5xx.Count -eq 0) {
  $lines += "- none"
} else {
  $backtest5xx | Select-Object -First 20 | ForEach-Object { $lines += (Format-RowLine -Row $_) }
}
$lines += ""

$lines += "## Sample: Run Monitor Unavailable"
$lines += ""
if ($monitorUnavailable.Count -eq 0) {
  $lines += "- none"
} else {
  $monitorUnavailable | Select-Object -First 20 | ForEach-Object { $lines += (Format-RowLine -Row $_) }
}
$lines += ""

$outDir = Split-Path -Parent $OutFile
if ($outDir) {
  New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}
$lines -join "`n" | Set-Content -Path $OutFile -Encoding UTF8

Write-Host "Cloud log digest written to: $OutFile"
