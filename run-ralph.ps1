# Ralph-TUI Execution Script
# Run this in PowerShell outside of Claude Code

Write-Host "🚀 Starting Ralph-TUI with Demo Bot PRD..." -ForegroundColor Green
Write-Host ""

# Change to project directory
Set-Location "c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"

# Clean up any stale sessions
Write-Host "Cleaning up stale sessions..." -ForegroundColor Yellow
Remove-Item -Path "$env:USERPROFILE\.config\ralph-tui\sessions.*" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$env:USERPROFILE\.config\ralph-tui\*.lock" -Force -ErrorAction SilentlyContinue

# Initialize fresh session files
New-Item -ItemType Directory -Path "$env:USERPROFILE\.config\ralph-tui" -Force | Out-Null
"[]" | Out-File -FilePath "$env:USERPROFILE\.config\ralph-tui\sessions.json" -Encoding UTF8 -NoNewline
New-Item -ItemType File -Path "$env:USERPROFILE\.config\ralph-tui\sessions.lock" -Force | Out-Null

Write-Host "✅ Session files initialized" -ForegroundColor Green
Write-Host ""

# Run ralph-tui
Write-Host "▶️  Executing Ralph-TUI..." -ForegroundColor Cyan
Write-Host "   PRD: prd-demo-bot.json" -ForegroundColor Gray
Write-Host "   User Stories: 33" -ForegroundColor Gray
Write-Host "   Max Iterations: 10" -ForegroundColor Gray
Write-Host ""

ralph-tui run --prd prd-demo-bot.json --iterations 10

Write-Host ""
Write-Host "✅ Ralph-TUI execution complete!" -ForegroundColor Green
