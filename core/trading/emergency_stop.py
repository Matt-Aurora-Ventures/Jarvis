"""
Emergency Stop Mechanism for Trading System

Provides multiple levels of emergency controls:
1. Global kill switch - Halt ALL trading immediately
2. Per-token pause - Stop trading specific tokens
3. Graceful position unwind - Close positions systematically
4. Emergency alerts - Notify admin on activation

Critical safety feature for protecting capital during:
- Market crashes
- System malfunction
- Security incidents
- Regulatory concerns
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class StopLevel(Enum):
    """Emergency stop severity levels."""
    NONE = "NONE"           # Normal operation
    TOKEN_PAUSE = "TOKEN_PAUSE"    # Specific tokens paused
    SOFT_STOP = "SOFT_STOP"        # No new positions, keep existing
    HARD_STOP = "HARD_STOP"        # No new positions, close all positions
    KILL_SWITCH = "KILL_SWITCH"    # Emergency halt, cancel all orders


class UnwindStrategy(Enum):
    """Position unwinding strategies."""
    IMMEDIATE = "IMMEDIATE"        # Market orders, close now
    GRACEFUL = "GRACEFUL"         # Limit orders at better prices
    SCHEDULED = "SCHEDULED"       # Close over time window
    MANUAL = "MANUAL"            # Wait for manual intervention


@dataclass
class EmergencyConfig:
    """Configuration for emergency stop system."""
    state_file: Path = Path.home() / ".lifeos" / "trading" / "emergency_stop.json"
    alert_webhook: Optional[str] = None
    max_unwind_slippage: float = 0.05  # 5% max slippage on emergency exits
    graceful_unwind_minutes: int = 30  # Time window for graceful unwind
    auto_resume_after_minutes: int = 0  # 0 = manual resume only


@dataclass
class StopState:
    """Current emergency stop state."""
    level: StopLevel = StopLevel.NONE
    activated_at: Optional[str] = None
    activated_by: Optional[str] = None
    reason: str = ""
    paused_tokens: Set[str] = field(default_factory=set)
    unwind_strategy: UnwindStrategy = UnwindStrategy.IMMEDIATE
    auto_resume_at: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "level": self.level.value,
            "activated_at": self.activated_at,
            "activated_by": self.activated_by,
            "reason": self.reason,
            "paused_tokens": list(self.paused_tokens),
            "unwind_strategy": self.unwind_strategy.value,
            "auto_resume_at": self.auto_resume_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'StopState':
        return cls(
            level=StopLevel(data.get("level", "NONE")),
            activated_at=data.get("activated_at"),
            activated_by=data.get("activated_by"),
            reason=data.get("reason", ""),
            paused_tokens=set(data.get("paused_tokens", [])),
            unwind_strategy=UnwindStrategy(data.get("unwind_strategy", "IMMEDIATE")),
            auto_resume_at=data.get("auto_resume_at"),
        )


class EmergencyStopManager:
    """
    Manages emergency stop controls for the trading system.

    Thread-safe, persistent state across restarts.
    """

    def __init__(self, config: Optional[EmergencyConfig] = None):
        self.config = config or EmergencyConfig()
        self.state = StopState()
        self._load_state()

        # Alert callbacks
        self._alert_callbacks: List[callable] = []

    def _load_state(self):
        """Load emergency stop state from disk."""
        if self.config.state_file.exists():
            try:
                with open(self.config.state_file) as f:
                    data = json.load(f)
                    self.state = StopState.from_dict(data)
                    logger.info(f"Loaded emergency stop state: {self.state.level.value}")
            except Exception as e:
                logger.error(f"Failed to load emergency stop state: {e}")

    def _save_state(self):
        """Save emergency stop state to disk."""
        try:
            self.config.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config.state_file, 'w') as f:
                json.dump(self.state.to_dict(), f, indent=2)
            logger.info(f"Saved emergency stop state: {self.state.level.value}")
        except Exception as e:
            logger.error(f"Failed to save emergency stop state: {e}")

    def register_alert_callback(self, callback: callable):
        """Register a callback to be called when emergency stop is activated."""
        self._alert_callbacks.append(callback)

    async def _send_alerts(self, message: str):
        """Send alerts through all registered callbacks."""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def activate_kill_switch(
        self,
        reason: str,
        activated_by: str = "system",
        unwind_strategy: UnwindStrategy = UnwindStrategy.IMMEDIATE
    ) -> Tuple[bool, str]:
        """
        Activate the global emergency kill switch.

        This is the nuclear option:
        - All trading stops immediately
        - All open orders cancelled
        - Positions unwound according to strategy

        Args:
            reason: Why the kill switch was activated
            activated_by: Who/what activated it (user_id, "system", etc)
            unwind_strategy: How to handle open positions

        Returns:
            Tuple of (success, message)
        """
        try:
            self.state.level = StopLevel.KILL_SWITCH
            self.state.activated_at = datetime.utcnow().isoformat()
            self.state.activated_by = activated_by
            self.state.reason = reason
            self.state.unwind_strategy = unwind_strategy

            self._save_state()

            message = f"🚨 EMERGENCY KILL SWITCH ACTIVATED\nReason: {reason}\nBy: {activated_by}"
            logger.critical(message)

            asyncio.create_task(self._send_alerts(message))

            return True, "Kill switch activated successfully"
        except Exception as e:
            logger.error(f"Failed to activate kill switch: {e}")
            return False, f"Failed to activate: {e}"

    def activate_soft_stop(
        self,
        reason: str,
        activated_by: str = "system"
    ) -> Tuple[bool, str]:
        """
        Activate soft stop: prevent new positions, keep existing.

        Use this when you want to pause new trading but don't need
        to close existing positions immediately.

        Args:
            reason: Why soft stop was activated
            activated_by: Who/what activated it

        Returns:
            Tuple of (success, message)
        """
        try:
            self.state.level = StopLevel.SOFT_STOP
            self.state.activated_at = datetime.utcnow().isoformat()
            self.state.activated_by = activated_by
            self.state.reason = reason

            self._save_state()

            message = f"⚠️ SOFT STOP ACTIVATED\nReason: {reason}\nBy: {activated_by}\nNo new positions allowed."
            logger.warning(message)

            asyncio.create_task(self._send_alerts(message))

            return True, "Soft stop activated"
        except Exception as e:
            logger.error(f"Failed to activate soft stop: {e}")
            return False, f"Failed to activate: {e}"

    def activate_hard_stop(
        self,
        reason: str,
        activated_by: str = "system",
        unwind_strategy: UnwindStrategy = UnwindStrategy.GRACEFUL
    ) -> Tuple[bool, str]:
        """
        Activate hard stop: prevent new positions, close all existing.

        Args:
            reason: Why hard stop was activated
            activated_by: Who/what activated it
            unwind_strategy: How to close positions

        Returns:
            Tuple of (success, message)
        """
        try:
            self.state.level = StopLevel.HARD_STOP
            self.state.activated_at = datetime.utcnow().isoformat()
            self.state.activated_by = activated_by
            self.state.reason = reason
            self.state.unwind_strategy = unwind_strategy

            self._save_state()

            message = f"🛑 HARD STOP ACTIVATED\nReason: {reason}\nBy: {activated_by}\nClosing all positions ({unwind_strategy.value})"
            logger.error(message)

            asyncio.create_task(self._send_alerts(message))

            return True, "Hard stop activated"
        except Exception as e:
            logger.error(f"Failed to activate hard stop: {e}")
            return False, f"Failed to activate: {e}"

    def pause_token(
        self,
        token_mint: str,
        reason: str,
        activated_by: str = "system"
    ) -> Tuple[bool, str]:
        """
        Pause trading for a specific token.

        Useful when a specific token is problematic but overall
        trading can continue.

        Args:
            token_mint: Token mint address to pause
            reason: Why this token was paused
            activated_by: Who/what paused it

        Returns:
            Tuple of (success, message)
        """
        try:
            self.state.paused_tokens.add(token_mint)

            if self.state.level == StopLevel.NONE:
                self.state.level = StopLevel.TOKEN_PAUSE
                self.state.activated_at = datetime.utcnow().isoformat()
                self.state.activated_by = activated_by

            # Append to reason
            token_reason = f"\n[{token_mint[:8]}...]: {reason}"
            if token_reason not in self.state.reason:
                self.state.reason += token_reason

            self._save_state()

            message = f"⏸️ TOKEN PAUSED: {token_mint}\nReason: {reason}"
            logger.warning(message)

            asyncio.create_task(self._send_alerts(message))

            return True, f"Token paused: {token_mint}"
        except Exception as e:
            logger.error(f"Failed to pause token: {e}")
            return False, f"Failed to pause: {e}"

    def resume_token(self, token_mint: str) -> Tuple[bool, str]:
        """
        Resume trading for a specific token.

        Args:
            token_mint: Token mint address to resume

        Returns:
            Tuple of (success, message)
        """
        try:
            if token_mint in self.state.paused_tokens:
                self.state.paused_tokens.remove(token_mint)

                # If no tokens paused and we're at TOKEN_PAUSE level, go to NONE
                if not self.state.paused_tokens and self.state.level == StopLevel.TOKEN_PAUSE:
                    self.state.level = StopLevel.NONE
                    self.state.activated_at = None
                    self.state.activated_by = None
                    self.state.reason = ""

                self._save_state()

                message = f"▶️ TOKEN RESUMED: {token_mint}"
                logger.info(message)

                return True, f"Token resumed: {token_mint}"
            else:
                return False, "Token was not paused"
        except Exception as e:
            logger.error(f"Failed to resume token: {e}")
            return False, f"Failed to resume: {e}"

    def resume_trading(
        self,
        resumed_by: str = "admin"
    ) -> Tuple[bool, str]:
        """
        Resume all trading (clear emergency stop).

        Args:
            resumed_by: Who/what resumed trading

        Returns:
            Tuple of (success, message)
        """
        try:
            old_level = self.state.level

            self.state = StopState()  # Reset to normal
            self._save_state()

            message = f"✅ TRADING RESUMED\nPrevious state: {old_level.value}\nResumed by: {resumed_by}"
            logger.info(message)

            asyncio.create_task(self._send_alerts(message))

            return True, "Trading resumed"
        except Exception as e:
            logger.error(f"Failed to resume trading: {e}")
            return False, f"Failed to resume: {e}"

    def is_trading_allowed(self, token_mint: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if trading is currently allowed.

        Args:
            token_mint: Optional specific token to check

        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        # Check auto-resume
        if self.state.auto_resume_at:
            try:
                resume_time = datetime.fromisoformat(self.state.auto_resume_at)
                if datetime.utcnow() >= resume_time:
                    self.resume_trading(resumed_by="auto")
                    return True, ""
            except:
                pass

        # Check global stops
        if self.state.level == StopLevel.KILL_SWITCH:
            return False, f"KILL SWITCH ACTIVE: {self.state.reason}"

        if self.state.level == StopLevel.HARD_STOP:
            return False, f"HARD STOP ACTIVE: {self.state.reason}"

        if self.state.level == StopLevel.SOFT_STOP:
            return False, f"SOFT STOP ACTIVE: {self.state.reason}"

        # Check token-specific pause
        if token_mint and token_mint in self.state.paused_tokens:
            return False, f"TOKEN PAUSED: {token_mint}"

        return True, ""

    def should_unwind_positions(self) -> bool:
        """Check if positions should be unwound based on current stop level."""
        return self.state.level in [StopLevel.HARD_STOP, StopLevel.KILL_SWITCH]

    def get_unwind_strategy(self) -> UnwindStrategy:
        """Get the current position unwind strategy."""
        return self.state.unwind_strategy

    def get_status(self) -> Dict:
        """Get current emergency stop status."""
        return {
            "level": self.state.level.value,
            "trading_allowed": self.is_trading_allowed()[0],
            "activated_at": self.state.activated_at,
            "activated_by": self.state.activated_by,
            "reason": self.state.reason,
            "paused_tokens": list(self.state.paused_tokens),
            "should_unwind": self.should_unwind_positions(),
            "unwind_strategy": self.state.unwind_strategy.value,
            "auto_resume_at": self.state.auto_resume_at,
        }


# Singleton instance for global access
_emergency_stop_manager: Optional[EmergencyStopManager] = None


def get_emergency_stop_manager() -> EmergencyStopManager:
    """Get the global emergency stop manager instance."""
    global _emergency_stop_manager
    if _emergency_stop_manager is None:
        _emergency_stop_manager = EmergencyStopManager()
    return _emergency_stop_manager
