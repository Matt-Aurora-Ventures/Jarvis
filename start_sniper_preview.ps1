param(
  [int]$Port = 3011
)

$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$desktopDir = Split-Path $repoRoot -Parent
$sourceDir = Join-Path $repoRoot "jarvis-sniper"
$previewDir = Join-Path $desktopDir "Jarvis-preview\jarvis-sniper"
$logsDir = Join-Path $repoRoot "logs"
$logFileName = "sniper_preview_$Port.log"
$pidFileName = "sniper_preview_$Port.pid"
$logPath = Join-Path $logsDir $logFileName
$pidPath = Join-Path $logsDir $pidFileName

function Get-ListenPid([int]$TargetPort) {
  $conn = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue
  if ($null -eq $conn) { return $null }
  return [int]$conn.OwningProcess
}

function Test-ProcessRunning([int]$ProcessId) {
  if ($ProcessId -le 0) { return $false }
  return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

$activePid = Get-ListenPid -TargetPort $Port
if ($activePid) {
  Write-Host "[INFO] Preview already listening on port $Port (PID $activePid)." -ForegroundColor Yellow
  Set-Content -Path $pidPath -Value $activePid -Encoding ascii
  Write-Host "[INFO] URL: http://127.0.0.1:$Port"
  Write-Host "[INFO] Log: $logPath"
  exit 0
}

Write-Host "[INFO] Syncing jarvis-sniper to preview copy..." -ForegroundColor Cyan
$robocopyArgs = @(
  $sourceDir,
  $previewDir,
  "/MIR",
  "/XD", "node_modules", ".next", ".runtime", ".git",
  "/XF", "npm-debug.log", "yarn-error.log"
)
& robocopy @robocopyArgs | Out-Null
$robocopyExit = $LASTEXITCODE
if ($robocopyExit -gt 3) {
  throw "robocopy failed with exit code $robocopyExit"
}

if (-not (Test-Path (Join-Path $previewDir "package.json"))) {
  throw "Preview directory does not contain package.json: $previewDir"
}

if (-not (Test-Path (Join-Path $previewDir "node_modules"))) {
  Write-Host "[INFO] Installing npm dependencies in preview copy..." -ForegroundColor Cyan
  & npm install --prefix $previewDir
  if ($LASTEXITCODE -ne 0) {
    throw "npm install failed in preview copy"
  }
}

if (Test-Path $logPath) {
  try {
    Remove-Item -Force $logPath -ErrorAction Stop
  } catch {
    $fallbackLogName = "sniper_preview_${Port}_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date)
    $logPath = Join-Path $logsDir $fallbackLogName
    Write-Host "[WARN] Existing log is locked, using $logPath" -ForegroundColor Yellow
  }
}

Write-Host "[INFO] Starting preview on http://127.0.0.1:$Port ..." -ForegroundColor Green
$cmd = "npx next dev --webpack --port $Port --hostname 127.0.0.1 > `"$logPath`" 2>&1"
$proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -WorkingDirectory $previewDir -PassThru

if ($null -eq $proc -or $proc.Id -le 0) {
  throw "Failed to start preview process"
}

Set-Content -Path $pidPath -Value $proc.Id -Encoding ascii

$timeoutSeconds = 35
$ready = $false
for ($i = 0; $i -lt $timeoutSeconds; $i++) {
  Start-Sleep -Seconds 1
  if (-not (Test-ProcessRunning -ProcessId $proc.Id)) {
    break
  }
  $listenPid = Get-ListenPid -TargetPort $Port
  if ($listenPid) {
    $ready = $true
    break
  }
}

if (-not $ready) {
  Write-Host "[ERROR] Preview failed to bind port $Port." -ForegroundColor Red
  if (Test-Path $logPath) {
    Write-Host "[ERROR] Tail of ${logPath}:" -ForegroundColor Red
    Get-Content -Path $logPath -Tail 80
  }
  if (Test-ProcessRunning -ProcessId $proc.Id) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
  }
  exit 1
}

$listenPid = Get-ListenPid -TargetPort $Port
Set-Content -Path $pidPath -Value $listenPid -Encoding ascii

Write-Host "[OK] Preview is running." -ForegroundColor Green
Write-Host "[OK] URL: http://127.0.0.1:$Port"
Write-Host "[OK] PID: $listenPid"
Write-Host "[OK] Log: $logPath"
