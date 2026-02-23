$ErrorActionPreference = "Stop"

$repoRoot = (Get-Location).Path
$runtimeDir = if ($env:JARVIS_RALPH_RUNTIME_DIR) {
    $env:JARVIS_RALPH_RUNTIME_DIR
} else {
    Join-Path $env:LOCALAPPDATA "Jarvis\ralph_wiggum"
}
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

function Resolve-Python311 {
    if ($env:JARVIS_PYTHON_311) {
        if (-not (Test-Path $env:JARVIS_PYTHON_311)) {
            throw "JARVIS_PYTHON_311 is set but path does not exist: $env:JARVIS_PYTHON_311"
        }
        return $env:JARVIS_PYTHON_311
    }

    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $resolved = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolved) {
            return $resolved.Trim()
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return $pythonCmd.Source
    }

    throw "Unable to locate Python. Set JARVIS_PYTHON_311 to a Python 3.11 executable path."
}
$python = Resolve-Python311
$pythonMinor = & $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
if ($pythonMinor -ne "3.11") {
    throw "Resolved Python is not 3.11 ($pythonMinor). Set JARVIS_PYTHON_311 to a Python 3.11 executable."
}

if (-not $env:JARVIS_CORE_MINIMAL_IMPORTS) { $env:JARVIS_CORE_MINIMAL_IMPORTS = "1" }
if (-not $env:PERPS_AI_MODE) { $env:PERPS_AI_MODE = "disabled" }
if (-not $env:PERPS_ALLOW_LIVE_ON_ARM) { $env:PERPS_ALLOW_LIVE_ON_ARM = "1" }

$watchdogPidFile = Join-Path $runtimeDir "watchdog.pid"
$stopFile = Join-Path $runtimeDir "watchdog.stop"
$stdoutLog = Join-Path $runtimeDir "watchdog_stdout.log"
$stderrLog = Join-Path $runtimeDir "watchdog_stderr.log"

if (Test-Path $watchdogPidFile) {
    $existingPid = Get-Content $watchdogPidFile -ErrorAction SilentlyContinue
    if ($existingPid) {
        $proc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Output "Ralph Wiggum watchdog already running (PID $existingPid)"
            exit 0
        }
    }
    Remove-Item $watchdogPidFile -Force -ErrorAction SilentlyContinue
}

Remove-Item $stopFile -Force -ErrorAction SilentlyContinue

$watchdogScript = Join-Path $repoRoot "scripts\ralph_wiggum_watchdog.py"
if (-not (Test-Path $watchdogScript)) {
    throw "Watchdog script not found: $watchdogScript"
}

$args = @(
    "-u",
    $watchdogScript,
    "--python-exe",
    $python,
    "--runtime-dir",
    $runtimeDir,
    "--reconcile-interval-seconds",
    "10",
    "--heartbeat-seconds",
    "5",
    "--max-queue-size",
    "256",
    "--dry-run"
)

$proc = Start-Process `
    -FilePath $python `
    -ArgumentList $args `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 2
$watchdogPid = if (Test-Path $watchdogPidFile) { Get-Content $watchdogPidFile } else { $proc.Id }

Write-Output "Ralph Wiggum watchdog started"
Write-Output ("Watchdog PID: {0}" -f $watchdogPid)
Write-Output ("Runtime dir : {0}" -f $runtimeDir)
Write-Output ("Watchdog log: {0}" -f (Join-Path $runtimeDir "watchdog.log"))
Write-Output ("Runner logs : {0}" -f (Join-Path $runtimeDir "runner_stdout_YYYYMMDD.log"))
