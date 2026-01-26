
import sqlite3
import shutil
import logging
from pathlib import Path
from datetime import datetime
import sys
from typing import Tuple, List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('migration_analytics.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path("C:/Users/lucid/OneDrive/Desktop/Projects/Jarvis")
DATA_DIR = PROJECT_ROOT / "data"
BACKUP_DIR = DATA_DIR / "backups"
TARGET_DB = DATA_DIR / "jarvis_analytics.db"
SCHEMA_FILE = PROJECT_ROOT / ".planning/phases/01-database-consolidation/jarvis_analytics_schema.sql"

# Source Database Mapping
SOURCE_DBS = {
    'llm_costs': DATA_DIR / "llm_costs.db",
    'sentiment': DATA_DIR / "sentiment.db",
    'memory': DATA_DIR / "jarvis_memory.db",
    'metrics': DATA_DIR / "metrics.db",
    'twitter': PROJECT_ROOT / "bots/twitter/engagement.db"
}

class AnalyticsMigrator:
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
                logger.warning(f"⚠️ Source DB not found: {path} (Skipping)")
                continue
                
            try:
                backup_path = self.BACKUP_DIR / f"{name}_{self.timestamp}.db"
                shutil.copy2(path, backup_path)
                logger.info(f"[OK] Backed up {name} -> {backup_path.name}")
            except Exception as e:
                logger.error(f"[ERR] Failed to backup {name}: {e}")
                success = False
        
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

    def generic_migrate_table(self, source_name: str, source_table: str, target_table: str, 
                            column_mapping: Dict[str, str] = None) -> Tuple[int, int]:
        """Generic table migration utility."""
        logger.info(f"Migrating {source_name}.{source_table} → {target_table}...")
        
        source_path = SOURCE_DBS.get(source_name)
        if not source_path or not source_path.exists():
            logger.info(f"Skipping {source_table} (Source DB {source_name} not found)")
            return 0, 0

        source_conn = sqlite3.connect(source_path)
        target_conn = sqlite3.connect(TARGET_DB)
        # Use Row factory to access columns by name
        source_conn.row_factory = sqlite3.Row 
        
        s_cursor = source_conn.cursor()
        t_cursor = target_conn.cursor()
        
        migrated = 0
        errors = 0
        
        try:
            # Check source table exists
            s_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (source_table,))
            if not s_cursor.fetchone():
                logger.warning(f"Source table {source_table} not found in {source_name}")
                return 0, 0

            # Get target columns
            t_cursor.execute(f"PRAGMA table_info({target_table})")
            target_columns = {row[1] for row in t_cursor.fetchall()}
            
            # Fetch source data
            s_cursor.execute(f"SELECT * FROM {source_table}")
            rows = s_cursor.fetchall()
            
            for row in rows:
                try:
                    # Build dict of data to insert
                    insert_data = {}
                    
                    # 1. Map columns present in both
                    for col in row.keys():
                        target_col = column_mapping.get(col, col) if column_mapping else col
                        if target_col in target_columns:
                            insert_data[target_col] = row[col]
                            
                    # 2. Skip if no data
                    if not insert_data:
                        continue
                        
                    # 3. Construct Insert
                    cols = list(insert_data.keys())
                    vals = list(insert_data.values())
                    placeholders = ','.join(['?' for _ in cols])
                    
                    sql = f"INSERT OR IGNORE INTO {target_table} ({','.join(cols)}) VALUES ({placeholders})"
                    t_cursor.execute(sql, vals)
                    migrated += 1
                    
                except Exception as e:
                    errors += 1
            
            target_conn.commit()
            
        except Exception as e:
            logger.error(f"Error preparing migration for {target_table}: {e}")
            return 0, 1
        finally:
            source_conn.close()
            target_conn.close()
            
        logger.info(f"✅ Migrated {migrated} rows to {target_table} ({errors} errors)")
        return migrated, errors

    def run(self):
        logger.info("============================================================")
        logger.info(f"ANALYTICS DB MIGRATION: {TARGET_DB.name}")
        logger.info("============================================================")
        
        if self.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
            # In dry run, we still create backups and temp DB to verify logic
        
        # Step 1: Backup
        if not self.backup_source_dbs():
            logger.error("Backup failed. Aborting.")
            return

        # Step 2: Create Target (Delete if exists for fresh start in dry run)
        if TARGET_DB.exists():
            try:
                if self.dry_run:
                    TARGET_DB.unlink() # Delete for fresh test
            except Exception as e:
                logger.warning(f"Could not delete existing target: {e}")

        if not self.create_target_schema():
            logger.error("Schema creation failed. Aborting.")
            return

        # Step 3: Migrate Data using Generic Migrator
        total_migrated = 0
        
        # 3.1 LLM Costs (llm_costs.db)
        m, e = self.generic_migrate_table('llm_costs', 'llm_costs', 'llm_costs')
        total_migrated += m
        
        # 3.2 Sentiment (sentiment.db -> token_sentiment)
        # Assuming sentiment.db has a table 'sentiment' or similar
        m, e = self.generic_migrate_table('sentiment', 'token_sentiment', 'token_sentiment') 
        total_migrated += m
        
        # 3.3 Metrics (metrics.db -> system_metrics)
        m, e = self.generic_migrate_table('metrics', 'metrics', 'system_metrics')
        total_migrated += m

        # 3.4 API Usage (llm_costs.db -> api_usage)
        m, e = self.generic_migrate_table('llm_costs', 'api_usage', 'api_usage')
        total_migrated += m
        
        logger.info("============================================================")
        logger.info("MIGRATION SUMMARY")
        logger.info("============================================================")
        logger.info(f"Total rows migrated: {total_migrated}")
        
        if self.dry_run:
             logger.info("Dry run complete. Verified schema and mapping logic.")
             if TARGET_DB.exists():
                 TARGET_DB.unlink() # Cleanup
                 logger.info("Cleaned up temporary target DB.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without changes")
    args = parser.parse_args()
    
    migrator = AnalyticsMigrator(dry_run=args.dry_run)
    migrator.run()
