#!/bin/bash
# URGENT VPS Security Hardening Script
# Run this IMMEDIATELY - Active brute force attacks detected
# Date: 2026-01-31

set -e

echo "========================================="
echo "URGENT VPS SECURITY HARDENING"
echo "========================================="
echo ""
echo "⚠️  WARNING: This will disable password SSH auth"
echo "⚠️  Make sure you have SSH key access configured!"
echo ""
read -p "Have you verified SSH key access works? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborting. Set up SSH keys first!"
    exit 1
fi

echo ""
echo "Step 1/4: Hardening SSH Configuration..."
echo "========================================="

# Backup SSH config
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup.$(date +%Y%m%d)

# Disable password authentication
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
grep -q "^PasswordAuthentication" /etc/ssh/sshd_config || echo "PasswordAuthentication no" >> /etc/ssh/sshd_config

# Restrict root login to key-only
sed -i 's/PermitRootLogin yes/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config

# Enable public key authentication
sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/PubkeyAuthentication no/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# Test SSH config
if sshd -t; then
    echo "✅ SSH config valid"
    systemctl restart sshd
    echo "✅ SSH service restarted"
else
    echo "❌ SSH config invalid! Restoring backup..."
    cp /etc/ssh/sshd_config.backup.$(date +%Y%m%d) /etc/ssh/sshd_config
    exit 1
fi

echo ""
echo "Step 2/4: Installing fail2ban..."
echo "=================================="

apt update
apt install -y fail2ban

# Create jail.local
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 86400
findtime = 600
maxretry = 3
destemail = root@localhost
sendername = Fail2Ban VPS Alert

[sshd]
enabled = true
port = 22,2222
logpath = /var/log/auth.log
maxretry = 3
bantime = 86400
EOF

# Enable and start fail2ban
systemctl enable fail2ban
systemctl start fail2ban

echo "✅ fail2ban installed and started"

# Ban the current attacker
fail2ban-client set sshd banip 170.64.139.8
echo "✅ Banned attacker IP: 170.64.139.8"

echo ""
echo "Step 3/4: Enabling UFW Firewall..."
echo "==================================="

# Allow SSH before enabling firewall
ufw allow 22/tcp
ufw allow 2222/tcp

# Allow Tailscale
ufw allow in on tailscale0

# Default policies
ufw default deny incoming
ufw default allow outgoing

# Enable firewall
ufw --force enable

echo "✅ UFW firewall enabled"

echo ""
echo "Step 4/4: Final Verification..."
echo "================================"

echo ""
echo "SSH Configuration:"
grep -E '^(PasswordAuthentication|PermitRootLogin|PubkeyAuthentication)' /etc/ssh/sshd_config

echo ""
echo "fail2ban Status:"
fail2ban-client status sshd

echo ""
echo "UFW Status:"
ufw status verbose

echo ""
echo "========================================="
echo "✅ SECURITY HARDENING COMPLETE"
echo "========================================="
echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo ""
echo "1. DO NOT close this SSH session yet"
echo "2. Open a NEW SSH session to verify key-based login works"
echo "3. If new session fails, restore backup:"
echo "   cp /etc/ssh/sshd_config.backup.$(date +%Y%m%d) /etc/ssh/sshd_config"
echo "   systemctl restart sshd"
echo "4. Monitor fail2ban: tail -f /var/log/fail2ban.log"
echo "5. Check banned IPs: fail2ban-client status sshd"
echo ""
echo "Recent attack attempts:"
grep "Failed password" /var/log/auth.log | tail -10
echo ""
echo "tap tap secure secure 🔒"
