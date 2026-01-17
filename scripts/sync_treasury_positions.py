#!/usr/bin/env python3
"""
Sync positions from TreasuryTrader to Scorekeeper for dashboard display.

Usage:
    python scripts/sync_treasury_positions.py
"""

import json
import sys
import io
from pathlib import Path

# Handle Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bots.treasury.scorekeeper import get_scorekeeper
from bots.treasury.trading import TreasuryTrader


def sync_positions():
    """Load treasury positions and sync to scorekeeper."""
    try:
        # Load treasury positions from disk
        positions_file = Path(__file__).parent.parent / "bots" / "treasury" / ".positions.json"

        if not positions_file.exists():
            print(f"[ERROR] Positions file not found: {positions_file}")
            return 0

        with open(positions_file) as f:
            treasury_positions = json.load(f)

        print(f"[INFO] Found {len(treasury_positions)} positions in treasury")

        # Get scorekeeper and sync
        scorekeeper = get_scorekeeper()
        synced = scorekeeper.sync_from_treasury_positions(treasury_positions)

        print(f"[SUCCESS] Synced {synced} OPEN positions to scorekeeper")

        # Display synced positions
        open_pos = scorekeeper.get_open_positions()
        if open_pos:
            print(f"\n[OPEN POSITIONS] {len(open_pos)} positions now visible in dashboard:")
            for pos in open_pos[:5]:
                print(f"  * {pos.symbol}: ${pos.entry_price:.6f} (TP: ${pos.take_profit_price:.6f}, SL: ${pos.stop_loss_price:.6f})")
            if len(open_pos) > 5:
                print(f"  ... and {len(open_pos) - 5} more")

        return synced

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    sync_positions()
