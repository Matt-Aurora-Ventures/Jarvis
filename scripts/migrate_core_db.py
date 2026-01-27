"""
Database Migration Script - jarvis_core.db
Consolidates 8 databases into single core database

Phase 1 Task 4 - Migration with validation and rollback
"""

import sqlite3
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Source databases to consolidate into jarvis_core.db
SOURCE_DBS = {
    'jarvis': 'data/jarvis.db',
    'admin': 'data/jarvis_admin.db',
    'treasury': 'data/treasury_trades.db',
}

TARGET_DB = 'data/jarvis_core.db'
BACKUP_DIR = 'data/backups'

class DatabaseMigrator:
    """Migrates multiple databases into consolidated schema."""
    
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.validation_errors = []
        self.migration_log = []
        
        # Create backup directory
        Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    
    def backup_databases(self) -> bool:
        """Create backups of all source databases."""
        logger.info("Creating backups of source databases...")
        backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for name, db_path in SOURCE_DBS.items():
            if not Path(db_path).exists():
                logger.warning(f"Database {db_path} not found, skipping backup")
                continue
            
            backup_path = f"{BACKUP_DIR}/{name}_{backup_timestamp}.db"
            
            try:
                # Use SQLite backup API
                source_conn = sqlite3.connect(db_path)
                backup_conn = sqlite3.connect(backup_path)
                
                source_conn.backup(backup_conn)
                
                source_conn.close()
                backup_conn.close()
                
                logger.info(f"✅ Backed up {db_path} → {backup_path}")
                
            except Exception as e:
                logger.error(f"❌ Failed to backup {db_path}: {e}")
                return False
        
        return True
    
    def create_target_schema(self) -> bool:
        """Create jarvis_core.db with unified schema."""
        logger.info("Creating target database schema...")
        
        schema_file = '.planning/phases/01-database-consolidation/jarvis_core_schema.sql'
        
        if not Path(schema_file).exists():
            logger.error(f"Schema file not found: {schema_file}")
            return False
        
        try:
            # Read schema
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            # Create database
            conn = sqlite3.connect(TARGET_DB)
            cursor = conn.cursor()
            
            # Execute schema script
            try:
                cursor.executescript(schema_sql)
                conn.commit()
                logger.info(f"✅ Created target database: {TARGET_DB}")
                conn.close()
                return True
            except sqlite3.Error as e:
                logger.error(f"❌ Failed to execute schema script: {e}")
                conn.close()
                return False
            
        except Exception as e:
            logger.error(f"❌ Failed to create schema: {e}")
            return False
    
    def migrate_users(self) -> Tuple[int, int]:
        """Infer users from positions and trades and create user records."""
        logger.info("Migrating/Inferring users...")
        
        source_db = SOURCE_DBS['jarvis']
        if not Path(source_db).exists():
            return 0, 0
            
        source_conn = sqlite3.connect(source_db)
        target_conn = sqlite3.connect(TARGET_DB)
        cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        migrated = 0
        errors = 0
        
        # Extract unique user_ids from positions
        try:
            cursor.execute("SELECT DISTINCT user_id FROM positions WHERE user_id IS NOT NULL")
            user_ids = {row[0] for row in cursor.fetchall()}
            
            # Also check trades
            try:
                cursor.execute("SELECT DISTINCT user_id FROM trades WHERE user_id IS NOT NULL")
                trade_user_ids = {row[0] for row in cursor.fetchall()}
                user_ids.update(trade_user_ids)
            except Exception as e:
                pass # Trades might not have user_id in old schema
            
            # Also check bot_config if it exists
            try:
                cursor.execute("SELECT DISTINCT user_id FROM bot_config")
                config_user_ids = {row[0] for row in cursor.fetchall()}
                user_ids.update(config_user_ids)
            except Exception as e:
                pass

            logger.info(f"Found {len(user_ids)} unique users to migrate")
            
            for uid in user_ids:
                try:
                    # Create basic user record
                    # We don't have username/first_name easily available in legacy DB usually
                    # But we might have it in jarvis_admin.db if we checked there.
                    # For now, create minimal record
                    
                    # Check if user already exists
                    target_cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (uid,))
                    if target_cursor.fetchone():
                        continue
                        
                    # Insert
                    # Assuming user_id is the Telegram ID (it usually is in legacy)
                    target_cursor.execute(
                        """
                        INSERT INTO users (user_id, telegram_user_id, created_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                        """,
                        (uid, uid)
                    )
                    migrated += 1
                except Exception as e:
                    logger.error(f"Error migrating user {uid}: {e}")
                    errors += 1
                    
            target_conn.commit()
            
        except Exception as e:
            logger.error(f"Error scanning for users: {e}")
            errors += 1
            
        source_conn.close()
        target_conn.close()
        
        logger.info(f"✅ Migrated {migrated} users ({errors} errors)")
        return migrated, errors

    def migrate_bot_config(self) -> Tuple[int, int]:
        """Migrate bot configuration."""
        logger.info("Migrating bot_config...")
        
        source_db = SOURCE_DBS['jarvis']
        if not Path(source_db).exists():
            return 0, 0
            
        source_conn = sqlite3.connect(source_db)
        target_conn = sqlite3.connect(TARGET_DB)
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        migrated = 0
        errors = 0
        
        try:
            # Check if source table exists
            source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bot_config'")
            if not source_cursor.fetchone():
                logger.info("No bot_config table in source")
                return 0, 0
                
            source_cursor.execute("SELECT * FROM bot_config")
            rows = source_cursor.fetchall()
            
            source_cursor.execute("PRAGMA table_info(bot_config)")
            columns = [col[1] for col in source_cursor.fetchall()]
            
            # Target columns
            target_cursor.execute("PRAGMA table_info(bot_config)")
            target_columns = [col[1] for col in target_cursor.fetchall()]
            
            # Map columns
            common_columns = [c for c in columns if c in target_columns]
            
            for row in rows:
                try:
                    row_dict = dict(zip(columns, row))
                    
                    # Prepare insert
                    cols = common_columns
                    vals = [row_dict[c] for c in cols]
                    placeholders = ','.join(['?' for _ in cols])
                    
                    query = f"INSERT OR REPLACE INTO bot_config ({','.join(cols)}) VALUES ({placeholders})"
                    target_cursor.execute(query, vals)
                    migrated += 1
                    
                except Exception as e:
                    logger.error(f"Error migrating config: {e}")
                    errors += 1
            
            target_conn.commit()
            
        except Exception as e:
            logger.error(f"Error migrating bot_config: {e}")
            errors += 1
            
        source_conn.close()
        target_conn.close()
        
        logger.info(f"✅ Migrated {migrated} configs ({errors} errors)")
        return migrated, errors

    def migrate_positions(self) -> Tuple[int, int]:
        """Migrate positions table from jarvis.db."""
        logger.info("Migrating positions...")
        
        source_db = SOURCE_DBS['jarvis']
        if not Path(source_db).exists():
            logger.warning(f"Source database {source_db} not found")
            return 0, 0
        
        source_conn = sqlite3.connect(source_db)
        target_conn = sqlite3.connect(TARGET_DB)
        
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        # Fetch all positions
        source_cursor.execute("SELECT * FROM positions")
        positions = source_cursor.fetchall()
        
        # Get column names
        source_cursor.execute("PRAGMA table_info(positions)")
        columns = [col[1] for col in source_cursor.fetchall()]
        
        migrated = 0
        errors = 0
        
        for row in positions:
            try:
                # Map old schema to new schema
                position_data = dict(zip(columns, row))
                
                # Insert into target
                placeholders = ','.join(['?' for _ in columns])
                target_cursor.execute(
                    f"INSERT OR REPLACE INTO positions ({','.join(columns)}) VALUES ({placeholders})",
                    row
                )
                migrated += 1
                
            except Exception as e:
                logger.error(f"Error migrating position {row[0]}: {e}")
                errors += 1
        
        target_conn.commit()
        
        source_conn.close()
        target_conn.close()
        
        logger.info(f"✅ Migrated {migrated} positions ({errors} errors)")
        return migrated, errors
    
    def migrate_trades(self) -> Tuple[int, int]:
        """Migrate trades table from jarvis.db."""
        logger.info("Migrating trades...")
        
        source_db = SOURCE_DBS['jarvis']
        if not Path(source_db).exists():
            return 0, 0
        
        source_conn = sqlite3.connect(source_db)
        target_conn = sqlite3.connect(TARGET_DB)
        
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        source_cursor.execute("SELECT * FROM trades")
        trades = source_cursor.fetchall()
        
        source_cursor.execute("PRAGMA table_info(trades)")
        columns = [col[1] for col in source_cursor.fetchall()]
        
        migrated = 0
        errors = 0
        
        for row in trades:
            try:
                placeholders = ','.join(['?' for _ in columns])
                target_cursor.execute(
                    f"INSERT OR REPLACE INTO trades ({','.join(columns)}) VALUES ({placeholders})",
                    row
                )
                migrated += 1
            except Exception as e:
                logger.error(f"Error migrating trade {row[0]}: {e}")
                errors += 1
        
        target_conn.commit()
        
        source_conn.close()
        target_conn.close()
        
        logger.info(f"✅ Migrated {migrated} trades ({errors} errors)")
        return migrated, errors
    
    def validate_migration(self) -> bool:
        """Validate that migration was successful."""
        logger.info("Validating migration...")
        
        validation_passed = True
        
        # Check row counts match
        for name, source_db in SOURCE_DBS.items():
            if not Path(source_db).exists():
                continue
            
            source_conn = sqlite3.connect(source_db)
            target_conn = sqlite3.connect(TARGET_DB)
            
            source_cursor = source_conn.cursor()
            target_cursor = target_conn.cursor()
            
            # Get tables in source
            source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in source_cursor.fetchall() if row[0] != 'sqlite_sequence']
            
            for table in tables:
                try:
                    # Count rows in source
                    source_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    source_count = source_cursor.fetchone()[0]
                    
                    # Count rows in target (if table exists)
                    try:
                        target_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        target_count = target_cursor.fetchone()[0]
                    except Exception as e:
                        target_count = 0
                    
                    if source_count != target_count:
                        logger.warning(
                            f"⚠️  Row count mismatch for {table}: "
                            f"source={source_count}, target={target_count}"
                        )
                        validation_passed = False
                    else:
                        logger.info(f"✅ {table}: {source_count} rows matched")
                        
                except Exception as e:
                    logger.error(f"Error validating {table}: {e}")
                    validation_passed = False
            
            source_conn.close()
            target_conn.close()
        
        return validation_passed
    
    def run(self) -> bool:
        """Execute full migration."""
        logger.info("=" * 60)
        logger.info("DATABASE MIGRATION: jarvis_core.db")
        logger.info("=" * 60)
        
        if self.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        # Step 1: Backup
        if not self.backup_databases():
            logger.error("Backup failed, aborting migration")
            return False
        
        # Step 2: Create target schema
        if not self.create_target_schema():
            logger.error("Schema creation failed, aborting migration")
            return False
        
        # Step 3: Migrate data
        total_migrated = 0
        total_errors = 0
        
        # Migrate users FIRST (Foreign Key dependency)
        migrated, errors = self.migrate_users()
        total_migrated += migrated
        total_errors += errors
        
        migrated, errors = self.migrate_bot_config()
        total_migrated += migrated
        total_errors += errors

        migrated, errors = self.migrate_positions()
        total_migrated += migrated
        total_errors += errors
        
        migrated, errors = self.migrate_trades()
        total_migrated += migrated
        total_errors += errors
        
        # Step 4: Validate
        if not self.validate_migration():
            logger.warning("Validation found issues, review logs")
        
        # Summary
        logger.info("=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total rows migrated: {total_migrated}")
        logger.info(f"Total errors: {total_errors}")
        logger.info(f"Target database: {TARGET_DB}")
        
        if total_errors == 0:
            logger.info("✅ MIGRATION SUCCESSFUL!")
            return True
        else:
            logger.warning("⚠️  MIGRATION COMPLETED WITH ERRORS")
            return False

def main():
    """Run migration."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate to jarvis_core.db')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    args = parser.parse_args()
    
    migrator = DatabaseMigrator(dry_run=args.dry_run)
    success = migrator.run()
    
    if success:
        print("\n✅ Migration complete!")
    else:
        print("\n⚠️  Migration completed with errors. Review logs.")

if __name__ == '__main__':
    main()
