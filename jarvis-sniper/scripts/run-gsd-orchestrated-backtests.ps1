param(
  [string]$CampaignId = "",
  [int[]]$ExpansionLadder = @(40, 80, 120, 160, 200, 300, 400, 500),
  [int]$TargetTradesPerStrategy = 5000,
  [string[]]$StrategyIds = @(),
  [int]$MaxStrategies = 0,
  [int]$HardTimeoutSec = 1200,
  [int]$PollEverySec = 10,
  [int]$PollTimeoutSec = 20,
  [int]$StallAfterSec = 420,
  [switch]$SkipOptimization,
  [switch]$SkipPublish,
  [switch]$Resume
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

Set-Location "c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\jarvis-sniper"

if ($PollEverySec -lt 5) { $PollEverySec = 5 }
if ($PollTimeoutSec -lt 5) { $PollTimeoutSec = 5 }
if ($StallAfterSec -lt 60) { $StallAfterSec = 60 }
if ($HardTimeoutSec -lt 120) { $HardTimeoutSec = 120 }

if ([string]::IsNullOrWhiteSpace($CampaignId)) {
  $CampaignId = "gsd-" + (Get-Date -Format "yyyyMMdd-HHmmss")
}

$campaignRoot = Join-Path (Get-Location) ".jarvis-cache\backtest-campaign\$CampaignId"
$statePath = Join-Path $campaignRoot "campaign-state.json"
$logPath = Join-Path $campaignRoot "campaign.log"
$docsOut = Join-Path (Get-Location) "docs\backtests\$CampaignId"
New-Item -ItemType Directory -Path $campaignRoot -Force | Out-Null
New-Item -ItemType Directory -Path $docsOut -Force | Out-Null

function Write-Log {
  param(
    [string]$Msg,
    [string]$Level = "INFO"
  )
  $line = "[$((Get-Date).ToString('o'))] [$Level] $Msg"
  $line | Add-Content -Path $logPath -Encoding UTF8
  Write-Host $line
}

function Save-Json {
  param([string]$Path, $Data)
  $tmpPath = "$Path.tmp"
  $json = $Data | ConvertTo-Json -Depth 100
  $json | Set-Content -Path $tmpPath -Encoding UTF8
  Move-Item -Path $tmpPath -Destination $Path -Force
}

function ConvertTo-HashtableDeep {
  param($InputObject)
  if ($null -eq $InputObject) { return $null }
  if ($InputObject -is [System.Collections.IDictionary]) {
    $h = @{}
    foreach ($k in $InputObject.Keys) {
      $h[$k] = ConvertTo-HashtableDeep -InputObject $InputObject[$k]
    }
    return $h
  }
  if ($InputObject -is [System.Collections.IEnumerable] -and -not ($InputObject -is [string])) {
    $arr = @()
    foreach ($item in $InputObject) {
      $arr += @(ConvertTo-HashtableDeep -InputObject $item)
    }
    return $arr
  }
  if ($InputObject -is [psobject]) {
    $props = $InputObject.PSObject.Properties
    if ((@($props)).Count -gt 0) {
      $h = @{}
      foreach ($p in $props) {
        $h[$p.Name] = ConvertTo-HashtableDeep -InputObject $p.Value
      }
      return $h
    }
  }
  return $InputObject
}

function Load-Json {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return $null }
  $raw = Get-Content -Path $Path -Raw
  if ([string]::IsNullOrWhiteSpace($raw)) { return $null }

  # PowerShell 5 compatibility: ConvertFrom-Json lacks -AsHashtable.
  $parsed = $null
  try {
    $parsed = $raw | ConvertFrom-Json -AsHashtable
  } catch {
    $parsed = $raw | ConvertFrom-Json
  }
  return (ConvertTo-HashtableDeep -InputObject $parsed)
}

function To-Num {
  param($Value, [double]$Fallback = 0)
  try {
    if ($null -eq $Value) { return $Fallback }
    $n = [double]$Value
    if ([double]::IsNaN($n) -or [double]::IsInfinity($n)) { return $Fallback }
    return $n
  } catch {
    return $Fallback
  }
}

function Parse-Percent {
  param([string]$Text)
  if ([string]::IsNullOrWhiteSpace($Text)) { return 0.0 }
  return (To-Num ($Text.Replace('%', '')) 0) / 100.0
}

function Normalize-RunRows {
  param(
    [array]$Rows,
    [string]$StrategyId
  )
  $filtered = @($Rows | Where-Object { $_.strategyId -eq $StrategyId })
  if ($filtered.Count -eq 0) {
    return [ordered]@{
      trades = 0
      winRate = 0.0
      expectancy = 0.0
      profitFactor = 0.0
      maxDrawdownPct = 100.0
      netPnl = 0.0
      sharpe = 0.0
      executionReliabilityPct = 0.0
      noRouteRate = 0.0
      unresolvedRate = 0.0
      executionAdjustedExpectancy = 0.0
      executionAdjustedNetPnlPct = 0.0
      degraded = $true
    }
  }

  $totalTrades = [int](($filtered | Measure-Object -Property trades -Sum).Sum)
  if ($totalTrades -lt 0) { $totalTrades = 0 }

  $weightedWin = 0.0
  $weightedExp = 0.0
  $weightedPf = 0.0
  $weightedSharpe = 0.0
  $weightedExecRel = 0.0
  $weightedNoRoute = 0.0
  $weightedUnresolved = 0.0
  $weightedExecAdjExp = 0.0
  $weightedExecAdjNetPnlPct = 0.0
  $degradedCount = 0
  $maxDd = 0.0
  foreach ($row in $filtered) {
    $trades = [int](To-Num $row.trades 0)
    $w = if ($totalTrades -gt 0) { $trades / [double]$totalTrades } else { 0.0 }
    $weightedWin += (Parse-Percent ([string]$row.winRate)) * $w
    $weightedExp += (To-Num $row.expectancy 0) * $w
    $weightedPf += (To-Num $row.profitFactor 0) * $w
    $weightedSharpe += (To-Num $row.sharpe 0) * $w
    $weightedExecRel += (To-Num $row.executionReliabilityPct 0) * $w
    $weightedNoRoute += (To-Num $row.noRouteRate 0) * $w
    $weightedUnresolved += (To-Num $row.unresolvedRate 0) * $w
    $weightedExecAdjExp += (To-Num $row.executionAdjustedExpectancy 0) * $w
    $weightedExecAdjNetPnlPct += (To-Num $row.executionAdjustedNetPnlPct 0) * $w
    if ([bool]$row.degraded) { $degradedCount += 1 }
    $dd = To-Num (([string]$row.maxDD).Replace('%', '')) 0
    if ($dd -gt $maxDd) { $maxDd = $dd }
  }
  $netPnl = $weightedExp * $totalTrades

  return [ordered]@{
    trades = $totalTrades
    winRate = $weightedWin
    expectancy = $weightedExp
    profitFactor = $weightedPf
    maxDrawdownPct = $maxDd
    netPnl = $netPnl
    sharpe = $weightedSharpe
    executionReliabilityPct = $weightedExecRel
    noRouteRate = $weightedNoRoute
    unresolvedRate = $weightedUnresolved
    executionAdjustedExpectancy = $weightedExecAdjExp
    executionAdjustedNetPnlPct = $weightedExecAdjNetPnlPct
    degraded = ($degradedCount -gt 0)
  }
}

function Get-ReducedTokens {
  param([int]$Current, [int[]]$Ladder)
  $idx = [array]::IndexOf($Ladder, $Current)
  if ($idx -gt 0) { return [int]$Ladder[$idx - 1] }
  return [Math]::Max(10, [int][Math]::Floor($Current * 0.75))
}

function Get-FamilyBaselineMaxTokens {
  param([string]$Family)
  switch ($Family) {
    "memecoin" { return 120 }
    "bags" { return 120 }
    "bluechip" { return 80 }
    "xstock" { return 80 }
    "prestock" { return 80 }
    "index" { return 80 }
    default { return [int]$ExpansionLadder[0] }
  }
}

function Get-FamilyExpansionLadder {
  param([string]$Family)
  switch ($Family) {
    "memecoin" { return @(120, 160, 200, 260, 320) }
    "bags" { return @(120, 160, 200, 260, 320) }
    "bluechip" { return @(80, 120, 160, 200) }
    "xstock" { return @(80, 120, 160, 200) }
    "prestock" { return @(80, 120, 160, 200) }
    "index" { return @(80, 120, 160, 200) }
    default { return $ExpansionLadder }
  }
}

function Add-UniqueListItem {
  param(
    [hashtable]$State,
    [string]$Key,
    [string]$Value
  )
  if ([string]::IsNullOrWhiteSpace($Value)) { return }
  if ($Key -notin @($State.Keys) -or $null -eq $State[$Key]) {
    $State[$Key] = @()
  }
  $arr = @($State[$Key] | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  if ($arr -notcontains $Value) { $arr += @($Value) }
  $State[$Key] = $arr
}

function Get-DynamicTimeoutSec {
  param(
    [int]$ExpectedRequests,
    [int]$Fallback = 240
  )
  $base = 180 + [int][Math]::Ceiling(([double][Math]::Max(1, $ExpectedRequests)) * 0.45)
  $bounded = [Math]::Max(180, [Math]::Min(300, $base))
  if ($bounded -lt 180) { return [Math]::Max(180, [Math]::Min(300, $Fallback)) }
  return $bounded
}

function Get-JitterBackoffSec {
  param([int]$Attempt = 1)
  $pow = [Math]::Pow(2, [Math]::Max(1, $Attempt) - 1)
  $base = [int][Math]::Min(30, (5 * $pow))
  $jitter = Get-Random -Minimum 0 -Maximum 4
  return [int]($base + $jitter)
}

function Is-TransientBacktestFailure {
  param(
    [string]$ErrorText,
    $Diagnostics = $null
  )
  $text = [string]$ErrorText
  if ($null -ne $Diagnostics) {
    try {
      $diagErr = [string]$Diagnostics.error
      if (-not [string]::IsNullOrWhiteSpace($diagErr)) {
        $text = "$text $diagErr"
      }
      $diagState = [string]$Diagnostics.state
      if (-not [string]::IsNullOrWhiteSpace($diagState)) {
        $text = "$text state=$diagState"
      }
    } catch {}
  }
  $t = $text.ToLowerInvariant()
  if ($t -match "timeout|timed out|status endpoint unreachable|no status motion|stalled") { return $true }
  if ($t -match "500|502|503|504|gateway|temporarily unavailable|connection reset|connection closed") { return $true }
  return $false
}

function Get-StrategyMapFromRoute {
  $routePath = Join-Path (Get-Location) "src\app\api\backtest\route.ts"
  if (-not (Test-Path $routePath)) {
    throw "Missing $routePath"
  }
  $raw = Get-Content -Path $routePath -Raw

  $catMap = @{}
  $catBlockMatch = [regex]::Match($raw, "const STRATEGY_CATEGORY:[\s\S]*?=\s*\{([\s\S]*?)\};")
  if ($catBlockMatch.Success) {
    $catRows = [regex]::Matches($catBlockMatch.Groups[1].Value, "(?m)^\s*([a-z0-9_]+):\s*'([a-z_]+)'")
    foreach ($m in $catRows) {
      $catMap[$m.Groups[1].Value] = $m.Groups[2].Value
    }
  }

  $cfgIds = @()
  $cfgBlockMatch = [regex]::Match(
    $raw,
    "const STRATEGY_CONFIGS_BASE:[\s\S]*?=\s*\{([\s\S]*?)\n\};\s*\n\s*const STRATEGY_CONFIGS",
    [System.Text.RegularExpressions.RegexOptions]::Singleline
  )
  if ($cfgBlockMatch.Success) {
    $cfgRows = [regex]::Matches($cfgBlockMatch.Groups[1].Value, "strategyId:\s*'([a-z0-9_]+)'")
    foreach ($m in $cfgRows) {
      $id = [string]$m.Groups[1].Value
      if ($id -and -not $cfgIds.Contains($id)) { $cfgIds += $id }
    }
  }
  if ($cfgIds.Count -eq 0) {
    throw "Could not parse STRATEGY_CONFIGS from route.ts"
  }

  $rows = @()
  foreach ($sid in $cfgIds) {
    $cat = if ($sid -in @($catMap.Keys)) { [string]$catMap[$sid] } else { "unknown" }
    $family =
      if ($cat -eq "xstock_index") {
        if ($sid.StartsWith("xstock_")) { "xstock" }
        elseif ($sid.StartsWith("prestock_")) { "prestock" }
        elseif ($sid.StartsWith("index_")) { "index" }
        else { "xstock" }
      } elseif ($cat -eq "memecoin" -or $cat -eq "bags" -or $cat -eq "bluechip") {
        $cat
      } else {
        "unknown"
      }
    $rows += [ordered]@{
      strategyId = $sid
      family = $family
      targetTrades = $TargetTradesPerStrategy
      achievedTrades = 0
      cumulativeTrades = 0
      passes = 0
      promoted = $false
      promotionReason = $null
      insufficiencyReason = $null
    }
  }
  return $rows
}

function New-CampaignState {
  param([array]$Strategies)
  $runsByStrategy = @{}
  foreach ($s in $Strategies) { $runsByStrategy[$s.strategyId] = @() }

  return [ordered]@{
    campaignId = $CampaignId
    startedAt = (Get-Date).ToString("o")
    updatedAt = (Get-Date).ToString("o")
    phase = "preflight"
    defaults = [ordered]@{
      strictNoSynthetic = $true
      includeEvidence = $true
      sourceTierPolicy = "adaptive_tiered"
      targetTradesPerStrategy = $TargetTradesPerStrategy
      cohort = "baseline_90d"
      lookbackHours = 2160
    }
    strategies = $Strategies
    runsByStrategy = $runsByStrategy
    attemptsByRunId = @{}
    runMetricsByRunId = @{}
    completedRunIds = @()
    failedRunIds = @()
    insufficientStrategies = @()
    insufficiencyAttemptsByStrategy = @{}
    familyPasses = @{}
    datasetManifestByFamily = @{}
    runtimeByRunIdSec = @{}
    telemetry = [ordered]@{
      timeoutRuns = 0
      stalledRuns = 0
      transientRetries = 0
      transientRetrySuccess = 0
      statusPolls = 0
      statusPollErrors = 0
      statusLatencyTotalMs = 0
      statusLatencyMaxMs = 0
      completionRatio = 0.0
      degradedCompletionRatio = 0.0
    }
    artifactIndex = @()
  }
}

function Save-State {
  param([hashtable]$State)
  $State.updatedAt = (Get-Date).ToString("o")
  Save-Json -Path $statePath -Data $State
}

function Invoke-JsonApi {
  param(
    [string]$Method,
    [string]$Uri,
    $Body = $null,
    [int]$TimeoutSec = 30
  )
  $job = Start-Job -ScriptBlock {
    param($Method, $Uri, $BodyObj)
    try {
      if ($null -eq $BodyObj) {
        $resp = Invoke-RestMethod -Method $Method -Uri $Uri -UseBasicParsing
      } else {
        $payload = $BodyObj | ConvertTo-Json -Depth 30 -Compress
        $resp = Invoke-RestMethod -Method $Method -Uri $Uri -ContentType "application/json" -Body $payload -UseBasicParsing
      }
      [pscustomobject]@{
        ok = $true
        response = $resp
      }
    } catch {
      [pscustomobject]@{
        ok = $false
        error = $_.Exception.Message
      }
    }
  } -ArgumentList $Method, $Uri, $Body

  $completed = Wait-Job -Job $job -Timeout $TimeoutSec
  if ($null -eq $completed) {
    try { Stop-Job -Job $job -Force } catch {}
    try { Remove-Job -Job $job -Force | Out-Null } catch {}
    throw "API timeout after ${TimeoutSec}s ($Method $Uri)"
  }

  $result = Receive-Job -Job $job
  Remove-Job -Job $job -Force | Out-Null

  if (-not $result.ok) {
    throw [string]$result.error
  }
  return $result.response
}

function Get-HttpErrorDetail {
  param($ErrorRecord)
  try {
    $resp = $ErrorRecord.Exception.Response
    if ($null -eq $resp) { return [string]$ErrorRecord.Exception.Message }
    $code = $resp.StatusCode.value__
    $desc = $resp.StatusDescription
    return "$code $desc"
  } catch {
    return [string]$ErrorRecord.Exception.Message
  }
}

function Start-BacktestJob {
  param(
    [hashtable]$Payload,
    [int]$TimeoutSec = 1200
  )

  $jsonBody = $Payload | ConvertTo-Json -Depth 30 -Compress
  $job = Start-Job -ScriptBlock {
    param($Body, $TimeoutSec)
    try {
      $resp = Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:3001/api/backtest" -ContentType "application/json" -Body $Body -TimeoutSec $TimeoutSec -UseBasicParsing
      return [pscustomobject]@{ ok = $true; response = $resp }
    } catch {
      return [pscustomobject]@{
        ok = $false
        error = $_.Exception.Message
        detail = ($_ | Out-String)
      }
    }
  } -ArgumentList $jsonBody, $TimeoutSec
  return $job
}

function Poll-RunUntilDone {
  param(
    [string]$RunId,
    [System.Management.Automation.Job]$Job,
    [int]$RunTimeoutSec = 1200,
    [int]$RunStallAfterSec = 420
  )
  $started = Get-Date
  $lastPollOk = $started
  $lastStatus = $null
  $lastHeartbeat = $started
  $lastMotionAt = $started
  $lastSeenMotionTs = 0L
  $pollCount = 0
  $pollErrorCount = 0
  $pollLatencyTotalMs = 0
  $pollLatencyMaxMs = 0

  while ($true) {
    if ($Job.State -in @("Completed", "Failed", "Stopped")) { break }
    Start-Sleep -Seconds $PollEverySec

    if (((Get-Date) - $started).TotalSeconds -ge $RunTimeoutSec) {
      try { Stop-Job -Job $Job -Force } catch {}
      return [ordered]@{
        ok = $false
        status = "timeout"
        error = "Hard timeout ${RunTimeoutSec}s"
        runStatus = $lastStatus
        telemetry = [ordered]@{
          polls = $pollCount
          pollErrors = $pollErrorCount
          statusLatencyTotalMs = $pollLatencyTotalMs
          statusLatencyMaxMs = $pollLatencyMaxMs
          statusLatencyAvgMs = if ($pollCount -gt 0) { [math]::Round($pollLatencyTotalMs / [double]$pollCount, 2) } else { 0 }
        }
      }
    }

    try {
      $pollStarted = Get-Date
      $status = Invoke-JsonApi -Method GET -Uri "http://127.0.0.1:3001/api/backtest/runs/$RunId" -TimeoutSec $PollTimeoutSec
      $latMs = [int][Math]::Max(0, ((Get-Date) - $pollStarted).TotalMilliseconds)
      $pollCount += 1
      $pollLatencyTotalMs += $latMs
      if ($latMs -gt $pollLatencyMaxMs) { $pollLatencyMaxMs = $latMs }
      $lastStatus = $status
      $lastPollOk = Get-Date
      $progressNow = [int](To-Num $status.progress 0)
      $completedNow = [int](To-Num $status.completedChunks 0)
      $failedNow = [int](To-Num $status.failedChunks 0)
      $statusUpdated = [int64](To-Num $status.updatedAt 0)
      $statusHeartbeat = [int64](To-Num $status.heartbeatAt 0)
      $statusDatasetMotion = [int64](To-Num $status.lastDatasetBatchAt 0)
      $motionTs = [Math]::Max($statusUpdated, [Math]::Max($statusHeartbeat, $statusDatasetMotion))
      if ($motionTs -gt $lastSeenMotionTs) {
        $lastSeenMotionTs = $motionTs
        $lastMotionAt = Get-Date
      }

      if (((Get-Date) - $lastHeartbeat).TotalSeconds -ge 60) {
        $state = [string]$status.state
        $chunks = "$completedNow/$([int](To-Num $status.totalChunks 0))"
        $elapsed = [int](((Get-Date) - $started).TotalSeconds)
        $staleFor = [int](((Get-Date) - $lastMotionAt).TotalSeconds)
        $ds = "$([int](To-Num $status.datasetsSucceeded 0))/$([int](To-Num $status.datasetsAttempted 0))"
        Write-Log "Heartbeat run=$RunId state=$state progress=${progressNow}% chunks=$chunks datasets=$ds elapsed=${elapsed}s noMotion=${staleFor}s"
        $lastHeartbeat = Get-Date
      }

      if (((Get-Date) - $lastMotionAt).TotalSeconds -ge $RunStallAfterSec) {
        try { Stop-Job -Job $Job -Force } catch {}
        return [ordered]@{
          ok = $false
          status = "stalled"
          error = "No status motion for ${RunStallAfterSec}s (updatedAt/heartbeatAt/lastDatasetBatchAt)"
          runStatus = $lastStatus
          telemetry = [ordered]@{
            polls = $pollCount
            pollErrors = $pollErrorCount
            statusLatencyTotalMs = $pollLatencyTotalMs
            statusLatencyMaxMs = $pollLatencyMaxMs
            statusLatencyAvgMs = if ($pollCount -gt 0) { [math]::Round($pollLatencyTotalMs / [double]$pollCount, 2) } else { 0 }
          }
        }
      }
    } catch {
      $pollErrorCount += 1
      if (((Get-Date) - $lastPollOk).TotalSeconds -ge $RunStallAfterSec) {
        try { Stop-Job -Job $Job -Force } catch {}
        return [ordered]@{
          ok = $false
          status = "stalled"
          error = "Status endpoint unreachable for ${RunStallAfterSec}s"
          runStatus = $lastStatus
          telemetry = [ordered]@{
            polls = $pollCount
            pollErrors = $pollErrorCount
            statusLatencyTotalMs = $pollLatencyTotalMs
            statusLatencyMaxMs = $pollLatencyMaxMs
            statusLatencyAvgMs = if ($pollCount -gt 0) { [math]::Round($pollLatencyTotalMs / [double]$pollCount, 2) } else { 0 }
          }
        }
      }
      # keep waiting; transient polling errors are non-fatal
    }
  }

  $jobResult = Receive-Job -Job $Job
  Remove-Job -Job $Job -Force | Out-Null
  if (-not $jobResult.ok) {
    return [ordered]@{
      ok = $false
      status = "failed"
      error = [string]$jobResult.error
      detail = $jobResult.detail
      runStatus = $lastStatus
      telemetry = [ordered]@{
        polls = $pollCount
        pollErrors = $pollErrorCount
        statusLatencyTotalMs = $pollLatencyTotalMs
        statusLatencyMaxMs = $pollLatencyMaxMs
        statusLatencyAvgMs = if ($pollCount -gt 0) { [math]::Round($pollLatencyTotalMs / [double]$pollCount, 2) } else { 0 }
      }
    }
  }

  $finalStatus = $null
  try { $finalStatus = Invoke-JsonApi -Method GET -Uri "http://127.0.0.1:3001/api/backtest/runs/$RunId" -TimeoutSec $PollTimeoutSec } catch {}
  return [ordered]@{
    ok = $true
    status = "completed"
    response = $jobResult.response
    runStatus = $finalStatus
    telemetry = [ordered]@{
      polls = $pollCount
      pollErrors = $pollErrorCount
      statusLatencyTotalMs = $pollLatencyTotalMs
      statusLatencyMaxMs = $pollLatencyMaxMs
      statusLatencyAvgMs = if ($pollCount -gt 0) { [math]::Round($pollLatencyTotalMs / [double]$pollCount, 2) } else { 0 }
    }
  }
}

function Add-ArtifactRef {
  param(
    [hashtable]$State,
    [string]$RunId
  )
  function Add-RefIfComplete {
    param([string]$ResolvedRunId)
    if ([string]::IsNullOrWhiteSpace($ResolvedRunId)) { return $false }
    $base = Join-Path (Get-Location) ".jarvis-cache\backtest-runs\$ResolvedRunId"
    $manifest = Join-Path $base "manifest.json"
    $evidence = Join-Path $base "evidence.json"
    $report = Join-Path $base "report.md"
    $csv = Join-Path $base "trades.csv"
    if (-not ((Test-Path $manifest) -and (Test-Path $evidence) -and (Test-Path $report) -and (Test-Path $csv))) {
      return $false
    }
    $ref = [ordered]@{
      runId = $RunId
      evidenceRunId = $ResolvedRunId
      manifestPath = $manifest
      evidencePath = $evidence
      reportPath = $report
      tradesCsvPath = $csv
    }
    $exists = $false
    foreach ($a in $State.artifactIndex) {
      if ($a.runId -eq $RunId -and $a.evidenceRunId -eq $ResolvedRunId) { $exists = $true; break }
    }
    if (-not $exists) { $State.artifactIndex += $ref }
    return $true
  }

  try {
    $meta = Invoke-JsonApi -Method GET -Uri "http://127.0.0.1:3001/api/backtest/runs/$RunId/artifacts" -TimeoutSec $PollTimeoutSec
    $artifactRunId = [string]$meta.artifactRunId
    if (Add-RefIfComplete -ResolvedRunId $artifactRunId) { return }
  } catch {
    # fallback below
  }

  try {
    $status = Invoke-JsonApi -Method GET -Uri "http://127.0.0.1:3001/api/backtest/runs/$RunId" -TimeoutSec $PollTimeoutSec
    $fallbackRunId = [string]$status.evidenceRunId
    [void](Add-RefIfComplete -ResolvedRunId $fallbackRunId)
  } catch {
    # artifact fetch is best-effort; failure is recorded via attempts
  }
}

function Evaluate-Promotion {
  param(
    [hashtable]$Metric,
    [string]$Family
  )
  if ([int]$Metric.trades -lt 5000) { return [ordered]@{ promoted = $false; reason = "trades < 5000" } }
  if ((To-Num $Metric.expectancy 0) -le 0) { return [ordered]@{ promoted = $false; reason = "expectancy <= 0" } }
  if ((To-Num $Metric.profitFactor 0) -lt 1.05) { return [ordered]@{ promoted = $false; reason = "profitFactor < 1.05" } }
  $maxDdGate = if ($Family -in @("memecoin", "bags")) { 45 } else { 30 }
  if ((To-Num $Metric.maxDrawdownPct 100) -gt $maxDdGate) { return [ordered]@{ promoted = $false; reason = "maxDD gate failed" } }
  $wrGate = if ($Family -in @("memecoin", "bags")) { 0.40 } else { 0.45 }
  if ((To-Num $Metric.winRate 0) -lt $wrGate) { return [ordered]@{ promoted = $false; reason = "winRate gate failed" } }
  if ((To-Num $Metric.executionReliabilityPct 0) -lt 80) { return [ordered]@{ promoted = $false; reason = "executionReliabilityPct < 80" } }
  return [ordered]@{ promoted = $true; reason = "passed promotion gates" }
}

function Invoke-StrategyAttempt {
  param(
    [hashtable]$State,
    [hashtable]$Entry,
    [int]$MaxTokens,
    [string]$SourcePolicy,
    [string]$DataScale,
    [string]$Mode
  )
  $strategyId = [string]$Entry.strategyId
  $family = [string]$Entry.family
  $safeMaxTokens = [int][Math]::Min(500, [Math]::Max(10, $MaxTokens))
  $runId = "$CampaignId-$strategyId-$Mode-$($SourcePolicy.Replace('_','-'))-m$safeMaxTokens-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
  $manifestId = "manifest-$runId"
  if ($family -notin @($State.datasetManifestByFamily.Keys)) {
    $State.datasetManifestByFamily[$family] = "$CampaignId-family-$family"
  }
  $datasetManifestId = [string]$State.datasetManifestByFamily[$family]
  $fetchBatchSize = if ($DataScale -eq "thorough") { 3 } else { 4 }
  $payload = [ordered]@{
    strategyId = $strategyId
    strategyIds = @($strategyId)
    family = $family
    tokenSymbol = "all"
    mode = $Mode
    dataScale = $DataScale
    maxTokens = $safeMaxTokens
    datasetManifestId = $datasetManifestId
    sourcePolicy = $SourcePolicy
    lookbackHours = 2160
    maxCandles = 2160
    fetchBatchSize = $fetchBatchSize
    strictNoSynthetic = $true
    targetTradesPerStrategy = $TargetTradesPerStrategy
    sourceTierPolicy = "adaptive_tiered"
    cohort = "baseline_90d"
    runId = $runId
    manifestId = $manifestId
    includeEvidence = $true
    includeReport = $true
    includeFullResults = $true
  }

  $State.runsByStrategy[$strategyId] += @($runId)
  $State.attemptsByRunId[$runId] = [ordered]@{
    runId = $runId
    strategyId = $strategyId
    startedAt = (Get-Date).ToString("o")
    status = "running"
    sourcePolicy = $SourcePolicy
    maxTokens = $safeMaxTokens
    mode = $Mode
    dataScale = $DataScale
  }
  Save-State -State $State

  Write-Log "Starting run $runId for $strategyId ($Mode, $DataScale, $SourcePolicy, maxTokens=$safeMaxTokens)"
  $requestMultiplier = if ($DataScale -eq "thorough") { 3 } else { 2 }
  $expectedRequests = [Math]::Max(20, ($safeMaxTokens * $requestMultiplier))
  $runTimeoutSec = Get-DynamicTimeoutSec -ExpectedRequests $expectedRequests -Fallback $HardTimeoutSec
  $job = Start-BacktestJob -Payload $payload -TimeoutSec $runTimeoutSec
  $result = Poll-RunUntilDone -RunId $runId -Job $job -RunTimeoutSec $runTimeoutSec -RunStallAfterSec $StallAfterSec

  $attempt = $State.attemptsByRunId[$runId]
  $attempt.endedAt = (Get-Date).ToString("o")
  $attempt.status = [string]$result.status
  $attempt.timeoutSec = $runTimeoutSec
  $attempt.expectedRequests = $expectedRequests
  $polls = [int](To-Num $result.telemetry.polls 0)
  $pollErrors = [int](To-Num $result.telemetry.pollErrors 0)
  $statusLatencyTotalMs = [int](To-Num $result.telemetry.statusLatencyTotalMs 0)
  $statusLatencyMaxMs = [int](To-Num $result.telemetry.statusLatencyMaxMs 0)
  $statusLatencyAvgMs = To-Num $result.telemetry.statusLatencyAvgMs 0
  $attempt.statusPolls = $polls
  $attempt.statusPollErrors = $pollErrors
  $attempt.statusLatencyTotalMs = $statusLatencyTotalMs
  $attempt.statusLatencyMaxMs = $statusLatencyMaxMs
  $attempt.statusLatencyAvgMs = $statusLatencyAvgMs
  $State.telemetry.statusPolls = [int](To-Num $State.telemetry.statusPolls 0) + $polls
  $State.telemetry.statusPollErrors = [int](To-Num $State.telemetry.statusPollErrors 0) + $pollErrors
  $State.telemetry.statusLatencyTotalMs = [int](To-Num $State.telemetry.statusLatencyTotalMs 0) + $statusLatencyTotalMs
  $prevLatencyMax = [int](To-Num $State.telemetry.statusLatencyMaxMs 0)
  if ($statusLatencyMaxMs -gt $prevLatencyMax) { $State.telemetry.statusLatencyMaxMs = $statusLatencyMaxMs }
  if ($result.status -eq "timeout") {
    $State.telemetry.timeoutRuns = [int](To-Num $State.telemetry.timeoutRuns 0) + 1
  }
  if ($result.status -eq "stalled") {
    $State.telemetry.stalledRuns = [int](To-Num $State.telemetry.stalledRuns 0) + 1
  }
  if (-not $result.ok) {
    $attempt.error = [string]$result.error
    $attempt.diagnostics = $result.runStatus
    Add-UniqueListItem -State $State -Key "failedRunIds" -Value $runId
    Save-State -State $State
    return [ordered]@{ ok = $false; runId = $runId; error = $result.error; payload = $payload; diagnostics = $result.runStatus }
  }
  $durationSec = 0
  try {
    $durationSec = [int]([Math]::Max(0, ((Get-Date $attempt.endedAt) - (Get-Date $attempt.startedAt)).TotalSeconds))
  } catch {
    $durationSec = 0
  }
  if ("runtimeByRunIdSec" -notin @($State.Keys)) { $State.runtimeByRunIdSec = @{} }
  $State.runtimeByRunIdSec[$runId] = $durationSec

  Add-UniqueListItem -State $State -Key "completedRunIds" -Value $runId
  Add-ArtifactRef -State $State -RunId $runId

  $rows = @($result.response.results)
  $metric = Normalize-RunRows -Rows $rows -StrategyId $strategyId
  $metric.executionReliabilityPct = To-Num $result.response.executionReliabilityPct $metric.executionReliabilityPct
  $metric.noRouteRate = To-Num $result.response.noRouteRate $metric.noRouteRate
  $metric.unresolvedRate = To-Num $result.response.unresolvedRate $metric.unresolvedRate
  $metric.executionAdjustedExpectancy = To-Num $result.response.executionAdjustedExpectancy $metric.executionAdjustedExpectancy
  $metric.executionAdjustedNetPnlPct = To-Num $result.response.executionAdjustedNetPnlPct $metric.executionAdjustedNetPnlPct
  $metric.degraded = [bool]$result.response.degraded
  $State.runMetricsByRunId[$runId] = $metric

  $stateEntry = Get-EntryByStrategyId -State $State -StrategyId $strategyId
  if ($null -eq $stateEntry) { $stateEntry = $Entry }
  $stateEntry.achievedTrades = [Math]::Max([int]$stateEntry.achievedTrades, [int]$metric.trades)
  $stateEntry.cumulativeTrades = [int]$stateEntry.cumulativeTrades + [int]$metric.trades
  $stateEntry.passes = [int]$stateEntry.passes + 1
  $familyKey = [string]$stateEntry.family
  $currentFamilyPasses = 0
  if ($familyKey -in @($State.familyPasses.Keys)) { $currentFamilyPasses = [int](To-Num $State.familyPasses[$familyKey] 0) }
  $State.familyPasses[$familyKey] = $currentFamilyPasses + 1

  Save-State -State $State
  return [ordered]@{ ok = $true; runId = $runId; metric = $metric; response = $result.response; payload = $payload }
}

function Invoke-StrategyWithRetries {
  param(
    [hashtable]$State,
    [hashtable]$Entry,
    [int]$MaxTokens,
    [string]$DataScale,
    [string]$Mode
  )
  $familyLadder = @(Get-FamilyExpansionLadder -Family ([string]$Entry.family))
  if ($familyLadder.Count -eq 0) { $familyLadder = $ExpansionLadder }
  $attemptMatrix = @(
    [ordered]@{ label = "A"; sourcePolicy = "gecko_only"; maxTokens = $MaxTokens },
    [ordered]@{ label = "B"; sourcePolicy = "allow_birdeye_fallback"; maxTokens = $MaxTokens },
    [ordered]@{ label = "C"; sourcePolicy = "gecko_only"; maxTokens = (Get-ReducedTokens -Current $MaxTokens -Ladder $familyLadder) }
  )

  foreach ($attempt in $attemptMatrix) {
    $res = Invoke-StrategyAttempt -State $State -Entry $Entry -MaxTokens ([int]$attempt.maxTokens) -SourcePolicy ([string]$attempt.sourcePolicy) -DataScale $DataScale -Mode $Mode
    $transientRetried = $false
    if (-not $res.ok -and (Is-TransientBacktestFailure -ErrorText ([string]$res.error) -Diagnostics $res.diagnostics)) {
      $transientRetried = $true
      $State.telemetry.transientRetries = [int](To-Num $State.telemetry.transientRetries 0) + 1
      $delaySec = Get-JitterBackoffSec -Attempt 1
      Write-Log "Transient failure for $($Entry.strategyId) attempt $($attempt.label); retrying once in ${delaySec}s" "WARN"
      Save-State -State $State
      Start-Sleep -Seconds $delaySec
      $retryRes = Invoke-StrategyAttempt -State $State -Entry $Entry -MaxTokens ([int]$attempt.maxTokens) -SourcePolicy ([string]$attempt.sourcePolicy) -DataScale $DataScale -Mode $Mode
      if ($retryRes.ok) {
        $State.telemetry.transientRetrySuccess = [int](To-Num $State.telemetry.transientRetrySuccess 0) + 1
        Save-State -State $State
        return $retryRes
      }
      $res = $retryRes
    }
    if ($res.ok) { return $res }
    if ($Entry.strategyId -notin @($State.insufficiencyAttemptsByStrategy.Keys)) {
      $State.insufficiencyAttemptsByStrategy[$Entry.strategyId] = @()
    }
    $State.insufficiencyAttemptsByStrategy[$Entry.strategyId] += @([ordered]@{
      at = (Get-Date).ToString("o")
      attempt = [string]$attempt.label
      sourcePolicy = [string]$attempt.sourcePolicy
      maxTokens = [int]$attempt.maxTokens
      transientRetried = $transientRetried
      error = [string]$res.error
    })
    Save-State -State $State
    Write-Log "Attempt $($attempt.label) failed for $($Entry.strategyId): $($res.error)" "WARN"
  }

  return [ordered]@{ ok = $false; error = "All retries failed (A/B/C)" }
}

function Get-EntryByStrategyId {
  param([hashtable]$State, [string]$StrategyId)
  foreach ($s in $State.strategies) { if ($s.strategyId -eq $StrategyId) { return $s } }
  return $null
}

function Mark-Insufficient {
  param([hashtable]$State, [string]$StrategyId, [string]$Reason)
  Add-UniqueListItem -State $State -Key "insufficientStrategies" -Value $StrategyId
  $entry = Get-EntryByStrategyId -State $State -StrategyId $StrategyId
  if ($null -ne $entry) {
    $entry.promoted = $false
    $entry.insufficiencyReason = $Reason
  }
}

function Run-Preflight {
  Write-Log "Phase A: preflight health checks"
  # 1. Port listen
  $listener = Get-NetTCPConnection -LocalPort 3001 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" } | Select-Object -First 1
  if (-not $listener) { throw "Dev server not listening on 3001" }

  # 2. POST /api/backtest health with deterministic local-candle probe first.
  # This avoids long external fetches in preflight while still validating run/status/artifact plumbing.
  $healthCandles = @()
  $nowTs = [int64]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())
  for ($i = 0; $i -lt 120; $i++) {
    $price = 100 + [Math]::Sin($i / 6.0) * 2 + ($i * 0.05)
    $open = [Math]::Round($price, 6)
    $close = [Math]::Round($price + [Math]::Sin($i / 3.0) * 0.4, 6)
    $high = [Math]::Round([Math]::Max($open, $close) + 0.3, 6)
    $low = [Math]::Round([Math]::Min($open, $close) - 0.3, 6)
    $vol = [Math]::Round(1000 + ($i % 10) * 25, 2)
    $healthCandles += @([ordered]@{
      timestamp = ($nowTs - (120 - $i) * 3600000)
      open = $open
      high = $high
      low = $low
      close = $close
      volume = $vol
    })
  }

  # Fallback probes for real-data route health if needed.
  $probeCandidates = @(
    [ordered]@{ strategyId = "bluechip_trend_follow"; tokenSymbol = "HEALTH"; dataScale = "fast"; maxTokens = 10; sourcePolicy = "gecko_only"; useClientCandles = $true; strictNoSynthetic = $false },
    [ordered]@{ strategyId = "bluechip_trend_follow"; tokenSymbol = "all"; dataScale = "fast"; maxTokens = 10; sourcePolicy = "gecko_only"; useClientCandles = $false; strictNoSynthetic = $true },
    [ordered]@{ strategyId = "momentum"; tokenSymbol = "all"; dataScale = "fast"; maxTokens = 20; sourcePolicy = "gecko_only"; useClientCandles = $false; strictNoSynthetic = $true }
  )
  $probeResp = $null
  $probeRun = $null
  foreach ($probe in $probeCandidates) {
    $probeRun = "preflight-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())-$([System.Guid]::NewGuid().ToString('N').Substring(0,6))"
    $probeBody = [ordered]@{
      strategyId = $probe.strategyId
      tokenSymbol = $probe.tokenSymbol
      mode = "quick"
      dataScale = $probe.dataScale
      maxTokens = $probe.maxTokens
      sourcePolicy = $probe.sourcePolicy
      lookbackHours = 2160
      strictNoSynthetic = [bool]$probe.strictNoSynthetic
      includeEvidence = $true
      runId = $probeRun
      manifestId = "manifest-$probeRun"
    }
    if ([bool]$probe.useClientCandles) {
      $probeBody.candles = $healthCandles
    }
    try {
      $probeResp = Invoke-JsonApi -Method POST -Uri "http://127.0.0.1:3001/api/backtest" -Body $probeBody -TimeoutSec 180
      if ($probeResp.runId) { break }
      $probeResp = $null
    } catch {
      $detail = Get-HttpErrorDetail -ErrorRecord $_
      Write-Log "Preflight probe failed [$($probe.strategyId)/$($probe.tokenSymbol)]: $detail" "WARN"
      $probeResp = $null
      Start-Sleep -Seconds 2
    }
  }
  if ($null -eq $probeResp -or -not $probeResp.runId) { throw "POST /api/backtest health probes failed (all candidates)" }

  # 3. GET /runs/:runId (poll until completed to avoid transient 404/partial state)
  $statusResp = $null
  $statusDeadline = (Get-Date).AddSeconds(180)
  while ((Get-Date) -lt $statusDeadline) {
    try {
      $statusResp = Invoke-JsonApi -Method GET -Uri "http://127.0.0.1:3001/api/backtest/runs/$($probeResp.runId)" -TimeoutSec 30
      if ($statusResp.runId -and (($statusResp.state -eq "completed") -or ($statusResp.progress -ge 100))) { break }
    } catch {
      # transient status miss while run registry is still being flushed
    }
    Start-Sleep -Seconds 3
  }
  if ($null -eq $statusResp -or -not $statusResp.runId) { throw "GET /api/backtest/runs/:runId failed in preflight window" }

  # 4. GET /runs/:runId/artifacts (retry because artifact persistence can lag run completion slightly)
  $artResp = $null
  $artifactDeadline = (Get-Date).AddSeconds(90)
  while ((Get-Date) -lt $artifactDeadline) {
    try {
      $artResp = Invoke-JsonApi -Method GET -Uri "http://127.0.0.1:3001/api/backtest/runs/$($probeResp.runId)/artifacts" -TimeoutSec 30
      if ($artResp.available.manifest -and $artResp.available.evidence -and $artResp.available.report -and $artResp.available.csv) { break }
    } catch {
      # transient 404 while artifacts are being finalized
    }

    # Fallback: artifacts endpoint may lag while status already has evidenceRunId.
    try {
      $statusNow = Invoke-JsonApi -Method GET -Uri "http://127.0.0.1:3001/api/backtest/runs/$($probeResp.runId)" -TimeoutSec 30
      $ev = [string]$statusNow.evidenceRunId
      if (-not [string]::IsNullOrWhiteSpace($ev)) {
        $base = Join-Path (Get-Location) ".jarvis-cache\backtest-runs\$ev"
        $manifestPath = Join-Path $base "manifest.json"
        $evidencePath = Join-Path $base "evidence.json"
        $reportPath = Join-Path $base "report.md"
        $csvPath = Join-Path $base "trades.csv"
        if ((Test-Path $manifestPath) -and (Test-Path $evidencePath) -and (Test-Path $reportPath) -and (Test-Path $csvPath)) {
          $artResp = [ordered]@{
            available = [ordered]@{
              manifest = $true
              evidence = $true
              report = $true
              csv = $true
            }
          }
          break
        }
      }
    } catch {
      # best effort only
    }
    Start-Sleep -Seconds 3
  }
  if ($null -eq $artResp) { throw "GET /api/backtest/runs/:runId/artifacts failed in preflight window" }
  if (-not $artResp.available.manifest) { throw "Artifact manifest missing in preflight" }
  if (-not $artResp.available.evidence) { throw "Artifact evidence missing in preflight" }
  if (-not $artResp.available.report) { throw "Artifact report missing in preflight" }
  if (-not $artResp.available.csv) { throw "Artifact csv missing in preflight" }
}

function Run-Smoke {
  param([hashtable]$State, [string]$StrategyId)
  Write-Log "Phase B: smoke run on $StrategyId"
  $entry = Get-EntryByStrategyId -State $State -StrategyId $StrategyId
  if ($null -eq $entry) { throw "Smoke strategy missing: $StrategyId" }
  $res = Invoke-StrategyWithRetries -State $State -Entry $entry -MaxTokens 10 -DataScale "fast" -Mode "quick"
  if (-not $res.ok) {
    throw "Smoke failed: $($res.error)"
  }
}

Write-Log "== Jarvis Sniper GSD Campaign Runner =="
Write-Log "CampaignId=$CampaignId"
Write-Log "StatePath=$statePath"
Write-Log "DocsOut=$docsOut"

$state = $null
if ($Resume) {
  $state = Load-Json -Path $statePath
  if ($null -eq $state) {
    Write-Log "Resume requested but no state found. Creating new campaign." "WARN"
  } else {
    Write-Log "Resumed campaign state from disk"
  }
}
if ($null -eq $state) {
  $strategies = Get-StrategyMapFromRoute
  if ($StrategyIds.Count -gt 0) {
    $allow = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($sid in $StrategyIds) {
      if (-not [string]::IsNullOrWhiteSpace($sid)) {
        [void]$allow.Add($sid.Trim())
      }
    }
    $strategies = @($strategies | Where-Object { $allow.Contains([string]$_.strategyId) })
    if ($strategies.Count -eq 0) {
      throw "No strategies matched -StrategyIds: $($StrategyIds -join ', ')"
    }
  }
  if ($MaxStrategies -gt 0 -and $strategies.Count -gt $MaxStrategies) {
    $strategies = @($strategies | Select-Object -First $MaxStrategies)
  }
  $state = New-CampaignState -Strategies $strategies
  Save-State -State $state
}

# Backward-compatible hydration for old campaign-state schema.
if ("insufficiencyAttemptsByStrategy" -notin @($state.Keys)) { $state.insufficiencyAttemptsByStrategy = @{} }
if ("familyPasses" -notin @($state.Keys)) { $state.familyPasses = @{} }
if ("datasetManifestByFamily" -notin @($state.Keys)) { $state.datasetManifestByFamily = @{} }
if ("runtimeByRunIdSec" -notin @($state.Keys)) { $state.runtimeByRunIdSec = @{} }
if ("telemetry" -notin @($state.Keys) -or $null -eq $state.telemetry) { $state.telemetry = @{} }
if ("timeoutRuns" -notin @($state.telemetry.Keys)) { $state.telemetry.timeoutRuns = 0 }
if ("stalledRuns" -notin @($state.telemetry.Keys)) { $state.telemetry.stalledRuns = 0 }
if ("transientRetries" -notin @($state.telemetry.Keys)) { $state.telemetry.transientRetries = 0 }
if ("transientRetrySuccess" -notin @($state.telemetry.Keys)) { $state.telemetry.transientRetrySuccess = 0 }
if ("statusPolls" -notin @($state.telemetry.Keys)) { $state.telemetry.statusPolls = 0 }
if ("statusPollErrors" -notin @($state.telemetry.Keys)) { $state.telemetry.statusPollErrors = 0 }
if ("statusLatencyTotalMs" -notin @($state.telemetry.Keys)) { $state.telemetry.statusLatencyTotalMs = 0 }
if ("statusLatencyMaxMs" -notin @($state.telemetry.Keys)) { $state.telemetry.statusLatencyMaxMs = 0 }
if ("completionRatio" -notin @($state.telemetry.Keys)) { $state.telemetry.completionRatio = 0.0 }
if ("degradedCompletionRatio" -notin @($state.telemetry.Keys)) { $state.telemetry.degradedCompletionRatio = 0.0 }

try {
  $state.phase = "preflight"; Save-State -State $state
  Run-Preflight
  Write-Log "Preflight passed"

  $state.phase = "smoke"; Save-State -State $state
  $smokeStrategyId = if (@($state.strategies).Count -gt 0) { [string]$state.strategies[0].strategyId } else { "bluechip_trend_follow" }
  Run-Smoke -State $state -StrategyId $smokeStrategyId
  Write-Log "Smoke passed"

  # Phase C: baseline chunked (fast)
  $state.phase = "baseline"; Save-State -State $state
  foreach ($entry in $state.strategies) {
    if ([int]$entry.achievedTrades -ge $TargetTradesPerStrategy) { continue }
    $baselineMaxTokens = Get-FamilyBaselineMaxTokens -Family ([string]$entry.family)
    $res = Invoke-StrategyWithRetries -State $state -Entry $entry -MaxTokens $baselineMaxTokens -DataScale "fast" -Mode "quick"
    if (-not $res.ok) {
      Mark-Insufficient -State $state -StrategyId $entry.strategyId -Reason "Baseline failed after retries"
      Save-State -State $state
    }
  }

  # Phase D: expansion loop
  $state.phase = "expansion"; Save-State -State $state
  foreach ($entry in $state.strategies) {
    if ([int]$entry.achievedTrades -ge $TargetTradesPerStrategy) { continue }
    $familyLadder = @(Get-FamilyExpansionLadder -Family ([string]$entry.family))
    if ($familyLadder.Count -eq 0) { $familyLadder = $ExpansionLadder }

    foreach ($tokens in $familyLadder) {
      if ([int]$entry.achievedTrades -ge $TargetTradesPerStrategy) { break }
      if ($tokens -le $familyLadder[0]) { continue } # baseline already handled
      $res = Invoke-StrategyWithRetries -State $state -Entry $entry -MaxTokens $tokens -DataScale "thorough" -Mode "quick"
      if (-not $res.ok) {
        Write-Log "Expansion failed for $($entry.strategyId) at maxTokens=$tokens ($($res.error))" "WARN"
      }
    }

    if ([int]$entry.achievedTrades -lt $TargetTradesPerStrategy) {
      Mark-Insufficient -State $state -StrategyId $entry.strategyId -Reason "Could not reach 5000 trades after expansion ladder"
      Save-State -State $state
    }
  }

  # Phase E: optimization (grid) for sufficiently covered strategies
  if (-not $SkipOptimization) {
    $state.phase = "optimization"; Save-State -State $state
    if ("optimizationBest" -notin @($state.Keys)) { $state.optimizationBest = @{} }
    foreach ($entry in $state.strategies) {
      if ([int]$entry.achievedTrades -lt 500) { continue } # skip extremely data-poor candidates
      $res = Invoke-StrategyWithRetries -State $state -Entry $entry -MaxTokens 120 -DataScale "thorough" -Mode "grid"
      if (-not $res.ok) { continue }
      $full = @($res.response.fullResults | Where-Object { $_.strategyId -eq $entry.strategyId })
      if ($full.Count -eq 0) { continue }
      $top = $full | Sort-Object -Property @{Expression = { To-Num $_.expectancy 0 }; Descending = $true}, @{Expression = { To-Num $_.profitFactor 0 }; Descending = $true} | Select-Object -First 1
      $state.optimizationBest[$entry.strategyId] = [ordered]@{
        runId = $res.runId
        config = $top.config
        expectancy = To-Num $top.expectancy 0
        executionAdjustedExpectancy = To-Num $res.response.executionAdjustedExpectancy (To-Num $top.expectancy 0)
        executionAdjustedNetPnlPct = To-Num $res.response.executionAdjustedNetPnlPct 0
        executionReliabilityPct = To-Num $res.response.executionReliabilityPct 0
        profitFactor = To-Num $top.profitFactor 0
        winRate = To-Num $top.winRate 0
        maxDrawdownPct = To-Num $top.maxDrawdownPct 100
        trades = [int](To-Num $top.totalTrades 0)
        degraded = [bool]$res.response.degraded
      }
      Save-State -State $state
    }
  }

  # Phase F: promotion
  $state.phase = "promotion"; Save-State -State $state
  foreach ($entry in $state.strategies) {
    # Prefer best optimization metrics; fallback to most recent quick run metric
    $metric = $null
    if (("optimizationBest" -in @($state.Keys)) -and ($entry.strategyId -in @($state.optimizationBest.Keys))) {
      $opt = $state.optimizationBest[$entry.strategyId]
      $metric = [ordered]@{
        trades = [int](To-Num $entry.achievedTrades 0)
        winRate = To-Num $opt.winRate 0
        expectancy = To-Num $opt.executionAdjustedExpectancy (To-Num $opt.expectancy 0)
        profitFactor = To-Num $opt.profitFactor 0
        maxDrawdownPct = To-Num $opt.maxDrawdownPct 100
        executionReliabilityPct = To-Num $opt.executionReliabilityPct 0
      }
    } else {
      $runIds = @($state.runsByStrategy[$entry.strategyId])
      $candidate = $null
      $reversed = @($runIds)
      [array]::Reverse($reversed)
      foreach ($rid in $reversed) {
        if ($rid -in @($state.runMetricsByRunId.Keys)) { $candidate = $state.runMetricsByRunId[$rid]; break }
      }
      if ($null -eq $candidate) { continue }
      $metric = [ordered]@{
        trades = [int](To-Num $entry.achievedTrades 0)
        winRate = To-Num $candidate.winRate 0
        expectancy = To-Num $candidate.executionAdjustedExpectancy (To-Num $candidate.expectancy 0)
        profitFactor = To-Num $candidate.profitFactor 0
        maxDrawdownPct = To-Num $candidate.maxDrawdownPct 100
        executionReliabilityPct = To-Num $candidate.executionReliabilityPct 0
      }
    }

    $decision = Evaluate-Promotion -Metric $metric -Family ([string]$entry.family)
    $entry.promoted = [bool]$decision.promoted
    $entry.promotionReason = [string]$decision.reason
    if (-not $entry.promoted -and [string]::IsNullOrWhiteSpace([string]$entry.insufficiencyReason)) {
      $entry.insufficiencyReason = [string]$decision.reason
    }
    Save-State -State $state
  }

  # Phase G: audit + publish
  $state.phase = "audit"; Save-State -State $state
  Write-Log "Audit complete: completed=$($state.completedRunIds.Count), failed=$($state.failedRunIds.Count), insufficient=$($state.insufficientStrategies.Count)"
  $completedRuns = @($state.completedRunIds).Count
  $failedRuns = @($state.failedRunIds).Count
  $attemptedRuns = $completedRuns + $failedRuns
  $completionRatio = if ($attemptedRuns -gt 0) { $completedRuns / [double]$attemptedRuns } else { 0.0 }
  $degradedCompletionRatio = if ($attemptedRuns -gt 0) { $failedRuns / [double]$attemptedRuns } else { 1.0 }
  $state.telemetry.completionRatio = [math]::Round($completionRatio, 4)
  $state.telemetry.degradedCompletionRatio = [math]::Round($degradedCompletionRatio, 4)
  $polls = [int](To-Num $state.telemetry.statusPolls 0)
  $latTotal = [int](To-Num $state.telemetry.statusLatencyTotalMs 0)
  $latAvg = if ($polls -gt 0) { [math]::Round($latTotal / [double]$polls, 2) } else { 0.0 }
  $latMax = [int](To-Num $state.telemetry.statusLatencyMaxMs 0)
  Write-Log "Telemetry: timeouts=$([int](To-Num $state.telemetry.timeoutRuns 0)) stalled=$([int](To-Num $state.telemetry.stalledRuns 0)) transientRetries=$([int](To-Num $state.telemetry.transientRetries 0)) retrySuccess=$([int](To-Num $state.telemetry.transientRetrySuccess 0)) statusLatency(avg/max)=${latAvg}ms/${latMax}ms completionRatio=$([math]::Round($completionRatio * 100, 2))% degradedRatio=$([math]::Round($degradedCompletionRatio * 100, 2))%"
  Save-State -State $state

  $degradedPublishThreshold = 0.35
  $skipPublishForDegraded = $degradedCompletionRatio -gt $degradedPublishThreshold
  if (-not $SkipPublish) {
    if ($skipPublishForDegraded) {
      Write-Log "Skipping publish: degraded completion ratio $([math]::Round($degradedCompletionRatio * 100, 2))% exceeded threshold $([math]::Round($degradedPublishThreshold * 100, 2))%" "WARN"
    } else {
      Write-Log "Publishing campaign artifacts to docs/backtests/$CampaignId"
      & powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\publish-backtest-campaign.ps1" -CampaignId $CampaignId
    }
  }

  $state.phase = "done"; Save-State -State $state
  Write-Log "Campaign complete. State: $statePath"
  Write-Log "Docs output: $docsOut"
} catch {
  Write-Log "Fatal campaign failure: $($_.Exception.Message)" "ERROR"
  $state.phase = "failed"
  Save-State -State $state
  throw
}
