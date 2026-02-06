# VPS Hardening Guide

**Purpose:** Security hardening procedures for Jarvis VPS servers
**Last Updated:** 2026-01-31
**Target Systems:**
- VPS 72.61.7.126 (Main Jarvis)
- VPS 76.13.106.100 (ClawdBot Gateway)

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [fail2ban Implementation](#fail2ban-implementation)
3. [UFW Firewall Configuration](#ufw-firewall-configuration)
4. [SSH Hardening](#ssh-hardening)
5. [System Updates](#system-updates)
6. [File Permissions](#file-permissions)
7. [Secrets Encryption](#secrets-encryption)
8. [Monitoring & Alerts](#monitoring--alerts)
9. [Incident Response](#incident-response)
10. [Compliance Checklist](#compliance-checklist)

---

## Security Overview

### Current Threat Landscape

**Detected Attack (2026-01-31 10:39 UTC):**
- Brute force SSH attempt on 72.61.7.126
- Multiple failed login attempts
- Source: Unknown attacker
- Response: Documented in `docs/SECURITY_AUDIT_BRUTE_FORCE_JAN_31.md`

### Defense Layers

1. **Network Layer:** UFW firewall, rate limiting
2. **Access Layer:** SSH key-only auth, fail2ban
3. **Application Layer:** Secrets encryption, environment isolation
4. **Data Layer:** Encrypted secrets, masked logs
5. **Monitoring Layer:** Alert system, log aggregation

---

## fail2ban Implementation

### Installation

```bash
# Install fail2ban
sudo apt-get update
sudo apt-get install -y fail2ban

# Verify installation
fail2ban-client --version
```

### Configuration

Create `/etc/fail2ban/jail.local`:

```ini
[DEFAULT]
# Ban time: 1 hour
bantime = 3600

# Find time window: 10 minutes
findtime = 600

# Max retries before ban
maxretry = 3

# Email alerts (optional)
destemail = admin@jarvis-system.com
sendername = Fail2Ban
action = %(action_mwl)s

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600

[sshd-ddos]
enabled = true
port = ssh
filter = sshd-ddos
logpath = /var/log/auth.log
maxretry = 5
bantime = 600

# Custom: API rate limiting (if applicable)
[jarvis-api]
enabled = true
port = 5000,5001
filter = jarvis-api
logpath = /home/jarvis/Jarvis/logs/*.log
maxretry = 10
findtime = 60
bantime = 600
```

### Custom Filter for Jarvis API

Create `/etc/fail2ban/filter.d/jarvis-api.conf`:

```ini
[Definition]
failregex = ^<HOST> .* "GET /api/.* HTTP/.*" 429 .*$
            ^<HOST> .* "POST /api/.* HTTP/.*" 401 .*$
            ^<HOST> .* "POST /api/.* HTTP/.*" 403 .*$

ignoreregex =
```

### Start and Enable

```bash
# Start fail2ban
sudo systemctl start fail2ban
sudo systemctl enable fail2ban

# Verify status
sudo fail2ban-client status

# Check SSH jail
sudo fail2ban-client status sshd
```

### Testing

```bash
# Simulate failed SSH attempts (from another machine)
# After 3 failures, IP should be banned

# Check banned IPs
sudo fail2ban-client status sshd

# Unban an IP (if needed)
sudo fail2ban-client set sshd unbanip 1.2.3.4
```

### Monitoring

```bash
# Watch fail2ban log
sudo tail -f /var/log/fail2ban.log

# List all banned IPs
sudo zgrep 'Ban' /var/log/fail2ban.log*

# Statistics
sudo fail2ban-client status | grep "Jail list"
```

---

## UFW Firewall Configuration

### Installation

```bash
# Install UFW
sudo apt-get install -y ufw

# Verify installation
ufw --version
```

### Basic Configuration

```bash
# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (IMPORTANT: Do this before enabling!)
sudo ufw allow ssh
# Or specific port:
# sudo ufw allow 22/tcp

# Allow HTTP/HTTPS (if web interface needed)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow custom ports (Jarvis services)
sudo ufw allow 5000/tcp comment 'Jarvis Control Deck'
sudo ufw allow 5001/tcp comment 'Jarvis Trading Web'
sudo ufw allow 18789/tcp comment 'ClawdBot Gateway'
sudo ufw allow 18791/tcp comment 'ClawdBot Browser Control'

# Enable firewall
sudo ufw enable

# Verify status
sudo ufw status verbose
```

### Advanced Rules

```bash
# Rate limiting for SSH (prevent brute force)
sudo ufw limit ssh/tcp comment 'SSH rate limit'

# Allow from specific IP only
sudo ufw allow from 1.2.3.4 to any port 22 comment 'Trusted IP SSH'

# Allow subnet
sudo ufw allow from 192.168.1.0/24 to any port 22 comment 'Local network'

# Block specific IP
sudo ufw deny from 1.2.3.4 comment 'Blocked attacker'

# Delete rule (by number)
sudo ufw status numbered
sudo ufw delete 5
```

### Application Profiles

Create `/etc/ufw/applications.d/jarvis`:

```ini
[Jarvis-Web]
title=Jarvis Web Interfaces
description=Trading and Control Deck
ports=5000,5001/tcp

[ClawdBot-Gateway]
title=ClawdBot Gateway
description=WebSocket and browser control
ports=18789,18791/tcp

[Jarvis-Full]
title=Jarvis Full Stack
description=All Jarvis services
ports=5000,5001,18789,18791/tcp
```

Then allow by profile:

```bash
sudo ufw allow Jarvis-Full
```

### Logging

```bash
# Enable logging
sudo ufw logging on

# Set log level (low, medium, high, full)
sudo ufw logging medium

# View logs
sudo tail -f /var/log/ufw.log
```

---

## SSH Hardening

### Generate SSH Key (Client Side)

```bash
# On your local machine
ssh-keygen -t ed25519 -C "jarvis-vps-access"

# Follow prompts, use strong passphrase
# Key will be saved to ~/.ssh/id_ed25519
```

### Copy Key to VPS

```bash
# Method 1: ssh-copy-id
ssh-copy-id -i ~/.ssh/id_ed25519.pub root@72.61.7.126

# Method 2: Manual
cat ~/.ssh/id_ed25519.pub | ssh root@72.61.7.126 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

### Disable Password Authentication

Edit `/etc/ssh/sshd_config`:

```bash
sudo nano /etc/ssh/sshd_config
```

Make these changes:

```ini
# Disable password authentication
PasswordAuthentication no
PermitEmptyPasswords no

# Disable root login (optional, create sudo user first)
PermitRootLogin prohibit-password
# Or completely disable:
# PermitRootLogin no

# Use key-based auth only
PubkeyAuthentication yes

# Disable unused features
ChallengeResponseAuthentication no
UsePAM yes

# Change default port (optional - security through obscurity)
# Port 2222

# Limit SSH access to specific users
AllowUsers jarvis-admin

# Disable X11 forwarding if not needed
X11Forwarding no

# Set login grace time
LoginGraceTime 30

# Max authentication attempts
MaxAuthTries 3

# Disconnect idle sessions
ClientAliveInterval 300
ClientAliveCountMax 2
```

Restart SSH:

```bash
sudo systemctl restart sshd

# Verify config before restart
sudo sshd -t
```

### Test Key-Based Login

```bash
# From local machine
ssh -i ~/.ssh/id_ed25519 root@72.61.7.126

# If successful, password auth is no longer needed
```

### SSH Client Config (Optional)

Create/edit `~/.ssh/config` on local machine:

```ini
Host jarvis-vps
    HostName 72.61.7.126
    User root
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3

Host clawdbot-vps
    HostName 76.13.106.100
    User root
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

Then connect with:

```bash
ssh jarvis-vps
```

---

## System Updates

### Automated Updates

Install unattended-upgrades:

```bash
sudo apt-get install -y unattended-upgrades apt-listchanges

# Configure
sudo dpkg-reconfigure -plow unattended-upgrades
```

Edit `/etc/apt/apt.conf.d/50unattended-upgrades`:

```ini
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    "${distro_id}:${distro_codename}-updates";
};

Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";

Unattended-Upgrade::Mail "admin@jarvis-system.com";
Unattended-Upgrade::MailReport "on-change";
```

### Manual Updates

```bash
# Update package list
sudo apt-get update

# Upgrade packages
sudo apt-get upgrade -y

# Full distribution upgrade
sudo apt-get dist-upgrade -y

# Remove old packages
sudo apt-get autoremove -y
sudo apt-get autoclean

# Check for required reboot
if [ -f /var/run/reboot-required ]; then
    echo "Reboot required"
    cat /var/run/reboot-required.pkgs
fi
```

### Update Script

Create `/root/scripts/update.sh`:

```bash
#!/bin/bash
# Automated update script

echo "Starting system update..."
apt-get update
apt-get upgrade -y
apt-get dist-upgrade -y
apt-get autoremove -y
apt-get autoclean

# Update Python packages (if needed)
# pip install --upgrade pip
# pip install -r /home/jarvis/Jarvis/requirements.txt --upgrade

echo "Update complete."

# Check reboot requirement
if [ -f /var/run/reboot-required ]; then
    echo "REBOOT REQUIRED"
    cat /var/run/reboot-required.pkgs
fi
```

Schedule with cron:

```bash
# Run weekly on Sundays at 3am
0 3 * * 0 /root/scripts/update.sh >> /var/log/system-updates.log 2>&1
```

---

## File Permissions

### Critical Files

```bash
# Secrets directory
chmod 700 /home/jarvis/Jarvis/secrets
chmod 600 /home/jarvis/Jarvis/secrets/*

# Environment files
chmod 600 /home/jarvis/Jarvis/lifeos/config/.env
chmod 600 /home/jarvis/Jarvis/bots/twitter/.env
chmod 600 /home/jarvis/Jarvis/tg_bot/.env

# SSH keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
chmod 600 ~/.ssh/id_*
chmod 644 ~/.ssh/*.pub

# Logs (readable by owner only)
chmod 700 /home/jarvis/Jarvis/logs
chmod 600 /home/jarvis/Jarvis/logs/*
```

### Verify Permissions

```bash
# Check secrets
find /home/jarvis/Jarvis/secrets -type f -exec ls -la {} \;

# Check .env files
find /home/jarvis/Jarvis -name ".env" -exec ls -la {} \;

# Check for world-readable secrets
find /home/jarvis/Jarvis -type f \( -name "*.key" -o -name "*.pem" -o -name "*secret*" \) -perm /o+r
```

---

## Secrets Encryption

### Using age (Modern Encryption)

```bash
# Install age
sudo apt-get install -y age

# Generate key
age-keygen -o /root/.age/key.txt
chmod 600 /root/.age/key.txt

# Encrypt secrets
age -r $(age-keygen -y /root/.age/key.txt) -o /root/secrets/keys.json.age /home/jarvis/Jarvis/secrets/keys.json

# Decrypt (when needed)
age -d -i /root/.age/key.txt /root/secrets/keys.json.age > /tmp/keys.json
```

### Automated Secrets Management

Create `/root/scripts/rotate-secrets.sh`:

```bash
#!/bin/bash
# Secret rotation script

# Backup current secrets (encrypted)
age -r $(age-keygen -y /root/.age/key.txt) \
    -o /root/backups/secrets-$(date +%Y%m%d).json.age \
    /home/jarvis/Jarvis/secrets/keys.json

# Keep only last 7 backups
find /root/backups -name "secrets-*.json.age" -mtime +7 -delete

echo "Secrets backed up to /root/backups/secrets-$(date +%Y%m%d).json.age"
```

Run daily:

```bash
0 2 * * * /root/scripts/rotate-secrets.sh >> /var/log/secret-rotation.log 2>&1
```

---

## Monitoring & Alerts

### Logwatch

```bash
# Install
sudo apt-get install -y logwatch

# Configure
sudo nano /etc/logwatch/conf/logwatch.conf
```

Set:

```ini
MailTo = admin@jarvis-system.com
Range = yesterday
Detail = Med
Service = All
```

### Monitoring Script

Create `/root/scripts/monitor.sh`:

```bash
#!/bin/bash
# System monitoring

# Disk space alert
df -H | grep -vE '^Filesystem|tmpfs|cdrom' | awk '{ print $5 " " $1 }' | while read output;
do
  usage=$(echo $output | awk '{ print $1}' | cut -d'%' -f1)
  partition=$(echo $output | awk '{ print $2 }')
  if [ $usage -ge 90 ]; then
    echo "ALERT: Partition $partition is ${usage}% full" | mail -s "Disk Space Alert" admin@jarvis-system.com
  fi
done

# Memory alert
mem_usage=$(free | grep Mem | awk '{print ($3/$2) * 100.0}' | cut -d. -f1)
if [ $mem_usage -ge 90 ]; then
  echo "ALERT: Memory usage is ${mem_usage}%" | mail -s "Memory Alert" admin@jarvis-system.com
fi

# Service checks
services=("supervisor" "postgresql" "redis")
for service in "${services[@]}"; do
  if ! systemctl is-active --quiet $service; then
    echo "ALERT: Service $service is not running" | mail -s "Service Alert" admin@jarvis-system.com
  fi
done
```

Run every hour:

```bash
0 * * * * /root/scripts/monitor.sh
```

---

## Incident Response

### Immediate Actions (If Compromised)

1. **Isolate System**
   ```bash
   # Block all incoming connections
   sudo ufw default deny incoming
   sudo ufw reload
   ```

2. **Kill Suspicious Processes**
   ```bash
   # List processes
   ps aux | grep -v "^\[" | sort -nrk 3,3 | head -n 20

   # Kill if needed
   sudo kill -9 <PID>
   ```

3. **Change All Credentials**
   - Generate new SSH keys
   - Rotate all API tokens
   - Change database passwords

4. **Check for Modifications**
   ```bash
   # Check recently modified files
   find /home/jarvis/Jarvis -type f -mtime -1 -ls

   # Check git status
   cd /home/jarvis/Jarvis
   git status
   git diff
   ```

5. **Review Logs**
   ```bash
   # SSH attempts
   sudo grep "Failed password" /var/log/auth.log

   # Successful logins
   sudo grep "Accepted publickey" /var/log/auth.log

   # System logs
   sudo journalctl -u sshd --since "1 hour ago"
   ```

6. **Document Everything**
   - Take screenshots
   - Save logs to external location
   - Create incident report

---

## Compliance Checklist

### Security Baseline

- [ ] fail2ban installed and configured
- [ ] UFW firewall enabled and rules set
- [ ] SSH key-only authentication
- [ ] Password authentication disabled
- [ ] Root login restricted
- [ ] System updates automated
- [ ] Secrets encrypted at rest
- [ ] File permissions hardened
- [ ] Monitoring alerts configured
- [ ] Backup strategy implemented
- [ ] Incident response plan documented
- [ ] Security audit log maintained

### Monthly Review

- [ ] Review fail2ban logs
- [ ] Audit UFW rules
- [ ] Check for security updates
- [ ] Rotate secrets/tokens
- [ ] Review access logs
- [ ] Test backup restoration
- [ ] Update documentation
- [ ] Security training (if team)

### Quarterly Audit

- [ ] Penetration testing
- [ ] Dependency vulnerability scan
- [ ] Access control review
- [ ] Disaster recovery drill
- [ ] Compliance verification
- [ ] Third-party audit (optional)

---

## Additional Resources

- fail2ban Documentation: https://www.fail2ban.org/
- UFW Guide: https://help.ubuntu.com/community/UFW
- SSH Hardening: https://www.ssh.com/academy/ssh/config
- Age Encryption: https://github.com/FiloSottile/age

---

**Last Review:** 2026-01-31
**Next Review:** 2026-02-28
**Maintained By:** Jarvis Security Team
