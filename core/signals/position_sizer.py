"""
Position Sizer

Calculates optimal position sizes based on risk parameters,
account size, and signal strength.

Supports multiple sizing methods including Kelly Criterion,
fixed fractional, and volatility-based sizing.

Prompts #128-135: Signal Processing
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum

logger = logging.getLogger(__name__)


class SizingMethod(str, Enum):
    """Position sizing methods"""
    FIXED_AMOUNT = "fixed_amount"         # Fixed dollar amount
    FIXED_PERCENTAGE = "fixed_percentage" # Fixed % of portfolio
    RISK_BASED = "risk_based"             # Based on stop loss distance
    KELLY = "kelly"                       # Kelly Criterion
    VOLATILITY = "volatility"             # Volatility-adjusted
    SIGNAL_SCALED = "signal_scaled"       # Scaled by signal strength
    HYBRID = "hybrid"                     # Combination of methods


@dataclass
class RiskParameters:
    """Risk parameters for position sizing"""
    # Account
    account_size: float = 10000.0
    max_position_pct: float = 10.0        # Max % of account per position
    max_total_exposure_pct: float = 50.0  # Max total portfolio exposure

    # Risk per trade
    risk_per_trade_pct: float = 1.0       # Max % to risk per trade
    max_loss_per_trade: float = 100.0     # Max dollar loss per trade

    # Stop loss
    default_stop_loss_pct: float = 5.0    # Default stop loss %
    trailing_stop_pct: float = 10.0       # Trailing stop %

    # Leverage (if applicable)
    max_leverage: float = 1.0             # Max leverage allowed
    use_leverage: bool = False

    # Volatility adjustment
    vol_lookback_days: int = 20           # Days for volatility calc
    vol_target_pct: float = 15.0          # Target annualized volatility

    # Kelly Criterion
    kelly_fraction: float = 0.25          # Fraction of full Kelly to use

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "account_size": self.account_size,
            "max_position_pct": self.max_position_pct,
            "max_total_exposure_pct": self.max_total_exposure_pct,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "max_loss_per_trade": self.max_loss_per_trade,
            "default_stop_loss_pct": self.default_stop_loss_pct,
            "trailing_stop_pct": self.trailing_stop_pct,
            "max_leverage": self.max_leverage,
            "use_leverage": self.use_leverage,
            "vol_lookback_days": self.vol_lookback_days,
            "vol_target_pct": self.vol_target_pct,
            "kelly_fraction": self.kelly_fraction
        }


@dataclass
class PositionSize:
    """Calculated position size"""
    token: str
    method: SizingMethod
    position_size_usd: float
    position_size_tokens: float
    entry_price: float

    # Risk metrics
    risk_amount: float = 0.0              # Dollar amount at risk
    risk_percent: float = 0.0             # % of account at risk
    stop_loss_price: float = 0.0
    stop_loss_percent: float = 0.0
    take_profit_price: float = 0.0
    take_profit_percent: float = 0.0

    # Sizing breakdown
    max_position_usd: float = 0.0         # Max allowed by rules
    signal_multiplier: float = 1.0        # Adjustment from signal strength
    volatility_multiplier: float = 1.0    # Adjustment from volatility

    # Metadata
    calculated_at: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "token": self.token,
            "method": self.method.value,
            "position_size_usd": self.position_size_usd,
            "position_size_tokens": self.position_size_tokens,
            "entry_price": self.entry_price,
            "risk_amount": self.risk_amount,
            "risk_percent": self.risk_percent,
            "stop_loss_price": self.stop_loss_price,
            "stop_loss_percent": self.stop_loss_percent,
            "take_profit_price": self.take_profit_price,
            "take_profit_percent": self.take_profit_percent,
            "max_position_usd": self.max_position_usd,
            "signal_multiplier": self.signal_multiplier,
            "volatility_multiplier": self.volatility_multiplier,
            "calculated_at": self.calculated_at.isoformat(),
            "confidence": self.confidence,
            "notes": self.notes
        }


class PositionSizer:
    """
    Calculates optimal position sizes

    Uses configurable risk parameters and multiple sizing methods
    to determine appropriate position sizes for trades.
    """

    def __init__(self, default_params: Optional[RiskParameters] = None):
        self.default_params = default_params or RiskParameters()
        self.current_positions: Dict[str, float] = {}  # token -> position size
        self.historical_volatility: Dict[str, float] = {}  # token -> annualized vol

    async def calculate_position_size(
        self,
        token: str,
        entry_price: float,
        method: SizingMethod = SizingMethod.RISK_BASED,
        signal_strength: float = 1.0,
        signal_confidence: float = 1.0,
        win_rate: float = 0.5,
        avg_win_loss_ratio: float = 1.5,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        volatility: Optional[float] = None,
        params: Optional[RiskParameters] = None
    ) -> PositionSize:
        """
        Calculate optimal position size

        Args:
            token: Token to trade
            entry_price: Expected entry price
            method: Sizing method to use
            signal_strength: Strength of signal (0-1)
            signal_confidence: Confidence in signal (0-1)
            win_rate: Historical win rate for this strategy
            avg_win_loss_ratio: Average win / average loss
            stop_loss_pct: Custom stop loss percentage
            take_profit_pct: Custom take profit percentage
            volatility: Token's annualized volatility
            params: Custom risk parameters

        Returns:
            PositionSize with all calculated values
        """
        p = params or self.default_params
        stop_loss = stop_loss_pct or p.default_stop_loss_pct
        take_profit = take_profit_pct or (stop_loss * avg_win_loss_ratio)
        vol = volatility or self.historical_volatility.get(token, 0.5)

        # Calculate max position based on account rules
        max_position = p.account_size * (p.max_position_pct / 100)

        # Check total exposure
        current_exposure = sum(self.current_positions.values())
        max_remaining = p.account_size * (p.max_total_exposure_pct / 100) - current_exposure
        max_position = min(max_position, max_remaining)

        # Calculate position size based on method
        if method == SizingMethod.FIXED_AMOUNT:
            position_size = min(1000, max_position)  # Default $1000

        elif method == SizingMethod.FIXED_PERCENTAGE:
            position_size = p.account_size * (p.max_position_pct / 100)

        elif method == SizingMethod.RISK_BASED:
            position_size = self._risk_based_size(p, stop_loss)

        elif method == SizingMethod.KELLY:
            position_size = self._kelly_size(
                p, win_rate, avg_win_loss_ratio
            )

        elif method == SizingMethod.VOLATILITY:
            position_size = self._volatility_adjusted_size(p, vol)

        elif method == SizingMethod.SIGNAL_SCALED:
            base_size = self._risk_based_size(p, stop_loss)
            position_size = base_size * signal_strength * signal_confidence

        elif method == SizingMethod.HYBRID:
            position_size = self._hybrid_size(
                p, stop_loss, vol, signal_strength, signal_confidence,
                win_rate, avg_win_loss_ratio
            )

        else:
            position_size = self._risk_based_size(p, stop_loss)

        # Apply signal multiplier
        signal_mult = (signal_strength + signal_confidence) / 2
        position_size *= signal_mult

        # Apply volatility multiplier if using volatility adjustment
        vol_mult = 1.0
        if vol > 0 and method in [SizingMethod.VOLATILITY, SizingMethod.HYBRID]:
            vol_mult = p.vol_target_pct / (vol * 100)
            vol_mult = max(0.5, min(vol_mult, 2.0))  # Cap between 0.5x and 2x
            position_size *= vol_mult

        # Cap at maximum
        position_size = min(position_size, max_position)

        # Ensure minimum viable position
        min_position = 10.0  # $10 minimum
        if position_size < min_position:
            position_size = 0.0  # Don't trade if below minimum

        # Calculate token amount
        tokens = position_size / entry_price if entry_price > 0 else 0

        # Calculate risk metrics
        risk_amount = position_size * (stop_loss / 100)
        risk_percent = (risk_amount / p.account_size) * 100 if p.account_size > 0 else 0

        # Calculate stop loss and take profit prices
        stop_loss_price = entry_price * (1 - stop_loss / 100)
        take_profit_price = entry_price * (1 + take_profit / 100)

        return PositionSize(
            token=token,
            method=method,
            position_size_usd=round(position_size, 2),
            position_size_tokens=round(tokens, 8),
            entry_price=entry_price,
            risk_amount=round(risk_amount, 2),
            risk_percent=round(risk_percent, 2),
            stop_loss_price=round(stop_loss_price, 4),
            stop_loss_percent=stop_loss,
            take_profit_price=round(take_profit_price, 4),
            take_profit_percent=take_profit,
            max_position_usd=round(max_position, 2),
            signal_multiplier=round(signal_mult, 2),
            volatility_multiplier=round(vol_mult, 2),
            confidence=signal_confidence
        )

    def _risk_based_size(
        self,
        params: RiskParameters,
        stop_loss_pct: float
    ) -> float:
        """Calculate position size based on risk per trade"""
        # Risk amount = Account * Risk%
        risk_amount = min(
            params.account_size * (params.risk_per_trade_pct / 100),
            params.max_loss_per_trade
        )

        # Position size = Risk amount / Stop loss %
        if stop_loss_pct > 0:
            position_size = risk_amount / (stop_loss_pct / 100)
        else:
            position_size = risk_amount

        return position_size

    def _kelly_size(
        self,
        params: RiskParameters,
        win_rate: float,
        win_loss_ratio: float
    ) -> float:
        """Calculate position size using Kelly Criterion"""
        # Kelly % = W - (1-W)/R
        # W = win rate, R = win/loss ratio
        kelly_pct = win_rate - ((1 - win_rate) / win_loss_ratio)

        # Use fractional Kelly (safer)
        kelly_pct *= params.kelly_fraction

        # Cap Kelly at max position
        kelly_pct = max(0, min(kelly_pct, params.max_position_pct / 100))

        return params.account_size * kelly_pct

    def _volatility_adjusted_size(
        self,
        params: RiskParameters,
        volatility: float
    ) -> float:
        """Calculate position size adjusted for volatility"""
        if volatility <= 0:
            return params.account_size * (params.max_position_pct / 100)

        # Target position volatility
        target_vol = params.vol_target_pct / 100

        # Position size = Account * (Target Vol / Asset Vol)
        vol_multiplier = target_vol / volatility
        vol_multiplier = max(0.25, min(vol_multiplier, 4.0))  # Cap

        base_size = params.account_size * (params.max_position_pct / 100)
        return base_size * vol_multiplier

    def _hybrid_size(
        self,
        params: RiskParameters,
        stop_loss_pct: float,
        volatility: float,
        signal_strength: float,
        signal_confidence: float,
        win_rate: float,
        win_loss_ratio: float
    ) -> float:
        """Calculate position size using hybrid approach"""
        # Get sizes from different methods
        risk_size = self._risk_based_size(params, stop_loss_pct)
        kelly_size = self._kelly_size(params, win_rate, win_loss_ratio)
        vol_size = self._volatility_adjusted_size(params, volatility)

        # Weighted average based on confidence
        if signal_confidence >= 0.8:
            # High confidence: lean towards Kelly
            weights = [0.3, 0.5, 0.2]
        elif signal_confidence >= 0.6:
            # Medium confidence: balanced
            weights = [0.4, 0.3, 0.3]
        else:
            # Low confidence: lean towards risk-based (conservative)
            weights = [0.6, 0.2, 0.2]

        hybrid_size = (
            risk_size * weights[0] +
            kelly_size * weights[1] +
            vol_size * weights[2]
        )

        return hybrid_size

    def set_volatility(self, token: str, volatility: float):
        """Set historical volatility for a token"""
        self.historical_volatility[token] = volatility

    def add_position(self, token: str, size_usd: float):
        """Track an open position"""
        self.current_positions[token] = self.current_positions.get(token, 0) + size_usd

    def close_position(self, token: str, size_usd: Optional[float] = None):
        """Close a position"""
        if token in self.current_positions:
            if size_usd:
                self.current_positions[token] -= size_usd
                if self.current_positions[token] <= 0:
                    del self.current_positions[token]
            else:
                del self.current_positions[token]

    def get_exposure_summary(self) -> Dict[str, Any]:
        """Get current exposure summary"""
        total_exposure = sum(self.current_positions.values())
        params = self.default_params

        return {
            "total_exposure_usd": total_exposure,
            "total_exposure_pct": (total_exposure / params.account_size * 100) if params.account_size > 0 else 0,
            "max_exposure_pct": params.max_total_exposure_pct,
            "remaining_capacity_usd": params.account_size * (params.max_total_exposure_pct / 100) - total_exposure,
            "position_count": len(self.current_positions),
            "positions": self.current_positions.copy()
        }

    async def suggest_position_size(
        self,
        token: str,
        entry_price: float,
        signal_strength: float,
        signal_confidence: float,
        direction: str = "long"
    ) -> Dict[str, Any]:
        """
        Get position size suggestion with reasoning

        Returns a recommendation with multiple sizing options.
        """
        # Calculate using different methods
        methods = [
            SizingMethod.RISK_BASED,
            SizingMethod.KELLY,
            SizingMethod.SIGNAL_SCALED,
            SizingMethod.HYBRID
        ]

        suggestions = {}
        for method in methods:
            size = await self.calculate_position_size(
                token=token,
                entry_price=entry_price,
                method=method,
                signal_strength=signal_strength,
                signal_confidence=signal_confidence
            )
            suggestions[method.value] = size.to_dict()

        # Determine recommended method
        if signal_confidence >= 0.8 and signal_strength >= 0.7:
            recommended = "hybrid"
            reasoning = "High confidence signal supports hybrid sizing with Kelly component"
        elif signal_confidence >= 0.6:
            recommended = "signal_scaled"
            reasoning = "Medium confidence - scale position with signal strength"
        else:
            recommended = "risk_based"
            reasoning = "Lower confidence - use conservative risk-based sizing"

        return {
            "token": token,
            "direction": direction,
            "entry_price": entry_price,
            "signal_strength": signal_strength,
            "signal_confidence": signal_confidence,
            "recommended_method": recommended,
            "reasoning": reasoning,
            "suggestions": suggestions,
            "exposure_summary": self.get_exposure_summary()
        }


# Singleton instance
_position_sizer: Optional[PositionSizer] = None


def get_position_sizer() -> PositionSizer:
    """Get position sizer singleton"""
    global _position_sizer

    if _position_sizer is None:
        _position_sizer = PositionSizer()

    return _position_sizer


# Testing
if __name__ == "__main__":
    async def test():
        sizer = PositionSizer(RiskParameters(
            account_size=10000,
            max_position_pct=10,
            risk_per_trade_pct=1
        ))

        # Set some volatility data
        sizer.set_volatility("SOL", 0.75)  # 75% annualized vol

        # Calculate position size
        size = await sizer.calculate_position_size(
            token="SOL",
            entry_price=150.0,
            method=SizingMethod.HYBRID,
            signal_strength=0.8,
            signal_confidence=0.75,
            win_rate=0.55,
            avg_win_loss_ratio=2.0,
            stop_loss_pct=5.0
        )

        print("Position Size Calculation:")
        print(f"  Token: {size.token}")
        print(f"  Method: {size.method.value}")
        print(f"  Position Size: ${size.position_size_usd:,.2f}")
        print(f"  Tokens: {size.position_size_tokens:.4f}")
        print(f"  Risk Amount: ${size.risk_amount:,.2f} ({size.risk_percent:.2f}%)")
        print(f"  Stop Loss: ${size.stop_loss_price:.2f} ({size.stop_loss_percent}%)")
        print(f"  Take Profit: ${size.take_profit_price:.2f} ({size.take_profit_percent:.1f}%)")

        # Get suggestion
        print("\n" + "="*50)
        suggestion = await sizer.suggest_position_size(
            token="SOL",
            entry_price=150.0,
            signal_strength=0.8,
            signal_confidence=0.75
        )

        print(f"\nRecommended: {suggestion['recommended_method']}")
        print(f"Reasoning: {suggestion['reasoning']}")

    asyncio.run(test())
