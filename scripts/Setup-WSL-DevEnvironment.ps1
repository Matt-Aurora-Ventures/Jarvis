# Windows PowerShell Script to Setup WSL Development Environment
# Launches the Linux setup script in WSL
# Usage: .\Setup-WSL-DevEnvironment.ps1

param(
    [switch]$CheckOnly,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# Colors
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Write-Success { Write-ColorOutput $args[0] "Green" }
function Write-Error { Write-ColorOutput $args[0] "Red" }
function Write-Warning { Write-ColorOutput $args[0] "Yellow" }
function Write-Info { Write-ColorOutput $args[0] "Cyan" }

# ASCII Art
Write-Host ""
Write-ColorOutput "╔══════════════════════════════════════════════════════════════╗" "Blue"
Write-ColorOutput "║           WSL Development Environment Setup (Windows)        ║" "Blue"
Write-ColorOutput "║         Claude CLI • Clawd Bot • Windsurf • GSD              ║" "Blue"
Write-ColorOutput "╚══════════════════════════════════════════════════════════════╝" "Blue"
Write-Host ""

if ($Help) {
    Write-Info "WSL Development Environment Setup Script"
    Write-Host ""
    Write-Host "Usage: .\Setup-WSL-DevEnvironment.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -CheckOnly    Check WSL status without installing"
    Write-Host "  -Help         Show this help message"
    Write-Host ""
    Write-Host "What this script does:"
    Write-Host "  1. Checks if WSL is installed"
    Write-Host "  2. Copies setup script to WSL"
    Write-Host "  3. Runs the Linux setup script"
    Write-Host "  4. Installs: Claude CLI, Clawd Bot, GSD, VS Code"
    Write-Host ""
    exit 0
}

# Check if WSL is installed
Write-Info "Checking WSL installation..."

try {
    $wslVersion = wsl --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "WSL not found"
    }
    Write-Success "✓ WSL is installed"
    Write-Host $wslVersion
} catch {
    Write-Error "✗ WSL is not installed or not accessible"
    Write-Host ""
    Write-Warning "To install WSL:"
    Write-Host "  1. Open PowerShell as Administrator"
    Write-Host "  2. Run: wsl --install"
    Write-Host "  3. Restart your computer"
    Write-Host "  4. Run this script again"
    Write-Host ""
    exit 1
}

# Check WSL status
Write-Info "Checking WSL status..."
try {
    $wslStatus = wsl --status 2>&1
    Write-Success "✓ WSL is configured"
    Write-Host $wslStatus
} catch {
    Write-Warning "⚠ Could not get WSL status (this is usually fine)"
}

# List WSL distributions
Write-Info "Installed WSL distributions:"
wsl --list --verbose

# Check if any distribution is installed
$distributions = wsl --list --quiet
if ($null -eq $distributions -or $distributions.Count -eq 0) {
    Write-Error "✗ No WSL distributions installed"
    Write-Host ""
    Write-Warning "To install Ubuntu:"
    Write-Host "  wsl --install -d Ubuntu"
    Write-Host ""
    exit 1
}

if ($CheckOnly) {
    Write-Success "✓ WSL check complete"
    exit 0
}

# Get the script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$setupScript = Join-Path $scriptDir "setup_wsl_complete.sh"

# Check if setup script exists
if (-not (Test-Path $setupScript)) {
    Write-Error "✗ Setup script not found: $setupScript"
    exit 1
}

Write-Success "✓ Found setup script: $setupScript"

# Copy script to WSL
Write-Info "Copying setup script to WSL..."

try {
    # Convert Windows path to WSL path for the copy
    $tempPath = "/tmp/setup_wsl_complete.sh"
    wsl cp $setupScript.Replace('\', '/').Replace('C:', '/mnt/c') $tempPath
    wsl chmod +x $tempPath

    Write-Success "✓ Script copied to WSL"
} catch {
    Write-Error "✗ Failed to copy script to WSL"
    Write-Host $_.Exception.Message
    exit 1
}

# Ask for confirmation
Write-Host ""
Write-Warning "This will install the following in WSL:"
Write-Host "  • Node.js 20.x"
Write-Host "  • Claude CLI (@anthropic-ai/claude-code)"
Write-Host "  • Python 3 with pip and uv"
Write-Host "  • Clawd Discord Bot"
Write-Host "  • GSD (Get Shit Done) Framework"
Write-Host "  • Visual Studio Code"
Write-Host "  • Development tools and dependencies"
Write-Host ""

$confirmation = Read-Host "Continue with installation? (yes/no)"
if ($confirmation -ne "yes" -and $confirmation -ne "y") {
    Write-Info "Installation cancelled"
    exit 0
}

# Run the setup script in WSL
Write-Host ""
Write-Info "Running setup script in WSL..."
Write-Info "This may take 5-10 minutes..."
Write-Host ""

try {
    # Run the script in WSL
    wsl bash /tmp/setup_wsl_complete.sh

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Success "════════════════════════════════════════════════════════════════"
        Write-Success "                    🎉 Setup Complete! 🎉"
        Write-Success "════════════════════════════════════════════════════════════════"
        Write-Host ""

        Write-Info "Next Steps (run these in WSL):"
        Write-Host ""
        Write-Host "  1. Configure API keys:"
        Write-Host "     wsl nano ~/.wsl_dev_config"
        Write-Host ""
        Write-Host "  2. Reload environment:"
        Write-Host "     wsl source ~/.bashrc"
        Write-Host ""
        Write-Host "  3. Verify installation:"
        Write-Host "     wsl bash ~/verify_wsl_setup.sh"
        Write-Host ""
        Write-Host "  4. Read quick start guide:"
        Write-Host "     wsl cat ~/WSL_QUICK_START.md"
        Write-Host ""
        Write-Host "Or just launch WSL:"
        Write-Host "     wsl"
        Write-Host ""

        # Offer to create desktop shortcuts
        $createShortcuts = Read-Host "Create desktop shortcuts for common tasks? (yes/no)"
        if ($createShortcuts -eq "yes" -or $createShortcuts -eq "y") {
            # Create shortcuts
            $desktopPath = [Environment]::GetFolderPath("Desktop")

            # WSL shortcut
            $wslShortcut = "$desktopPath\WSL Terminal.lnk"
            $WshShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut($wslShortcut)
            $Shortcut.TargetPath = "wsl.exe"
            $Shortcut.Save()
            Write-Success "✓ Created: WSL Terminal.lnk"

            # Clawd shortcut
            $clawdShortcut = "$desktopPath\Start Clawd Bot.lnk"
            $Shortcut = $WshShell.CreateShortcut($clawdShortcut)
            $Shortcut.TargetPath = "wsl.exe"
            $Shortcut.Arguments = "bash -c 'cd ~/clawd && source venv/bin/activate && python main.py'"
            $Shortcut.Save()
            Write-Success "✓ Created: Start Clawd Bot.lnk"

            # Verify shortcut
            $verifyShortcut = "$desktopPath\Verify WSL Setup.lnk"
            $Shortcut = $WshShell.CreateShortcut($verifyShortcut)
            $Shortcut.TargetPath = "wsl.exe"
            $Shortcut.Arguments = "bash ~/verify_wsl_setup.sh"
            $Shortcut.Save()
            Write-Success "✓ Created: Verify WSL Setup.lnk"

            Write-Success "✓ Desktop shortcuts created!"
        }

    } else {
        Write-Error "✗ Setup script failed with exit code $LASTEXITCODE"
        Write-Warning "Check the error messages above for details"
        exit 1
    }

} catch {
    Write-Error "✗ Failed to run setup script"
    Write-Host $_.Exception.Message
    exit 1
}

Write-Host ""
Write-Success "🚀 You're all set! Launch WSL with: wsl"
Write-Host ""
