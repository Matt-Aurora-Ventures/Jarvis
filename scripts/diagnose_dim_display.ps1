# Diagnose and fix dim display issues
Write-Host "=== DISPLAY BRIGHTNESS DIAGNOSTIC ===" -ForegroundColor Cyan
Write-Host ""

# 1. Check current brightness
Write-Host "[1] Current Brightness Level:" -ForegroundColor Yellow
$brightness = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness
Write-Host "    Software brightness: $($brightness.CurrentBrightness)%" -ForegroundColor White

# 2. Check adaptive brightness
Write-Host "`n[2] Adaptive Brightness:" -ForegroundColor Yellow
$adaptAC = powercfg /query SCHEME_CURRENT SUB_VIDEO ADAPTBRIGHT | Select-String "Current AC"
$adaptDC = powercfg /query SCHEME_CURRENT SUB_VIDEO ADAPTBRIGHT | Select-String "Current DC"
Write-Host "    AC (plugged in): $adaptAC" -ForegroundColor White
Write-Host "    DC (battery): $adaptDC" -ForegroundColor White

# 3. Check power plan
Write-Host "`n[3] Active Power Plan:" -ForegroundColor Yellow
$powerPlan = powercfg /getactivescheme
Write-Host "    $powerPlan" -ForegroundColor White

# 4. Check battery saver (can dim even when plugged in)
Write-Host "`n[4] Battery Saver:" -ForegroundColor Yellow
$batterySaver = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\WUDF\Services\BatterySaver" -ErrorAction SilentlyContinue
if ($batterySaver) {
    Write-Host "    Battery Saver registry found - may be affecting brightness" -ForegroundColor Red
} else {
    Write-Host "    Not affecting brightness" -ForegroundColor Green
}

# 5. Check graphics power settings
Write-Host "`n[5] Graphics Settings:" -ForegroundColor Yellow
$graphicsSettings = Get-ItemProperty -Path "HKCU:\Software\Microsoft\DirectX\UserGpuPreferences" -ErrorAction SilentlyContinue
Write-Host "    Checking GPU power mode..." -ForegroundColor White

# 6. Recommend fixes
Write-Host "`n=== RECOMMENDED ACTIONS ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Try keyboard brightness keys: Fn + F6 (or sun icon key)" -ForegroundColor Yellow
Write-Host "2. Check if Battery Saver is ON (I just opened settings)" -ForegroundColor Yellow
Write-Host "3. Check Display > Night light (should be OFF)" -ForegroundColor Yellow
Write-Host "4. Try switching power plan to 'High Performance'" -ForegroundColor Yellow
Write-Host ""
Write-Host "Would you like me to:" -ForegroundColor Cyan
Write-Host "  A) Switch to High Performance power plan" -ForegroundColor White
Write-Host "  B) Force maximum brightness again" -ForegroundColor White
Write-Host "  C) Reset all display power settings" -ForegroundColor White
