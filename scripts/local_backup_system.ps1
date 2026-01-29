# Local Windows Backup System
# Runs without shutting down, coordinates with VPS backups

$ErrorActionPreference = "Continue"

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "💾 LOCAL BACKUP SYSTEM (WINDOWS)" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# Configuration
$BACKUP_ROOT = "C:\Users\lucid\Backups"
$JARVIS_ROOT = "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
$CLAUDE_ROOT = "$env:USERPROFILE\.claude"
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$BACKUP_DIR = "$BACKUP_ROOT\local_$TIMESTAMP"

# Critical paths to backup
$CRITICAL_PATHS = @(
    "$JARVIS_ROOT\bots",
    "$JARVIS_ROOT\core",
    "$JARVIS_ROOT\tg_bot",
    "$JARVIS_ROOT\lifeos\config",
    "$JARVIS_ROOT\scripts",
    "$CLAUDE_ROOT\debug",
    "$CLAUDE_ROOT\hooks",
    "$CLAUDE_ROOT\commands",
    "$CLAUDE_ROOT\.credentials.json",
    "$CLAUDE_ROOT\.env",
    "$env:USERPROFILE\.lifeos"
)

# Create backup directory
Write-Host "📦 Creating backup directory: $BACKUP_DIR" -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null

# Backup function with error handling
function Backup-Path {
    param(
        [string]$SourcePath,
        [string]$DestinationRoot
    )

    if (Test-Path $SourcePath) {
        try {
            $RelativeName = Split-Path -Leaf $SourcePath
            $DestPath = Join-Path $DestinationRoot $RelativeName

            Write-Host "  📁 Backing up: $RelativeName" -ForegroundColor Green

            if (Test-Path $SourcePath -PathType Container) {
                # Directory - use robocopy for efficiency
                robocopy $SourcePath $DestPath /E /Z /R:2 /W:1 /NFL /NDL /NP /MT:8 | Out-Null
            } else {
                # Single file
                Copy-Item $SourcePath $DestPath -Force
            }

            Write-Host "    ✅ Success" -ForegroundColor Green
            return $true
        }
        catch {
            Write-Host "    ❌ Error: $_" -ForegroundColor Red
            return $false
        }
    } else {
        Write-Host "  ⚠️  Path not found: $SourcePath" -ForegroundColor Yellow
        return $false
    }
}

# Perform backups
Write-Host "`n🔄 Starting backup process..." -ForegroundColor Cyan
$SuccessCount = 0
$FailCount = 0

foreach ($Path in $CRITICAL_PATHS) {
    if (Backup-Path -SourcePath $Path -DestinationRoot $BACKUP_DIR) {
        $SuccessCount++
    } else {
        $FailCount++
    }
}

# Generate checksums (security)
Write-Host "`n🔒 Generating checksums..." -ForegroundColor Cyan
$ChecksumFile = Join-Path $BACKUP_DIR "checksums.txt"

Get-ChildItem -Path $BACKUP_DIR -Recurse -File | ForEach-Object {
    $Hash = Get-FileHash -Path $_.FullName -Algorithm SHA256
    "$($Hash.Hash)  $($_.FullName.Replace($BACKUP_DIR, '.'))" | Out-File -Append -FilePath $ChecksumFile
}

Write-Host "✅ Checksums saved: $ChecksumFile" -ForegroundColor Green

# Sync to VPS (if accessible)
Write-Host "`n☁️  Attempting VPS sync..." -ForegroundColor Cyan
$VPS_HOST = $env:VPS_HOST
$VPS_USER = $env:VPS_USER
$VPS_BACKUP_PATH = "/root/clawd/backups/from_windows"

if ($VPS_HOST -and $VPS_USER) {
    try {
        Write-Host "  📡 Syncing to VPS: $VPS_USER@$VPS_HOST" -ForegroundColor Yellow

        # Use SCP to transfer (requires SSH keys set up)
        scp -r -o ConnectTimeout=10 "$BACKUP_DIR" "${VPS_USER}@${VPS_HOST}:${VPS_BACKUP_PATH}/"

        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ VPS sync successful" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  VPS sync failed (exit code: $LASTEXITCODE)" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "  ⚠️  VPS sync error: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠️  VPS credentials not set (export VPS_HOST and VPS_USER)" -ForegroundColor Yellow
}

# Cleanup old backups (keep last 10)
Write-Host "`n🧹 Cleaning old backups..." -ForegroundColor Cyan
$OldBackups = Get-ChildItem -Path $BACKUP_ROOT -Directory |
              Where-Object { $_.Name -match "^local_\d{8}_\d{6}$" } |
              Sort-Object Name -Descending |
              Select-Object -Skip 10

foreach ($OldBackup in $OldBackups) {
    try {
        Remove-Item -Path $OldBackup.FullName -Recurse -Force
        Write-Host "  🗑️  Deleted: $($OldBackup.Name)" -ForegroundColor Gray
    }
    catch {
        Write-Host "  ⚠️  Could not delete: $($OldBackup.Name)" -ForegroundColor Yellow
    }
}

# Summary
Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ BACKUP COMPLETE" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "`n📊 Summary:" -ForegroundColor White
Write-Host "  Success: $SuccessCount paths" -ForegroundColor Green
Write-Host "  Failed: $FailCount paths" -ForegroundColor $(if ($FailCount -gt 0) { "Red" } else { "Green" })
Write-Host "  Location: $BACKUP_DIR" -ForegroundColor Cyan
Write-Host "  Checksums: $ChecksumFile" -ForegroundColor Cyan
Write-Host "`n⏰ Next backup: Run this script again (or schedule with Task Scheduler)" -ForegroundColor Yellow
