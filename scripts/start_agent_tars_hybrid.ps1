# Agent TARS + Claude CLI - Hybrid Browser Launcher
# Uses override config to enable hybrid (DOM + visual) browser control

$Host.UI.RawUI.WindowTitle = "Agent TARS Hybrid Launcher"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                ║" -ForegroundColor Cyan
Write-Host "║     Agent TARS + Claude CLI (Hybrid)           ║" -ForegroundColor Cyan
Write-Host "║                                                ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$agentTarsPath = "C:\Users\lucid\.agent-tars"
$proxyScript  = Join-Path $agentTarsPath "claude-cli-proxy.js"
$configBase   = Join-Path $agentTarsPath "agent.config.json"
$configOv     = Join-Path $agentTarsPath "agent.config.override.json"

# Kill any existing proxy processes
Write-Host "[1/4] Cleaning up old processes..." -ForegroundColor Yellow
Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*Claude CLI Proxy*" } | Stop-Process -Force -ErrorAction SilentlyContinue

# Start the proxy server
Write-Host "[2/4] Starting Claude CLI Proxy..." -ForegroundColor Yellow
$proxyJob = Start-Process -FilePath "node" -ArgumentList $proxyScript -WindowStyle Minimized -PassThru

Start-Sleep -Seconds 3

# Verify proxy is running
Write-Host "[3/4] Verifying proxy server..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8890/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    Write-Host "[3/4] ✓ Proxy server running on port 8890" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Proxy server failed to start" -ForegroundColor Red
    Write-Host "- Check if Node.js is installed: node --version" -ForegroundColor Yellow
    Write-Host "- Check if port 8890 is available" -ForegroundColor Yellow
    Write-Host "- View error: $($_.Exception.Message)" -ForegroundColor Yellow
    Stop-Process -Id $proxyJob.Id -Force -ErrorAction SilentlyContinue
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""

# Start Agent TARS with override config
Write-Host "[4/4] Starting Agent TARS (Hybrid)..." -ForegroundColor Yellow
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:8890"
$agentCmd = "set ANTHROPIC_BASE_URL=http://127.0.0.1:8890 && agent-tars --config `"$configBase`" --config `"$configOv`" --open"
$agentJob = Start-Process -FilePath "cmd" -ArgumentList "/k", $agentCmd -PassThru

Write-Host ""
Write-Host "════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "✓ Agent TARS is starting (Hybrid mode)..." -ForegroundColor Green
Write-Host ""
Write-Host "Web UI: http://localhost:8888 or 8889" -ForegroundColor Cyan
Write-Host "Proxy: http://127.0.0.1:8890" -ForegroundColor Cyan
Write-Host ""
Write-Host "Process IDs:" -ForegroundColor Yellow
Write-Host "  Proxy: $($proxyJob.Id)" -ForegroundColor Gray
Write-Host "  Agent TARS: $($agentJob.Id)" -ForegroundColor Gray
Write-Host "════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

Read-Host "Press Enter to close launcher (services will keep running)"
