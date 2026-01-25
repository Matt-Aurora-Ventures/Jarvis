"""
Risk Management Module - Position sizing, risk scoring, and portfolio protection.
"""

import logging
import math
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classifications."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    EXTREME = "extreme"


@dataclass
class RiskAssessment:
    """Risk assessment result."""
    overall_score: float  # 0-100
    level: RiskLevel
    factors: Dict[str, float]
    warnings: List[str]
    recommendations: List[str]


# === POSITION SIZING ===

class PositionSizer:
    """
    Calculate optimal position sizes based on risk parameters.

    Implements:
    - Fixed percentage risk
    - Kelly Criterion
    - Volatility-adjusted sizing
    - Maximum position limits

    Usage:
        sizer = PositionSizer(portfolio_value=10000)

        size = sizer.calculate_position(
            entry_price=100,
            stop_loss=90,
            risk_percent=2.0
        )
    """

    def __init__(
        self,
        portfolio_value: float,
        max_position_percent: float = 10.0,
        max_risk_per_trade_percent: float = 2.0,
        max_total_risk_percent: float = 20.0
    ):
        self.portfolio_value = portfolio_value
        self.max_position_percent = max_position_percent
        self.max_risk_per_trade = max_risk_per_trade_percent
        self.max_total_risk = max_total_risk_percent
        self.current_risk = 0.0

    def update_portfolio_value(self, value: float):
        """Update portfolio value."""
        self.portfolio_value = value

    def calculate_position_fixed_risk(
        self,
        entry_price: float,
        stop_loss: float,
        risk_percent: float = None
    ) -> Dict[str, float]:
        """
        Calculate position size using fixed percentage risk.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_percent: Risk per trade (default: max_risk_per_trade)

        Returns:
            Dict with position_size, position_value, risk_amount, etc.
        """
        risk_percent = risk_percent or self.max_risk_per_trade

        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss)

        if risk_per_share == 0:
            return {
                "position_size": 0,
                "position_value": 0,
                "risk_amount": 0,
                "risk_percent": 0,
                "error": "Stop loss equals entry price"
            }

        # Calculate risk amount
        risk_amount = self.portfolio_value * (risk_percent / 100)

        # Calculate position size
        position_size = risk_amount / risk_per_share

        # Apply max position limit
        max_position_value = self.portfolio_value * (self.max_position_percent / 100)
        max_position_size = max_position_value / entry_price

        if position_size > max_position_size:
            position_size = max_position_size
            risk_amount = position_size * risk_per_share

        position_value = position_size * entry_price

        # Guard against division by zero
        risk_percent = (risk_amount / self.portfolio_value) * 100 if self.portfolio_value > 0 else 0

        return {
            "position_size": position_size,
            "position_value": position_value,
            "risk_amount": risk_amount,
            "risk_percent": risk_percent,
            "shares_or_tokens": position_size,
            "stop_loss_distance_percent": (risk_per_share / entry_price) * 100
        }

    def calculate_kelly_position(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        fraction: float = 0.25  # Use 1/4 Kelly for safety
    ) -> Dict[str, float]:
        """
        Calculate position size using Kelly Criterion.

        Args:
            win_rate: Historical win rate (0-1)
            avg_win: Average winning trade return
            avg_loss: Average losing trade return (positive number)
            fraction: Kelly fraction to use (default 0.25 = quarter Kelly)

        Returns:
            Dict with kelly_percent, recommended_position_percent
        """
        if avg_loss == 0:
            return {"kelly_percent": 0, "recommended_position_percent": 0, "error": "avg_loss is zero"}

        # Kelly formula: f* = (bp - q) / b
        # where b = avg_win / avg_loss, p = win_rate, q = 1 - win_rate
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - win_rate

        kelly = (b * p - q) / b

        # Apply fraction
        kelly = kelly * fraction

        # Clamp to reasonable range
        kelly = max(0, min(kelly, self.max_position_percent / 100))

        recommended_value = self.portfolio_value * kelly

        return {
            "kelly_percent": kelly * 100,
            "recommended_position_percent": kelly * 100,
            "recommended_value": recommended_value,
            "full_kelly_percent": (kelly / fraction) * 100 if fraction > 0 else 0
        }

    def calculate_volatility_adjusted(
        self,
        entry_price: float,
        atr: float,  # Average True Range
        atr_multiplier: float = 2.0,
        risk_percent: float = None
    ) -> Dict[str, float]:
        """
        Calculate position size adjusted for volatility (ATR-based).

        Args:
            entry_price: Entry price
            atr: Average True Range
            atr_multiplier: Multiplier for ATR to set stop (default 2x ATR)
            risk_percent: Risk per trade

        Returns:
            Dict with position details
        """
        risk_percent = risk_percent or self.max_risk_per_trade

        # Calculate stop loss based on ATR
        stop_distance = atr * atr_multiplier
        stop_loss = entry_price - stop_distance  # For long position

        return self.calculate_position_fixed_risk(
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_percent=risk_percent
        )


# === RISK SCORING ===

class RiskScorer:
    """
    Score risk for tokens and trades.

    Factors considered:
    - Liquidity
    - Market cap
    - Volatility
    - Contract verification
    - Trading volume
    - Price change
    - Buy/sell ratio
    """

    def __init__(self):
        self.weights = {
            "liquidity": 20,
            "market_cap": 15,
            "volatility": 15,
            "volume": 15,
            "price_change": 10,
            "buy_sell_ratio": 10,
            "age": 10,
            "holders": 5
        }

    def score_token(
        self,
        market_cap: float,
        liquidity: float,
        volume_24h: float,
        price_change_24h: float,
        buy_sell_ratio: float,
        token_age_days: int = 0,
        holders: int = 0
    ) -> RiskAssessment:
        """
        Score token risk.

        Returns:
            RiskAssessment with score 0-100 (higher = more risky)
        """
        factors = {}
        warnings = []
        recommendations = []

        # Liquidity score (higher liquidity = lower risk)
        if liquidity < 1000:
            factors["liquidity"] = 100
            warnings.append("Extremely low liquidity - high slippage risk")
        elif liquidity < 10000:
            factors["liquidity"] = 80
            warnings.append("Low liquidity")
        elif liquidity < 100000:
            factors["liquidity"] = 50
        elif liquidity < 1000000:
            factors["liquidity"] = 25
        else:
            factors["liquidity"] = 10

        # Market cap score
        if market_cap < 10000:
            factors["market_cap"] = 100
            warnings.append("Micro cap - extreme volatility expected")
        elif market_cap < 100000:
            factors["market_cap"] = 80
            warnings.append("Very small market cap")
        elif market_cap < 1000000:
            factors["market_cap"] = 50
        elif market_cap < 10000000:
            factors["market_cap"] = 25
        else:
            factors["market_cap"] = 10

        # Volatility (from price change)
        abs_change = abs(price_change_24h)
        if abs_change > 100:
            factors["volatility"] = 100
            warnings.append("Extreme volatility (>100% move)")
        elif abs_change > 50:
            factors["volatility"] = 80
        elif abs_change > 25:
            factors["volatility"] = 50
        elif abs_change > 10:
            factors["volatility"] = 25
        else:
            factors["volatility"] = 10

        # Volume score (relative to market cap)
        if market_cap > 0:
            volume_ratio = volume_24h / market_cap
            if volume_ratio > 5:
                factors["volume"] = 90  # Suspicious high volume
                warnings.append("Volume > 5x market cap - possible manipulation")
            elif volume_ratio > 1:
                factors["volume"] = 50
            elif volume_ratio > 0.1:
                factors["volume"] = 25
            else:
                factors["volume"] = 60  # Low volume
                warnings.append("Low trading volume")
        else:
            factors["volume"] = 50

        # Price change direction
        if price_change_24h > 500:
            factors["price_change"] = 100
            warnings.append("Massive pump - likely to dump")
        elif price_change_24h > 100:
            factors["price_change"] = 80
        elif price_change_24h < -50:
            factors["price_change"] = 90
            warnings.append("Major dump in progress")
        elif price_change_24h < -25:
            factors["price_change"] = 70
        else:
            factors["price_change"] = 30

        # Buy/sell ratio
        if buy_sell_ratio > 3:
            factors["buy_sell_ratio"] = 30  # Strong buying
        elif buy_sell_ratio > 1.5:
            factors["buy_sell_ratio"] = 20
        elif buy_sell_ratio > 0.7:
            factors["buy_sell_ratio"] = 40
        elif buy_sell_ratio > 0.3:
            factors["buy_sell_ratio"] = 70
            warnings.append("Sell pressure exceeds buy pressure")
        else:
            factors["buy_sell_ratio"] = 90
            warnings.append("Heavy selling - possible dump")

        # Token age
        if token_age_days < 1:
            factors["age"] = 100
            warnings.append("Brand new token - highest risk category")
        elif token_age_days < 7:
            factors["age"] = 80
            warnings.append("Token less than 1 week old")
        elif token_age_days < 30:
            factors["age"] = 50
        elif token_age_days < 90:
            factors["age"] = 30
        else:
            factors["age"] = 15

        # Holders
        if holders < 100:
            factors["holders"] = 90
            warnings.append("Very few holders - concentration risk")
        elif holders < 500:
            factors["holders"] = 60
        elif holders < 2000:
            factors["holders"] = 35
        else:
            factors["holders"] = 15

        # Calculate weighted score
        total_score = 0
        total_weight = 0
        for factor, score in factors.items():
            weight = self.weights.get(factor, 10)
            total_score += score * weight
            total_weight += weight

        overall_score = total_score / total_weight if total_weight > 0 else 50

        # Determine level
        if overall_score >= 80:
            level = RiskLevel.EXTREME
            recommendations.append("Avoid this token - extremely high risk")
        elif overall_score >= 65:
            level = RiskLevel.VERY_HIGH
            recommendations.append("Only trade with money you can afford to lose completely")
            recommendations.append("Use tight stop losses")
        elif overall_score >= 50:
            level = RiskLevel.HIGH
            recommendations.append("Reduce position size")
            recommendations.append("Set stop loss immediately after entry")
        elif overall_score >= 35:
            level = RiskLevel.MEDIUM
            recommendations.append("Standard position sizing appropriate")
        elif overall_score >= 20:
            level = RiskLevel.LOW
        else:
            level = RiskLevel.VERY_LOW

        return RiskAssessment(
            overall_score=overall_score,
            level=level,
            factors=factors,
            warnings=warnings,
            recommendations=recommendations
        )


# === PORTFOLIO RISK ===

class PortfolioRiskManager:
    """
    Manage overall portfolio risk.

    Tracks:
    - Total portfolio risk
    - Correlation between positions
    - Maximum drawdown
    - Risk-adjusted returns
    """

    def __init__(
        self,
        max_portfolio_risk: float = 20.0,
        max_single_position: float = 10.0,
        max_correlated_exposure: float = 30.0
    ):
        self.max_portfolio_risk = max_portfolio_risk
        self.max_single_position = max_single_position
        self.max_correlated_exposure = max_correlated_exposure
        self.positions: Dict[str, Dict] = {}

    def add_position(
        self,
        symbol: str,
        value: float,
        risk_percent: float,
        category: str = "default"
    ):
        """Add or update a position."""
        self.positions[symbol] = {
            "value": value,
            "risk_percent": risk_percent,
            "category": category
        }

    def remove_position(self, symbol: str):
        """Remove a position."""
        if symbol in self.positions:
            del self.positions[symbol]

    def get_portfolio_risk(self) -> Dict[str, Any]:
        """Calculate total portfolio risk."""
        if not self.positions:
            return {
                "total_risk": 0,
                "position_count": 0,
                "largest_position_percent": 0,
                "risk_by_category": {}
            }

        total_value = sum(p["value"] for p in self.positions.values())
        if total_value == 0:
            return {
                "total_risk": 0,
                "position_count": 0,
                "largest_position_percent": 0,
                "risk_by_category": {}
            }

        # Calculate weighted risk
        total_risk = sum(
            p["value"] * p["risk_percent"] / 100
            for p in self.positions.values()
        ) / total_value * 100

        # Largest position
        largest = max(p["value"] for p in self.positions.values())
        largest_percent = (largest / total_value) * 100

        # Risk by category
        risk_by_category: Dict[str, float] = {}
        for pos in self.positions.values():
            cat = pos["category"]
            if cat not in risk_by_category:
                risk_by_category[cat] = 0
            risk_by_category[cat] += pos["value"]

        for cat in risk_by_category:
            risk_by_category[cat] = (risk_by_category[cat] / total_value) * 100

        return {
            "total_risk": total_risk,
            "position_count": len(self.positions),
            "largest_position_percent": largest_percent,
            "risk_by_category": risk_by_category,
            "within_limits": total_risk <= self.max_portfolio_risk and largest_percent <= self.max_single_position
        }

    def can_add_position(
        self,
        value: float,
        risk_percent: float,
        category: str = "default"
    ) -> tuple[bool, str]:
        """Check if a new position can be added within risk limits."""
        current = self.get_portfolio_risk()
        total_value = sum(p["value"] for p in self.positions.values()) + value

        if total_value == 0:
            return True, "OK"

        # Check single position limit
        position_percent = (value / total_value) * 100
        if position_percent > self.max_single_position:
            return False, f"Position size ({position_percent:.1f}%) exceeds limit ({self.max_single_position}%)"

        # Check total risk
        new_risk = (current["total_risk"] * (total_value - value) / total_value +
                    risk_percent * value / total_value)
        if new_risk > self.max_portfolio_risk:
            return False, f"Total risk ({new_risk:.1f}%) would exceed limit ({self.max_portfolio_risk}%)"

        # Check category exposure
        cat_value = sum(
            p["value"] for p in self.positions.values()
            if p["category"] == category
        ) + value
        cat_percent = (cat_value / total_value) * 100
        if cat_percent > self.max_correlated_exposure:
            return False, f"Category exposure ({cat_percent:.1f}%) would exceed limit ({self.max_correlated_exposure}%)"

        return True, "OK"


# === SINGLETON INSTANCES ===

_position_sizer: Optional[PositionSizer] = None
_risk_scorer: Optional[RiskScorer] = None
_portfolio_risk: Optional[PortfolioRiskManager] = None


def get_position_sizer(portfolio_value: float = 10000) -> PositionSizer:
    global _position_sizer
    if _position_sizer is None:
        _position_sizer = PositionSizer(portfolio_value)
    return _position_sizer


def get_risk_scorer() -> RiskScorer:
    global _risk_scorer
    if _risk_scorer is None:
        _risk_scorer = RiskScorer()
    return _risk_scorer


def get_portfolio_risk_manager() -> PortfolioRiskManager:
    global _portfolio_risk
    if _portfolio_risk is None:
        _portfolio_risk = PortfolioRiskManager()
    return _portfolio_risk
