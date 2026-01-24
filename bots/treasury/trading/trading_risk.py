"""
Trading Risk Management

Token safety checks, spending limits, and risk classification.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List

from .types import RiskLevel
from .constants import (
    ESTABLISHED_TOKENS,
    HIGH_RISK_PATTERNS,
    BLOCKED_TOKENS,
    BLOCKED_SYMBOLS,
    MAX_TRADE_USD,
    MAX_DAILY_USD,
    MAX_POSITION_PCT,
    MAX_HIGH_RISK_POSITION_PCT,
    MAX_UNVETTED_POSITION_PCT,
    MIN_LIQUIDITY_USD,
    TP_SL_CONFIG,
    POSITION_SIZE,
    DAILY_VOLUME_FILE,
)

logger = logging.getLogger(__name__)

# Import SafeState if available
try:
    from core.safe_state import SafeState
    SAFE_STATE_AVAILABLE = True
except ImportError:
    SAFE_STATE_AVAILABLE = False
    SafeState = None


class RiskChecker:
    """Risk management utilities for trading operations."""

    def __init__(self, daily_volume_file: Path = None):
        """
        Initialize risk checker.

        Args:
            daily_volume_file: Path to daily volume tracking file
        """
        self.daily_volume_file = daily_volume_file or DAILY_VOLUME_FILE
        self._volume_state = None

        if SAFE_STATE_AVAILABLE and self.daily_volume_file:
            self.daily_volume_file.parent.mkdir(parents=True, exist_ok=True)
            self._volume_state = SafeState(self.daily_volume_file, default_value={})

    # ==========================================================================
    # TOKEN SAFETY METHODS
    # ==========================================================================

    @staticmethod
    def is_blocked_token(token_mint: str, token_symbol: str = "") -> Tuple[bool, str]:
        """
        Check if token is blocked from trading (stablecoins, WSOL, etc.).

        Returns:
            Tuple of (is_blocked, reason)
        """
        if token_mint in BLOCKED_TOKENS:
            name = BLOCKED_TOKENS[token_mint]
            return True, f"{name} is a stablecoin/blocked token - not tradeable"
        if token_symbol.upper() in BLOCKED_SYMBOLS:
            return True, f"{token_symbol} is a stablecoin - not tradeable"
        return False, ""

    @staticmethod
    def is_high_risk_token(token_mint: str) -> bool:
        """
        Check if token matches high-risk patterns (e.g., pump.fun).

        High-risk tokens aren't blocked but get:
        - Smaller position sizes (15% of normal)
        - Extra liquidity checks
        - Tighter monitoring
        """
        mint_lower = token_mint.lower()
        for pattern in HIGH_RISK_PATTERNS:
            if pattern in mint_lower:
                return True
        return False

    @staticmethod
    def is_established_token(token_mint: str) -> bool:
        """Check if token is in our vetted established tokens list."""
        return token_mint in ESTABLISHED_TOKENS

    @staticmethod
    def classify_token_risk(token_mint: str, token_symbol: str) -> str:
        """
        Classify token into risk tiers for position sizing.

        Returns:
            ESTABLISHED - Vetted tokens, full position size
            MID - Known symbols but not in whitelist, 50% position
            MICRO - Unknown tokens with liquidity, 25% position
            HIGH_RISK - Pump.fun and similar, 15% position + extra checks
        """
        # Established whitelist - these are safe
        if RiskChecker.is_established_token(token_mint):
            return "ESTABLISHED"

        # XStocks pattern (starts with Xs) - backed assets
        if token_mint.startswith("Xs"):
            return "ESTABLISHED"

        # High-risk patterns (pump.fun etc) - trade with caution, not banned
        if RiskChecker.is_high_risk_token(token_mint):
            return "HIGH_RISK"

        # Known major symbols (might be on different mint)
        major_symbols = ["BTC", "ETH", "SOL", "USDC", "USDT", "BONK", "WIF", "JUP", "PYTH"]
        if token_symbol.upper() in major_symbols:
            return "MID"

        # Tokenized equity symbols
        if token_symbol.upper().endswith("X") and len(token_symbol) <= 6:
            return "MID"

        # Everything else is micro cap risk
        return "MICRO"

    @staticmethod
    def get_risk_adjusted_position_size(
        token_mint: str,
        token_symbol: str,
        base_position_usd: float
    ) -> Tuple[float, str]:
        """
        Adjust position size based on token risk classification.

        Returns:
            Tuple of (adjusted_position_usd, risk_tier)
        """
        risk_tier = RiskChecker.classify_token_risk(token_mint, token_symbol)

        if risk_tier == "ESTABLISHED":
            return base_position_usd, risk_tier  # Full size

        elif risk_tier == "MID":
            return base_position_usd * 0.50, risk_tier  # 50% size

        elif risk_tier == "HIGH_RISK":
            # Pump.fun and similar - small positions, not banned
            return base_position_usd * MAX_HIGH_RISK_POSITION_PCT, risk_tier  # 15% size

        else:  # MICRO
            return base_position_usd * MAX_UNVETTED_POSITION_PCT, risk_tier  # 25% size

    # ==========================================================================
    # SPENDING LIMITS
    # ==========================================================================

    def get_daily_volume(self) -> float:
        """Get total trading volume for today (UTC) with file locking."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        try:
            if self._volume_state:
                data = self._volume_state.read()
                if data.get('date') == today:
                    return data.get('volume_usd', 0.0)
            elif self.daily_volume_file.exists():
                with open(self.daily_volume_file) as f:
                    data = json.load(f)
                    if data.get('date') == today:
                        return data.get('volume_usd', 0.0)
        except Exception as e:
            logger.debug(f"Failed to load daily volume: {e}")
        return 0.0

    def add_daily_volume(self, amount_usd: float):
        """Add to daily trading volume with file locking."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        current = self.get_daily_volume()
        try:
            if self._volume_state:
                self._volume_state.write({'date': today, 'volume_usd': current + amount_usd})
            else:
                self.daily_volume_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.daily_volume_file, 'w') as f:
                    json.dump({'date': today, 'volume_usd': current + amount_usd}, f)
        except Exception as e:
            logger.error(f"Failed to save daily volume: {e}")

    def check_spending_limits(self, amount_usd: float, portfolio_usd: float) -> Tuple[bool, str]:
        """
        Check if trade passes spending limits.

        Returns:
            Tuple of (allowed, reason)
        """
        # Check single trade limit
        if amount_usd > MAX_TRADE_USD:
            return False, f"Trade ${amount_usd:.2f} exceeds max single trade ${MAX_TRADE_USD}"

        # Check daily limit
        daily_volume = self.get_daily_volume()
        if daily_volume + amount_usd > MAX_DAILY_USD:
            remaining = MAX_DAILY_USD - daily_volume
            return False, f"Daily limit reached. Used ${daily_volume:.2f}/{MAX_DAILY_USD}. Remaining: ${remaining:.2f}"

        # Check position concentration
        if portfolio_usd > 0:
            position_pct = amount_usd / portfolio_usd
            if position_pct > MAX_POSITION_PCT:
                return False, f"Position {position_pct*100:.1f}% exceeds max {MAX_POSITION_PCT*100:.0f}% of portfolio"

        return True, ""

    # ==========================================================================
    # TP/SL CALCULATIONS
    # ==========================================================================

    @staticmethod
    def get_tp_sl_levels(
        entry_price: float,
        sentiment_grade: str,
        custom_tp: float = None,
        custom_sl: float = None
    ) -> Tuple[float, float]:
        """
        Calculate take profit and stop loss prices.

        Args:
            entry_price: Entry price in USD
            sentiment_grade: A, B+, C, etc.
            custom_tp: Override TP percentage
            custom_sl: Override SL percentage

        Returns:
            Tuple of (take_profit_price, stop_loss_price)
        """
        # Default: +20% TP, -10% SL if grade not found
        config = TP_SL_CONFIG.get(sentiment_grade, {'take_profit': 0.20, 'stop_loss': 0.10})

        tp_pct = custom_tp if custom_tp else config['take_profit']
        sl_pct = custom_sl if custom_sl else config['stop_loss']

        take_profit = entry_price * (1 + tp_pct)
        stop_loss = entry_price * (1 - sl_pct)

        return take_profit, stop_loss

    # ==========================================================================
    # POSITION SIZING
    # ==========================================================================

    @staticmethod
    def calculate_position_size(portfolio_usd: float, risk_level: RiskLevel = RiskLevel.MODERATE) -> float:
        """Calculate position size in USD based on risk level."""
        return portfolio_usd * POSITION_SIZE[risk_level]
