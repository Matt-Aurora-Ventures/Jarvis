# Adjust monitor brightness
param(
    [int]$Brightness = 80
)

# Get the brightness WMI class
$monitors = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods

if ($monitors) {
    foreach ($monitor in $monitors) {
        Write-Host "Setting brightness to $Brightness%..."
        Invoke-CimMethod -InputObject $monitor -MethodName WmiSetBrightness -Arguments @{Timeout=1; Brightness=$Brightness}
        Write-Host "Brightness adjusted successfully to $Brightness%!"
    }
} else {
    Write-Host "ERROR: Cannot control brightness via software (external monitors may require physical buttons)"
    Write-Host ""
    Write-Host "Alternative: Opening Windows Display Settings..."
    Start-Process ms-settings:display
}
