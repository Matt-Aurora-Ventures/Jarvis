#!/bin/bash
# Jarvis Cron Setup Script
# Sets up all scheduled tasks for the Jarvis ecosystem
#
# Usage: sudo bash scripts/setup-cron.sh

set -euo pipefail

JARVIS_HOME="${JARVIS_HOME:-/home/jarvis/Jarvis}"

echo "Setting up Jarvis cron jobs..."

# Create cron file for jarvis user
CRON_FILE="/etc/cron.d/jarvis"

cat > "${CRON_FILE}" << 'EOF'
# Jarvis Scheduled Tasks
# Managed by setup-cron.sh - do not edit manually

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
JARVIS_HOME=/home/jarvis/Jarvis

# Nightly self-evolution reflection cycle at 4:00 AM UTC
0 4 * * * jarvis /bin/bash ${JARVIS_HOME}/scripts/self-evolution-reflect.sh >> ${JARVIS_HOME}/logs/cron-reflection.log 2>&1

# Hourly health check
0 * * * * jarvis /bin/bash ${JARVIS_HOME}/scripts/vps_health_check.sh >> ${JARVIS_HOME}/logs/cron-health.log 2>&1

# Daily log rotation at 3:00 AM UTC
0 3 * * * jarvis find ${JARVIS_HOME}/logs -name "*.log" -size +100M -exec gzip {} \; 2>/dev/null

# Weekly backup of critical state at 2:00 AM Sunday
0 2 * * 0 jarvis tar -czf ${JARVIS_HOME}/backups/state_$(date +\%Y\%m\%d).tar.gz ${JARVIS_HOME}/data ${JARVIS_HOME}/bots/treasury/.positions.json ${JARVIS_HOME}/bots/twitter/.grok_state.json 2>/dev/null || true

# Redis hydration every 6 hours (if script exists)
0 */6 * * * jarvis [ -f ${JARVIS_HOME}/scripts/redis-hydration.sh ] && /bin/bash ${JARVIS_HOME}/scripts/redis-hydration.sh >> ${JARVIS_HOME}/logs/cron-redis.log 2>&1 || true
EOF

chmod 644 "${CRON_FILE}"

echo "Cron jobs installed at ${CRON_FILE}"
echo ""
echo "Scheduled tasks:"
echo "  - Nightly reflection: 4:00 AM UTC"
echo "  - Hourly health check: Every hour"
echo "  - Daily log rotation: 3:00 AM UTC"
echo "  - Weekly backup: 2:00 AM Sunday"
echo "  - Redis hydration: Every 6 hours"
echo ""
echo "To verify: cat ${CRON_FILE}"
