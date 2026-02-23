$ErrorActionPreference = "Stop"

$runtimeDir = if ($env:JARVIS_RALPH_RUNTIME_DIR) {
    $env:JARVIS_RALPH_RUNTIME_DIR
} else {
    Join-Path $env:LOCALAPPDATA "Jarvis\ralph_wiggum"
}
$watchdogPidFile = Join-Path $runtimeDir "watchdog.pid"
$runnerPidFile = Join-Path $runtimeDir "runner.pid"
$stopFile = Join-Path $runtimeDir "watchdog.stop"
$runtimePattern = [regex]::Escape($runtimeDir)
$runnerLock = Join-Path $runtimeDir "runner.lock"
$runnerLockPattern = [regex]::Escape($runnerLock)

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
Set-Content -Path $stopFile -Value "stop" -Encoding utf8

$stopped = @()

if (Test-Path $runnerPidFile) {
    $runnerPid = Get-Content $runnerPidFile -ErrorAction SilentlyContinue
    if ($runnerPid) {
        $proc = Get-Process -Id $runnerPid -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $runnerPid -Force
            $stopped += "runner:$runnerPid"
        }
    }
    Remove-Item $runnerPidFile -Force -ErrorAction SilentlyContinue
}

if (Test-Path $watchdogPidFile) {
    $watchdogPid = Get-Content $watchdogPidFile -ErrorAction SilentlyContinue
    if ($watchdogPid) {
        $proc = Get-Process -Id $watchdogPid -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $watchdogPid -Force
            $stopped += "watchdog:$watchdogPid"
        }
    }
    Remove-Item $watchdogPidFile -Force -ErrorAction SilentlyContinue
}

# Sweep and stop any orphaned loop processes not tracked by PID files.
$leftovers = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like "python*" -and (
        ($_.CommandLine -match "core\.jupiter_perps\.runner" -and ($_.CommandLine -match $runnerLockPattern -or $_.CommandLine -match $runtimePattern)) -or
        ($_.CommandLine -match "scripts[\\/]+ralph_wiggum_parallel_loop\.py" -and $_.CommandLine -match $runtimePattern) -or
        ($_.CommandLine -match "scripts[\\/]+ralph_wiggum_watchdog\.py" -and $_.CommandLine -match $runtimePattern)
    )
}
foreach ($p in $leftovers) {
    if ($p.ProcessId -eq $PID) {
        continue
    }
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    $stopped += "leftover:$($p.ProcessId)"
}

Write-Output "Ralph Wiggum loop stop requested"
if ($stopped.Count -gt 0) {
    Write-Output ("Stopped: {0}" -f ($stopped -join ", "))
}
Write-Output ("Stop flag: {0}" -f $stopFile)
