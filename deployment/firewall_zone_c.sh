#!/usr/bin/env bash
# firewall_zone_c.sh — Harden the Zone C (signer) host firewall.
#
# Applies iptables rules to enforce:
#   - Default DENY all inbound
#   - Default DENY all forwarding
#   - Outbound allowed ONLY to:
#       Helius RPC: api.helius.xyz:443
#       Jito RPC (optional): mainnet.block-engine.jito.wtf:443
#       PostgreSQL (internal only): 5432 (Zone B internal IP)
#       DNS: 53 UDP (nameserver resolution)
#   - Loopback always allowed
#   - NO SSH password login (key-only enforced separately)
#
# Usage: sudo bash deployment/firewall_zone_c.sh <ZONE_B_INTERNAL_IP>
#
# Prerequisites:
#   - iptables installed
#   - Running as root (sudo)
#   - Set HELIUS_IP environment variable if Helius IP changes
#
# WARNING: Run this script AFTER verifying you can SSH in via key-based auth.
# Locking yourself out requires physical console access or cloud rescue mode.

set -euo pipefail

ZONE_B_IP="${1:-}"
if [[ -z "${ZONE_B_IP}" ]]; then
    echo "Usage: sudo bash firewall_zone_c.sh <ZONE_B_INTERNAL_IP>"
    echo "Example: sudo bash firewall_zone_c.sh 10.0.1.10"
    exit 1
fi

# Helius RPC IPs (resolve once — pin these)
# Refresh if Helius changes their infrastructure
HELIUS_HOSTS=(
    "api.helius.xyz"
    "mainnet.helius-rpc.com"
)

# Jito block engine (optional — comment out if not using Jito)
JITO_HOSTS=(
    "mainnet.block-engine.jito.wtf"
    "ny.mainnet.block-engine.jito.wtf"
    "amsterdam.mainnet.block-engine.jito.wtf"
)

# Public Solana mainnet RPC fallback (use only if Helius is down)
SOLANA_MAINNET_IP="api.mainnet-beta.solana.com"

echo "==> Flushing existing iptables rules..."
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X

echo "==> Setting default DENY policies..."
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

echo "==> Allowing loopback..."
iptables -A INPUT  -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

echo "==> Allowing established/related connections (stateful)..."
iptables -A INPUT  -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

echo "==> Allowing DNS (UDP/TCP 53) outbound for hostname resolution..."
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

echo "==> Allowing outbound to Helius RPC (port 443)..."
for host in "${HELIUS_HOSTS[@]}"; do
    IPS=$(getent hosts "${host}" | awk '{ print $1 }')
    for ip in ${IPS}; do
        echo "    ${host} -> ${ip}:443"
        iptables -A OUTPUT -p tcp -d "${ip}" --dport 443 -j ACCEPT
    done
done

echo "==> Allowing outbound to Jito RPC (port 443)..."
for host in "${JITO_HOSTS[@]}"; do
    IPS=$(getent hosts "${host}" | awk '{ print $1 }') || true
    for ip in ${IPS}; do
        echo "    ${host} -> ${ip}:443"
        iptables -A OUTPUT -p tcp -d "${ip}" --dport 443 -j ACCEPT
    done
done

echo "==> Allowing outbound to Zone B PostgreSQL (${ZONE_B_IP}:5432)..."
iptables -A OUTPUT -p tcp -d "${ZONE_B_IP}" --dport 5432 -j ACCEPT

echo "==> Allowing outbound ICMP (ping) for connectivity testing..."
iptables -A OUTPUT -p icmp --icmp-type echo-request -j ACCEPT
iptables -A INPUT  -p icmp --icmp-type echo-reply   -j ACCEPT

echo ""
echo "==> Final iptables ruleset:"
iptables -L -v --line-numbers

echo ""
echo "==> Persisting rules..."
if command -v iptables-save &>/dev/null; then
    iptables-save > /etc/iptables/rules.v4
    echo "Rules saved to /etc/iptables/rules.v4"
    echo "Install iptables-persistent to auto-restore on reboot:"
    echo "  apt-get install iptables-persistent"
fi

echo ""
echo "DONE. Zone C firewall applied."
echo ""
echo "Verify you can still reach Helius:"
echo "  curl -s -o /dev/null -w '%{http_code}' https://api.helius.xyz/v0/health"
echo ""
echo "Next steps:"
echo "  1. Disable password SSH: Edit /etc/ssh/sshd_config"
echo "       PasswordAuthentication no"
echo "       PermitRootLogin no"
echo "     Then: systemctl restart sshd"
echo "  2. Consider hardware wallet for treasury keys"
echo "  3. Set up monitoring: prometheus-client metrics → Zone B scraper"
