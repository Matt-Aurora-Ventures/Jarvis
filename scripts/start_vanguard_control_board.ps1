$ErrorActionPreference = "Stop"

$repoRoot = (Get-Location).Path
$runtimeDir = if ($env:JARVIS_RALPH_RUNTIME_DIR) {
    $env:JARVIS_RALPH_RUNTIME_DIR
} else {
    Join-Path $env:LOCALAPPDATA "Jarvis\vanguard-standalone"
}
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$hostBind = if ($env:VANGUARD_CONTROL_HOST) { $env:VANGUARD_CONTROL_HOST } else { "127.0.0.1" }
$portBind = if ($env:VANGUARD_CONTROL_PORT) { [int]$env:VANGUARD_CONTROL_PORT } else { 8181 }

function Resolve-Python {
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
    throw "Unable to locate Python. Set JARVIS_PYTHON_311."
}

$python = Resolve-Python
$pidFile = Join-Path $runtimeDir "control_board.pid"
$stdoutLog = Join-Path $runtimeDir "control_board_stdout.log"
$stderrLog = Join-Path $runtimeDir "control_board_stderr.log"

if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($existingPid) {
        $existingProc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($existingProc) {
            Write-Output "Vanguard control board already running (PID $existingPid)"
            exit 0
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

if (-not $env:VANGUARD_CONTROL_TOKEN_SECRET) { $env:VANGUARD_CONTROL_TOKEN_SECRET = "local-dev-secret-change-me" }
if (-not $env:JARVIS_RALPH_RUNTIME_DIR) { $env:JARVIS_RALPH_RUNTIME_DIR = $runtimeDir }
if (-not $env:PERPS_CONTROL_STATE_PATH) { $env:PERPS_CONTROL_STATE_PATH = (Join-Path $runtimeDir "control_state.json") }
if (-not $env:PYTHONDONTWRITEBYTECODE) { $env:PYTHONDONTWRITEBYTECODE = "1" }
if (-not $env:PYTHONPYCACHEPREFIX) { $env:PYTHONPYCACHEPREFIX = (Join-Path $env:TEMP "jarvis_pycache") }

$args = @(
    "-u",
    "-m",
    "scripts.start_vanguard_control_board",
    "--host",
    $hostBind,
    "--port",
    "$portBind"
)

$proc = Start-Process `
    -FilePath $python `
    -ArgumentList $args `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $pidFile -Value $proc.Id -Encoding ascii
Start-Sleep -Seconds 2

Write-Output "Vanguard control board started"
Write-Output ("PID        : {0}" -f $proc.Id)
Write-Output ("URL        : http://{0}:{1}/" -f $hostBind, $portBind)
Write-Output ("Runtime dir: {0}" -f $runtimeDir)
Write-Output ("Logs       : {0}" -f $stderrLog)
