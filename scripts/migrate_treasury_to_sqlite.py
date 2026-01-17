#!/usr/bin/env python3
"""
Migrate Treasury Data from JSON to SQLite

Reads existing JSON files and imports them into the new SQLite database.
Creates a backup of the JSON files before migration.

Usage:
    python scripts/migrate_treasury_to_sqlite.py [--dry-run]
"""

import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from bots.treasury.database import (
    TreasuryDatabase,
    DBPosition,
    get_treasury_database,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Source JSON files
DATA_DIR = project_root / "data"
SCOREKEEPER_FILE = DATA_DIR / "treasury_scorekeeper.json"
ORDERS_FILE = DATA_DIR / "treasury_orders.json"
BACKUP_DIR = DATA_DIR / "backup"


def load_json_data():
    """Load existing JSON data."""
    data = {
        "positions": {},
        "trades": [],
        "scorecard": {},
    }

    if SCOREKEEPER_FILE.exists():
        try:
            with open(SCOREKEEPER_FILE) as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data.get('positions', {}))} positions from JSON")
        except Exception as e:
            logger.error(f"Failed to load scorekeeper JSON: {e}")

    return data


def backup_json_files():
    """Backup JSON files before migration."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for src_file in [SCOREKEEPER_FILE, ORDERS_FILE]:
        if src_file.exists():
            dst_file = BACKUP_DIR / f"{src_file.stem}_{timestamp}.json"
            shutil.copy2(src_file, dst_file)
            logger.info(f"Backed up {src_file.name} to {dst_file.name}")


def migrate_position(pos_data: dict, db: TreasuryDatabase) -> bool:
    """Migrate a single position to SQLite."""
    try:
        # Map old status to new
        status_map = {
            "open": "OPEN",
            "closed_tp": "CLOSED",
            "closed_sl": "CLOSED",
            "closed_manual": "CLOSED",
            "failed": "CLOSED",
        }

        old_status = pos_data.get("status", "open")
        new_status = status_map.get(old_status, "OPEN")

        # Determine exit reason from old status
        exit_reason = None
        if old_status == "closed_tp":
            exit_reason = "TP"
        elif old_status == "closed_sl":
            exit_reason = "SL"
        elif old_status in ("closed_manual", "failed"):
            exit_reason = "MANUAL"

        position = DBPosition(
            id=pos_data["id"],
            token_address=pos_data.get("token_mint", ""),
            token_symbol=pos_data.get("symbol", "UNKNOWN"),
            side="LONG",  # Current system only does longs
            entry_price=pos_data.get("entry_price", 0),
            entry_amount_sol=pos_data.get("entry_amount_sol", 0),
            entry_amount_tokens=pos_data.get("entry_amount_tokens", 0),
            entry_timestamp=pos_data.get("opened_at", datetime.now(timezone.utc).isoformat()),
            exit_price=pos_data.get("exit_price") if new_status == "CLOSED" else None,
            exit_timestamp=pos_data.get("closed_at") if new_status == "CLOSED" else None,
            exit_reason=exit_reason,
            pnl_sol=pos_data.get("pnl_sol") if new_status == "CLOSED" else None,
            pnl_percent=pos_data.get("pnl_pct") if new_status == "CLOSED" else None,
            tp_price=pos_data.get("take_profit_price"),
            sl_price=pos_data.get("stop_loss_price"),
            status=new_status,
            tx_entry=pos_data.get("tx_signature_entry", ""),
            tx_exit=pos_data.get("tx_signature_exit", ""),
            user_id=pos_data.get("user_id", 0),
        )

        # Insert directly (not via open_position to avoid duplicate stat updates)
        with db._get_conn() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO positions (
                    id, token_address, token_symbol, side,
                    entry_price, entry_amount_sol, entry_amount_tokens,
                    entry_timestamp, exit_price, exit_timestamp, exit_reason,
                    pnl_sol, pnl_percent, tp_price, sl_price,
                    status, tx_entry, tx_exit, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.id,
                position.token_address,
                position.token_symbol,
                position.side,
                position.entry_price,
                position.entry_amount_sol,
                position.entry_amount_tokens,
                position.entry_timestamp,
                position.exit_price,
                position.exit_timestamp,
                position.exit_reason,
                position.pnl_sol,
                position.pnl_percent,
                position.tp_price,
                position.sl_price,
                position.status,
                position.tx_entry,
                position.tx_exit,
                position.user_id,
            ))

        return True

    except Exception as e:
        logger.error(f"Failed to migrate position {pos_data.get('id')}: {e}")
        return False


def migrate_scorecard(scorecard: dict, db: TreasuryDatabase):
    """Migrate scorecard stats to SQLite."""
    try:
        with db._get_conn() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE treasury_stats SET
                    total_trades = ?,
                    total_wins = ?,
                    total_losses = ?,
                    current_streak = ?,
                    best_win_streak = ?,
                    worst_loss_streak = ?,
                    all_time_pnl_sol = ?,
                    largest_win_sol = ?,
                    largest_loss_sol = ?,
                    updated_at = ?
                WHERE id = 1
            """, (
                scorecard.get("total_trades", 0),
                scorecard.get("winning_trades", 0),
                scorecard.get("losing_trades", 0),
                scorecard.get("current_streak", 0),
                scorecard.get("best_streak", 0),
                scorecard.get("worst_streak", 0),
                scorecard.get("total_pnl_sol", 0),
                scorecard.get("largest_win_sol", 0),
                scorecard.get("largest_loss_sol", 0),
                datetime.now(timezone.utc).isoformat(),
            ))

        logger.info("Migrated scorecard stats")

    except Exception as e:
        logger.error(f"Failed to migrate scorecard: {e}")


def verify_migration(json_data: dict, db: TreasuryDatabase) -> bool:
    """Verify migration was successful."""
    json_pos_count = len(json_data.get("positions", {}))

    with db._get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM positions")
        db_pos_count = cursor.fetchone()[0]

    if json_pos_count != db_pos_count:
        logger.error(f"Position count mismatch: JSON={json_pos_count}, DB={db_pos_count}")
        return False

    logger.info(f"Verification passed: {db_pos_count} positions migrated")
    return True


def main(dry_run: bool = False):
    """Run the migration."""
    logger.info("=" * 60)
    logger.info("TREASURY JSON → SQLite MIGRATION")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    # Load existing data
    json_data = load_json_data()

    if not json_data.get("positions"):
        logger.warning("No positions found in JSON - nothing to migrate")
        return

    if not dry_run:
        # Backup JSON files
        backup_json_files()

    # Initialize database
    db = get_treasury_database()
    logger.info(f"Database initialized at {db.db_path}")

    # Migrate positions
    positions = json_data.get("positions", {})
    migrated = 0
    failed = 0

    for pos_id, pos_data in positions.items():
        if dry_run:
            logger.info(f"Would migrate: {pos_data.get('symbol')} ({pos_id})")
            migrated += 1
        else:
            if migrate_position(pos_data, db):
                migrated += 1
            else:
                failed += 1

    logger.info(f"Positions: {migrated} migrated, {failed} failed")

    # Migrate scorecard
    if not dry_run and json_data.get("scorecard"):
        migrate_scorecard(json_data["scorecard"], db)

    # Verify
    if not dry_run:
        if verify_migration(json_data, db):
            logger.info("✅ Migration completed successfully")
        else:
            logger.error("❌ Migration verification failed")

    logger.info("=" * 60)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    main(dry_run=dry_run)
