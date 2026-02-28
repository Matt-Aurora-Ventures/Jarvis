#!/bin/bash
# ============================================================================
# JARVIS Docker Startup Script
# ============================================================================
# Usage:
#   ./scripts/docker-start.sh              # Start core services
#   ./scripts/docker-start.sh --monitoring # Include Prometheus + Grafana
#   ./scripts/docker-start.sh --ollama     # Include local Ollama LLM
#   ./scripts/docker-start.sh --all        # Start everything
#   ./scripts/docker-start.sh --stop       # Stop all services
#   ./scripts/docker-start.sh --logs       # Follow logs
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.bots.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default profiles
PROFILES=""

load_claude_auth_token() {
    if [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
        return
    fi

    local cred_path="${HOME}/.claude/.credentials.json"
    if [ ! -f "$cred_path" ]; then
        return
    fi

    local token
    token="$(python3 - "$cred_path" <<'PY'
import json
import sys
import time

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    oauth = data.get("claudeAiOauth") or {}
    token = str(oauth.get("accessToken") or "").strip()
    if not token:
        raise SystemExit(0)

    expires_at = oauth.get("expiresAt")
    if expires_at is not None:
        expires_ms = int(str(expires_at))
        if int(time.time() * 1000) >= expires_ms:
            raise SystemExit(0)

    print(token)
except Exception:
    raise SystemExit(0)
PY
)"

    if [ -n "$token" ]; then
        export ANTHROPIC_AUTH_TOKEN="$token"
        echo -e "${GREEN}Loaded ANTHROPIC_AUTH_TOKEN from ~/.claude/.credentials.json${NC}"
    else
        echo -e "${YELLOW}Claude credentials found but no valid token; run 'claude setup-token'.${NC}"
    fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --monitoring)
            PROFILES="$PROFILES --profile monitoring"
            shift
            ;;
        --ollama)
            PROFILES="$PROFILES --profile with-ollama"
            shift
            ;;
        --all)
            PROFILES="--profile monitoring --profile with-ollama"
            shift
            ;;
        --stop)
            echo -e "${YELLOW}Stopping JARVIS services...${NC}"
            docker-compose -f "$COMPOSE_FILE" $PROFILES down
            echo -e "${GREEN}Services stopped.${NC}"
            exit 0
            ;;
        --logs)
            docker-compose -f "$COMPOSE_FILE" logs -f supervisor
            exit 0
            ;;
        --status)
            docker-compose -f "$COMPOSE_FILE" ps
            exit 0
            ;;
        --restart)
            echo -e "${YELLOW}Restarting supervisor...${NC}"
            docker-compose -f "$COMPOSE_FILE" restart supervisor
            echo -e "${GREEN}Supervisor restarted.${NC}"
            exit 0
            ;;
        --health)
            echo -e "${YELLOW}Checking health...${NC}"
            curl -s http://localhost:${HEALTH_PORT:-8080}/health | python3 -m json.tool
            exit 0
            ;;
        -h|--help)
            echo "JARVIS Docker Startup Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --monitoring    Include Prometheus + Grafana"
            echo "  --ollama        Include local Ollama LLM"
            echo "  --all           Start all services"
            echo "  --stop          Stop all services"
            echo "  --logs          Follow supervisor logs"
            echo "  --status        Show service status"
            echo "  --restart       Restart supervisor"
            echo "  --health        Check health endpoint"
            echo "  -h, --help      Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

load_claude_auth_token

# Check for .env file
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}Warning: .env file not found.${NC}"
    echo "Copy .env.docker.example to .env and configure your credentials."
    echo ""
    if [ -f "$PROJECT_DIR/.env.docker.example" ]; then
        echo "Example: cp .env.docker.example .env"
    fi
    exit 1
fi

# Check for secrets directory
if [ ! -d "$PROJECT_DIR/secrets" ]; then
    echo -e "${YELLOW}Warning: secrets directory not found.${NC}"
    echo "Creating secrets directory..."
    mkdir -p "$PROJECT_DIR/secrets"
fi

# Check for required secrets
if [ ! -f "$PROJECT_DIR/secrets/keys.json" ]; then
    echo -e "${YELLOW}Warning: secrets/keys.json not found.${NC}"
    echo "Some features may not work without API keys."
fi

# Create necessary directories
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/data"

# Build and start services
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   JARVIS Bot System - Docker Deployment${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Compose file: $COMPOSE_FILE"
echo "Profiles: ${PROFILES:-"(core only)"}"
echo ""

# Pull latest images
echo -e "${YELLOW}Pulling latest images...${NC}"
docker-compose -f "$COMPOSE_FILE" $PROFILES pull --quiet

# Build custom images
echo -e "${YELLOW}Building JARVIS supervisor image...${NC}"
docker-compose -f "$COMPOSE_FILE" $PROFILES build --quiet supervisor

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker-compose -f "$COMPOSE_FILE" $PROFILES up -d

# Wait for health check
echo ""
echo -e "${YELLOW}Waiting for health check...${NC}"
for i in {1..30}; do
    if curl -sf http://localhost:${HEALTH_PORT:-8080}/health > /dev/null 2>&1; then
        echo -e "${GREEN}Health check passed!${NC}"
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

# Show status
echo ""
echo -e "${GREEN}Services started:${NC}"
docker-compose -f "$COMPOSE_FILE" ps

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "Health endpoint: http://localhost:${HEALTH_PORT:-8080}/health"
if [[ "$PROFILES" == *"monitoring"* ]]; then
    echo -e "Prometheus: http://localhost:9090"
    echo -e "Grafana: http://localhost:3001"
fi
if [[ "$PROFILES" == *"with-ollama"* ]]; then
    echo -e "Ollama: http://localhost:11434"
fi
echo -e "${GREEN}============================================${NC}"
echo ""
echo "To view logs: docker-compose -f docker-compose.bots.yml logs -f supervisor"
echo "To stop: $0 --stop"
