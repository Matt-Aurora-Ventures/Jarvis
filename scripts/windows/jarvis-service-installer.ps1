# Jarvis Automation Service Installer
# Run as Administrator

param(
    [switch],
    [switch]
)

 = 'Jarvis Automation Service'
 = Split-Path -Parent (Split-Path -Parent  = 'python'

Write-Host 'Jarvis Automation Service Manager' -ForegroundColor Cyan
Write-Host '==================================' -ForegroundColor Cyan

if ( binPath= "\bots\supervisor.py" start= auto DisplayName= " ") {
    sc.exe stop DESCRIPTION:
        Deletes a service entry from the registry.
        If the service is running, or another process has an
        open handle to the service, the service is simply marked
        for deletion.
USAGE:
        sc <server> delete [service name]
    Write-Host '[OK] Service uninstalled' -ForegroundColor Green
} elseif (
} elseif (
} else {
    Write-Host 'Usage:'
    Write-Host '  .\jarvis-service-installer.ps1 -Install'
    Write-Host '  .\jarvis-service-installer.ps1 -Uninstall'
    Write-Host '  .\jarvis-service-installer.ps1 -Start'
    Write-Host '  .\jarvis-service-installer.ps1 -Stop'
}
