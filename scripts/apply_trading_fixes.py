#!/usr/bin/env python3
"""
Apply critical fixes to trading.py for race condition prevention.

Run this script once to patch the trading engine with safe state management.

Usage:
    python scripts/apply_trading_fixes.py
"""

import re
from pathlib import Path

TRADING_FILE = Path(__file__).parent.parent / "bots" / "treasury" / "trading.py"


def apply_fixes():
    """Apply all fixes to trading.py"""
    print(f"Reading {TRADING_FILE}...")
    content = TRADING_FILE.read_text(encoding="utf-8")
    original = content

    # Fix 1: Add SafeState import after scorekeeper import
    if "from core.safe_state import SafeState" not in content:
        print("Adding SafeState import...")
        content = content.replace(
            "from .scorekeeper import get_scorekeeper, Scorekeeper\n\n# Import centralized audit trail",
            """from .scorekeeper import get_scorekeeper, Scorekeeper

# Import safe state management for race-condition-free file access
try:
    from core.safe_state import SafeState
    SAFE_STATE_AVAILABLE = True
except ImportError:
    SAFE_STATE_AVAILABLE = False
    SafeState = None

# Import centralized audit trail"""
        )

    # Fix 2: Update _load_state to use SafeState
    old_load_state = '''    def _load_state(self):
        """Load positions and history from disk."""
        # Load positions
        if self.POSITIONS_FILE.exists():
            try:
                with open(self.POSITIONS_FILE) as f:
                    data = json.load(f)
                    for pos_data in data:
                        pos = Position.from_dict(pos_data)
                        self.positions[pos.id] = pos
            except Exception as e:
                logger.error(f"Failed to load positions: {e}")

        # Load history
        if self.HISTORY_FILE.exists():
            try:
                with open(self.HISTORY_FILE) as f:
                    data = json.load(f)
                    self.trade_history = [Position.from_dict(p) for p in data]
            except Exception as e:
                logger.error(f"Failed to load history: {e}")'''

    new_load_state = '''    def _load_state(self):
        """Load positions and history from disk with file locking."""
        # Use SafeState for race-condition-free access
        if SAFE_STATE_AVAILABLE:
            self._positions_state = SafeState(self.POSITIONS_FILE, default_value=[])
            self._history_state = SafeState(self.HISTORY_FILE, default_value=[])
            self._volume_state = SafeState(self.DAILY_VOLUME_FILE, default_value={})
            self._audit_state = SafeState(self.AUDIT_LOG_FILE, default_value=[])

            try:
                data = self._positions_state.read()
                for pos_data in data:
                    pos = Position.from_dict(pos_data)
                    self.positions[pos.id] = pos
            except Exception as e:
                logger.error(f"Failed to load positions: {e}")

            try:
                data = self._history_state.read()
                self.trade_history = [Position.from_dict(p) for p in data]
            except Exception as e:
                logger.error(f"Failed to load history: {e}")
        else:
            # Fallback to original implementation
            if self.POSITIONS_FILE.exists():
                try:
                    with open(self.POSITIONS_FILE) as f:
                        data = json.load(f)
                        for pos_data in data:
                            pos = Position.from_dict(pos_data)
                            self.positions[pos.id] = pos
                except Exception as e:
                    logger.error(f"Failed to load positions: {e}")

            if self.HISTORY_FILE.exists():
                try:
                    with open(self.HISTORY_FILE) as f:
                        data = json.load(f)
                        self.trade_history = [Position.from_dict(p) for p in data]
                except Exception as e:
                    logger.error(f"Failed to load history: {e}")'''

    if "_positions_state = SafeState" not in content:
        print("Updating _load_state method...")
        content = content.replace(old_load_state, new_load_state)

    # Fix 3: Update _save_state to use SafeState
    old_save_state = '''    def _save_state(self):
        """Save positions and history to disk."""
        try:
            # Save positions
            with open(self.POSITIONS_FILE, 'w') as f:
                json.dump([p.to_dict() for p in self.positions.values()], f, indent=2)

            # Save history
            with open(self.HISTORY_FILE, 'w') as f:
                json.dump([p.to_dict() for p in self.trade_history], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")'''

    new_save_state = '''    def _save_state(self):
        """Save positions and history to disk with file locking."""
        try:
            if SAFE_STATE_AVAILABLE and hasattr(self, '_positions_state'):
                # Use SafeState for atomic writes with locking
                self._positions_state.write([p.to_dict() for p in self.positions.values()])
                self._history_state.write([p.to_dict() for p in self.trade_history])
            else:
                # Fallback to original implementation
                with open(self.POSITIONS_FILE, 'w') as f:
                    json.dump([p.to_dict() for p in self.positions.values()], f, indent=2)
                with open(self.HISTORY_FILE, 'w') as f:
                    json.dump([p.to_dict() for p in self.trade_history], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")'''

    if "self._positions_state.write" not in content:
        print("Updating _save_state method...")
        content = content.replace(old_save_state, new_save_state)

    # Fix 4: Update _get_daily_volume to use SafeState
    old_get_volume = '''    def _get_daily_volume(self) -> float:
        """Get total trading volume for today (UTC)."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        try:
            if self.DAILY_VOLUME_FILE.exists():
                with open(self.DAILY_VOLUME_FILE) as f:
                    data = json.load(f)
                    if data.get('date') == today:
                        return data.get('volume_usd', 0.0)
        except Exception as e:
            logger.debug(f"Failed to load daily volume: {e}")
        return 0.0'''

    new_get_volume = '''    def _get_daily_volume(self) -> float:
        """Get total trading volume for today (UTC) with file locking."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        try:
            if SAFE_STATE_AVAILABLE and hasattr(self, '_volume_state'):
                data = self._volume_state.read()
                if data.get('date') == today:
                    return data.get('volume_usd', 0.0)
            elif self.DAILY_VOLUME_FILE.exists():
                with open(self.DAILY_VOLUME_FILE) as f:
                    data = json.load(f)
                    if data.get('date') == today:
                        return data.get('volume_usd', 0.0)
        except Exception as e:
            logger.debug(f"Failed to load daily volume: {e}")
        return 0.0'''

    if "self._volume_state.read()" not in content:
        print("Updating _get_daily_volume method...")
        content = content.replace(old_get_volume, new_get_volume)

    # Fix 5: Update _add_daily_volume to use SafeState
    old_add_volume = '''    def _add_daily_volume(self, amount_usd: float):
        """Add to daily trading volume."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        current = self._get_daily_volume()
        try:
            with open(self.DAILY_VOLUME_FILE, 'w') as f:
                json.dump({'date': today, 'volume_usd': current + amount_usd}, f)
        except Exception as e:
            logger.error(f"Failed to save daily volume: {e}")'''

    new_add_volume = '''    def _add_daily_volume(self, amount_usd: float):
        """Add to daily trading volume with file locking."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        current = self._get_daily_volume()
        try:
            if SAFE_STATE_AVAILABLE and hasattr(self, '_volume_state'):
                self._volume_state.write({'date': today, 'volume_usd': current + amount_usd})
            else:
                with open(self.DAILY_VOLUME_FILE, 'w') as f:
                    json.dump({'date': today, 'volume_usd': current + amount_usd}, f)
        except Exception as e:
            logger.error(f"Failed to save daily volume: {e}")'''

    if "self._volume_state.write" not in content:
        print("Updating _add_daily_volume method...")
        content = content.replace(old_add_volume, new_add_volume)

    # Check if changes were made
    if content == original:
        print("No changes needed - file may already be patched or has different formatting.")
        return False

    # Write back
    print(f"Writing fixes to {TRADING_FILE}...")
    TRADING_FILE.write_text(content, encoding="utf-8")
    print("Done! Trading engine now uses SafeState for race-condition-free file access.")
    return True


if __name__ == "__main__":
    apply_fixes()
