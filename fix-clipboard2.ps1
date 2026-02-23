# Aggressive clipboard fix
Write-Output "=== Aggressive Clipboard Fix ==="

# 1. Re-enable clipboard via registry
Write-Output "Checking registry..."
$regPath = "HKCU:\Software\Microsoft\Clipboard"
if (!(Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}
Set-ItemProperty -Path $regPath -Name "EnableClipboardHistory" -Value 1 -Type DWord -Force
Write-Output "  Clipboard History: ENABLED"

# Check if clipboard is disabled by policy
$policyPath = "HKCU:\Software\Policies\Microsoft\Windows\System"
if (Test-Path $policyPath) {
    $clipDisabled = Get-ItemProperty -Path $policyPath -Name "AllowClipboardHistory" -ErrorAction SilentlyContinue
    if ($clipDisabled -and $clipDisabled.AllowClipboardHistory -eq 0) {
        Set-ItemProperty -Path $policyPath -Name "AllowClipboardHistory" -Value 1 -Force
        Write-Output "  Policy was BLOCKING clipboard - FIXED"
    }
    $crossClip = Get-ItemProperty -Path $policyPath -Name "AllowCrossDeviceClipboard" -ErrorAction SilentlyContinue
    if ($crossClip -and $crossClip.AllowCrossDeviceClipboard -eq 0) {
        Set-ItemProperty -Path $policyPath -Name "AllowCrossDeviceClipboard" -Value 1 -Force
        Write-Output "  Cross-device clipboard was BLOCKED - FIXED"
    }
}

# Local machine policy check
$lmPolicy = "HKLM:\Software\Policies\Microsoft\Windows\System"
if (Test-Path $lmPolicy) {
    $vals = Get-ItemProperty -Path $lmPolicy -ErrorAction SilentlyContinue
    if ($vals.AllowClipboardHistory -eq 0) {
        Write-Output "  WARNING: Machine-level policy blocking clipboard"
    }
}

# 2. Restart all clipboard-related services
Write-Output ""
Write-Output "Restarting services..."
Get-Service -Name cbdhsvc* | ForEach-Object {
    Restart-Service -Name $_.Name -Force -ErrorAction SilentlyContinue
    Write-Output "  Restarted: $($_.Name)"
}

# 3. Kill and restart explorer (refreshes clipboard chain)
Write-Output ""
Write-Output "Restarting Explorer..."
Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process explorer
Start-Sleep -Seconds 3

# 4. Re-register clipboard COM objects
Write-Output "Re-registering clipboard..."
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Clipboard]::Clear()
Start-Sleep -Milliseconds 500
[System.Windows.Forms.Clipboard]::SetText("Clipboard fixed!")
$test = [System.Windows.Forms.Clipboard]::GetText()
Write-Output "  Test result: $test"

Write-Output ""
Write-Output "=== DONE - Try Ctrl+C and Ctrl+V now ==="
