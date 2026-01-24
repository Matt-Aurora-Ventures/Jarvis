#!/bin/bash
# Setup Ollama on All Servers - One-Command Deployment
# Usage: ./setup_ollama_all_servers.sh [local|vps|both]

set -e

DEPLOY_TARGET="${1:-both}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Ollama Multi-Server Deployment ==="
echo "Target: $DEPLOY_TARGET"
echo ""

# Configuration
VPS_HOST="${VPS_HOST:-your-vps-hostname}"  # Set via env or edit here
VPS_USER="${VPS_USER:-root}"
VPS_MODEL="qwen2.5-coder:32b"  # Production model
LOCAL_MODEL="qwen2.5-coder:7b"  # Dev model

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

function log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

function log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

function setup_local() {
    log_info "Setting up Ollama locally..."

    # Check if Ollama is installed
    if ! command -v ollama &> /dev/null; then
        log_warn "Ollama not installed. Installing..."
        
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            curl -fsSL https://ollama.ai/install.sh | sh
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            log_warn "macOS detected. Install via: brew install ollama"
            exit 1
        else
            log_warn "Windows detected. Download from: https://ollama.ai/download/windows"
            exit 1
        fi
    else
        log_info "Ollama already installed: $(ollama --version)"
    fi

    # Start Ollama service
    log_info "Starting Ollama service..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo systemctl start ollama || true
        sudo systemctl enable ollama || true
    fi

    # Wait for Ollama to be ready
    log_info "Waiting for Ollama API..."
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            log_info "Ollama API ready!"
            break
        fi
        sleep 1
    done

    # Pull model
    log_info "Pulling model: $LOCAL_MODEL (this may take a while)..."
    ollama pull "$LOCAL_MODEL"

    # Update .env
    log_info "Updating .env for local Ollama..."
    ENV_FILE="$PROJECT_ROOT/.env"
    
    if [ -f "$ENV_FILE" ]; then
        # Backup original
        cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%s)"
        
        # Add or update Ollama config
        if ! grep -q "ANTHROPIC_BASE_URL" "$ENV_FILE"; then
            cat >> "$ENV_FILE" << EOF

# === Ollama Local Mode (added $(date)) ===
ANTHROPIC_BASE_URL=http://localhost:11434
ANTHROPIC_AUTH_TOKEN=ollama
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
OLLAMA_MODEL=$LOCAL_MODEL
AI_SUPERVISOR_ENABLED=true
EOF
            log_info "Added Ollama config to .env"
        else
            log_warn "Ollama config already exists in .env, skipping"
        fi
    else
        log_error ".env not found at $ENV_FILE"
    fi

    # Test
    log_info "Testing Ollama..."
    ollama list
    
    log_info "Local setup complete! ✓"
    echo ""
    echo "Next steps:"
    echo "  1. Restart supervisor: python bots/supervisor.py"
    echo "  2. Test Claude: claude --model $LOCAL_MODEL"
    echo "  3. Check health: curl http://127.0.0.1:8080/health"
}

function setup_vps() {
    log_info "Setting up Ollama on VPS: $VPS_USER@$VPS_HOST..."

    if [ "$VPS_HOST" = "your-vps-hostname" ]; then
        log_error "VPS_HOST not set. Export VPS_HOST=your-server.com first."
        exit 1
    fi

    # Create remote setup script
    REMOTE_SCRIPT=$(cat << 'EOFSCRIPT'
#!/bin/bash
set -e

echo "[VPS] Installing Ollama..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.ai/install.sh | sh
fi

echo "[VPS] Starting Ollama service..."
sudo systemctl start ollama
sudo systemctl enable ollama

echo "[VPS] Waiting for API..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "[VPS] API ready!"
        break
    fi
    sleep 1
done

echo "[VPS] Pulling model: MODEL_PLACEHOLDER..."
ollama pull MODEL_PLACEHOLDER

echo "[VPS] Setup complete!"
ollama list
EOFSCRIPT
)

    # Replace placeholder
    REMOTE_SCRIPT="${REMOTE_SCRIPT//MODEL_PLACEHOLDER/$VPS_MODEL}"

    # Execute on VPS
    log_info "Deploying to VPS..."
    ssh "$VPS_USER@$VPS_HOST" "bash -s" <<< "$REMOTE_SCRIPT"

    # Update VPS .env
    log_info "Updating VPS .env..."
    ssh "$VPS_USER@$VPS_HOST" << EOFENV
cd ~/jarvis || cd /opt/jarvis || { echo "Project dir not found"; exit 1; }

if [ -f .env ]; then
    cp .env .env.backup.\$(date +%s)
    
    if ! grep -q "ANTHROPIC_BASE_URL" .env; then
        cat >> .env << EOF

# === Ollama Local Mode (VPS) ===
ANTHROPIC_BASE_URL=http://localhost:11434
ANTHROPIC_AUTH_TOKEN=ollama
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
OLLAMA_MODEL=$VPS_MODEL
AI_SUPERVISOR_ENABLED=true
EOF
        echo "[VPS] Ollama config added to .env"
    else
        echo "[VPS] Ollama config already exists"
    fi
fi
EOFENV

    log_info "VPS setup complete! ✓"
    echo ""
    echo "Next steps:"
    echo "  1. SSH to VPS and restart supervisor"
    echo "  2. Verify: ssh $VPS_USER@$VPS_HOST 'curl http://127.0.0.1:8080/health'"
}

# Main execution
case "$DEPLOY_TARGET" in
    local)
        setup_local
        ;;
    vps)
        setup_vps
        ;;
    both)
        setup_local
        echo ""
        echo "==================================="
        echo ""
        setup_vps
        ;;
    *)
        log_error "Invalid target: $DEPLOY_TARGET"
        echo "Usage: $0 [local|vps|both]"
        exit 1
        ;;
esac

echo ""
log_info "=== Deployment Complete ==="
echo ""
echo "Ollama is now running on:"
if [ "$DEPLOY_TARGET" = "local" ] || [ "$DEPLOY_TARGET" = "both" ]; then
    echo "  ✓ Local machine (http://localhost:11434)"
fi
if [ "$DEPLOY_TARGET" = "vps" ] || [ "$DEPLOY_TARGET" = "both" ]; then
    echo "  ✓ VPS: $VPS_HOST (http://localhost:11434)"
fi
echo ""
echo "Models installed:"
if [ "$DEPLOY_TARGET" = "local" ] || [ "$DEPLOY_TARGET" = "both" ]; then
    echo "  Local:  $LOCAL_MODEL"
fi
if [ "$DEPLOY_TARGET" = "vps" ] || [ "$DEPLOY_TARGET" = "both" ]; then
    echo "  VPS:    $VPS_MODEL"
fi
