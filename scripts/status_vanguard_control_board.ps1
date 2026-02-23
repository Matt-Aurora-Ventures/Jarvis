$ErrorActionPreference = "Stop"

$runtimeDir = if ($env:JARVIS_RALPH_RUNTIME_DIR) {
    $env:JARVIS_RALPH_RUNTIME_DIR
} else {
    Join-Path $env:LOCALAPPDATA "Jarvis\vanguard-standalone"
}
$hostBind = if ($env:VANGUARD_CONTROL_HOST) { $env:VANGUARD_CONTROL_HOST } else { "127.0.0.1" }
$portBind = if ($env:VANGUARD_CONTROL_PORT) { [int]$env:VANGUARD_CONTROL_PORT } else { 8181 }
$pidFile = Join-Path $runtimeDir "control_board.pid"

$result = [ordered]@{
    runtime_dir = $runtimeDir
    running = $false
    pid = $null
    url = "http://$hostBind`:$portBind/"
    health = $null
    stderr_log = (Join-Path $runtimeDir "control_board_stderr.log")
}

if (Test-Path $pidFile) {
    $procId = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($procId) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            $result.running = $true
            $result.pid = [int]$procId
        }
    }
}

try {
    $result.health = Invoke-RestMethod -Uri "http://$hostBind`:$portBind/api/v1/public/health" -Method Get -TimeoutSec 5
} catch {
    $result.health = @{ error = $_.Exception.Message }
}

$result | ConvertTo-Json -Depth 5
