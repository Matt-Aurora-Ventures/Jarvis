#!/bin/bash
# ============================================================================
# Jarvis Docker Deployment Script
# ============================================================================
# Usage:
#   ./scripts/docker-deploy.sh build     # Build image
#   ./scripts/docker-deploy.sh start     # Start stack
#   ./scripts/docker-deploy.sh stop      # Stop stack
#   ./scripts/docker-deploy.sh restart   # Restart supervisor only
#   ./scripts/docker-deploy.sh logs      # Follow logs
#   ./scripts/docker-deploy.sh backup    # Backup state
#   ./scripts/docker-deploy.sh restore   # Restore from backup
#   ./scripts/docker-deploy.sh status    # Show status
#   ./scripts/docker-deploy.sh update    # Pull latest and restart
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Ensure data directories exist
ensure_dirs() {
    mkdir -p data/redis logs backups bots/data

    # Ensure state files exist
    for f in bots/treasury/.positions.json bots/twitter/.grok_state.json data/trust_ladder.json bots/data/context_state.json; do
        if [ ! -f "$f" ]; then
            echo '{}' > "$f"
        fi
    done

    log_success "Data directories ready"
}

# Build Docker image
cmd_build() {
    log_info "Building Jarvis Docker image..."

    local version="${1:-latest}"
    docker build -t "jarvis:${version}" -t "jarvis:latest" .

    log_success "Image built: jarvis:${version}"
}

# Start the stack
cmd_start() {
    ensure_dirs

    log_info "Starting Jarvis stack..."
    docker compose up -d

    # Wait for health check
    log_info "Waiting for health check..."
    local retries=30
    while [ $retries -gt 0 ]; do
        if docker compose ps | grep -q "(healthy)"; then
            log_success "Jarvis is healthy!"
            break
        fi
        sleep 2
        retries=$((retries - 1))
    done

    if [ $retries -eq 0 ]; then
        log_warn "Health check timeout - check logs with: docker compose logs -f"
    fi

    docker compose ps
}

# Stop the stack
cmd_stop() {
    log_info "Stopping Jarvis stack..."
    docker compose down
    log_success "Stack stopped"
}

# Restart supervisor only (fast recovery)
cmd_restart() {
    log_info "Restarting jarvis-supervisor..."

    local start_time=$(date +%s.%N)
    docker compose restart jarvis-supervisor
    local end_time=$(date +%s.%N)
    local elapsed=$(echo "$end_time - $start_time" | bc)

    log_success "Supervisor restarted in ${elapsed}s"
}

# Show logs
cmd_logs() {
    docker compose logs -f jarvis-supervisor
}

# Backup state
cmd_backup() {
    local backup_name="jarvis_backup_$(date +%Y%m%d_%H%M%S)"
    local backup_dir="backups/${backup_name}"

    log_info "Creating backup: ${backup_name}"

    mkdir -p "$backup_dir"

    # Copy state files
    cp -r data "$backup_dir/"
    cp -r bots/data "$backup_dir/bots_data"
    cp bots/treasury/.positions.json "$backup_dir/" 2>/dev/null || true
    cp bots/twitter/.grok_state.json "$backup_dir/" 2>/dev/null || true

    # Export Redis data
    if docker compose ps | grep -q "jarvis-redis"; then
        docker compose exec -T redis redis-cli BGSAVE
        sleep 2
        docker cp jarvis-redis:/data/dump.rdb "$backup_dir/" 2>/dev/null || true
    fi

    # Create tarball
    tar -czf "backups/${backup_name}.tar.gz" -C backups "$backup_name"
    rm -rf "$backup_dir"

    log_success "Backup created: backups/${backup_name}.tar.gz"

    # Keep only last 7 backups
    ls -t backups/*.tar.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
}

# Restore from backup
cmd_restore() {
    local backup_file="${1:-}"

    if [ -z "$backup_file" ]; then
        log_info "Available backups:"
        ls -la backups/*.tar.gz 2>/dev/null || echo "No backups found"
        log_error "Usage: $0 restore <backup_file.tar.gz>"
        exit 1
    fi

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi

    log_warn "This will overwrite current state. Stop the stack first!"
    read -p "Continue? (y/N) " confirm
    if [ "$confirm" != "y" ]; then
        log_info "Aborted"
        exit 0
    fi

    log_info "Restoring from: $backup_file"

    local temp_dir=$(mktemp -d)
    tar -xzf "$backup_file" -C "$temp_dir"
    local backup_name=$(ls "$temp_dir")

    # Restore state
    cp -r "$temp_dir/$backup_name/data/"* data/ 2>/dev/null || true
    cp -r "$temp_dir/$backup_name/bots_data/"* bots/data/ 2>/dev/null || true
    cp "$temp_dir/$backup_name/.positions.json" bots/treasury/ 2>/dev/null || true
    cp "$temp_dir/$backup_name/.grok_state.json" bots/twitter/ 2>/dev/null || true

    rm -rf "$temp_dir"

    log_success "Restore complete. Start the stack with: $0 start"
}

# Show status
cmd_status() {
    echo ""
    log_info "=== Container Status ==="
    docker compose ps

    echo ""
    log_info "=== Resource Usage ==="
    docker stats --no-stream jarvis-supervisor jarvis-redis 2>/dev/null || true

    echo ""
    log_info "=== Recent Logs ==="
    docker compose logs --tail=20 jarvis-supervisor 2>/dev/null || true
}

# Update to latest image
cmd_update() {
    log_info "Pulling latest images..."
    docker compose pull

    log_info "Restarting with new images..."
    docker compose up -d

    log_success "Update complete"
    cmd_status
}

# Health check
cmd_health() {
    log_info "Checking health..."

    # Redis
    if docker compose exec -T redis redis-cli ping | grep -q PONG; then
        log_success "Redis: healthy"
    else
        log_error "Redis: unhealthy"
    fi

    # Supervisor
    if docker compose ps | grep jarvis-supervisor | grep -q "(healthy)"; then
        log_success "Supervisor: healthy"
    else
        log_warn "Supervisor: not healthy yet"
    fi

    # Memory usage
    local mem_usage=$(docker stats --no-stream --format "{{.MemUsage}}" jarvis-supervisor 2>/dev/null || echo "N/A")
    log_info "Memory usage: $mem_usage"
}

# Show help
cmd_help() {
    echo "Jarvis Docker Deployment Script"
    echo ""
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "Commands:"
    echo "  build [version]  Build Docker image"
    echo "  start            Start the full stack"
    echo "  stop             Stop the full stack"
    echo "  restart          Restart supervisor only (fast)"
    echo "  logs             Follow supervisor logs"
    echo "  backup           Create state backup"
    echo "  restore <file>   Restore from backup"
    echo "  status           Show stack status"
    echo "  update           Pull latest and restart"
    echo "  health           Check health status"
    echo "  help             Show this help"
}

# Main
case "${1:-help}" in
    build)   cmd_build "${2:-latest}" ;;
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    logs)    cmd_logs ;;
    backup)  cmd_backup ;;
    restore) cmd_restore "${2:-}" ;;
    status)  cmd_status ;;
    update)  cmd_update ;;
    health)  cmd_health ;;
    help|*)  cmd_help ;;
esac
