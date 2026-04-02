#!/bin/bash
# Firewall Rules for ClawdBot Security
# Restricts gateway ports to Tailscale network only
#
# Run on VPS: bash firewall-rules.sh

set -e

# Tailscale subnet (100.x.x.x)
TAILSCALE_SUBNET="100.0.0.0/8"

# Gateway ports
FRIDAY_PORT=18789
MATT_PORT=18800
JARVIS_PORT=18801

echo "=========================================="
echo "ClawdBot Firewall Configuration"
echo "=========================================="

# Check if iptables is available
if ! command -v iptables &> /dev/null; then
    echo "ERROR: iptables not installed"
    exit 1
fi

# =============================================================================
# Option 1: UFW (if installed)
# =============================================================================

if command -v ufw &> /dev/null; then
    echo "Using UFW..."

    # Allow Tailscale subnet
    ufw allow from $TAILSCALE_SUBNET to any port $FRIDAY_PORT
    ufw allow from $TAILSCALE_SUBNET to any port $MATT_PORT
    ufw allow from $TAILSCALE_SUBNET to any port $JARVIS_PORT

    # Deny public access to gateway ports
    ufw deny $FRIDAY_PORT
    ufw deny $MATT_PORT
    ufw deny $JARVIS_PORT

    # Allow health API publicly (for external monitoring)
    ufw allow 18888

    echo "UFW rules applied"
    ufw status

# =============================================================================
# Option 2: iptables (direct)
# =============================================================================

else
    echo "Using iptables..."

    # Allow Tailscale access to gateway ports
    iptables -A INPUT -s $TAILSCALE_SUBNET -p tcp --dport $FRIDAY_PORT -j ACCEPT
    iptables -A INPUT -s $TAILSCALE_SUBNET -p tcp --dport $MATT_PORT -j ACCEPT
    iptables -A INPUT -s $TAILSCALE_SUBNET -p tcp --dport $JARVIS_PORT -j ACCEPT

    # Allow localhost (for health checks)
    iptables -A INPUT -i lo -p tcp --dport $FRIDAY_PORT -j ACCEPT
    iptables -A INPUT -i lo -p tcp --dport $MATT_PORT -j ACCEPT
    iptables -A INPUT -i lo -p tcp --dport $JARVIS_PORT -j ACCEPT

    # Block public access to gateway ports
    iptables -A INPUT -p tcp --dport $FRIDAY_PORT -j DROP
    iptables -A INPUT -p tcp --dport $MATT_PORT -j DROP
    iptables -A INPUT -p tcp --dport $JARVIS_PORT -j DROP

    # Allow health API publicly
    iptables -A INPUT -p tcp --dport 18888 -j ACCEPT

    echo "iptables rules applied"
    iptables -L -n | grep -E "(18789|18800|18801|18888)"
fi

echo ""
echo "=========================================="
echo "Firewall configured!"
echo "=========================================="
echo ""
echo "Gateway ports (18789, 18800, 18801):"
echo "  - Accessible from Tailscale (100.x.x.x)"
echo "  - Blocked from public internet"
echo ""
echo "Health API port (18888):"
echo "  - Accessible publicly (for external monitoring)"
echo ""
echo "To verify, try from outside Tailscale:"
echo "  curl http://76.13.106.100:18789  # Should timeout"
echo "  curl http://76.13.106.100:18888/health  # Should work"
