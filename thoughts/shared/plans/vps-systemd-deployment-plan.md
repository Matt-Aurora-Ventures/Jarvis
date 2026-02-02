# Feature Plan: VPS Systemd Service Deployment
Created: 2026-01-31
Author: architect-agent

## Overview

Deploy `bots/supervisor.py` as a systemd service on both VPS hosts (72.61.7.126 and srv1302498.hstgr.cloud) to enable 24/7 bot operation independent of SSH sessions. This includes automatic restart on failure, log rotation, and proper security hardening.

## Requirements

- [ ] Supervisor runs 24/7 on VPS without SSH session
- [ ] Automatic restart on crash (max 100 restarts with backoff)
- [ ] Log rotation to prevent disk exhaustion
- [ ] Systemd watchdog integration (already coded in supervisor.py)
- [ ] Security hardening (limited permissions, sandboxing)
- [ ] Easy deployment and rollback procedures
- [ ] Works on both VPS hosts

## Design

### Architecture
```
VPS Host
+-- /etc/systemd/system/jarvis-supervisor.service (service definition)
+-- /home/jarvis/Jarvis/ (code deployment)
|   +-- bots/supervisor.py (entrypoint)
|   +-- .env (consolidated environment)
|   +-- logs/ (application logs)
+-- /var/log/jarvis/ (system logs via journald)
+-- /etc/logrotate.d/jarvis (log rotation config)

Supervisor Process
+-- systemd (manages service lifecycle)
+-- WatchdogSec=300 (5-minute health check)
+-- Restart=always (auto-restart on failure)
+-- RestartSec=10 (10s delay between restarts)
```

### Key Files

| File | Location | Purpose |
|------|----------|---------|
| jarvis-supervisor.service | /etc/systemd/system/ | Systemd unit file |
| install-vps.sh | deploy/ | Installation script |
| uninstall-vps.sh | deploy/ | Rollback script |
| jarvis-logrotate | /etc/logrotate.d/ | Log rotation config |

### Data Flow
1. systemd starts jarvis-supervisor.service on boot
2. supervisor.py loads .env and starts all bot components
3. Each component runs as coroutine with independent crash recovery
4. Watchdog pings systemd every 60s (health monitor interval)
5. If no ping for 300s (5 min), systemd restarts the service
6. journald captures stdout/stderr, logrotate manages log files

## Dependencies

| Dependency | Type | Reason |
|------------|------|--------|
| Python 3.11+ | System | Runtime for supervisor.py |
| systemd | System | Service management |
| logrotate | System | Log rotation |
| .env file | Config | Environment variables |
| jarvis user | System | Non-root service account |

## Implementation Phases

### Phase 1: Service Definition
**Files to create:**
- `deploy/jarvis-supervisor.service` - Enhanced systemd unit
- `deploy/jarvis-logrotate` - Log rotation config

**Acceptance:**
- [ ] Service file passes systemd-analyze verify
- [ ] Logrotate config passes syntax check
- [ ] Watchdog integration confirmed

**Estimated effort:** Small

### Phase 2: Installation Script
**Files to create:**
- `deploy/install-vps.sh` - Full installation script
- `deploy/uninstall-vps.sh` - Rollback script

**Dependencies:** Phase 1

**Acceptance:**
- [ ] Script creates jarvis user if missing
- [ ] Script sets correct permissions
- [ ] Script enables service for boot
- [ ] Rollback script cleanly removes service

**Estimated effort:** Medium

### Phase 3: Deployment
**Actions:**
- Deploy to 72.61.7.126 (main Jarvis VPS)
- Deploy to srv1302498.hstgr.cloud (ClawdBot gateway) 
- Verify both are running

**Dependencies:** Phase 2

**Acceptance:**
- [ ] Service running on both hosts
- [ ] Survives reboot
- [ ] Auto-restarts after kill -9

**Estimated effort:** Medium

### Phase 4: Monitoring and Verification
**Files to create:**
- `scripts/check-vps-health.sh` - Remote health check script

**Verification procedures:**
- [ ] Log rotation working (check after 24h)
- [ ] Memory usage stable over time
- [ ] Watchdog triggering on hangs

**Estimated effort:** Small

## Deliverables

### 1. jarvis-supervisor.service

```ini
[Unit]
Description=Jarvis LifeOS Supervisor - Autonomous Trading & Social AI
Documentation=https://github.com/lucid/jarvis
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
NotifyAccess=all
User=jarvis
Group=jarvis
WorkingDirectory=/home/jarvis/Jarvis

# Environment
EnvironmentFile=/home/jarvis/Jarvis/.env

# Execution
ExecStart=/usr/bin/python3 bots/supervisor.py
ExecReload=/bin/kill -HUP $MAINPID

# Restart policy
Restart=always
RestartSec=10
StartLimitIntervalSec=600
StartLimitBurst=10

# Timeouts
TimeoutStartSec=60
TimeoutStopSec=30

# Watchdog - supervisor.py sends WATCHDOG=1 every 60s
# If no ping for 300s (5 min), systemd restarts
WatchdogSec=300

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
ReadWritePaths=/home/jarvis/Jarvis/logs /home/jarvis/Jarvis/data /home/jarvis/Jarvis/.lifeos /tmp

# Resource limits
MemoryMax=4G
CPUQuota=90%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=jarvis-supervisor

[Install]
WantedBy=multi-user.target
```

### 2. jarvis-logrotate

```
/home/jarvis/Jarvis/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 640 jarvis jarvis
    sharedscripts
    postrotate
        systemctl kill -s HUP jarvis-supervisor.service 2>/dev/null || true
    endscript
}

/var/log/jarvis/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 640 jarvis jarvis
}
```


## Deployment Procedure

### Step-by-Step for VPS 72.61.7.126 (Main Jarvis)

```bash
# 1. From local machine, sync code to VPS
cd /path/to/Jarvis
rsync -avz --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
    ./ jarvis@72.61.7.126:~/Jarvis/

# 2. Copy deployment scripts
scp deploy/jarvis-supervisor.service deploy/install-vps.sh deploy/uninstall-vps.sh \
    jarvis@72.61.7.126:~/deploy/

# 3. SSH to VPS and run installation
ssh root@72.61.7.126
cd /home/jarvis
bash deploy/install-vps.sh

# 4. Create/consolidate .env file
nano /home/jarvis/Jarvis/.env
# Add all required environment variables
chown jarvis:jarvis /home/jarvis/Jarvis/.env
chmod 600 /home/jarvis/Jarvis/.env

# 5. Start the service
systemctl start jarvis-supervisor

# 6. Verify running
systemctl status jarvis-supervisor
journalctl -u jarvis-supervisor -f
```

### Step-by-Step for VPS srv1302498.hstgr.cloud (ClawdBot Gateway)

Same process, but note from BOOTSTRAP_VPS.md that this host may not have systemd.

```bash
# Check if systemd is available
ssh root@srv1302498.hstgr.cloud 'systemctl --version'

# If no systemd, use nohup approach:
cd /root/clawd/Jarvis
set -a; . .env; set +a
nohup python3 bots/supervisor.py > logs/supervisor.out.log 2> logs/supervisor.err.log &
echo $! > run/supervisor.pid
```

## Testing Procedures

### 1. Basic Service Test
```bash
# Start service
sudo systemctl start jarvis-supervisor

# Check running
sudo systemctl status jarvis-supervisor

# Check logs
sudo journalctl -u jarvis-supervisor -n 50
```

### 2. Restart on Crash Test
```bash
# Find the supervisor process
ps aux | grep supervisor.py

# Kill it (simulating crash)
sudo kill -9 $(pgrep -f 'bots/supervisor.py')

# Wait 15 seconds and check it restarted
sleep 15
sudo systemctl status jarvis-supervisor
# Should show active (running)
```

### 3. Watchdog Test
```bash
# View watchdog status
systemctl show jarvis-supervisor | grep -i watchdog

# Simulate a hang (careful in production)
# The watchdog should restart after 5 minutes of no ping
```

### 4. Reboot Persistence Test
```bash
# Reboot the VPS
sudo reboot

# After reboot, SSH back in and check
sudo systemctl status jarvis-supervisor
# Should be running
```

### 5. Log Rotation Test
```bash
# Force log rotation
sudo logrotate -f /etc/logrotate.d/jarvis

# Check rotated logs
ls -la /home/jarvis/Jarvis/logs/
# Should see .log.1.gz files
```


## Rollback Plan

If something goes wrong:

### Quick Rollback (< 5 minutes)
```bash
# 1. Stop the broken service immediately
sudo systemctl stop jarvis-supervisor

# 2. Disable to prevent boot issues
sudo systemctl disable jarvis-supervisor

# 3. Fall back to manual nohup mode
cd /home/jarvis/Jarvis
set -a; . .env; set +a
nohup python3 bots/supervisor.py > logs/supervisor.out.log 2>&1 &
echo $! > run/supervisor.pid
```

### Full Rollback
```bash
# Run the uninstall script
sudo bash /home/jarvis/deploy/uninstall-vps.sh --keep-data

# Service is now removed, data preserved
# Can run manually with nohup until issue is fixed
```

### Common Issues and Fixes

| Issue | Symptom | Fix |
|-------|---------|-----|
| Service wont start | Exit code 1 | Check journalctl for Python errors |
| Permission denied | Exit code 217 | chown -R jarvis:jarvis /home/jarvis/Jarvis |
| .env not found | Exit code 237 | Create .env file and set permissions |
| Memory limit hit | OOM killed | Increase MemoryMax in service file |
| Watchdog timeout | Constant restarts | Check if supervisor.py is hanging |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| VPS reboot during trading | High | Supervisor auto-restarts; positions persist in .lifeos/trading/ |
| Memory leak over time | Medium | MemoryMax=4G limit + weekly service restart via cron |
| Log disk exhaustion | High | Logrotate configured for 7-day retention |
| Conflicting instances | High | SingleInstanceLock prevents multiple supervisors |
| Env vars missing | High | Validation on startup catches missing critical vars |

## Open Questions

- [ ] Should srv1302498.hstgr.cloud run the same supervisor or a different subset of bots?
- [ ] Is 4GB MemoryMax sufficient? Need to monitor over time.
- [ ] Should we add Healthchecks.io integration for external monitoring?

## Success Criteria

1. Service running 24/7 without SSH session
2. Auto-restart within 10 seconds of crash
3. Survives VPS reboot
4. Logs rotated daily, 7-day retention
5. Memory usage stable (no leaks)
6. Watchdog correctly detects hangs

