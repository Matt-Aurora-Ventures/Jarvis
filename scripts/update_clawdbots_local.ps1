# Update ClawdBots to OpenClaw 2026.2.3 (Local Windows Gateway)
# Run in PowerShell: .\update_clawdbots_local.ps1

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "ClawdBots Update to OpenClaw 2026.2.3" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

$gatewayPath = "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\docker\clawdbot-gateway"

# Check if docker is running
try {
    docker ps | Out-Null
} catch {
    Write-Host "ERROR: Docker is not running" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again" -ForegroundColor Yellow
    exit 1
}

# Navigate to gateway directory
if (-not (Test-Path $gatewayPath)) {
    Write-Host "ERROR: Gateway directory not found at $gatewayPath" -ForegroundColor Red
    exit 1
}

Set-Location $gatewayPath

Write-Host "Step 1: Backing up current configuration..." -ForegroundColor Yellow
$backupDir = "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\backups"
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
docker compose config > "$backupDir\docker-compose-backup-$timestamp.yml"
Write-Host "✓ Configuration backed up to $backupDir" -ForegroundColor Green

Write-Host ""
Write-Host "Step 2: Stopping current containers..." -ForegroundColor Yellow
docker compose down
Write-Host "✓ Containers stopped" -ForegroundColor Green

Write-Host ""
Write-Host "Step 3: Starting containers with OpenClaw 2026.2.3..." -ForegroundColor Yellow
Write-Host "(This will pull and install openclaw@2026.2.3)" -ForegroundColor Gray
docker compose up -d
Write-Host "✓ Containers started" -ForegroundColor Green

Write-Host ""
Write-Host "Step 4: Waiting for containers to initialize (60s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 60

Write-Host ""
Write-Host "Step 5: Verifying installation..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Friday version:" -ForegroundColor Cyan
try {
    docker compose exec friday openclaw --version
} catch {
    Write-Host "Warning: Friday not responding yet" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Matt version:" -ForegroundColor Cyan
try {
    docker compose exec matt openclaw --version
} catch {
    Write-Host "Warning: Matt not responding yet" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Jarvis version:" -ForegroundColor Cyan
try {
    docker compose exec jarvis openclaw --version
} catch {
    Write-Host "Warning: Jarvis not responding yet" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 6: Checking container status..." -ForegroundColor Yellow
docker compose ps

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Update Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Monitor logs with:" -ForegroundColor White
Write-Host "  docker compose logs -f" -ForegroundColor Gray
Write-Host ""
Write-Host "Check individual bot logs:" -ForegroundColor White
Write-Host "  docker compose logs -f friday" -ForegroundColor Gray
Write-Host "  docker compose logs -f matt" -ForegroundColor Gray
Write-Host "  docker compose logs -f jarvis" -ForegroundColor Gray
Write-Host ""
Write-Host "Test Telegram integration:" -ForegroundColor White
Write-Host "  Send '/models' to each bot to test new inline model selection" -ForegroundColor Gray
Write-Host ""
Write-Host "Check health endpoints:" -ForegroundColor White
Write-Host "  curl http://localhost:18789/health" -ForegroundColor Gray
Write-Host "  curl http://localhost:18790/health" -ForegroundColor Gray
Write-Host "  curl http://localhost:18791/health" -ForegroundColor Gray
Write-Host ""
