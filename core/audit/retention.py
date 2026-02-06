"""
Audit Log Retention Policy

Manages audit log lifecycle:
- Archive old logs (move to archive directory)
- Delete expired logs (beyond retention period)
- Compress archived logs (gzip)

Default retention:
- Active logs: 90 days
- Archived logs: 2x retention period (180 days)
- Expired logs: Deleted after 2x retention
"""

import gzip
import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Default audit directory
DEFAULT_AUDIT_DIR = Path("bots/logs/audit")


class RetentionPolicy:
    """
    Manages audit log retention lifecycle.

    Provides methods to:
    - Archive logs older than retain_days
    - Delete archived logs older than 2x retain_days
    - Compress archived logs for storage efficiency
    """

    def __init__(
        self,
        retain_days: int = 90,
        audit_dir: Optional[Path] = None,
        archive_subdir: str = "archive",
    ):
        """
        Initialize the retention policy.

        Args:
            retain_days: Number of days to keep active logs (default 90)
            audit_dir: Directory containing audit logs
            archive_subdir: Subdirectory name for archived logs
        """
        self.retain_days = retain_days
        self.audit_dir = Path(audit_dir) if audit_dir else DEFAULT_AUDIT_DIR
        self.archive_dir = self.audit_dir / archive_subdir

        # Ensure directories exist
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_date(self, file_path: Path) -> Optional[datetime]:
        """
        Extract date from audit log filename.

        Expected formats:
        - audit_YYYYMMDD.jsonl
        - audit_YYYYMMDD.json
        - audit_YYYYMMDD.jsonl.gz
        """
        name = file_path.name

        # Remove extensions
        for ext in [".gz", ".jsonl", ".json"]:
            if name.endswith(ext):
                name = name[:-len(ext)]

        # Extract date portion (last 8 characters if present)
        parts = name.split("_")
        if len(parts) >= 2:
            date_str = parts[-1]
            if len(date_str) == 8 and date_str.isdigit():
                try:
                    return datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

        # Fallback to file modification time
        try:
            mtime = file_path.stat().st_mtime
            return datetime.fromtimestamp(mtime, tz=timezone.utc)
        except Exception:
            return None

    def _is_older_than(self, file_path: Path, days: int) -> bool:
        """Check if a file is older than the specified number of days."""
        file_date = self._get_file_date(file_path)
        if file_date is None:
            return False

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return file_date < cutoff

    def archive_old_logs(self) -> List[Path]:
        """
        Archive logs older than retain_days.

        Moves old log files from audit_dir to archive_dir.

        Returns:
            List of archived file paths
        """
        archived = []

        # Find all log files (not in archive)
        for pattern in ["*.jsonl", "*.json"]:
            for log_file in self.audit_dir.glob(pattern):
                # Skip if already in archive
                if self.archive_dir in log_file.parents:
                    continue

                if self._is_older_than(log_file, self.retain_days):
                    try:
                        dest = self.archive_dir / log_file.name
                        shutil.move(str(log_file), str(dest))
                        archived.append(dest)
                        logger.info(f"Archived: {log_file.name}")
                    except Exception as e:
                        logger.error(f"Failed to archive {log_file}: {e}")

        return archived

    def delete_expired_logs(self) -> List[Path]:
        """
        Delete archived logs older than 2x retain_days.

        Returns:
            List of deleted file paths
        """
        deleted = []
        expiry_days = self.retain_days * 2

        # Find all files in archive
        for pattern in ["*.jsonl", "*.json", "*.jsonl.gz", "*.json.gz"]:
            for archive_file in self.archive_dir.glob(pattern):
                if self._is_older_than(archive_file, expiry_days):
                    try:
                        archive_file.unlink()
                        deleted.append(archive_file)
                        logger.info(f"Deleted expired: {archive_file.name}")
                    except Exception as e:
                        logger.error(f"Failed to delete {archive_file}: {e}")

        return deleted

    def compress_archived(self) -> List[Path]:
        """
        Compress uncompressed archived logs.

        Returns:
            List of compressed file paths
        """
        compressed = []

        # Find uncompressed files in archive
        for pattern in ["*.jsonl", "*.json"]:
            for archive_file in self.archive_dir.glob(pattern):
                # Skip if already has .gz version
                gz_path = archive_file.with_suffix(archive_file.suffix + ".gz")
                if gz_path.exists():
                    continue

                try:
                    # Read and compress
                    with open(archive_file, "rb") as f_in:
                        with gzip.open(gz_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)

                    # Remove original after successful compression
                    archive_file.unlink()
                    compressed.append(gz_path)
                    logger.info(f"Compressed: {archive_file.name}")

                except Exception as e:
                    logger.error(f"Failed to compress {archive_file}: {e}")
                    # Clean up partial compressed file
                    if gz_path.exists():
                        gz_path.unlink()

        return compressed

    def run(self) -> Dict[str, Any]:
        """
        Run the full retention policy.

        Executes in order:
        1. Archive old logs
        2. Delete expired logs
        3. Compress archived logs

        Returns:
            Summary of actions taken
        """
        logger.info(f"Running retention policy (retain_days={self.retain_days})")

        archived = self.archive_old_logs()
        deleted = self.delete_expired_logs()
        compressed = self.compress_archived()

        result = {
            "archived": [str(p) for p in archived],
            "deleted": [str(p) for p in deleted],
            "compressed": [str(p) for p in compressed],
            "archived_count": len(archived),
            "deleted_count": len(deleted),
            "compressed_count": len(compressed),
            "run_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            f"Retention complete: {len(archived)} archived, "
            f"{len(deleted)} deleted, {len(compressed)} compressed"
        )

        return result

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics for audit logs.

        Returns:
            Statistics about audit log storage
        """
        def get_dir_stats(dir_path: Path) -> Dict[str, Any]:
            total_size = 0
            file_count = 0
            oldest = None
            newest = None

            for file_path in dir_path.iterdir():
                if file_path.is_file():
                    file_count += 1
                    total_size += file_path.stat().st_size

                    file_date = self._get_file_date(file_path)
                    if file_date:
                        if oldest is None or file_date < oldest:
                            oldest = file_date
                        if newest is None or file_date > newest:
                            newest = file_date

            return {
                "file_count": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "oldest_file": oldest.isoformat() if oldest else None,
                "newest_file": newest.isoformat() if newest else None,
            }

        return {
            "active": get_dir_stats(self.audit_dir),
            "archived": get_dir_stats(self.archive_dir) if self.archive_dir.exists() else {},
            "retain_days": self.retain_days,
            "audit_dir": str(self.audit_dir),
            "archive_dir": str(self.archive_dir),
        }
