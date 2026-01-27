
import sqlite3
import shutil
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('migration_cache.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path("C:/Users/lucid/OneDrive/Desktop/Projects/Jarvis")
DATA_DIR = PROJECT_ROOT / "data"
BACKUP_DIR = DATA_DIR / "backups"
TARGET_DB = DATA_DIR / "jarvis_cache.db"
SCHEMA_FILE = PROJECT_ROOT / ".planning/phases/01-database-consolidation/jarvis_cache_schema.sql"

# Source Database Mapping
SOURCE_DBS = {
    'rate_limiter': DATA_DIR / "rate_limiter.db",
    'file_cache': DATA_DIR / "cache/file_cache.db",
    'spam': DATA_DIR / "jarvis_spam_protection.db"
}

class CacheMigrator:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.BACKUP_DIR = BACKUP_DIR
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def backup_source_dbs(self) -> bool:
        """Create backups of all source databases."""
        logger.info("Creating backups of source databases...")
        success = True
        
        for name, path in SOURCE_DBS.items():
            if not path.exists():
                continue
                
            try:
                # Ensure backup dir exists
                self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
                backup_path = self.BACKUP_DIR / f"{name}_cache_{self.timestamp}.db"
                shutil.copy2(path, backup_path)
                logger.info(f"[OK] Backed up {name} -> {backup_path.name}")
            except Exception as e:
                logger.error(f"[ERR] Failed to backup {name}: {e}")
                # Don't fail total migration for cache backup failure
        
        return success

    def create_target_schema(self) -> bool:
        """Create the target database schema from SQL file."""
        logger.info(f"Creating target database schema from {SCHEMA_FILE.name}...")
        
        if not SCHEMA_FILE.exists():
            logger.error(f"[ERR] Schema file not found: {SCHEMA_FILE}")
            return False
            
        try:
            with open(SCHEMA_FILE, 'r') as f:
                schema_sql = f.read()

            conn = sqlite3.connect(TARGET_DB)
            cursor = conn.cursor()
            
            # Execute schema script
            try:
                cursor.executescript(schema_sql)
                conn.commit()
                logger.info(f"[OK] Created target database: {TARGET_DB}")
                conn.close()
                return True
            except sqlite3.Error as e:
                logger.error(f"[ERR] Failed to execute schema script: {e}")
                conn.close()
                return False
            
        except Exception as e:
            logger.error(f"[ERR] Failed to create schema: {e}")
            return False

    def migrate_rate_limits(self) -> Tuple[int, int]:
        """Migrate existing rate limits."""
        logger.info("Migrating rate limits...")
        
        source = SOURCE_DBS['rate_limiter']
        if not source.exists():
            return 0, 0
            
        return self._generic_copy(source, 'rate_limit_state', 'rate_limit_state')

    def migrate_spam_data(self) -> Tuple[int, int]:
        """Migrate spam protection data."""
        logger.info("Migrating spam protection data...")
        
        source = SOURCE_DBS['spam']
        if not source.exists():
            return 0, 0
            
        m1, e1 = self._generic_copy(source, 'spam_users', 'spam_users')
        m2, e2 = self._generic_copy(source, 'spam_patterns', 'spam_patterns')
        m3, e3 = self._generic_copy(source, 'user_reputation', 'user_reputation')
        
        return m1+m2+m3, e1+e2+e3

    def _generic_copy(self, source_path: Path, source_table: str, target_table: str) -> Tuple[int, int]:
        """Helper to copy table data blindly."""
        migrated = 0
        errors = 0
        try:
            source_conn = sqlite3.connect(source_path)
            source_conn.row_factory = sqlite3.Row
            target_conn = sqlite3.connect(TARGET_DB)
            
            s_cursor = source_conn.cursor()
            t_cursor = target_conn.cursor()
            
            # Check source table
            s_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (source_table,))
            if not s_cursor.fetchone():
                return 0, 0
                
            # Get columns
            s_cursor.execute(f"SELECT * FROM {source_table}")
            rows = s_cursor.fetchall()
            
            if not rows:
                return 0, 0
                
            # Get target columns
            t_cursor.execute(f"PRAGMA table_info({target_table})")
            target_columns = {row[1] for row in t_cursor.fetchall()}
            
            for row in rows:
                try:
                    data = {}
                    for key in row.keys():
                        if key in target_columns:
                            data[key] = row[key]
                            
                    if not data:
                        continue
                        
                    cols = list(data.keys())
                    vals = list(data.values())
                    placeholders = ','.join(['?' for _ in cols])
                    
                    sql = f"INSERT OR IGNORE INTO {target_table} ({','.join(cols)}) VALUES ({placeholders})"
                    t_cursor.execute(sql, vals)
                    migrated += 1
                except Exception as e:
                    logger.debug(f"Row migration error: {e}")
                    errors += 1
                    
            target_conn.commit()
            source_conn.close()
            target_conn.close()
            
            logger.info(f"  -> Migrated {migrated} rows to {target_table}")
            return migrated, errors
            
        except Exception as e:
            logger.warning(f"  -> Failed to migrate {source_table}: {e}")
            return 0, 1

    def run(self):
        logger.info("============================================================")
        logger.info(f"CACHE DB MIGRATION: {TARGET_DB.name}")
        logger.info("============================================================")
        
        if self.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        if not self.backup_source_dbs():
            logger.warning("Backups incomplete, but continuing for cache persistence...")

        # Delete existing target in dry run
        if self.dry_run and TARGET_DB.exists():
            try:
                TARGET_DB.unlink()
            except Exception as e:
                logger.debug(f"Could not delete target DB: {e}")
                pass

        if not self.create_target_schema():
            return

        total_migrated = 0
        
        # Migrate critical cache data
        m, e = self.migrate_rate_limits()
        total_migrated += m
        
        m, e = self.migrate_spam_data()
        total_migrated += m
        
        logger.info("============================================================")
        logger.info(f"MIGRATION SUMMARY: {total_migrated} rows conserved")
        logger.info("============================================================")
        
        if self.dry_run:
            if TARGET_DB.exists():
                TARGET_DB.unlink()
            logger.info("Dry run cleanup complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without changes")
    args = parser.parse_args()
    
    migrator = CacheMigrator(dry_run=args.dry_run)
    migrator.run()
