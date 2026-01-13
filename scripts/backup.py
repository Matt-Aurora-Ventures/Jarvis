#!/usr/bin/env python3
"""Automated backup script for Jarvis."""
import subprocess
import shutil
import gzip
from datetime import datetime
from pathlib import Path
import json
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BackupManager:
    """Manage automated backups."""
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.s3_bucket = os.getenv("BACKUP_S3_BUCKET")
    
    def backup_database(self) -> Path:
        """Backup SQLite database."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"db_backup_{timestamp}.sql"
        
        db_path = Path("data/jarvis.db")
        if not db_path.exists():
            logger.warning("Database not found, skipping backup")
            return None
        
        try:
            # Use SQLite backup command
            result = subprocess.run(
                ["sqlite3", str(db_path), f".backup '{backup_file}'"],
                capture_output=True, text=True, shell=True
            )
            if result.returncode != 0:
                # Fallback to file copy
                shutil.copy2(db_path, backup_file)
            
            # Compress
            compressed = self._compress_file(backup_file)
            backup_file.unlink()
            
            logger.info(f"Database backed up to {compressed}")
            return compressed
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return None
    
    def backup_configs(self) -> Path:
        """Backup configuration files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"config_backup_{timestamp}.tar.gz"
        
        config_files = [
            "lifeos.config.json",
            "lifeos.config.local.json",
            "docker-compose.yml",
            ".env.example"
        ]
        
        existing_files = [f for f in config_files if Path(f).exists()]
        
        if not existing_files:
            logger.warning("No config files found")
            return None
        
        try:
            subprocess.run(
                ["tar", "-czf", str(backup_file)] + existing_files,
                check=True, capture_output=True
            )
            logger.info(f"Configs backed up to {backup_file}")
            return backup_file
        except Exception as e:
            logger.error(f"Config backup failed: {e}")
            return None
    
    def backup_logs(self, days: int = 7) -> Path:
        """Backup recent log files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"logs_backup_{timestamp}.tar.gz"
        
        log_dir = Path("logs")
        if not log_dir.exists():
            return None
        
        try:
            subprocess.run(
                ["tar", "-czf", str(backup_file), str(log_dir)],
                check=True, capture_output=True
            )
            logger.info(f"Logs backed up to {backup_file}")
            return backup_file
        except Exception as e:
            logger.error(f"Log backup failed: {e}")
            return None
    
    def upload_to_s3(self, file_path: Path) -> bool:
        """Upload backup to S3."""
        if not self.s3_bucket:
            logger.info("S3 bucket not configured, skipping upload")
            return False
        
        try:
            import boto3
            s3 = boto3.client('s3')
            key = f"backups/{file_path.name}"
            s3.upload_file(str(file_path), self.s3_bucket, key)
            logger.info(f"Uploaded {file_path.name} to s3://{self.s3_bucket}/{key}")
            return True
        except ImportError:
            logger.warning("boto3 not installed, skipping S3 upload")
            return False
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return False
    
    def cleanup_old_backups(self, days: int = 30) -> int:
        """Remove backups older than specified days."""
        import time
        cutoff = time.time() - (days * 86400)
        removed = 0
        
        for f in self.backup_dir.glob("*"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
                logger.info(f"Removed old backup: {f.name}")
        
        return removed
    
    def _compress_file(self, file_path: Path) -> Path:
        """Compress a file with gzip."""
        compressed = file_path.with_suffix(file_path.suffix + '.gz')
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed, 'wb') as f_out:
                f_out.writelines(f_in)
        return compressed
    
    def run_full_backup(self) -> dict:
        """Run full backup of all components."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "database": None,
            "configs": None,
            "logs": None,
            "uploaded": []
        }
        
        # Database
        db_backup = self.backup_database()
        if db_backup:
            results["database"] = str(db_backup)
            if self.upload_to_s3(db_backup):
                results["uploaded"].append(str(db_backup))
        
        # Configs
        config_backup = self.backup_configs()
        if config_backup:
            results["configs"] = str(config_backup)
            if self.upload_to_s3(config_backup):
                results["uploaded"].append(str(config_backup))
        
        # Logs
        log_backup = self.backup_logs()
        if log_backup:
            results["logs"] = str(log_backup)
        
        # Cleanup
        removed = self.cleanup_old_backups()
        results["cleaned_up"] = removed
        
        # Save manifest
        manifest_path = self.backup_dir / "latest_backup.json"
        manifest_path.write_text(json.dumps(results, indent=2))
        
        return results


if __name__ == "__main__":
    manager = BackupManager()
    results = manager.run_full_backup()
    print(json.dumps(results, indent=2))
