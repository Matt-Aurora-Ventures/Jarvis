# Boost laptop display brightness and contrast
Write-Host "Boosting laptop display settings..." -ForegroundColor Cyan

# 1. Set brightness to absolute maximum
Write-Host "`n[1/5] Setting brightness to maximum..."
$monitors = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods
foreach ($monitor in $monitors) {
    Invoke-CimMethod -InputObject $monitor -MethodName WmiSetBrightness -Arguments @{Timeout=1; Brightness=100}
}
Write-Host "✓ Brightness set to 100%"

# 2. Disable adaptive brightness
Write-Host "`n[2/5] Disabling adaptive brightness..."
powercfg /setacvalueindex SCHEME_CURRENT SUB_VIDEO ADAPTBRIGHT 0 | Out-Null
powercfg /setdcvalueindex SCHEME_CURRENT SUB_VIDEO ADAPTBRIGHT 0 | Out-Null
Write-Host "✓ Adaptive brightness disabled"

# 3. Disable display dimming
Write-Host "`n[3/5] Disabling display dimming..."
powercfg /setacvalueindex SCHEME_CURRENT SUB_VIDEO VIDEODIM 100 | Out-Null
powercfg /setdcvalueindex SCHEME_CURRENT SUB_VIDEO VIDEODIM 100 | Out-Null
Write-Host "✓ Display dimming disabled"

# 4. Apply power settings
Write-Host "`n[4/5] Applying power plan changes..."
powercfg /setactive SCHEME_CURRENT | Out-Null
Write-Host "✓ Power plan updated"

# 5. Check for color filters (can make display appear darker)
Write-Host "`n[5/5] Checking color filters..."
$colorFilterPath = "HKCU:\Software\Microsoft\ColorFiltering"
if (Test-Path $colorFilterPath) {
    $filterActive = (Get-ItemProperty -Path $colorFilterPath -Name Active -ErrorAction SilentlyContinue).Active
    if ($filterActive -eq 1) {
        Set-ItemProperty -Path $colorFilterPath -Name Active -Value 0
        Write-Host "✓ Color filter was enabled - now disabled"
    } else {
        Write-Host "✓ No color filter active"
    }
} else {
    Write-Host "✓ No color filter settings found"
}

Write-Host "`n" -NoNewline
Write-Host "========================================" -ForegroundColor Green
Write-Host "Display brightness boost complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nIf still darker than expected, try:" -ForegroundColor Yellow
Write-Host "  - Use the brightness keys on your keyboard (Fn + brightness up)"
Write-Host "  - Check Windows Settings > Display > Night light (should be OFF)"
Write-Host "  - Check Windows Settings > Display > HDR (if enabled, adjust SDR brightness)"
