"""
State Backup System - Atomic writes and disaster recovery.

Fixes Issue #2: State loss from incomplete writes during crashes.

Provides:
- StateBackup: Atomic write operations (write → temp file → rename)
- Hourly snapshots to archive/
- Auto-cleanup (24-hour retention)
- Read-safe access with fallback to last good backup
"""

from core.state_backup.state_backup import (
    StateBackup,
    get_state_backup,
)

__all__ = [
    "StateBackup",
    "get_state_backup",
]
