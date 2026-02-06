# Agent TARS Quick Start Script (PowerShell)
# Uses Claude 3.7 Sonnet with Anthropic API

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Starting Agent TARS with Claude 3.7 Sonnet" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check if ANTHROPIC_API_KEY is set
if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "ERROR: ANTHROPIC_API_KEY environment variable not set" -ForegroundColor Red
    Write-Host "Please set it with: `$env:ANTHROPIC_API_KEY = 'your_api_key'" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Launch Agent TARS with config
& agent-tars --config "C:\Users\lucid\.agent-tars\agent.config.json" --open

Read-Host "Press Enter to exit"
