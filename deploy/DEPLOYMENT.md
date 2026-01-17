# JARVIS Deployment Guide

Deploy JARVIS for 24/7 autonomous operation on a Linux server (VPS/cloud).

## Quick Start (5 Minutes)

```bash
# 1. Clone to server
git clone <your-repo> /opt/jarvis
cd /opt/jarvis

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Create environment file
cp .env.example .env
nano .env  # Add your credentials

# 4. Run setup script
sudo bash deploy/setup_systemd.sh

# 5. Start service
sudo systemctl start jarvis
```

## Requirements

- **OS**: Ubuntu 20.04+ / Debian 11+ (or any systemd-based Linux)
- **Python**: 3.10+
- **RAM**: 1GB minimum, 2GB recommended
- **Disk**: 5GB free space
- **Network**: Outbound HTTPS (443)

## Environment Variables

Create `/opt/jarvis/.env` with:

```bash
# Required
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_ADMIN_IDS=your-telegram-user-id

# Trading (optional but recommended)
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
WALLET_PRIVATE_KEY=your-wallet-private-key
TREASURY_LIVE_MODE=true

# X/Twitter (optional)
JARVIS_ACCESS_TOKEN=twitter-oauth-token
X_BOT_ENABLED=true

# AI APIs (optional)
XAI_API_KEY=grok-api-key
ANTHROPIC_API_KEY=claude-api-key
GROK_API_KEY=same-as-xai

# External monitoring (optional)
HEALTHCHECKS_URL=https://hc-ping.com/your-uuid
HEARTBEAT_INTERVAL=60
```

## Systemd Commands

```bash
# Start/stop/restart
sudo systemctl start jarvis
sudo systemctl stop jarvis
sudo systemctl restart jarvis

# Check status
sudo systemctl status jarvis

# View logs
journalctl -u jarvis -f         # Follow live
journalctl -u jarvis --since today  # Today's logs
journalctl -u jarvis -n 100     # Last 100 lines

# Enable/disable auto-start
sudo systemctl enable jarvis    # Start on boot
sudo systemctl disable jarvis   # Don't start on boot
```

## External Monitoring

### Healthchecks.io (Recommended - Free)

1. Go to https://healthchecks.io
2. Create new check (name: "Jarvis")
3. Copy the ping URL
4. Add to .env: `HEALTHCHECKS_URL=https://hc-ping.com/your-uuid`

Jarvis will ping every 60 seconds. If it misses 5 minutes, you get alerted.

### BetterStack (Alternative)

1. Go to https://betterstack.com/uptime
2. Create heartbeat monitor
3. Add to .env: `BETTERSTACK_URL=your-heartbeat-url`

## Recommended VPS Providers

| Provider | Min Cost | Notes |
|----------|----------|-------|
| Hetzner | $4/mo | Best value, EU/US |
| DigitalOcean | $4/mo | Easy setup |
| Vultr | $5/mo | Global locations |
| Linode | $5/mo | Good support |

**Recommended specs**: 1 vCPU, 1GB RAM, 25GB SSD

## Security Best Practices

1. **SSH Keys Only**: Disable password auth
2. **Firewall**: Only allow SSH (22) and health endpoint (8080 if needed)
3. **Updates**: `sudo apt update && sudo apt upgrade`
4. **Non-root**: Service runs as `jarvis` user (created by setup script)

```bash
# Basic firewall setup
sudo ufw default deny incoming
sudo ufw allow ssh
sudo ufw allow 8080/tcp  # Optional: health endpoint
sudo ufw enable
```

## Telegram Auto-Responder

When you're away, JARVIS can auto-respond to messages:

```
/away 2h Going for lunch       # Away for 2 hours with message
/away 30m                      # Away for 30 minutes
/away Custom message           # Away indefinitely
/back                          # I'm back
/awaystatus                    # Check status
```

## Troubleshooting

### Service won't start

```bash
# Check logs
journalctl -u jarvis -n 50

# Check permissions
ls -la /opt/jarvis/.env

# Test manually
cd /opt/jarvis && python3 bots/supervisor.py
```

### Missing dependencies

```bash
cd /opt/jarvis
pip3 install -r requirements.txt
```

### Permission denied

```bash
sudo chown -R jarvis:jarvis /opt/jarvis
```

### Can't connect to APIs

Check your .env file has correct tokens and the server has outbound HTTPS access.

## File Locations

| Path | Purpose |
|------|---------|
| `/opt/jarvis/` | Application root |
| `/opt/jarvis/.env` | Environment variables |
| `/opt/jarvis/logs/` | Application logs |
| `/etc/systemd/system/jarvis.service` | Systemd service |
| `~/.lifeos/` | Runtime state files |

## Updates

```bash
cd /opt/jarvis
git pull
pip3 install -r requirements.txt  # If deps changed
sudo systemctl restart jarvis
```

## Estimated Monthly Cost

| Component | Cost |
|-----------|------|
| VPS (1GB) | $4-5 |
| Healthchecks.io | Free |
| Domain (optional) | ~$1 |
| **Total** | **~$5-7/month** |

Free tier APIs (Telegram, most crypto APIs) keep costs minimal.
