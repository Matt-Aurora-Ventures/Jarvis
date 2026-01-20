# Backup and Recovery Guide

## Overview

Jarvis includes a comprehensive backup and recovery system to protect critical trading state and configuration.

## Quick Start

### Create a Backup

```bash
# Quick position backup before risky operation
python scripts/backup_positions.py

# Full system backup
python scripts/backup_positions.py --type full --description "Pre-deployment backup"

# Emergency backup
python scripts/backup_positions.py --emergency
```

### List Backups

```bash
# List all backups
python scripts/restore_backup.py --list

# List only position backups
python scripts/restore_backup.py --list --type positions_only
```

### Restore from Backup

```bash
# Dry run (simulate restore)
python scripts/restore_backup.py --latest --dry-run

# Restore latest backup
python scripts/restore_backup.py --latest

# Restore specific backup
python scripts/restore_backup.py --restore full_20260119_120000

# Restore only positions (not config)
python scripts/restore_backup.py --latest --files positions exit_intents
```

### Verify Backup Integrity

```bash
python scripts/restore_backup.py --verify full_20260119_120000
```

## What Gets Backed Up

### Critical Files

The backup system automatically backs up:

| File | Description | Backup Type |
|------|-------------|-------------|
| `bots/treasury/.positions.json` | Active trading positions | positions_only, full |
| `~/.lifeos/trading/exit_intents.json` | Exit orders and intents | positions_only, full |
| `bots/twitter/.grok_state.json` | Grok AI state and costs | full |
| `bots/supervisor_config.json` | Supervisor configuration | config_only, full |
| `bots/treasury/config.json` | Treasury settings | config_only, full |
| `tg_bot/config.py` | Telegram bot config | config_only, full |

### Backup Types

- **full**: All critical files (positions + config)
- **positions_only**: Only trading state (positions, exit intents)
- **config_only**: Only configuration files
- **incremental**: Same as full (supports future incremental logic)

## Automated Backups

### Setup Scheduled Backups

```bash
# Every 6 hours (default)
python scripts/scheduled_backup.py

# Custom interval
python scripts/scheduled_backup.py --interval 4

# Daily at 2 AM
python scripts/scheduled_backup.py --daily --daily-hour 2

# Positions only, every 2 hours
python scripts/scheduled_backup.py --interval 2 --type positions_only
```

### Integrate with Supervisor

Add to `bots/supervisor.py` configuration:

```python
# Add backup component
components = [
    # ... existing components ...
    {
        "name": "backup_scheduler",
        "module": "scripts.scheduled_backup",
        "function": "BackupScheduler",
        "kwargs": {
            "interval_hours": 6,
            "backup_type": "incremental"
        },
        "health_check": None,
        "restart_on_failure": True
    }
]
```

## Recovery Scenarios

### Scenario 1: Corrupted Position State

**Problem**: `.positions.json` is corrupted or has invalid data

**Solution**:
```bash
# 1. Verify latest backup
python scripts/restore_backup.py --verify $(python scripts/restore_backup.py --list | head -2 | tail -1 | awk '{print $1}')

# 2. Restore positions (dry run first)
python scripts/restore_backup.py --latest --files positions --dry-run

# 3. Restore for real
python scripts/restore_backup.py --latest --files positions
```

### Scenario 2: Accidental Configuration Change

**Problem**: Changed config and system is broken

**Solution**:
```bash
# Restore config files from before the change
python scripts/restore_backup.py --type config_only --latest

# Or restore from specific time
python scripts/restore_backup.py --list --type config_only
python scripts/restore_backup.py --restore config_only_20260119_100000
```

### Scenario 3: Complete System Recovery

**Problem**: Need to restore entire system state

**Solution**:
```bash
# 1. Stop all bots
pkill -f supervisor.py

# 2. List available backups
python scripts/restore_backup.py --list --type full

# 3. Verify backup integrity
python scripts/restore_backup.py --verify full_20260119_120000

# 4. Restore (with confirmation)
python scripts/restore_backup.py --restore full_20260119_120000

# 5. Restart system
python bots/supervisor.py
```

### Scenario 4: Rollback After Bad Trades

**Problem**: Want to restore positions from before a series of bad trades

**Solution**:
```bash
# 1. Find backup from before the trades
python scripts/restore_backup.py --list

# 2. Check what's in that backup
python scripts/restore_backup.py --verify positions_only_20260119_080000

# 3. Restore (positions only)
python scripts/restore_backup.py --restore positions_only_20260119_080000 --files positions exit_intents
```

## Backup Rotation and Cleanup

### Automatic Cleanup

The backup system automatically cleans up old backups based on:
- **Retention period**: 30 days (default)
- **Max backups**: 100 (default)

### Manual Cleanup

```bash
# Preview cleanup (dry run)
python scripts/restore_backup.py --cleanup --dry-run

# Actually delete old backups
python scripts/restore_backup.py --cleanup
```

### Custom Retention Policy

```python
from core.backup_manager import BackupManager

manager = BackupManager(
    retention_days=60,  # Keep for 60 days
    max_backups=200     # Keep max 200 backups
)
```

## Programmatic Usage

### Python API

```python
from core.backup_manager import BackupManager

# Create manager
manager = BackupManager()

# Create backup
metadata = manager.create_backup(
    backup_type="full",
    description="Before strategy change"
)
print(f"Created backup: {metadata.backup_id}")

# List backups
backups = manager.list_backups(backup_type="positions_only")
for backup in backups:
    print(f"{backup.backup_id}: {backup.timestamp} ({backup.size_bytes} bytes)")

# Restore
results = manager.restore_backup(
    backup_id="full_20260119_120000",
    dry_run=False
)
print(f"Restored {len(results['restored_files'])} files")

# Verify
verify_results = manager.verify_backup("full_20260119_120000")
if verify_results["valid"]:
    print("Backup is valid")
```

### Emergency Backup Helper

```python
from core.backup_manager import create_emergency_backup

# Quick emergency backup before risky operation
metadata = create_emergency_backup("About to deploy new strategy")
```

## Backup Storage Location

Default: `~/.lifeos/backups/`

Structure:
```
~/.lifeos/backups/
├── backup_metadata.json          # Global metadata
├── full_20260119_120000/
│   ├── metadata.json              # Backup-specific metadata
│   ├── bots_treasury_.positions.json
│   ├── exit_intents.json
│   └── ...
├── positions_only_20260119_130000/
│   ├── metadata.json
│   └── bots_treasury_.positions.json
└── ...
```

### Custom Backup Directory

```bash
# Via command line
python scripts/backup_positions.py --backup-dir /custom/path

# Via Python
manager = BackupManager(backup_dir=Path("/custom/path"))
```

## Pre-Restore Safety

The system automatically creates `.pre_restore_*.bak` files before overwriting:

```bash
# Example
bots/treasury/.positions.json.pre_restore_20260119_120530.bak
```

These provide an additional safety net if restore goes wrong.

## Best Practices

### When to Backup

1. **Before risky operations**
   ```bash
   python scripts/backup_positions.py --emergency
   # ... perform risky operation ...
   ```

2. **Before configuration changes**
   ```bash
   python scripts/backup_positions.py --type config_only
   # ... edit config ...
   ```

3. **Before deploying new strategies**
   ```bash
   python scripts/backup_positions.py --type full --description "Pre-deploy v2.1"
   ```

4. **Regular schedule** (automated)
   ```bash
   # Set and forget
   python scripts/scheduled_backup.py --interval 6
   ```

### Backup Verification

Always verify critical backups:

```bash
# After creating important backup
python scripts/restore_backup.py --verify full_20260119_120000

# Regular verification checks
for backup in $(python scripts/restore_backup.py --list | awk '{print $1}'); do
    python scripts/restore_backup.py --verify $backup
done
```

### Testing Recovery

Periodically test recovery in non-production:

```bash
# Test restore without affecting production
python scripts/restore_backup.py --latest --dry-run
```

## Troubleshooting

### Backup Failed

**Check disk space**:
```bash
df -h ~/.lifeos/backups
```

**Check permissions**:
```bash
ls -la ~/.lifeos/backups
```

**Check logs**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
# Run backup again to see detailed logs
```

### Restore Failed

**Verify backup first**:
```bash
python scripts/restore_backup.py --verify <backup_id>
```

**Check for file locks**:
```bash
# Stop all bots first
pkill -f supervisor.py
# Then restore
```

**Check restore results**:
```python
results = manager.restore_backup(backup_id, dry_run=False)
if results["errors"]:
    print("Errors:", results["errors"])
```

### Corrupted Backup

**Try older backup**:
```bash
# List all backups
python scripts/restore_backup.py --list

# Try second-newest
python scripts/restore_backup.py --restore <older_backup_id>
```

**Manual extraction**:
```bash
# Backups are just JSON files
cd ~/.lifeos/backups/<backup_id>/
cat bots_treasury_.positions.json
```

## Integration with Monitoring

### Health Check

```python
from core.backup_manager import BackupManager

def backup_health_check():
    manager = BackupManager()
    backups = manager.list_backups()

    if not backups:
        return {"status": "error", "message": "No backups found"}

    latest = backups[0]
    age_hours = (datetime.now() - datetime.fromisoformat(latest.timestamp)).total_seconds() / 3600

    if age_hours > 24:
        return {"status": "warning", "message": f"Latest backup is {age_hours:.1f}h old"}

    return {"status": "ok", "latest_backup": latest.backup_id}
```

### Alerts

Set up alerts for:
- No backup in 24+ hours
- Backup verification failures
- Low disk space in backup directory
- Restore failures

## API Reference

See `core/backup_manager.py` for full API documentation.

Key classes:
- `BackupManager`: Main backup/restore orchestration
- `BackupMetadata`: Backup metadata and info
- `create_emergency_backup()`: Quick emergency backup
- `restore_latest_backup()`: Quick restore helper
