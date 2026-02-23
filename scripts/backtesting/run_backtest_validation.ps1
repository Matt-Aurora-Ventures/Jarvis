param(
  [switch]$Strict
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$ArtifactsDir = Join-Path $RepoRoot "artifacts\backtest_validation"
$CompareDir = Join-Path $RepoRoot "artifacts\backtest_compare"

New-Item -ItemType Directory -Path $ArtifactsDir -Force | Out-Null
New-Item -ItemType Directory -Path $CompareDir -Force | Out-Null

Push-Location $RepoRoot
try {
  $contractMode = if ($Strict) { "--strict" } else { "--warning" }
  python "scripts/backtesting/validate_backtest_contract.py" $contractMode
  if ($LASTEXITCODE -ne 0 -and $Strict) {
    throw "Backtest contract validation failed in strict mode."
  }

  $commands = @(
    @{
      Name = "python_backtest_suite"
      Command = "python -m pytest tests/backtesting/test_backtest.py -q"
    },
    @{
      Name = "jarvis_sniper_backtest_suite"
      Command = "npm --prefix jarvis-sniper run test -- src/__tests__/bags-backtest-api.test.ts src/__tests__/backtest-route-execution-realism.test.ts src/__tests__/backtest-campaign-orchestrator.test.ts"
    }
  )

  $results = @()
  foreach ($entry in $commands) {
    $name = $entry.Name
    $command = $entry.Command
    Write-Host "[backtest-validation] running: $name"
    Write-Host "[backtest-validation] command: $command"

    & powershell -NoProfile -Command $command
    $exitCode = $LASTEXITCODE
    $status = if ($exitCode -eq 0) { "pass" } else { "fail" }
    $results += [PSCustomObject]@{
      name = $name
      command = $command
      exit_code = $exitCode
      status = $status
    }

    if ($exitCode -ne 0 -and $Strict) {
      throw "Command failed in strict mode: $name"
    }
  }

  $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
  $reportPath = Join-Path $ArtifactsDir ("run_summary_" + $timestamp + ".json")
  $overall = if (($results | Where-Object { $_.status -eq "fail" }).Count -eq 0) { "pass" } else { "warn" }
  $report = [PSCustomObject]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    strict_mode = [bool]$Strict
    overall_status = $overall
    commands = $results
  }
  $report | ConvertTo-Json -Depth 5 | Set-Content -Path $reportPath -Encoding UTF8

  $latestPath = Join-Path $CompareDir "latest_run.json"
  $report | ConvertTo-Json -Depth 5 | Set-Content -Path $latestPath -Encoding UTF8

  if ($overall -eq "warn") {
    Write-Warning "Backtest validation completed with warnings (non-strict mode)."
  } else {
    Write-Host "[backtest-validation] all commands passed."
  }
}
finally {
  Pop-Location
}
