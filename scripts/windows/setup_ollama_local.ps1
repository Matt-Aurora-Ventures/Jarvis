# Setup Ollama Locally on Windows
# Run this script to install and configure Ollama for local Claude Code

$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
$LocalModel = "qwen2.5-coder:7b"  # Change to 14b or 32b if you have more RAM

Write-Host "=== Ollama Local Setup for Windows ===" -ForegroundColor Cyan
Write-Host ""

# Check if Ollama is installed
Write-Host "[1/5] Checking Ollama installation..." -ForegroundColor Yellow
$OllamaInstalled = Get-Command ollama -ErrorAction SilentlyContinue

if (-not $OllamaInstalled) {
    Write-Host "Ollama not found. Installing via winget..." -ForegroundColor Yellow
    
    try {
        winget install Ollama.Ollama
        Write-Host "Ollama installed successfully!" -ForegroundColor Green
        
        # Add to PATH for current session
        $env:Path += ";C:\Users\$env:USERNAME\AppData\Local\Programs\Ollama"
        
        Write-Host "Please restart your terminal after this script completes." -ForegroundColor Yellow
    } catch {
        Write-Host "ERROR: Failed to install via winget." -ForegroundColor Red
        Write-Host "Please install manually from: https://ollama.ai/download/windows" -ForegroundColor Yellow
        exit 1
    }
} else {
    $Version = ollama --version
    Write-Host "Ollama already installed: $Version" -ForegroundColor Green
}

# Wait for Ollama service to start
Write-Host ""
Write-Host "[2/5] Starting Ollama service..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Check if Ollama API is responding
Write-Host "Waiting for Ollama API to be ready..."
$MaxAttempts = 30
$Attempt = 0
$ApiReady = $false

while ($Attempt -lt $MaxAttempts -and -not $ApiReady) {
    try {
        $Response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -Method GET -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($Response.StatusCode -eq 200) {
            $ApiReady = $true
            Write-Host "Ollama API is ready!" -ForegroundColor Green
        }
    } catch {
        $Attempt++
        Start-Sleep -Seconds 1
    }
}

if (-not $ApiReady) {
    Write-Host "WARNING: Ollama API not responding. It may still be starting up." -ForegroundColor Yellow
    Write-Host "Continue anyway? (Y/N)" -ForegroundColor Yellow
    $Continue = Read-Host
    if ($Continue -ne 'Y' -and $Continue -ne 'y') {
        exit 1
    }
}

# Pull model
Write-Host ""
Write-Host "[3/5] Pulling model: $LocalModel" -ForegroundColor Yellow
Write-Host "This may take several minutes depending on your internet speed..." -ForegroundColor Yellow
try {
    ollama pull $LocalModel
    Write-Host "Model downloaded successfully!" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to pull model. Is Ollama running?" -ForegroundColor Red
    Write-Host "Try running: ollama serve" -ForegroundColor Yellow
    exit 1
}

# Update .env
Write-Host ""
Write-Host "[4/5] Updating .env configuration..." -ForegroundColor Yellow
$EnvFile = Join-Path $ProjectRoot ".env"

if (Test-Path $EnvFile) {
    # Backup
    $Backup = "$EnvFile.backup." + (Get-Date -Format "yyyyMMddHHmmss")
    Copy-Item $EnvFile $Backup
    Write-Host "Created backup: $Backup" -ForegroundColor Gray
    
    # Check if already configured
    $EnvContent = Get-Content $EnvFile -Raw
    
    if ($EnvContent -notmatch "ANTHROPIC_BASE_URL") {
        # Add Ollama config
        $OllamaConfig = @"

# === Ollama Local Mode (added $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")) ===
ANTHROPIC_BASE_URL=http://localhost:11434
ANTHROPIC_AUTH_TOKEN=ollama
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
OLLAMA_MODEL=$LocalModel
AI_SUPERVISOR_ENABLED=true
"@
        Add-Content -Path $EnvFile -Value $OllamaConfig
        Write-Host "Added Ollama configuration to .env" -ForegroundColor Green
    } else {
        Write-Host "Ollama config already exists in .env - skipping" -ForegroundColor Yellow
    }
} else {
    Write-Host "WARNING: .env file not found at $EnvFile" -ForegroundColor Yellow
}

# Test setup
Write-Host ""
Write-Host "[5/5] Testing Ollama setup..." -ForegroundColor Yellow
try {
    $Models = ollama list
    Write-Host "Available models:" -ForegroundColor Green
    Write-Host $Models
} catch {
    Write-Host "WARNING: Could not list models" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "=== Setup Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Ollama Configuration:" -ForegroundColor Cyan
Write-Host "  API: http://localhost:11434"
Write-Host "  Model: $LocalModel"
Write-Host "  Privacy: Complete (runs locally)"
Write-Host "  Cost: $0 (no API fees)"
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Restart supervisor:"
Write-Host "     python bots\supervisor.py"
Write-Host ""
Write-Host "  2. Test Claude Code locally:"
Write-Host "     claude --model $LocalModel"
Write-Host ""
Write-Host "  3. Verify ai_supervisor is running:"
Write-Host "     curl http://127.0.0.1:8080/health"
Write-Host ""
Write-Host "  4. For higher quality responses, upgrade to larger model:"
Write-Host "     ollama pull qwen2.5-coder:14b"
Write-Host ""

# Offer to start supervisor now
Write-Host "Start supervisor now? (Y/N)" -ForegroundColor Yellow
$StartNow = Read-Host

if ($StartNow -eq 'Y' -or $StartNow -eq 'y') {
    Write-Host "Starting supervisor..." -ForegroundColor Cyan
    Set-Location $ProjectRoot
    python bots\supervisor.py
}
