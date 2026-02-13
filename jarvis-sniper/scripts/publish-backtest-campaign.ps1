param(
  [Parameter(Mandatory = $true)][string]$CampaignId
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

Set-Location "c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\jarvis-sniper"

$statePath = Join-Path (Get-Location) ".jarvis-cache\backtest-campaign\$CampaignId\campaign-state.json"
if (-not (Test-Path $statePath)) {
  throw "Campaign state not found: $statePath"
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

function Load-JsonCompat {
  param([string]$Path)
  $raw = Get-Content -Path $Path -Raw
  $parsed = $null
  try {
    $parsed = $raw | ConvertFrom-Json -AsHashtable
  } catch {
    $parsed = $raw | ConvertFrom-Json
  }
  return (ConvertTo-HashtableDeep -InputObject $parsed)
}

$state = Load-JsonCompat -Path $statePath
$outDir = Join-Path (Get-Location) "docs\backtests\$CampaignId"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

$summaryPath = Join-Path $outDir "CAMPAIGN_SUMMARY.md"
$scoreboardPath = Join-Path $outDir "STRATEGY_SCOREBOARD.csv"
$promotedPath = Join-Path $outDir "PROMOTED_PARAMS.json"
$insufficientPath = Join-Path $outDir "INSUFFICIENCY_REPORT.md"
$approachFailurePath = Join-Path $outDir "APPROACH_FAILURE_LOG.md"
$artifactIndexPath = Join-Path $outDir "ARTIFACT_INDEX.md"

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

function LatestMetricForStrategy {
  param(
    [hashtable]$State,
    [string]$StrategyId
  )
  $runIds = @()
  if ($State.runsByStrategy.ContainsKey($StrategyId)) {
    $runIds = @($State.runsByStrategy[$StrategyId])
  }
  if ($runIds.Count -eq 0) { return $null }
  $rid = $runIds[$runIds.Count - 1]
  if (-not $State.runMetricsByRunId.ContainsKey($rid)) { return $null }
  return $State.runMetricsByRunId[$rid]
}

function AbsOrRaw {
  param([string]$Path)
  if ([string]::IsNullOrWhiteSpace($Path)) { return "" }
  try {
    $resolved = Resolve-Path -Path $Path -ErrorAction Stop
    return [string]$resolved.Path
  } catch {
    return [string]$Path
  }
}

function Get-GatePasses {
  param(
    [hashtable]$StrategyEntry,
    [hashtable]$Metric
  )
  $family = [string]$StrategyEntry.family
  $trades = [int](To-Num $StrategyEntry.achievedTrades 0)
  $expectancy = To-Num $Metric.expectancy 0
  $pf = To-Num $Metric.profitFactor 0
  $dd = To-Num $Metric.maxDrawdownPct 100
  $wr = To-Num $Metric.winRate 0
  $ddGate = if ($family -in @('memecoin', 'bags')) { 45 } else { 30 }
  $wrGate = if ($family -in @('memecoin', 'bags')) { 0.40 } else { 0.45 }
  return [ordered]@{
    trades = $trades -ge 5000
    expectancy = $expectancy -gt 0
    profitFactor = $pf -ge 1.05
    maxDrawdown = $dd -le $ddGate
    winRate = $wr -ge $wrGate
  }
}

# Scoreboard
$rows = @()
foreach ($s in $state.strategies) {
  $m = LatestMetricForStrategy -State $state -StrategyId ([string]$s.strategyId)
  $rows += [pscustomobject]@{
    strategyId = $s.strategyId
    family = $s.family
    targetTrades = $s.targetTrades
    achievedTrades = $s.achievedTrades
    cumulativeTrades = $s.cumulativeTrades
    promoted = $s.promoted
    promotionReason = $s.promotionReason
    insufficiencyReason = $s.insufficiencyReason
    winRate = if ($null -eq $m) { "" } else { [math]::Round((To-Num $m.winRate 0) * 100, 2).ToString() + "%" }
    expectancy = if ($null -eq $m) { "" } else { [math]::Round((To-Num $m.expectancy 0), 6) }
    profitFactor = if ($null -eq $m) { "" } else { [math]::Round((To-Num $m.profitFactor 0), 6) }
    maxDrawdownPct = if ($null -eq $m) { "" } else { [math]::Round((To-Num $m.maxDrawdownPct 0), 4) }
    netPnl = if ($null -eq $m) { "" } else { [math]::Round((To-Num $m.netPnl 0), 6) }
  }
}
$rows | Export-Csv -Path $scoreboardPath -NoTypeInformation -Encoding UTF8

# Promoted params
$promoted = @()
foreach ($s in $state.strategies) {
  if (-not $s.promoted) { continue }
  $sid = [string]$s.strategyId
  $cfg = $null
  $compositeScore = $null
  $promotedFromRunId = $null
  if ($state.ContainsKey("optimizationBest") -and $state.optimizationBest.ContainsKey($sid)) {
    $cfg = $state.optimizationBest[$sid].config
    $compositeScore = if ($state.optimizationBest[$sid].ContainsKey('compositeScore')) { To-Num $state.optimizationBest[$sid].compositeScore $null } else { $null }
    $promotedFromRunId = [string]$state.optimizationBest[$sid].runId
  } elseif ($state.ContainsKey("runMetricsByRunId") -and $state.ContainsKey("runsByStrategy")) {
    $runIds = @($state.runsByStrategy[$sid])
    if ($runIds.Count -gt 0) { $promotedFromRunId = [string]$runIds[$runIds.Count - 1] }
  }
  $metric = LatestMetricForStrategy -State $state -StrategyId $sid
  if ($null -eq $metric) { $metric = @{} }
  $gatePasses = Get-GatePasses -StrategyEntry $s -Metric $metric
  $evidenceRunIds = @()
  if ($state.ContainsKey("runsByStrategy") -and $state.runsByStrategy.ContainsKey($sid)) {
    $evidenceRunIds = @($state.runsByStrategy[$sid])
  }
  $oldParams = $null
  if ($state.ContainsKey('seedParamsByStrategy') -and $state.seedParamsByStrategy.ContainsKey($sid)) {
    $oldParams = $state.seedParamsByStrategy[$sid]
  }

  $promoted += [ordered]@{
    strategyId = $sid
    family = $s.family
    oldParams = $oldParams
    newParams = $cfg
    evidenceRunIds = $evidenceRunIds
    compositeScore = $compositeScore
    gatePasses = $gatePasses
    promotedAt = (Get-Date -Format o)
    promotedFromRunId = $promotedFromRunId
    promotionReason = [string]$s.promotionReason
  }
}
$promoted | ConvertTo-Json -Depth 20 | Set-Content -Path $promotedPath -Encoding UTF8

# Insufficiency report
$ins = @()
$ins += "# Insufficiency Report - $CampaignId"
$ins += ""
$ins += "Generated: $(Get-Date -Format o)"
$ins += ""
$ins += "| Strategy | Family | Achieved Trades | Reason |"
$ins += "|---|---:|---:|---|"
foreach ($s in $state.strategies) {
  if ([string]::IsNullOrWhiteSpace([string]$s.insufficiencyReason)) { continue }
  $ins += "| $($s.strategyId) | $($s.family) | $($s.achievedTrades) | $($s.insufficiencyReason) |"
}
$ins -join "`r`n" | Set-Content -Path $insufficientPath -Encoding UTF8

# Summary report (locked format)
$passedCount = @($state.strategies | Where-Object { $_.promoted }).Count
$failedCount = @($state.strategies | Where-Object { -not $_.promoted }).Count
$artifactLines = @()
foreach ($a in $state.artifactIndex) {
  $manifest = AbsOrRaw -Path ([string]$a.manifestPath)
  $evidence = AbsOrRaw -Path ([string]$a.evidencePath)
  $report = AbsOrRaw -Path ([string]$a.reportPath)
  $trades = AbsOrRaw -Path ([string]$a.tradesCsvPath)
  $artifactLines += "- Run `$($a.runId)` (`$($a.evidenceRunId)`):"
  $artifactLines += "  - $manifest"
  $artifactLines += "  - $evidence"
  $artifactLines += "  - $report"
  $artifactLines += "  - $trades"
}

$summary = @()
$summary += "# Backtest Campaign Summary - $CampaignId"
$summary += ""
$summary += "Generated: $(Get-Date -Format o)"
$summary += ""
$summary += "## What passed"
$summary += "- Promoted strategies: **$passedCount**"
$summary += "- Completed runs: **$($state.completedRunIds.Count)**"
$summary += "- Evidence artifacts indexed: **$($state.artifactIndex.Count)**"
$summary += ""
$summary += "## What failed and why"
$summary += "- Non-promoted strategies: **$failedCount**"
foreach ($s in $state.strategies | Where-Object { -not $_.promoted }) {
  $reason = if ([string]::IsNullOrWhiteSpace([string]$s.insufficiencyReason)) { $s.promotionReason } else { $s.insufficiencyReason }
  $summary += "- `$($s.strategyId)`: $reason"
}
$summary += ""
$summary += "## Promoted strategies and params"
if ($promoted.Count -eq 0) {
  $summary += "- None promoted in this campaign."
} else {
  foreach ($p in $promoted) {
    $summary += "- `$($p.strategyId)` ($($p.family)): $($p.promotionReason)"
  }
}
$summary += ""
$summary += "## Artifact index with absolute paths"
if ($artifactLines.Count -eq 0) {
  $summary += "- No artifacts indexed."
} else {
  $summary += $artifactLines
}
$summary += ""
$summary += "## Next actions if insufficiencies remain"
$remaining = @($state.strategies | Where-Object { [int]$_.achievedTrades -lt [int]$_.targetTrades }).Count
if ($remaining -eq 0) {
  $summary += "- No insufficiencies remain. Proceed to parameter integration and live validation."
} else {
  $summary += "- Strategies below target trades: **$remaining**"
  $summary += "- Re-run expansion ladder for insufficient strategies with tighter chunking and source fallback matrix."
  $summary += "- Validate promoted configs on out-of-sample cohorts before deployment."
}

$summary -join "`r`n" | Set-Content -Path $summaryPath -Encoding UTF8

# Approach failure log
$failure = @()
$failure += "# Approach Failure Log - $CampaignId"
$failure += ""
$failure += "Generated: $(Get-Date -Format o)"
$failure += ""
$failure += "| RunId | Strategy | Source Policy | Mode | Max Tokens | Status | Error | Ended At |"
$failure += "|---|---|---|---|---:|---|---|---|"
foreach ($runId in @($state.attemptsByRunId.Keys | Sort-Object)) {
  $a = $state.attemptsByRunId[$runId]
  if ([string]$a.status -eq "completed") { continue }
  $failure += "| $runId | $($a.strategyId) | $($a.sourcePolicy) | $($a.mode) | $($a.maxTokens) | $($a.status) | $(([string]$a.error).Replace('|','/')) | $($a.endedAt) |"
}
$failure -join "`r`n" | Set-Content -Path $approachFailurePath -Encoding UTF8

# Artifact index (absolute paths)
$artifactMd = @()
$artifactMd += "# Artifact Index - $CampaignId"
$artifactMd += ""
$artifactMd += "Generated: $(Get-Date -Format o)"
$artifactMd += ""
if (@($state.artifactIndex).Count -eq 0) {
  $artifactMd += "- No artifact entries."
} else {
  foreach ($a in $state.artifactIndex) {
    $artifactMd += "## Run $($a.runId) (evidence $($a.evidenceRunId))"
    $artifactMd += "- Manifest: $(AbsOrRaw -Path ([string]$a.manifestPath))"
    $artifactMd += "- Evidence: $(AbsOrRaw -Path ([string]$a.evidencePath))"
    $artifactMd += "- Report: $(AbsOrRaw -Path ([string]$a.reportPath))"
    $artifactMd += "- Trades CSV: $(AbsOrRaw -Path ([string]$a.tradesCsvPath))"
    $artifactMd += ""
  }
}
$artifactMd -join "`r`n" | Set-Content -Path $artifactIndexPath -Encoding UTF8

Write-Host "Published campaign outputs to $outDir"
Write-Host "- $summaryPath"
Write-Host "- $scoreboardPath"
Write-Host "- $promotedPath"
Write-Host "- $insufficientPath"
Write-Host "- $approachFailurePath"
Write-Host "- $artifactIndexPath"
