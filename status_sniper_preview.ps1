param(
  [int]$Port = 3011
)

$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$logsDir = Join-Path $repoRoot "logs"
$logPath = Join-Path $logsDir "sniper_preview_$Port.log"
$pidPath = Join-Path $logsDir "sniper_preview_$Port.pid"

if (-not (Test-Path $logPath)) {
  $latest = Get-ChildItem -Path $logsDir -Filter "sniper_preview_${Port}*.log" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if ($latest) {
    $logPath = $latest.FullName
  }
}

function Get-ListenPid([int]$TargetPort) {
  $conn = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue
  if ($null -eq $conn) { return $null }
  return [int]$conn.OwningProcess
}

function Test-ProcessRunning([int]$ProcessId) {
  if ($ProcessId -le 0) { return $false }
  return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

$pidFromFile = $null
if (Test-Path $pidPath) {
  $raw = (Get-Content -Path $pidPath -Raw).Trim()
  if ($raw -match '^\d+$') {
    $pidFromFile = [int]$raw
  }
}

$listenPid = Get-ListenPid -TargetPort $Port

Write-Host "Preview Status"
Write-Host "-------------"
Write-Host "Port: $Port"
Write-Host "URL:  http://127.0.0.1:$Port"
Write-Host "PID file: $pidPath"
Write-Host "Log file: $logPath"
Write-Host ""

if ($listenPid) {
  Write-Host "[RUNNING] Port $Port is listening (PID $listenPid)." -ForegroundColor Green
  if ($pidFromFile -and $pidFromFile -ne $listenPid) {
    Write-Host "[WARN] PID file ($pidFromFile) differs from listener PID ($listenPid)." -ForegroundColor Yellow
  }
  exit 0
}

if ($pidFromFile -and (Test-ProcessRunning -ProcessId $pidFromFile)) {
  Write-Host "[STARTING/UNBOUND] Process $pidFromFile exists but port $Port is not listening." -ForegroundColor Yellow
  if (Test-Path $logPath) {
    Write-Host ""
    Write-Host "Log tail:"
    Get-Content -Path $logPath -Tail 40
  }
  exit 1
}

Write-Host "[STOPPED] Preview is not running." -ForegroundColor Red
if (Test-Path $logPath) {
  Write-Host ""
  Write-Host "Last log tail:"
  Get-Content -Path $logPath -Tail 30
}
exit 1
