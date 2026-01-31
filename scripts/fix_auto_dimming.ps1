# Fix Auto-Dimming on New Laptop
# Disables Intel/AMD/NVIDIA auto-dimming features
Write-Host "=== FIXING AUTO-DIMMING ISSUE ===" -ForegroundColor Cyan
Write-Host ""

# 1. Disable Intel Display Power Saving Technology (DPST)
Write-Host "[1/6] Disabling Intel DPST..." -ForegroundColor Yellow
$intelKeys = @(
    "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000",
    "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0001",
    "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0002"
)

foreach ($key in $intelKeys) {
    if (Test-Path $key) {
        Set-ItemProperty -Path $key -Name "Disable_DynamicPowerState" -Value 1 -Type DWord -Force -ErrorAction SilentlyContinue
        Set-ItemProperty -Path $key -Name "DisableDMDynamicPS" -Value 1 -Type DWord -Force -ErrorAction SilentlyContinue
        Set-ItemProperty -Path $key -Name "EnableVRR" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "    Done" -ForegroundColor Green

# 2. Disable Panel Self-Refresh (PSR)
Write-Host "[2/6] Disabling Panel Self-Refresh..." -ForegroundColor Yellow
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers" -Name "DisablePSR" -Value 1 -PropertyType DWord -Force -ErrorAction SilentlyContinue | Out-Null
Write-Host "    Done" -ForegroundColor Green

# 3. Disable AMD Vari-Bright
Write-Host "[3/6] Disabling AMD Vari-Bright..." -ForegroundColor Yellow
$amdKey = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000"
if (Test-Path $amdKey) {
    Set-ItemProperty -Path $amdKey -Name "KMD_EnableBrightnessInterface2" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
}
Write-Host "    Done" -ForegroundColor Green

# 4. Disable NVIDIA Dynamic Display
Write-Host "[4/6] Disabling NVIDIA dynamic features..." -ForegroundColor Yellow
$nvidiaKey = "HKLM:\SYSTEM\CurrentControlSet\Services\nvlddmkm"
if (Test-Path $nvidiaKey) {
    Set-ItemProperty -Path $nvidiaKey -Name "DisableWriteCombining" -Value 1 -Type DWord -Force -ErrorAction SilentlyContinue
}
Write-Host "    Done" -ForegroundColor Green

# 5. Disable Windows Content Adaptive Brightness Control
Write-Host "[5/6] Disabling Windows CABC..." -ForegroundColor Yellow
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\DWM" -Name "UseDpiScaling" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
Write-Host "    Done" -ForegroundColor Green

# 6. Force brightness to maximum
Write-Host "[6/6] Forcing brightness to 100%..." -ForegroundColor Yellow
$monitors = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods
foreach ($monitor in $monitors) {
    Invoke-CimMethod -InputObject $monitor -MethodName WmiSetBrightness -Arguments @{Timeout=1; Brightness=100} | Out-Null
}
Write-Host "    Done" -ForegroundColor Green

Write-Host ""
Write-Host "=== RESTART REQUIRED ===" -ForegroundColor Cyan
Write-Host "For changes to fully take effect, please restart your computer." -ForegroundColor Yellow
Write-Host ""
Write-Host "Or try this quick fix:" -ForegroundColor Cyan
Write-Host "  1. Press Ctrl+Shift+Win+B (resets graphics driver)" -ForegroundColor White
Write-Host "  2. Screen will flash black briefly" -ForegroundColor White
Write-Host "  3. Brightness should be restored" -ForegroundColor White
