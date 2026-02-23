# OpenClaw VPS Setup Script
# Run from PowerShell: .\scripts\setup_openclaw_vps.ps1

$VPS_IP = "76.13.106.100"
$SSH_KEY = "$env:USERPROFILE\.ssh\id_ed25519_vps"

Write-Host "=== OpenClaw VPS Setup ===" -ForegroundColor Cyan

# The full setup script to run on the VPS
$REMOTE_SCRIPT = @'
set -e
echo ">>> Updating system..."
apt-get update -qq

echo ">>> Installing Node.js 22..."
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs

echo ">>> Node version:"
node --version
npm --version

echo ">>> Installing OpenClaw..."
npm install -g openclaw@latest

echo ">>> OpenClaw version:"
openclaw --version 2>/dev/null || echo "installed"

echo ">>> Running OpenClaw onboard with daemon..."
openclaw onboard --install-daemon

echo ""
echo "============================================"
echo "  OpenClaw installed! Next steps:"
echo "  1. Run: openclaw channels login"
echo "  2. Run: openclaw gateway --port 18789"
echo "  3. Web UI: http://76.13.106.100:18789/"
echo "============================================"
'@

Write-Host "Connecting to VPS at $VPS_IP..." -ForegroundColor Yellow
Write-Host "You may be prompted for your SSH key passphrase." -ForegroundColor Yellow
Write-Host ""

# SSH in and run the setup
ssh -i $SSH_KEY -o StrictHostKeyChecking=no root@$VPS_IP $REMOTE_SCRIPT
