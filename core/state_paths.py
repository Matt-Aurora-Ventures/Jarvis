"""
Centralized State File Paths.

All persistent state files should be stored under ~/.lifeos/ to ensure:
1. Consistency across restarts
2. Easy backup and recovery
3. No confusion about where state is stored
4. Proper isolation from source code

Usage:
    from core.state_paths import STATE_PATHS
    positions_file = STATE_PATHS.positions
"""

import os
from pathlib import Path


class StatePaths:
    """Centralized path manager for all persistent state files.

    All state files are stored under ~/.lifeos/ with consistent naming.
    """

    def __init__(self):
        # Base directories
        self.lifeos_root = Path.home() / ".lifeos"
        self.trading_dir = self.lifeos_root / "trading"
        self.data_dir = self.lifeos_root / "data"
        self.bots_dir = self.lifeos_root / "bots"
        self.logs_dir = self.lifeos_root / "logs"

        # Ensure directories exist
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Create directories if they don't exist."""
        for dir_path in [
            self.lifeos_root,
            self.trading_dir,
            self.data_dir,
            self.bots_dir,
            self.logs_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    # ========== Trading State Files ==========

    @property
    def positions(self) -> Path:
        """Treasury positions state file (primary - ~/.lifeos/trading/)."""
        return self.trading_dir / "positions.json"

    @property
    def trader_positions(self) -> Path:
        """Treasury positions state file (secondary - data/trader/)."""
        # Secondary location in project data directory for backup/tooling access
        trader_dir = Path(__file__).parent.parent / "data" / "trader"
        trader_dir.mkdir(parents=True, exist_ok=True)
        return trader_dir / "positions.json"

    @property
    def trader_trade_history(self) -> Path:
        """Treasury trade history (canonical - data/trader/)."""
        trader_dir = Path(__file__).parent.parent / "data" / "trader"
        trader_dir.mkdir(parents=True, exist_ok=True)
        return trader_dir / "trade_history.json"

    @property
    def trader_daily_volume(self) -> Path:
        """Treasury daily volume (canonical - data/trader/)."""
        trader_dir = Path(__file__).parent.parent / "data" / "trader"
        trader_dir.mkdir(parents=True, exist_ok=True)
        return trader_dir / "daily_volume.json"

    @property
    def exit_intents(self) -> Path:
        """Exit intent tracking for positions."""
        return self.trading_dir / "exit_intents.json"

    @property
    def execution_reliability(self) -> Path:
        """Execution reliability metrics."""
        return self.trading_dir / "execution_reliability.json"

    @property
    def perps_state(self) -> Path:
        """Jupiter perpetuals state."""
        return self.trading_dir / "perps_state.json"

    @property
    def lut_module_state(self) -> Path:
        """LUT micro alpha module state."""
        return self.trading_dir / "lut_module_state.json"

    @property
    def lut_daemon_state(self) -> Path:
        """LUT daemon state."""
        return self.trading_dir / "lut_daemon_state.json"

    @property
    def symbol_map(self) -> Path:
        """Token symbol mapping."""
        return self.trading_dir / "symbol_map.json"

    @property
    def reconcile_report(self) -> Path:
        """Position reconciliation report."""
        return self.trading_dir / "reconcile_report.json"

    @property
    def intent_trade_report(self) -> Path:
        """Intent-trade reconciliation report."""
        return self.trading_dir / "intent_trade_report.json"

    # ========== Grok/AI State Files ==========

    @property
    def grok_state(self) -> Path:
        """Grok client state (rate limits, etc.)."""
        return self.data_dir / "grok_state.json"

    @property
    def grok_cache(self) -> Path:
        """Grok response cache."""
        return self.data_dir / "grok_cache.json"

    @property
    def grok_usage(self) -> Path:
        """Grok API usage tracking."""
        return self.data_dir / "grok_usage.json"

    @property
    def grok_cookies(self) -> Path:
        """Grok session cookies."""
        return self.data_dir / "grok_cookies.json"

    # ========== Bot State Files ==========

    @property
    def x_engine_state(self) -> Path:
        """X/Twitter autonomous engine state."""
        return self.bots_dir / "x_engine_state.json"

    @property
    def x_bot_state(self) -> Path:
        """X bot general state."""
        return self.bots_dir / "x_bot_state.json"

    @property
    def circuit_breaker_state(self) -> Path:
        """Circuit breaker state for X CLI."""
        return self.bots_dir / "circuit_breaker_state.json"

    @property
    def agent_registry_state(self) -> Path:
        """Agent registry state."""
        return self.data_dir / "agents" / "registry_state.json"

    # ========== System State Files ==========

    @property
    def restart_state(self) -> Path:
        """Autonomous restart state."""
        return self.data_dir / "restart_state.json"

    @property
    def backup_state(self) -> Path:
        """Backup manager state."""
        return self.data_dir / "backup_state.json"

    @property
    def sniper_state(self) -> Path:
        """Micro cap sniper state."""
        return self.data_dir / "sniper_state.json"

    @property
    def audit_log(self) -> Path:
        """Security audit log (append-only JSONL)."""
        return self.logs_dir / "audit.jsonl"

    # ========== Legacy Path Migration ==========

    def get_legacy_path(self, state_type: str) -> Path | None:
        """Get legacy path for migration purposes.

        Returns the old path where state might have been stored,
        or None if no legacy path exists.
        """
        from pathlib import Path as P

        # Map of state types to their old locations
        legacy_map = {
            "positions": P(__file__).parent.parent / "bots" / "treasury" / ".positions.json",
            "trade_history": P(__file__).parent.parent / "bots" / "treasury" / ".trade_history.json",
            "grok_state": P(__file__).parent.parent / "bots" / "twitter" / ".grok_state.json",
            "x_engine_state": P(__file__).parent.parent / "data" / ".x_engine_state.json",
            "circuit_breaker": P(__file__).parent.parent / "data" / ".circuit_breaker_state.json",
        }

        return legacy_map.get(state_type)

    def migrate_if_needed(self, state_type: str) -> bool:
        """Migrate state from legacy location if it exists and new doesn't.

        Returns True if migration occurred.
        """
        import shutil
        import logging

        logger = logging.getLogger(__name__)

        # Get paths
        new_path = getattr(self, state_type, None)
        legacy_path = self.get_legacy_path(state_type)

        if not new_path or not legacy_path:
            return False

        # Check if migration needed
        if legacy_path.exists() and not new_path.exists():
            try:
                new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_path, new_path)
                logger.info(f"Migrated {state_type} from {legacy_path} to {new_path}")
                return True
            except Exception as e:
                logger.warning(f"Failed to migrate {state_type}: {e}")
                return False

        return False


# Singleton instance
STATE_PATHS = StatePaths()


def get_state_path(name: str) -> Path:
    """Convenience function to get a state path by name.

    Args:
        name: Name of the state file (e.g., "positions", "grok_state")

    Returns:
        Path to the state file

    Raises:
        AttributeError: If the state name is not recognized
    """
    return getattr(STATE_PATHS, name)
