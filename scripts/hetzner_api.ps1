# Hetzner Cloud API helper (read/write)
# Loads token from secrets\hetzner.env or HETZNER_API_TOKEN env var.

$ErrorActionPreference = "Stop"

function Get-HetznerToken {
    if ($env:HETZNER_API_TOKEN) { return $env:HETZNER_API_TOKEN }
    $envFile = "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\secrets\hetzner.env"
    if (Test-Path $envFile) {
        $line = Get-Content $envFile | Where-Object { $_ -match "^HETZNER_API_TOKEN=" } | Select-Object -First 1
        if ($line) {
            return ($line -split "=", 2)[1].Trim()
        }
    }
    throw "HETZNER_API_TOKEN not found."
}

function Invoke-HetznerApi {
    param(
        [Parameter(Mandatory=$true)][string]$Method,
        [Parameter(Mandatory=$true)][string]$Path,
        [object]$Body = $null
    )
    $token = Get-HetznerToken
    $headers = @{
        "Authorization" = "Bearer $token"
        "Content-Type"  = "application/json"
    }
    $uri = "https://api.hetzner.cloud/v1$Path"
    if ($Body -ne $null) {
        $json = $Body | ConvertTo-Json -Depth 6
        return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -Body $json
    }
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
}

function Get-HetznerServers {
    Invoke-HetznerApi -Method GET -Path "/servers"
}

function Get-HetznerSshKeys {
    Invoke-HetznerApi -Method GET -Path "/ssh_keys"
}

function Add-HetznerSshKey {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$PublicKey
    )
    $body = @{
        name = $Name
        public_key = $PublicKey
    }
    Invoke-HetznerApi -Method POST -Path "/ssh_keys" -Body $body
}

function Set-HetznerServerPower {
    param(
        [Parameter(Mandatory=$true)][int]$ServerId,
        [Parameter(Mandatory=$true)][ValidateSet("on","off","reboot","reset","shutdown","poweron","poweroff")][string]$Action
    )
    $actionPath = switch ($Action) {
        "on" { "poweron" }
        "off" { "poweroff" }
        default { $Action }
    }
    Invoke-HetznerApi -Method POST -Path "/servers/$ServerId/actions/$actionPath"
}

Write-Host "Hetzner API helper loaded. Examples:" -ForegroundColor Cyan
Write-Host "  Get-HetznerServers" -ForegroundColor Gray
Write-Host "  Get-HetznerSshKeys" -ForegroundColor Gray
Write-Host "  Add-HetznerSshKey -Name 'friday key' -PublicKey 'ssh-ed25519 AAAA... friday@clawdbot'" -ForegroundColor Gray
Write-Host "  Set-HetznerServerPower -ServerId 123456 -Action reboot" -ForegroundColor Gray
