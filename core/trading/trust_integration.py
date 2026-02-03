"""
Trust Ladder Trading Integration
================================
Integrates the trust ladder with trading decisions for autonomous position sizing.

Trust Levels:
  0 (Supervised):  Max $25 per trade, requires confirmation
  1 (Assisted):    Max $100 per trade, 24h cooldown on large trades
  2 (Monitored):   Max $500 per trade, daily limit $2000
  3 (Autonomous):  Max $2000 per trade, daily limit $10000
  4 (Trusted):     Max $5000 per trade, daily limit $25000

Risk Scaling:
  - Position size scales with trust level
  - Stop-loss tightens at lower trust levels
  - Take-profit targets adjust based on historical win rate

Usage:
    from core.trading.trust_integration import TrustAwareTrader

    trader = TrustAwareTrader()

    # Check if trade is allowed
    allowed, reason = trader.can_execute_trade(amount_usd=500)

    # Get recommended position size
    position = trader.get_position_parameters(
        token="BONK",
        sentiment_score=0.75,
        base_amount_usd=100
    )

    # Record trade outcome (updates trust ladder)
    trader.record_outcome(success=True, pnl_percent=15.5)
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TrustLevel:
    """Trust level configuration."""
    level: int
    name: str
    max_trade_usd: float
    daily_limit_usd: float
    requires_confirmation: bool
    stop_loss_multiplier: float  # 1.0 = standard, 1.5 = tighter
    cooldown_hours: int  # Hours between large trades


# Trust level configurations
TRUST_LEVELS = {
    0: TrustLevel(0, "Supervised", 25, 100, True, 1.5, 24),
    1: TrustLevel(1, "Assisted", 100, 500, True, 1.3, 12),
    2: TrustLevel(2, "Monitored", 500, 2000, False, 1.2, 6),
    3: TrustLevel(3, "Autonomous", 2000, 10000, False, 1.0, 2),
    4: TrustLevel(4, "Trusted", 5000, 25000, False, 0.9, 1),
}


@dataclass
class PositionParameters:
    """Recommended position parameters based on trust level."""
    amount_usd: float
    stop_loss_percent: float
    take_profit_percent: float
    requires_confirmation: bool
    reasoning: str


class TrustAwareTrader:
    """
    Trading decisions integrated with trust ladder.

    Automatically adjusts position sizes and risk parameters
    based on the bot's accumulated trust score.
    """

    def __init__(self, trust_ladder_path: Optional[str] = None):
        """
        Initialize the trust-aware trader.

        Args:
            trust_ladder_path: Path to trust_ladder.json (default: data/trust_ladder.json)
        """
        if trust_ladder_path:
            self.trust_path = Path(trust_ladder_path)
        else:
            jarvis_home = os.environ.get("JARVIS_HOME", ".")
            self.trust_path = Path(jarvis_home) / "data" / "trust_ladder.json"

        self._load_trust_ladder()
        self._daily_spent: float = 0.0
        self._daily_reset: datetime = datetime.now(timezone.utc)
        self._last_large_trade: Optional[datetime] = None

    def _load_trust_ladder(self) -> None:
        """Load trust ladder from file."""
        try:
            if self.trust_path.exists():
                with open(self.trust_path) as f:
                    self._trust_data = json.load(f)
            else:
                logger.warning(f"Trust ladder not found at {self.trust_path}, using defaults")
                self._trust_data = {
                    "level": 0,
                    "level_name": "Supervised",
                    "successful_actions": 0,
                    "major_errors": 0,
                }
        except Exception as e:
            logger.error(f"Failed to load trust ladder: {e}")
            self._trust_data = {"level": 0}

    def _save_trust_ladder(self) -> None:
        """Save trust ladder to file."""
        try:
            self.trust_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.trust_path, "w") as f:
                json.dump(self._trust_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save trust ladder: {e}")

    @property
    def current_level(self) -> TrustLevel:
        """Get current trust level configuration."""
        level_num = min(self._trust_data.get("level", 0), 4)
        return TRUST_LEVELS[level_num]

    @property
    def successful_actions(self) -> int:
        """Number of successful actions."""
        return self._trust_data.get("successful_actions", 0)

    def _reset_daily_if_needed(self) -> None:
        """Reset daily spent if new day."""
        now = datetime.now(timezone.utc)
        if now.date() > self._daily_reset.date():
            self._daily_spent = 0.0
            self._daily_reset = now

    def can_execute_trade(
        self,
        amount_usd: float,
        skip_cooldown: bool = False,
    ) -> Tuple[bool, str]:
        """
        Check if a trade is allowed under current trust level.

        Args:
            amount_usd: Trade amount in USD
            skip_cooldown: Bypass cooldown check (for user-initiated trades)

        Returns:
            (allowed, reason) tuple
        """
        self._reset_daily_if_needed()
        level = self.current_level

        # Check max trade size
        if amount_usd > level.max_trade_usd:
            return False, f"Amount ${amount_usd:.2f} exceeds trust level max ${level.max_trade_usd:.2f}"

        # Check daily limit
        if self._daily_spent + amount_usd > level.daily_limit_usd:
            remaining = level.daily_limit_usd - self._daily_spent
            return False, f"Daily limit reached. Remaining: ${remaining:.2f}"

        # Check cooldown for large trades (>50% of max)
        if not skip_cooldown and amount_usd > level.max_trade_usd * 0.5:
            if self._last_large_trade:
                cooldown_end = self._last_large_trade + timedelta(hours=level.cooldown_hours)
                if datetime.now(timezone.utc) < cooldown_end:
                    wait_minutes = (cooldown_end - datetime.now(timezone.utc)).total_seconds() / 60
                    return False, f"Cooldown active. Wait {wait_minutes:.0f} minutes"

        return True, "Trade allowed"

    def get_position_parameters(
        self,
        token: str,
        sentiment_score: float,
        base_amount_usd: float,
        base_stop_loss: float = 15.0,
        base_take_profit: float = 30.0,
    ) -> PositionParameters:
        """
        Calculate position parameters based on trust level and sentiment.

        Args:
            token: Token symbol
            sentiment_score: AI sentiment score (0.0 to 1.0)
            base_amount_usd: Desired trade amount
            base_stop_loss: Base stop-loss percentage
            base_take_profit: Base take-profit percentage

        Returns:
            PositionParameters with adjusted values
        """
        level = self.current_level

        # Scale amount by trust level (and cap at max)
        trust_multiplier = 0.5 + (level.level * 0.25)  # 0.5 to 1.5
        sentiment_multiplier = 0.5 + (sentiment_score * 0.5)  # 0.5 to 1.0

        adjusted_amount = base_amount_usd * trust_multiplier * sentiment_multiplier
        adjusted_amount = min(adjusted_amount, level.max_trade_usd)

        # Tighter stop-loss at lower trust levels
        adjusted_stop_loss = base_stop_loss * level.stop_loss_multiplier

        # More conservative take-profit at lower trust levels
        tp_multiplier = 1.0 + ((4 - level.level) * 0.1)  # 1.4 down to 1.0
        adjusted_take_profit = base_take_profit * tp_multiplier

        reasoning = (
            f"Trust Level {level.level} ({level.name}): "
            f"Base ${base_amount_usd:.2f} × trust {trust_multiplier:.2f} × sentiment {sentiment_multiplier:.2f} "
            f"= ${adjusted_amount:.2f}"
        )

        return PositionParameters(
            amount_usd=adjusted_amount,
            stop_loss_percent=adjusted_stop_loss,
            take_profit_percent=adjusted_take_profit,
            requires_confirmation=level.requires_confirmation,
            reasoning=reasoning,
        )

    def record_outcome(
        self,
        success: bool,
        pnl_percent: Optional[float] = None,
        is_major_error: bool = False,
    ) -> None:
        """
        Record trade outcome and update trust ladder.

        Args:
            success: Whether the trade was successful
            pnl_percent: Profit/loss percentage (optional)
            is_major_error: Flag for major errors (causes trust level drop)
        """
        self._load_trust_ladder()  # Refresh

        if success:
            self._trust_data["successful_actions"] = self.successful_actions + 1
            logger.info(f"Trade success recorded. Total: {self.successful_actions}")

            # Check for level up
            milestones = self._trust_data.get("milestones", {})
            current_level = self._trust_data.get("level", 0)

            level_thresholds = {1: 10, 2: 50, 3: 200, 4: 1000}
            next_level = current_level + 1

            if next_level in level_thresholds:
                if self.successful_actions >= level_thresholds[next_level]:
                    self._trust_data["level"] = next_level
                    self._trust_data["level_name"] = TRUST_LEVELS[next_level].name
                    logger.info(f"🎉 Trust level UP! Now at level {next_level}: {TRUST_LEVELS[next_level].name}")

        elif is_major_error:
            # Major error: drop trust level
            self._trust_data["major_errors"] = self._trust_data.get("major_errors", 0) + 1
            current_level = self._trust_data.get("level", 0)
            if current_level > 0:
                self._trust_data["level"] = current_level - 1
                self._trust_data["level_name"] = TRUST_LEVELS[current_level - 1].name
                logger.warning(f"⚠️ Trust level DOWN due to major error. Now at level {current_level - 1}")

        # Update timestamp
        self._trust_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Add to action log
        if "action_log" not in self._trust_data:
            self._trust_data["action_log"] = []

        self._trust_data["action_log"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "pnl_percent": pnl_percent,
            "is_major_error": is_major_error,
        })

        # Keep only last 100 actions in log
        self._trust_data["action_log"] = self._trust_data["action_log"][-100:]

        self._save_trust_ladder()

    def mark_trade_executed(self, amount_usd: float) -> None:
        """Mark that a trade was executed (for daily limit tracking)."""
        self._reset_daily_if_needed()
        self._daily_spent += amount_usd

        if amount_usd > self.current_level.max_trade_usd * 0.5:
            self._last_large_trade = datetime.now(timezone.utc)

    def get_status(self) -> Dict[str, Any]:
        """Get current trading trust status."""
        self._reset_daily_if_needed()
        level = self.current_level

        return {
            "trust_level": level.level,
            "trust_name": level.name,
            "successful_actions": self.successful_actions,
            "major_errors": self._trust_data.get("major_errors", 0),
            "max_trade_usd": level.max_trade_usd,
            "daily_limit_usd": level.daily_limit_usd,
            "daily_spent_usd": self._daily_spent,
            "daily_remaining_usd": level.daily_limit_usd - self._daily_spent,
            "requires_confirmation": level.requires_confirmation,
            "next_level_at": {1: 10, 2: 50, 3: 200, 4: 1000}.get(level.level + 1, "Max level"),
        }


# Global instance
_trader: Optional[TrustAwareTrader] = None


def get_trust_trader() -> TrustAwareTrader:
    """Get or create the global trust-aware trader."""
    global _trader
    if _trader is None:
        _trader = TrustAwareTrader()
    return _trader
