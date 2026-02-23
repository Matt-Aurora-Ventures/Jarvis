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

$status = [ordered]@{
    runtime_dir = $runtimeDir
    watchdog_running = $false
    watchdog_pid = $null
    runner_running = $false
    runner_pid = $null
    stop_flag_present = (Test-Path $stopFile)
    watchdog_log = (Join-Path $runtimeDir "watchdog.log")
}

$watchdogProc = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like "python*" -and
    $_.CommandLine -match "scripts[\\/]+ralph_wiggum_watchdog\.py" -and
    $_.CommandLine -match $runtimePattern
} | Select-Object -First 1

if ($watchdogProc) {
    $status.watchdog_running = $true
    $status.watchdog_pid = [int]$watchdogProc.ProcessId
} elseif (Test-Path $watchdogPidFile) {
    $watchdogPidValue = Get-Content $watchdogPidFile -ErrorAction SilentlyContinue
    if ($watchdogPidValue) {
        $proc = Get-Process -Id $watchdogPidValue -ErrorAction SilentlyContinue
        if ($proc) {
            $status.watchdog_running = $true
            $status.watchdog_pid = [int]$watchdogPidValue
        }
    }
}

$runnerLock = Join-Path $runtimeDir "runner.lock"
$runnerLockPattern = [regex]::Escape($runnerLock)
$runnerProc = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like "python*" -and
    $_.CommandLine -match "core\.jupiter_perps\.runner" -and
    ($_.CommandLine -match $runnerLockPattern -or $_.CommandLine -match $runtimePattern)
} | Select-Object -First 1

if ($runnerProc) {
    $status.runner_running = $true
    $status.runner_pid = [int]$runnerProc.ProcessId
} elseif (Test-Path $runnerPidFile) {
    $runnerPidValue = Get-Content $runnerPidFile -ErrorAction SilentlyContinue
    if ($runnerPidValue) {
        $proc = Get-Process -Id $runnerPidValue -ErrorAction SilentlyContinue
        if ($proc) {
            $status.runner_running = $true
            $status.runner_pid = [int]$runnerPidValue
        }
    }
}

$status | ConvertTo-Json -Depth 3
