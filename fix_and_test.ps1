Write-Host "=== Killing stale processes ===" -ForegroundColor Cyan
Get-Process -Name node, python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Write-Host "=== Running investment service tests ===" -ForegroundColor Green
Set-Location "c:\Users\lucid\Desktop\Jarvis"
python -m pytest services/investments/tests/ -v --tb=short

Write-Host "`n=== Done ===" -ForegroundColor Green
Read-Host "Press Enter to close"
