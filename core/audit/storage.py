"""
Audit Storage Backends

Provides different storage backends for audit logs:
- AuditStore: Abstract base class
- FileAuditStore: Append-only JSONL files
- JSONAuditStore: Structured daily JSON files

Features:
- Query support with filtering
- Export to JSON/CSV formats
- Date range filtering
"""

import csv
import json
import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from core.audit.logger import AuditEntry

logger = logging.getLogger(__name__)

# Default audit directory
DEFAULT_AUDIT_DIR = Path("bots/logs/audit")


class AuditStore(ABC):
    """Abstract base class for audit storage backends."""

    @abstractmethod
    def write(self, entry: AuditEntry) -> None:
        """Write an audit entry to storage."""
        pass

    @abstractmethod
    def get_logs(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit logs with optional filtering.

        Args:
            filters: Optional filter criteria:
                - actor: Filter by actor
                - action: Filter by action
                - resource: Filter by resource
                - start_time: Filter by start time (datetime)
                - end_time: Filter by end time (datetime)
            limit: Maximum number of entries to return

        Returns:
            List of audit entries as dictionaries
        """
        pass

    @abstractmethod
    def export(
        self,
        format: str,
        output_path: Path,
        date_range: Tuple[datetime, datetime]
    ) -> None:
        """
        Export audit logs to a file.

        Args:
            format: Export format ('json' or 'csv')
            output_path: Path to output file
            date_range: Tuple of (start_time, end_time)
        """
        pass


class FileAuditStore(AuditStore):
    """
    Append-only JSONL file storage.

    Stores audit entries in daily JSON Lines files for easy streaming
    and append-only semantics.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        file_prefix: str = "audit"
    ):
        """
        Initialize the file audit store.

        Args:
            base_dir: Base directory for audit files
            file_prefix: Prefix for log file names
        """
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_AUDIT_DIR
        self.file_prefix = file_prefix
        self._lock = threading.Lock()

        # Ensure directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_current_file(self) -> Path:
        """Get the current day's log file path."""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return self.base_dir / f"{self.file_prefix}_{today}.jsonl"

    def write(self, entry: AuditEntry) -> None:
        """Write an audit entry to the current day's file."""
        with self._lock:
            log_file = self._get_current_file()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

    def get_logs(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Retrieve audit logs with optional filtering."""
        filters = filters or {}
        results = []

        # Get all log files, sorted by date (newest first)
        log_files = sorted(self.base_dir.glob(f"{self.file_prefix}_*.jsonl"), reverse=True)

        for log_file in log_files:
            if len(results) >= limit:
                break

            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if len(results) >= limit:
                            break

                        try:
                            entry = json.loads(line)

                            if self._matches_filters(entry, filters):
                                results.append(entry)

                        except json.JSONDecodeError:
                            continue

            except Exception as e:
                logger.warning(f"Error reading {log_file}: {e}")

        return results

    def _matches_filters(self, entry: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if an entry matches the given filters."""
        # Actor filter
        if "actor" in filters and entry.get("actor") != filters["actor"]:
            return False

        # Action filter
        if "action" in filters and entry.get("action") != filters["action"]:
            return False

        # Resource filter
        if "resource" in filters and entry.get("resource") != filters["resource"]:
            return False

        # Time range filters
        if "start_time" in filters or "end_time" in filters:
            try:
                entry_time = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))

                if "start_time" in filters:
                    start = filters["start_time"]
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if entry_time < start:
                        return False

                if "end_time" in filters:
                    end = filters["end_time"]
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                    if entry_time > end:
                        return False

            except (KeyError, ValueError):
                return False

        return True

    def export(
        self,
        format: str,
        output_path: Path,
        date_range: Tuple[datetime, datetime]
    ) -> None:
        """Export audit logs to a file."""
        start_time, end_time = date_range

        # Get logs in the date range
        logs = self.get_logs(
            filters={"start_time": start_time, "end_time": end_time},
            limit=1000000  # Large limit for export
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format.lower() == "json":
            self._export_json(logs, output_path, date_range)
        elif format.lower() == "csv":
            self._export_csv(logs, output_path)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _export_json(
        self,
        logs: List[Dict[str, Any]],
        output_path: Path,
        date_range: Tuple[datetime, datetime]
    ) -> None:
        """Export logs to JSON format."""
        export_data = {
            "metadata": {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "start_time": date_range[0].isoformat(),
                "end_time": date_range[1].isoformat(),
                "total_entries": len(logs),
            },
            "entries": logs,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

    def _export_csv(self, logs: List[Dict[str, Any]], output_path: Path) -> None:
        """Export logs to CSV format."""
        if not logs:
            # Write empty CSV with headers
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "actor", "action", "resource", "details", "success"])
            return

        # Collect all possible fields
        all_fields = set()
        for log in logs:
            all_fields.update(log.keys())

        # Sort fields with common ones first
        priority_fields = ["timestamp", "actor", "action", "resource", "details", "success"]
        fields = [f for f in priority_fields if f in all_fields]
        fields.extend(sorted(f for f in all_fields if f not in priority_fields))

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()

            for log in logs:
                # Convert complex fields to JSON strings
                row = {}
                for field in fields:
                    value = log.get(field, "")
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    row[field] = value
                writer.writerow(row)


class JSONAuditStore(AuditStore):
    """
    Structured JSON file storage.

    Stores audit entries in daily JSON files with metadata.
    Good for smaller volumes where structured access is preferred.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        file_prefix: str = "audit"
    ):
        """
        Initialize the JSON audit store.

        Args:
            base_dir: Base directory for audit files
            file_prefix: Prefix for log file names
        """
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_AUDIT_DIR
        self.file_prefix = file_prefix
        self._lock = threading.Lock()

        # Ensure directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_current_file(self) -> Path:
        """Get the current day's JSON file path."""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return self.base_dir / f"{self.file_prefix}_{today}.json"

    def _load_file(self, file_path: Path) -> Dict[str, Any]:
        """Load a JSON audit file."""
        if not file_path.exists():
            return {
                "metadata": {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "file": file_path.name,
                },
                "entries": [],
            }

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_file(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Save a JSON audit file."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def write(self, entry: AuditEntry) -> None:
        """Write an audit entry to the current day's JSON file."""
        with self._lock:
            log_file = self._get_current_file()
            data = self._load_file(log_file)

            data["entries"].append(entry.to_dict())
            data["metadata"]["updated_at"] = datetime.now(timezone.utc).isoformat()
            data["metadata"]["entry_count"] = len(data["entries"])

            self._save_file(log_file, data)

    def get_logs(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Retrieve audit logs with optional filtering."""
        filters = filters or {}
        results = []

        # Get all JSON log files, sorted by date (newest first)
        log_files = sorted(self.base_dir.glob(f"{self.file_prefix}_*.json"), reverse=True)

        for log_file in log_files:
            if len(results) >= limit:
                break

            try:
                data = self._load_file(log_file)

                for entry in data.get("entries", []):
                    if len(results) >= limit:
                        break

                    if self._matches_filters(entry, filters):
                        results.append(entry)

            except Exception as e:
                logger.warning(f"Error reading {log_file}: {e}")

        return results

    def _matches_filters(self, entry: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if an entry matches the given filters."""
        # Same logic as FileAuditStore
        if "actor" in filters and entry.get("actor") != filters["actor"]:
            return False

        if "action" in filters and entry.get("action") != filters["action"]:
            return False

        if "resource" in filters and entry.get("resource") != filters["resource"]:
            return False

        if "start_time" in filters or "end_time" in filters:
            try:
                entry_time = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))

                if "start_time" in filters:
                    start = filters["start_time"]
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if entry_time < start:
                        return False

                if "end_time" in filters:
                    end = filters["end_time"]
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                    if entry_time > end:
                        return False

            except (KeyError, ValueError):
                return False

        return True

    def export(
        self,
        format: str,
        output_path: Path,
        date_range: Tuple[datetime, datetime]
    ) -> None:
        """Export audit logs to a file."""
        # Use FileAuditStore's export logic
        start_time, end_time = date_range

        logs = self.get_logs(
            filters={"start_time": start_time, "end_time": end_time},
            limit=1000000
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format.lower() == "json":
            export_data = {
                "metadata": {
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "total_entries": len(logs),
                },
                "entries": logs,
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)

        elif format.lower() == "csv":
            FileAuditStore(self.base_dir)._export_csv(logs, output_path)

        else:
            raise ValueError(f"Unsupported export format: {format}")
