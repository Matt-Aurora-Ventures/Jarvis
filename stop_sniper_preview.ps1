param(
  [int]$Port = 3011
)

$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$logsDir = Join-Path $repoRoot "logs"
$pidPath = Join-Path $logsDir "sniper_preview_$Port.pid"

function Get-ListenPid([int]$TargetPort) {
  $conn = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue
  if ($null -eq $conn) { return $null }
  return [int]$conn.OwningProcess
}

function Stop-IfRunning([int]$ProcessId) {
  if ($ProcessId -le 0) { return }
  $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
  if ($null -ne $proc) {
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "[INFO] Stopped PID $ProcessId" -ForegroundColor Yellow
  }
}

$pidFromFile = $null
if (Test-Path $pidPath) {
  $raw = (Get-Content -Path $pidPath -Raw).Trim()
  if ($raw -match '^\d+$') {
    $pidFromFile = [int]$raw
  }
}

if ($pidFromFile) {
  Stop-IfRunning -ProcessId $pidFromFile
}

$listenPid = Get-ListenPid -TargetPort $Port
if ($listenPid) {
  Write-Host "[INFO] Port $Port still has listener PID $listenPid; stopping it." -ForegroundColor Yellow
  Stop-IfRunning -ProcessId $listenPid
}

Start-Sleep -Milliseconds 400
$postPid = Get-ListenPid -TargetPort $Port
if ($postPid) {
  Write-Host "[ERROR] Port $Port is still listening (PID $postPid)." -ForegroundColor Red
  exit 1
}

if (Test-Path $pidPath) {
  Remove-Item -Force $pidPath
}

Write-Host "[OK] Preview stopped. Port $Port is free." -ForegroundColor Green
exit 0
