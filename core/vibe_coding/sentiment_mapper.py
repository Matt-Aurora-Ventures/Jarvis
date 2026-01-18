"""
Sentiment Mapper - Maps market vibe to code changes.

Bridges sentiment analysis to autonomous code generation:
- Bullish market → Aggressive trading parameters
- Bearish market → Defensive risk management
- Sideways market → Tight range trading
- Volatile market → Wider stops, smaller positions
"""

import logging
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market conditions detected from sentiment."""
    BULLISH = "bullish"        # Sustained uptrend, positive sentiment
    BEARISH = "bearish"        # Downtrend, fear signals
    SIDEWAYS = "sideways"      # Consolidation, neutral sentiment
    VOLATILE = "volatile"      # High volatility, mixed signals
    FEAR = "fear"             # Extreme fear, panic selling
    EUPHORIA = "euphoria"     # Extreme bullishness, potential peak


class SentimentMapper:
    """
    Maps sentiment scores to trading regime parameters.

    Produces configuration changes that get applied autonomously:
    ```
    Sentiment 75/100 (Bullish) →
    {
        "position_size": 1.2x,        # Larger positions
        "stop_loss_pct": 8.0,         # Tighter stops
        "take_profit_pct": 40.0,      # Higher targets
        "max_concurrent_trades": 15,  # More aggressive
    }
    ```
    """

    # Sentiment thresholds
    THRESHOLDS = {
        80: MarketRegime.EUPHORIA,      # Extreme bullish
        70: MarketRegime.BULLISH,       # Bullish
        60: MarketRegime.SIDEWAYS,      # Neutral-bullish
        40: MarketRegime.SIDEWAYS,      # Neutral
        30: MarketRegime.BEARISH,       # Bearish
        20: MarketRegime.FEAR,          # Extreme bearish
    }

    # Regime-specific parameters
    REGIME_PARAMETERS = {
        MarketRegime.EUPHORIA: {
            "position_size_multiplier": 0.8,  # Reduce in euphoria (risk management)
            "stop_loss_pct": 10.0,
            "take_profit_pct": 60.0,
            "max_concurrent_trades": 10,
            "risk_level": "conservative",
            "description": "Extreme bullishness - take profits, reduce size"
        },
        MarketRegime.BULLISH: {
            "position_size_multiplier": 1.3,
            "stop_loss_pct": 8.0,
            "take_profit_pct": 40.0,
            "max_concurrent_trades": 20,
            "risk_level": "aggressive",
            "description": "Strong uptrend - expand positions"
        },
        MarketRegime.SIDEWAYS: {
            "position_size_multiplier": 1.0,
            "stop_loss_pct": 5.0,
            "take_profit_pct": 20.0,
            "max_concurrent_trades": 15,
            "risk_level": "moderate",
            "description": "Range-bound - tight stops and targets"
        },
        MarketRegime.VOLATILE: {
            "position_size_multiplier": 0.7,
            "stop_loss_pct": 15.0,
            "take_profit_pct": 30.0,
            "max_concurrent_trades": 8,
            "risk_level": "conservative",
            "description": "High volatility - smaller positions, wider stops"
        },
        MarketRegime.BEARISH: {
            "position_size_multiplier": 0.5,
            "stop_loss_pct": 6.0,
            "take_profit_pct": 15.0,
            "max_concurrent_trades": 5,
            "risk_level": "very_conservative",
            "description": "Downtrend - minimal trading, focus on shorting"
        },
        MarketRegime.FEAR: {
            "position_size_multiplier": 0.3,
            "stop_loss_pct": 4.0,
            "take_profit_pct": 10.0,
            "max_concurrent_trades": 2,
            "risk_level": "minimal",
            "description": "Extreme fear - mostly cash, only best setups"
        },
    }

    def __init__(self):
        """Initialize sentiment mapper."""
        self.current_regime = MarketRegime.SIDEWAYS
        self.sentiment_history: List[float] = []
        self.regime_history: List[MarketRegime] = []

    def analyze_sentiment(self, grok_score: float) -> MarketRegime:
        """
        Classify market regime based on Grok sentiment score.

        Args:
            grok_score: 0-100 sentiment from Grok

        Returns:
            MarketRegime classification
        """
        self.sentiment_history.append(grok_score)

        # Determine regime based on score
        for threshold in sorted(self.THRESHOLDS.keys(), reverse=True):
            if grok_score >= threshold:
                regime = self.THRESHOLDS[threshold]
                break
        else:
            regime = MarketRegime.FEAR

        self.current_regime = regime
        self.regime_history.append(regime)

        logger.info(f"Sentiment: {grok_score:.1f}/100 → Regime: {regime.value}")

        return regime

    def get_trading_parameters(self, regime: Optional[MarketRegime] = None) -> Dict:
        """
        Get trading parameters for current market regime.

        Returns:
            Dict of parameters to apply to trading engine
        """
        regime = regime or self.current_regime
        params = self.REGIME_PARAMETERS.get(regime, self.REGIME_PARAMETERS[MarketRegime.SIDEWAYS])

        return dict(params)  # Return copy

    def detect_regime_change(self) -> Optional[str]:
        """
        Detect if market regime has changed significantly.

        Returns:
            Message describing regime change, or None if no change
        """
        if len(self.regime_history) < 2:
            return None

        current = self.regime_history[-1]
        previous = self.regime_history[-2]

        if current != previous:
            message = f"Regime shift: {previous.value.upper()} → {current.value.upper()}"
            logger.warning(message)
            return message

        return None

    def get_adaptation_rules(self) -> List[str]:
        """
        Generate human-readable adaptation rules for current regime.

        Used by vibe-coding engine to generate code changes.

        Returns:
            List of rules to apply
        """
        regime = self.current_regime
        params = self.REGIME_PARAMETERS[regime]

        rules = [
            f"🎯 {params['description']}",
            f"📊 Position size: {params['position_size_multiplier']:.1f}x normal",
            f"🛑 Stop loss: {params['stop_loss_pct']}%",
            f"🎁 Take profit: {params['take_profit_pct']}%",
            f"⚙️ Max trades: {params['max_concurrent_trades']}",
            f"⚠️ Risk level: {params['risk_level']}",
        ]

        return rules

    def generate_code_adaptations(self) -> Dict[str, str]:
        """
        Generate code changes for current regime.

        Produces Python code snippets that can be directly applied.

        Returns:
            Dict of config_key -> new_value
        """
        params = self.get_trading_parameters()

        adaptations = {
            "MAX_POSITION_SIZE_USD": str(int(1000 * params["position_size_multiplier"])),
            "STOP_LOSS_PCT": str(params["stop_loss_pct"]),
            "TAKE_PROFIT_PCT": str(params["take_profit_pct"]),
            "MAX_CONCURRENT_POSITIONS": str(params["max_concurrent_trades"]),
            "RISK_LEVEL": f"RiskLevel.{params['risk_level'].upper()}",
        }

        return adaptations

    def should_take_new_position(self, regime: Optional[MarketRegime] = None) -> bool:
        """
        Based on vibe, should we enter new positions?

        Returns:
            True if regime is favorable for new entries
        """
        regime = regime or self.current_regime

        # Only take new positions in favorable regimes
        favorable = [MarketRegime.BULLISH, MarketRegime.SIDEWAYS]

        return regime in favorable

    def should_tighten_stops(self, regime: Optional[MarketRegime] = None) -> bool:
        """Should we tighten stop losses in current regime?"""
        regime = regime or self.current_regime
        return regime in [MarketRegime.BULLISH, MarketRegime.EUPHORIA]

    def should_reduce_exposure(self, regime: Optional[MarketRegime] = None) -> bool:
        """Should we close some positions to reduce risk?"""
        regime = regime or self.current_regime
        return regime in [MarketRegime.BEARISH, MarketRegime.FEAR, MarketRegime.EUPHORIA]

    def get_summary(self) -> Dict:
        """Get current vibe summary."""
        if not self.sentiment_history:
            return {"status": "No data"}

        avg_sentiment = sum(self.sentiment_history) / len(self.sentiment_history)
        regime = self.current_regime

        return {
            "current_regime": regime.value,
            "current_sentiment": self.sentiment_history[-1],
            "average_sentiment": avg_sentiment,
            "history_length": len(self.sentiment_history),
            "rules": self.get_adaptation_rules(),
            "code_adaptations": self.generate_code_adaptations(),
        }
