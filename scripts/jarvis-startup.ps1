param(
    [switch]$Once,
    [switch]$SkipInstall,
    [switch]$SkipPull,
    [switch]$SkipBuild,
    [string]$ComposeFile,
    [string]$Profiles,
    [int]$LoopIntervalSeconds = 30,
    [int]$HealthTimeoutSeconds = 180,
    [string]$HealthUrl = "http://localhost:8080/health"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = [System.IO.Path]::GetFullPath((Join-Path $scriptDir ".."))

if (-not $ComposeFile -and $env:JARVIS_COMPOSE_FILE) {
    $ComposeFile = $env:JARVIS_COMPOSE_FILE
}

if (-not $ComposeFile) {
    $ComposeFile = Join-Path $projectDir "docker-compose-multi.yml"
    if (-not (Test-Path $ComposeFile)) {
        $ComposeFile = Join-Path $projectDir "docker-compose.bots.yml"
    }
}

if (-not $Profiles -and $env:JARVIS_PROFILES) {
    $Profiles = $env:JARVIS_PROFILES
}

$logRoot = Join-Path $projectDir "logs"
$startupLogDir = Join-Path $logRoot "startup"
New-Item -ItemType Directory -Force -Path $startupLogDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile = Join-Path $startupLogDir ("jarvis-startup-{0}.log" -f $timestamp)
$latestLog = Join-Path $startupLogDir "jarvis-startup-latest.log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $line = "[{0}][{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Add-Content -Path $logFile -Value $line
    Add-Content -Path $latestLog -Value $line
}

function Write-Status {
    param([string]$Message)
    Write-Host $Message
    Write-Log $Message "STATUS"
}

function Invoke-Logged {
    param(
        [string]$Command,
        [string[]]$CmdArgs = @(),
        [switch]$IgnoreErrors
    )
    $cmdLine = "$Command $($CmdArgs -join ' ')"
    Write-Log "RUN $cmdLine"
    & $Command @CmdArgs 2>&1 | ForEach-Object { Add-Content -Path $logFile -Value $_; Add-Content -Path $latestLog -Value $_ }
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $IgnoreErrors) {
        Write-Log "FAIL ($code) $cmdLine" "WARN"
        return $false
    }
    return $true
}

function Ensure-Tool {
    param(
        [string]$Name,
        [string]$Command,
        [string]$WingetId
    )
    if (Get-Command $Command -ErrorAction SilentlyContinue) {
        return $true
    }
    if ($SkipInstall) {
        Write-Log "$Name missing and installs disabled" "WARN"
        return $false
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Log "winget missing; cannot install $Name automatically" "WARN"
        return $false
    }
    Write-Log "Installing $Name via winget ($WingetId)"
    Invoke-Logged "winget" @("install", "-e", "--id", $WingetId, "--accept-source-agreements", "--accept-package-agreements", "--silent") -IgnoreErrors
    Start-Sleep -Seconds 5
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

function Get-ComposeCommand {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        & docker compose version *> $null
        if ($LASTEXITCODE -eq 0) {
            return @("docker", "compose")
        }
    }
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        return @("docker-compose")
    }
    return $null
}

function Ensure-DockerRunning {
    if (Invoke-Logged "docker" @("info") -IgnoreErrors) {
        return $true
    }

    $desktopExe = Join-Path ${Env:ProgramFiles} "Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $desktopExe)) {
        $desktopExe = Join-Path ${Env:ProgramFiles(x86)} "Docker\Docker\Docker Desktop.exe"
    }
    if (Test-Path $desktopExe) {
        Write-Log "Starting Docker Desktop"
        Start-Process -FilePath $desktopExe | Out-Null
        Start-Sleep -Seconds 10
    } else {
        Write-Log "Docker Desktop not found" "WARN"
    }

    for ($i = 0; $i -lt 30; $i++) {
        if (Invoke-Logged "docker" @("info") -IgnoreErrors) {
            return $true
        }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Ensure-EnvFile {
    $envFile = Join-Path $projectDir ".env"
    if (Test-Path $envFile) {
        return
    }
    $example = Join-Path $projectDir ".env.multi.example"
    if (-not (Test-Path $example)) {
        $example = Join-Path $projectDir ".env.docker.example"
    }
    if (Test-Path $example) {
        Copy-Item -Path $example -Destination $envFile -Force
        Write-Log "Created .env from $example"
    } else {
        Write-Log "No .env example found; skipping .env creation" "WARN"
    }
}

function Set-ClaudeAuthTokenFromLocalCredentials {
    if (-not [string]::IsNullOrWhiteSpace($env:ANTHROPIC_AUTH_TOKEN)) {
        Write-Log "ANTHROPIC_AUTH_TOKEN already set in environment"
        return
    }

    $credPath = Join-Path $env:USERPROFILE ".claude\.credentials.json"
    if (-not (Test-Path $credPath)) {
        Write-Log "Claude credentials not found at $credPath"
        return
    }

    try {
        $raw = Get-Content -Path $credPath -Raw
        $json = $raw | ConvertFrom-Json
        $token = [string]$json.claudeAiOauth.accessToken
        if ([string]::IsNullOrWhiteSpace($token)) {
            Write-Log "Claude credentials present but access token is empty" "WARN"
            return
        }

        $expiresAtRaw = [string]$json.claudeAiOauth.expiresAt
        $expiresAtMs = 0L
        if ([int64]::TryParse($expiresAtRaw, [ref]$expiresAtMs) -and $expiresAtMs -gt 0) {
            $nowMs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
            if ($nowMs -ge $expiresAtMs) {
                Write-Log "Claude access token is expired; run 'claude setup-token' to refresh" "WARN"
                return
            }
        }

        $env:ANTHROPIC_AUTH_TOKEN = $token.Trim()
        Write-Log "Loaded ANTHROPIC_AUTH_TOKEN from local Claude credentials"
    } catch {
        Write-Log "Failed to load Claude credentials: $($_.Exception.Message)" "WARN"
    }
}

function Wait-For-Health {
    param([int]$TimeoutSeconds)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -UseBasicParsing -Uri $HealthUrl -TimeoutSec 5
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds 3
        }
    }
    return $false
}

Write-Status "Jarvis startup loop starting..."
Write-Log "Compose file: $ComposeFile"

# Auto-set MCP env for docker runtime
if (-not $env:MCP_AUTO_START) { $env:MCP_AUTO_START = "true" }
if (-not $env:JARVIS_MCP_CONFIG) { $env:JARVIS_MCP_CONFIG = "/app/config/mcp.docker.json" }

# Ensure prerequisites
Ensure-Tool "Docker Desktop" "docker" "Docker.DockerDesktop" | Out-Null
Ensure-Tool "Git" "git" "Git.Git" | Out-Null

if (-not (Ensure-DockerRunning)) {
    Write-Status "Docker is not running yet. Will keep retrying..."
}

Ensure-EnvFile
Set-ClaudeAuthTokenFromLocalCredentials
New-Item -ItemType Directory -Force -Path (Join-Path $projectDir "secrets") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $projectDir "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $projectDir "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $projectDir "data\\ai_memory") | Out-Null

$composeCmd = Get-ComposeCommand
if (-not $composeCmd) {
    Write-Status "Docker compose not available yet. Waiting..."
}

$profileArgs = @()
if ($Profiles) {
    $profileArgs = $Profiles.Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
}

$didInitialSetup = $false

while ($true) {
    if (-not (Ensure-DockerRunning)) {
        Start-Sleep -Seconds 10
        if ($Once) { break }
        continue
    }

    $composeCmd = Get-ComposeCommand
    if (-not $composeCmd) {
        Write-Log "docker compose not found" "WARN"
        Start-Sleep -Seconds 10
        if ($Once) { break }
        continue
    }

    $baseArgs = @()
    if ($composeCmd.Length -gt 1) {
        $baseArgs += $composeCmd[1..($composeCmd.Length - 1)]
    }
    $baseArgs += @("-f", $ComposeFile)
    $baseArgs += $profileArgs

    if (-not $didInitialSetup) {
        if (-not $SkipPull) {
            Invoke-Logged $composeCmd[0] ($baseArgs + @("pull")) -IgnoreErrors | Out-Null
        }
        if (-not $SkipBuild) {
            Invoke-Logged $composeCmd[0] ($baseArgs + @("build")) -IgnoreErrors | Out-Null
        }
        $didInitialSetup = $true
    }

    Invoke-Logged $composeCmd[0] ($baseArgs + @("up", "-d", "--remove-orphans")) -IgnoreErrors | Out-Null

    if (Wait-For-Health -TimeoutSeconds $HealthTimeoutSeconds) {
        Write-Status "Jarvis is healthy."
    } else {
        Write-Status "Health check failed. Capturing diagnostics and retrying..."
        Invoke-Logged $composeCmd[0] ($baseArgs + @("ps")) -IgnoreErrors | Out-Null
        Invoke-Logged $composeCmd[0] ($baseArgs + @("logs", "--tail=200")) -IgnoreErrors | Out-Null
        Invoke-Logged $composeCmd[0] ($baseArgs + @("restart")) -IgnoreErrors | Out-Null
    }

    if ($Once) { break }
    Start-Sleep -Seconds $LoopIntervalSeconds
}

Write-Status "Jarvis startup loop ended."
