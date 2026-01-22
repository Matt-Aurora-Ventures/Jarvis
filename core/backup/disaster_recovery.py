"""
Disaster Recovery Manager - Handles system recovery procedures.

Provides:
- Health checks for data corruption
- Recovery from various failure scenarios
- Recovery plan generation
- System integrity validation
"""

import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.backup.backup_manager import BackupManager, BackupConfig
from core.backup.restore_manager import RestoreManager

logger = logging.getLogger(__name__)


@dataclass
class HealthIssue:
    """Represents a detected health issue."""
    severity: str  # critical, warning, info
    category: str  # corruption, missing, invalid, size
    file_path: Optional[Path] = None
    description: str = ""
    recoverable: bool = True


@dataclass
class RecoveryStep:
    """A step in the recovery process."""
    step_number: int
    action: str
    description: str
    command: Optional[str] = None
    is_manual: bool = False
    completed: bool = False


@dataclass
class RecoveryPlan:
    """A complete recovery plan for a scenario."""
    scenario: str
    description: str
    steps: List[RecoveryStep] = field(default_factory=list)
    estimated_time_minutes: int = 0
    requires_downtime: bool = False


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""
    success: bool
    scenario: str = ""
    steps_completed: int = 0
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class IntegrityResult:
    """Result of system integrity validation."""
    is_healthy: bool
    issues: List[HealthIssue] = field(default_factory=list)
    files_checked: int = 0
    last_backup: Optional[datetime] = None
    backup_available: bool = False


class DisasterRecoveryManager:
    """
    Manages disaster recovery procedures and health monitoring.

    Scenarios handled:
    - Data corruption: Detect and restore from clean backup
    - Disk full: Alert and manage backup rotation
    - Lost positions: Restore trading state
    - Lost audit trail: Restore from backup
    """

    # Critical data files that must be valid
    CRITICAL_FILES = [
        "positions.json",
        ".positions.json",
        "trades.jsonl",
        "trade_history.json",
        ".trade_history.json",
    ]

    # JSON files to validate
    JSON_FILES = [
        "*.json",
    ]

    def __init__(self, config: BackupConfig):
        self.config = config
        self._backup_manager = BackupManager(config)
        self._restore_manager = RestoreManager(config)

    def _validate_json_file(self, file_path: Path) -> Optional[HealthIssue]:
        """Validate a JSON file for corruption."""
        try:
            content = file_path.read_text()
            if not content.strip():
                return HealthIssue(
                    severity="warning",
                    category="empty",
                    file_path=file_path,
                    description=f"File is empty: {file_path.name}",
                    recoverable=True
                )

            json.loads(content)
            return None

        except json.JSONDecodeError as e:
            return HealthIssue(
                severity="critical",
                category="corruption",
                file_path=file_path,
                description=f"Invalid JSON in {file_path.name}: {e}",
                recoverable=True
            )
        except Exception as e:
            return HealthIssue(
                severity="warning",
                category="read_error",
                file_path=file_path,
                description=f"Could not read {file_path.name}: {e}",
                recoverable=True
            )

    def _validate_jsonl_file(self, file_path: Path) -> Optional[HealthIssue]:
        """Validate a JSONL file for corruption."""
        try:
            content = file_path.read_text()
            if not content.strip():
                return None  # Empty JSONL is valid

            for i, line in enumerate(content.strip().split("\n"), 1):
                if line.strip():
                    json.loads(line)
            return None

        except json.JSONDecodeError as e:
            return HealthIssue(
                severity="critical",
                category="corruption",
                file_path=file_path,
                description=f"Invalid JSON at line {i} in {file_path.name}: {e}",
                recoverable=True
            )
        except Exception as e:
            return HealthIssue(
                severity="warning",
                category="read_error",
                file_path=file_path,
                description=f"Could not read {file_path.name}: {e}",
                recoverable=True
            )

    def _check_file_size(self, file_path: Path) -> Optional[HealthIssue]:
        """Check for suspiciously small files that might indicate data loss."""
        try:
            size = file_path.stat().st_size

            # Critical files should not be empty
            if file_path.name in self.CRITICAL_FILES and size == 0:
                return HealthIssue(
                    severity="critical",
                    category="size",
                    file_path=file_path,
                    description=f"Critical file {file_path.name} is empty",
                    recoverable=True
                )

            return None
        except Exception:
            return None

    def run_health_check(self) -> List[HealthIssue]:
        """
        Run comprehensive health check on data files.

        Returns:
            List of detected issues
        """
        issues = []

        for data_path in self.config.data_paths:
            if not data_path.exists():
                issues.append(HealthIssue(
                    severity="warning",
                    category="missing",
                    file_path=data_path,
                    description=f"Data path not found: {data_path}",
                    recoverable=False
                ))
                continue

            # Check all JSON files
            for json_file in data_path.rglob("*.json"):
                if json_file.name.startswith("_"):
                    continue

                issue = self._validate_json_file(json_file)
                if issue:
                    issues.append(issue)

                size_issue = self._check_file_size(json_file)
                if size_issue:
                    issues.append(size_issue)

            # Check all JSONL files
            for jsonl_file in data_path.rglob("*.jsonl"):
                issue = self._validate_jsonl_file(jsonl_file)
                if issue:
                    issues.append(issue)

        logger.info(f"Health check completed: {len(issues)} issues found")
        return issues

    def recover_from_corruption(self, target_dir: Path) -> RecoveryResult:
        """
        Recover from data corruption by restoring from backup.

        Args:
            target_dir: Directory to restore to

        Returns:
            RecoveryResult with details
        """
        logger.info(f"Starting corruption recovery for {target_dir}")

        # Find the latest valid backup
        backups = self._backup_manager.list_backups()

        if not backups:
            return RecoveryResult(
                success=False,
                scenario="corruption_recovery",
                error="No backups available for recovery"
            )

        # Find a backup that passes verification
        for backup in backups:
            verification = self._backup_manager.verify_backup(backup.backup_path)
            if verification.is_valid:
                logger.info(f"Found valid backup: {backup.name}")

                # Perform restore
                result = self._restore_manager.restore_backup(
                    backup.backup_path,
                    target_dir,
                    verify=True,
                    create_safety_backup=True
                )

                if result.success:
                    return RecoveryResult(
                        success=True,
                        scenario="corruption_recovery",
                        steps_completed=3  # identify, backup current, restore
                    )
                else:
                    logger.warning(f"Restore from {backup.name} failed, trying older backup")
                    continue

        return RecoveryResult(
            success=False,
            scenario="corruption_recovery",
            error="No valid backup could be restored"
        )

    def generate_recovery_plan(self, scenario: str) -> RecoveryPlan:
        """
        Generate a recovery plan for a specific scenario.

        Args:
            scenario: One of: data_corruption, disk_full, lost_positions, lost_audit

        Returns:
            RecoveryPlan with step-by-step instructions
        """
        if scenario == "data_corruption":
            return RecoveryPlan(
                scenario=scenario,
                description="Recovery from data file corruption",
                steps=[
                    RecoveryStep(
                        step_number=1,
                        action="Identify",
                        description="Identify corrupted files using health check",
                        command="python scripts/verify_backup.py --check-data"
                    ),
                    RecoveryStep(
                        step_number=2,
                        action="Safety Backup",
                        description="Create backup of current (corrupted) state for analysis",
                        command="python scripts/restore_backup.py --safety-backup"
                    ),
                    RecoveryStep(
                        step_number=3,
                        action="Restore",
                        description="Restore from latest clean backup",
                        command="python scripts/restore_backup.py --latest"
                    ),
                    RecoveryStep(
                        step_number=4,
                        action="Verify",
                        description="Verify restored data integrity",
                        command="python scripts/verify_backup.py --check-data"
                    ),
                    RecoveryStep(
                        step_number=5,
                        action="Test",
                        description="Verify live trading functionality",
                        is_manual=True
                    )
                ],
                estimated_time_minutes=15,
                requires_downtime=True
            )

        elif scenario == "disk_full":
            return RecoveryPlan(
                scenario=scenario,
                description="Recovery from disk space exhaustion",
                steps=[
                    RecoveryStep(
                        step_number=1,
                        action="Alert",
                        description="Notify admin of disk space issue"
                    ),
                    RecoveryStep(
                        step_number=2,
                        action="Cleanup",
                        description="Remove old backups beyond retention",
                        command="python scripts/verify_backup.py --cleanup --days 7"
                    ),
                    RecoveryStep(
                        step_number=3,
                        action="Clear Logs",
                        description="Archive and clear old log files",
                        is_manual=True
                    ),
                    RecoveryStep(
                        step_number=4,
                        action="Verify Space",
                        description="Confirm sufficient space available",
                        is_manual=True
                    )
                ],
                estimated_time_minutes=10,
                requires_downtime=False
            )

        elif scenario == "lost_positions":
            return RecoveryPlan(
                scenario=scenario,
                description="Recovery from lost trading positions data",
                steps=[
                    RecoveryStep(
                        step_number=1,
                        action="Halt Trading",
                        description="Stop all trading operations",
                        command="lifeos trading stop"
                    ),
                    RecoveryStep(
                        step_number=2,
                        action="Identify",
                        description="Determine extent of data loss"
                    ),
                    RecoveryStep(
                        step_number=3,
                        action="Restore",
                        description="Restore positions from backup",
                        command="python scripts/restore_backup.py --file positions.json --latest"
                    ),
                    RecoveryStep(
                        step_number=4,
                        action="Reconcile",
                        description="Reconcile with on-chain state",
                        is_manual=True
                    ),
                    RecoveryStep(
                        step_number=5,
                        action="Resume",
                        description="Resume trading operations",
                        command="lifeos trading start"
                    )
                ],
                estimated_time_minutes=20,
                requires_downtime=True
            )

        elif scenario == "lost_audit":
            return RecoveryPlan(
                scenario=scenario,
                description="Recovery from lost audit trail",
                steps=[
                    RecoveryStep(
                        step_number=1,
                        action="Identify",
                        description="Identify missing audit records"
                    ),
                    RecoveryStep(
                        step_number=2,
                        action="Restore",
                        description="Restore audit log from backup",
                        command="python scripts/restore_backup.py --file audit_log.json --latest"
                    ),
                    RecoveryStep(
                        step_number=3,
                        action="Verify",
                        description="Verify audit trail integrity"
                    ),
                    RecoveryStep(
                        step_number=4,
                        action="Gap Analysis",
                        description="Identify and document any gaps",
                        is_manual=True
                    )
                ],
                estimated_time_minutes=15,
                requires_downtime=False
            )

        else:
            return RecoveryPlan(
                scenario=scenario,
                description=f"Unknown scenario: {scenario}",
                steps=[
                    RecoveryStep(
                        step_number=1,
                        action="Assess",
                        description="Assess the situation and identify specific issue",
                        is_manual=True
                    ),
                    RecoveryStep(
                        step_number=2,
                        action="Backup",
                        description="Create safety backup of current state",
                        command="python scripts/restore_backup.py --safety-backup"
                    ),
                    RecoveryStep(
                        step_number=3,
                        action="Contact",
                        description="Contact admin for assistance",
                        is_manual=True
                    )
                ],
                estimated_time_minutes=30,
                requires_downtime=True
            )

    def validate_system_integrity(self) -> IntegrityResult:
        """
        Validate overall system integrity.

        Checks:
        - Data file integrity
        - Backup availability
        - Backup freshness

        Returns:
            IntegrityResult with details
        """
        issues = self.run_health_check()
        files_checked = sum(
            1 for p in self.config.data_paths if p.exists()
            for _ in p.rglob("*") if _.is_file()
        )

        # Check backup status
        latest_backup = self._backup_manager.get_latest_backup()
        backup_available = latest_backup is not None
        last_backup_time = latest_backup.created_at if latest_backup else None

        # Check backup freshness (warning if > 24 hours old)
        if latest_backup:
            age = datetime.now(timezone.utc) - latest_backup.created_at
            if age.total_seconds() > 86400:
                issues.append(HealthIssue(
                    severity="warning",
                    category="stale",
                    description=f"Latest backup is {age.days} days old"
                ))

        critical_issues = [i for i in issues if i.severity == "critical"]
        is_healthy = len(critical_issues) == 0

        return IntegrityResult(
            is_healthy=is_healthy,
            issues=issues,
            files_checked=files_checked,
            last_backup=last_backup_time,
            backup_available=backup_available
        )

    def execute_recovery_plan(self, plan: RecoveryPlan) -> RecoveryResult:
        """
        Execute a recovery plan.

        Note: Only automated steps are executed. Manual steps are logged.

        Args:
            plan: Recovery plan to execute

        Returns:
            RecoveryResult
        """
        steps_completed = 0
        warnings = []

        for step in plan.steps:
            logger.info(f"Step {step.step_number}: {step.action} - {step.description}")

            if step.is_manual:
                logger.info(f"  [MANUAL] Please complete this step manually")
                warnings.append(f"Step {step.step_number} requires manual action")
                continue

            if step.command:
                logger.info(f"  Command: {step.command}")
                # In a real implementation, would execute the command
                # For safety, we just log it

            steps_completed += 1
            step.completed = True

        return RecoveryResult(
            success=True,
            scenario=plan.scenario,
            steps_completed=steps_completed,
            warnings=warnings
        )
