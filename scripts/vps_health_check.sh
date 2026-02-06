#!/bin/bash
# VPS Health Check Script
# Comprehensive health audit for both Jarvis VPS servers
# Run on each VPS to verify system status

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

check_disk_space() {
    print_header "DISK SPACE"

    df -h | grep -E '^/dev/' | while read line; do
        usage=$(echo $line | awk '{print $5}' | sed 's/%//')
        mount=$(echo $line | awk '{print $6}')

        if [ "$usage" -gt 90 ]; then
            print_error "Disk $mount is ${usage}% full (CRITICAL)"
        elif [ "$usage" -gt 75 ]; then
            print_warning "Disk $mount is ${usage}% full"
        else
            print_success "Disk $mount is ${usage}% full"
        fi
    done
}

check_memory() {
    print_header "MEMORY USAGE"

    total=$(free -m | awk 'NR==2{print $2}')
    used=$(free -m | awk 'NR==2{print $3}')
    free_mem=$(free -m | awk 'NR==2{print $4}')
    usage=$((used * 100 / total))

    echo "Total: ${total}MB | Used: ${used}MB | Free: ${free_mem}MB"

    if [ "$usage" -gt 90 ]; then
        print_error "Memory usage is ${usage}% (CRITICAL)"
    elif [ "$usage" -gt 75 ]; then
        print_warning "Memory usage is ${usage}%"
    else
        print_success "Memory usage is ${usage}%"
    fi
}

check_cpu() {
    print_header "CPU LOAD"

    load=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    cores=$(nproc)

    echo "1-minute load average: $load (${cores} cores)"

    # Simple check: if load > cores, warn
    if (( $(echo "$load > $cores" | bc -l) )); then
        print_warning "Load average is above number of cores"
    else
        print_success "Load average is normal"
    fi
}

check_supervisor() {
    print_header "SUPERVISOR STATUS"

    if pgrep -f "supervisor.py" > /dev/null; then
        pid=$(pgrep -f "supervisor.py")
        uptime=$(ps -p $pid -o etime= | tr -d ' ')
        print_success "Supervisor is running (PID: $pid, Uptime: $uptime)"

        # Check log for recent errors
        if [ -f "logs/supervisor.log" ]; then
            error_count=$(tail -n 100 logs/supervisor.log | grep -i "error" | wc -l)
            if [ "$error_count" -gt 10 ]; then
                print_warning "Found $error_count errors in last 100 log lines"
            else
                print_success "Found $error_count errors in last 100 log lines"
            fi
        fi
    else
        print_error "Supervisor is NOT running"
    fi
}

check_bots() {
    print_header "BOT STATUS"

    # Expected bots on main VPS (72.61.7.126)
    bots=(
        "autonomous_x"
        "sentiment_reporter"
        "autonomous_manager"
        "bags_intel"
        "buy_bot"
        "treasury"
    )

    for bot in "${bots[@]}"; do
        if pgrep -f "$bot" > /dev/null 2>&1; then
            print_success "$bot is running"
        else
            print_warning "$bot is NOT running (may be expected if not on this VPS)"
        fi
    done
}

check_network() {
    print_header "NETWORK CONNECTIVITY"

    # Check external connectivity
    if ping -c 1 8.8.8.8 > /dev/null 2>&1; then
        print_success "External network is reachable"
    else
        print_error "Cannot reach external network"
    fi

    # Check DNS
    if ping -c 1 google.com > /dev/null 2>&1; then
        print_success "DNS resolution is working"
    else
        print_error "DNS resolution failed"
    fi

    # Check open ports
    echo -e "\nListening ports:"
    netstat -tlnp 2>/dev/null | grep LISTEN | head -n 10 || ss -tlnp | head -n 10
}

check_security() {
    print_header "SECURITY STATUS"

    # Check if fail2ban is running
    if systemctl is-active --quiet fail2ban 2>/dev/null; then
        print_success "fail2ban is running"
        banned=$(fail2ban-client status sshd 2>/dev/null | grep "Banned" | awk '{print $4}')
        echo "  Currently banned IPs: $banned"
    elif command -v fail2ban-client >/dev/null 2>&1; then
        print_warning "fail2ban is installed but not running"
    else
        print_warning "fail2ban is not installed"
    fi

    # Check UFW status
    if command -v ufw >/dev/null 2>&1; then
        status=$(ufw status 2>/dev/null | head -n 1)
        if echo "$status" | grep -q "active"; then
            print_success "UFW firewall is active"
        else
            print_warning "UFW firewall is not active"
        fi
    else
        print_warning "UFW is not installed"
    fi

    # Check for recent SSH login attempts
    echo -e "\nRecent SSH login attempts:"
    tail -n 20 /var/log/auth.log 2>/dev/null | grep sshd || echo "  (log not accessible)"
}

check_environment() {
    print_header "ENVIRONMENT VARIABLES"

    required_vars=(
        "TELEGRAM_BOT_TOKEN"
        "XAI_API_KEY"
        "ANTHROPIC_API_KEY"
    )

    env_file="lifeos/config/.env"

    if [ -f "$env_file" ]; then
        print_success "Environment file exists: $env_file"

        for var in "${required_vars[@]}"; do
            if grep -q "^${var}=" "$env_file" 2>/dev/null; then
                print_success "$var is set"
            else
                print_warning "$var is NOT set in .env"
            fi
        done
    else
        print_error "Environment file not found: $env_file"
    fi
}

check_database() {
    print_header "DATABASE STATUS"

    # Check PostgreSQL
    if systemctl is-active --quiet postgresql 2>/dev/null; then
        print_success "PostgreSQL is running"
    elif pgrep postgres > /dev/null 2>&1; then
        print_success "PostgreSQL process is running"
    else
        print_warning "PostgreSQL is not running (may not be needed)"
    fi

    # Check Redis
    if systemctl is-active --quiet redis 2>/dev/null; then
        print_success "Redis is running"
    elif pgrep redis > /dev/null 2>&1; then
        print_success "Redis process is running"
    else
        print_warning "Redis is not running (may not be needed)"
    fi
}

check_logs() {
    print_header "RECENT LOG ERRORS"

    log_files=(
        "logs/supervisor.log"
        "logs/autonomous_x.log"
        "logs/treasury.log"
    )

    for log in "${log_files[@]}"; do
        if [ -f "$log" ]; then
            error_count=$(tail -n 100 "$log" | grep -i "error" | wc -l)
            if [ "$error_count" -gt 5 ]; then
                print_warning "$log: $error_count errors in last 100 lines"
            else
                print_success "$log: $error_count errors in last 100 lines"
            fi
        fi
    done
}

check_git_status() {
    print_header "GIT STATUS"

    if [ -d ".git" ]; then
        branch=$(git branch --show-current 2>/dev/null || echo "unknown")
        print_success "Current branch: $branch"

        # Check if clean
        if git diff-index --quiet HEAD -- 2>/dev/null; then
            print_success "Working directory is clean"
        else
            print_warning "Working directory has uncommitted changes"
            git status --short
        fi

        # Check if behind origin
        git fetch origin "$branch" 2>/dev/null
        behind=$(git rev-list HEAD..origin/"$branch" --count 2>/dev/null || echo "0")
        if [ "$behind" -gt 0 ]; then
            print_warning "Branch is $behind commits behind origin"
        else
            print_success "Branch is up to date with origin"
        fi
    else
        print_error "Not a git repository"
    fi
}

# Main execution
main() {
    clear
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                  VPS HEALTH CHECK                           ║"
    echo "║                   Jarvis System                             ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    echo "Hostname: $(hostname)"
    echo "IP: $(hostname -I | awk '{print $1}')"
    echo "Date: $(date)"
    echo "Uptime: $(uptime -p)"

    check_disk_space
    check_memory
    check_cpu
    check_supervisor
    check_bots
    check_network
    check_security
    check_environment
    check_database
    check_logs
    check_git_status

    print_header "HEALTH CHECK COMPLETE"

    echo -e "\n${BLUE}Recommendations:${NC}"
    echo "1. Review any warnings or errors above"
    echo "2. Check supervisor logs: tail -f logs/supervisor.log"
    echo "3. Monitor resource usage: htop"
    echo "4. Review security logs: sudo tail -f /var/log/auth.log"
    echo ""
}

# Run main function
main
