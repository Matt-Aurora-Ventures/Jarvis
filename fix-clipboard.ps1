# Fix clipboard issues on Windows 11
Write-Output "=== Clipboard Fix ==="

# 1. Restart clipboard user service
$svc = Get-Service -Name cbdhsvc* | Select-Object -First 1
if ($svc) {
    Write-Output "Restarting $($svc.Name)..."
    Restart-Service -Name $svc.Name -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $status = (Get-Service -Name $svc.Name).Status
    Write-Output "Service status: $status"
}

# 2. Kill any processes known to lock clipboard
$clipLockers = @("ScreenClip", "TextInputHost")
foreach ($proc in $clipLockers) {
    $p = Get-Process -Name $proc -ErrorAction SilentlyContinue
    if ($p) {
        Write-Output "Stopping $proc (known clipboard locker)..."
        Stop-Process -Name $proc -Force -ErrorAction SilentlyContinue
    }
}

# 3. Clear and test clipboard
Start-Sleep -Seconds 1
Set-Clipboard -Value ""
Start-Sleep -Milliseconds 500
Set-Clipboard -Value "Clipboard is working again!"
$result = Get-Clipboard
Write-Output "Clipboard test: $result"
Write-Output ""
Write-Output "Try Ctrl+C / Ctrl+V now. If still broken, try: Win+V to open Clipboard History and toggle it off/on."
