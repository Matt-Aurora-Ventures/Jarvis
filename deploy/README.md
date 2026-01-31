# JARVIS Systemd Service Deployment

This directory contains systemd service units and deployment scripts for running JARVIS in production.

## Deployment Modes

### 1. Supervisor Mode (Recommended for Most Users)

Single systemd service that runs `supervisor.py`, which orchestrates all bot components.

**Pros:**
- Simple deployment (one service to manage)
- Supervisor handles inter-bot coordination
- Unified logging and error handling
- Resource sharing between components

**Cons:**
- Single point of failure (if supervisor crashes, all bots stop)
- Harder to isolate resource usage per component

**Files:**
- `jarvis.service` - Main supervisor service

**Install:**
```bash
sudo ./deploy/install-services.sh --supervisor-only
sudo systemctl start jarvis
```

### 2. Split Services Mode (Recommended for Production)

Each bot component runs as an independent systemd service with its own lifecycle.

**Pros:**
- Fault isolation (one bot crash doesn't affect others)
- Independent resource limits per component
- Can restart individual services without affecting others
- Better observability (separate logs per service)

**Cons:**
- More complex deployment (5 services to manage)
- Requires manual coordination (e.g., only one can poll Telegram)

**Files:**
- `jarvis.target` - Groups all services
- `jarvis-telegram.service` - Telegram bot gateway
- `jarvis-sentiment.service` - Sentiment reporter
- `jarvis-twitter.service` - Twitter/X autonomous poster
- `jarvis-buytracker.service` - Buy tracker bot
- `jarvis-treasury.service` - Treasury trading bot

**Install:**
```bash
sudo ./deploy/install-services.sh --split-services
sudo systemctl start jarvis.target
```

## Service Features

All services include:

✅ **Auto-restart:** `Restart=always` with 10-20s delays
✅ **Watchdog monitoring:** systemd restarts if no heartbeat
✅ **Resource limits:** Memory (512M-2G) and CPU (30-80%) quotas
✅ **Security hardening:** NoNewPrivileges, ProtectSystem, PrivateTmp
✅ **Systemd journal logging:** Centralized logging via journalctl
✅ **Environment isolation:** Reads from `/opt/jarvis/.env`

## Prerequisites

1. **System Requirements:**
   - Linux with systemd (Ubuntu 20.04+, Debian 11+, CentOS 8+)
   - Python 3.9+
   - User `jarvis` created: `sudo useradd -r -m -d /opt/jarvis jarvis`

2. **Installation Directory:**
   ```bash
   sudo mkdir -p /opt/jarvis
   sudo cp -r . /opt/jarvis/
   sudo chown -R jarvis:jarvis /opt/jarvis
   ```

3. **Environment File:**
   Create `/opt/jarvis/.env` with:
   ```bash
   TELEGRAM_BOT_TOKEN=...
   XAI_API_KEY=...
   HELIUS_API_KEY=...
   # ... (see .env.template)
   ```

4. **Dependencies:**
   ```bash
   cd /opt/jarvis
   sudo -u jarvis python3 -m pip install -r requirements.txt
   ```

## Installation

```bash
# 1. Clone or copy JARVIS to /opt/jarvis
sudo cp -r /path/to/Jarvis /opt/jarvis
sudo chown -R jarvis:jarvis /opt/jarvis

# 2. Configure environment
sudo cp /opt/jarvis/.env.template /opt/jarvis/.env
sudo nano /opt/jarvis/.env  # Edit with your API keys

# 3. Install systemd services
cd /opt/jarvis
sudo chmod +x deploy/install-services.sh
sudo ./deploy/install-services.sh --supervisor-only

# 4. Start JARVIS
sudo systemctl start jarvis
sudo systemctl status jarvis
```

## Management Commands

### Supervisor Mode

```bash
# Start/stop/restart
sudo systemctl start jarvis
sudo systemctl stop jarvis
sudo systemctl restart jarvis

# Enable auto-start on boot
sudo systemctl enable jarvis

# View logs
sudo journalctl -u jarvis -f
sudo journalctl -u jarvis --since "1 hour ago"

# Check status
sudo systemctl status jarvis
```

### Split Services Mode

```bash
# Start all services
sudo systemctl start jarvis.target

# Stop all services
sudo systemctl stop jarvis.target

# Restart individual service
sudo systemctl restart jarvis-telegram.service

# View logs for all services
sudo journalctl -u 'jarvis-*' -f

# View logs for specific service
sudo journalctl -u jarvis-twitter -f

# Check status of all services
sudo systemctl status 'jarvis-*'

# Enable auto-start
sudo systemctl enable jarvis.target
```

## Watchdog Monitoring

All services support systemd watchdog monitoring:

- **Supervisor Mode:** `WatchdogSec=300` (5 minutes)
  - Supervisor pings systemd every minute via `systemd_notify("WATCHDOG=1")`
  - If no ping received in 5 minutes, systemd restarts the service

- **Split Services Mode:** Various watchdog timeouts per component
  - Telegram: 5 minutes
  - Sentiment: 1 hour (runs on schedule)
  - Twitter: 1 hour (runs on schedule)
  - BuyTracker: 10 minutes
  - Treasury: 10 minutes

If a bot hangs or deadlocks, systemd will automatically restart it.

## Resource Limits

| Service | Memory Limit | CPU Quota |
|---------|--------------|-----------|
| Supervisor (all bots) | 2G | 80% |
| Telegram | 1G | 50% |
| Sentiment | 512M | 30% |
| Twitter | 512M | 30% |
| BuyTracker | 512M | 30% |
| Treasury | 1G | 50% |

Adjust limits in service files if needed.

## Security Hardening

All services include:

```ini
NoNewPrivileges=true          # Prevents privilege escalation
ProtectSystem=strict          # Read-only /usr, /boot, /efi
ProtectHome=read-only         # Read-only home directories
ReadWritePaths=/opt/jarvis    # Explicit write permission needed
PrivateTmp=true               # Isolated /tmp directory
```

## Troubleshooting

### Service fails to start

1. Check logs:
   ```bash
   sudo journalctl -u jarvis -n 50
   ```

2. Verify .env file exists and is readable:
   ```bash
   sudo ls -la /opt/jarvis/.env
   sudo cat /opt/jarvis/.env  # Check for missing keys
   ```

3. Test manually:
   ```bash
   sudo -u jarvis -i
   cd /opt/jarvis
   python3 bots/supervisor.py  # Should start without errors
   ```

### Watchdog timeout (service keeps restarting)

Check if the bot is hanging:
```bash
sudo journalctl -u jarvis --since "1 hour ago" | grep -i watchdog
```

Increase `WatchdogSec` in the service file if legitimate long operations occur.

### High resource usage

Check resource consumption:
```bash
systemctl status jarvis  # Shows current memory/CPU
journalctl -u jarvis | grep -i memory
```

Adjust `MemoryMax` and `CPUQuota` in service files.

### Conflict errors (Telegram polling)

Only one service can poll Telegram at a time. If using split services mode, ensure:
- Only `jarvis-telegram.service` is running
- Disable other bots' Telegram polling via environment variables

## Migration from Supervisor to Split Services

1. Stop supervisor:
   ```bash
   sudo systemctl stop jarvis
   sudo systemctl disable jarvis
   ```

2. Install split services:
   ```bash
   sudo ./deploy/install-services.sh --split-services
   ```

3. Start services:
   ```bash
   sudo systemctl start jarvis.target
   ```

4. Verify all running:
   ```bash
   sudo systemctl status 'jarvis-*'
   ```

## References

- [systemd Service Documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [systemd Watchdog](https://www.freedesktop.org/software/systemd/man/sd_notify.html)
- [Security Hardening](https://www.freedesktop.org/software/systemd/man/systemd.exec.html#Security)

---

**Last Updated:** 2026-01-31
**Status:** Production-Ready ✅
