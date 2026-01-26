"""
Demo Bot - JarvisTheme

Beautiful emoji theme constants and indicator methods for JARVIS UI.
"""

from typing import Tuple


class JarvisTheme:
    """Beautiful emoji theme for JARVIS UI."""

    # Status indicators
    LIVE = "🟢"
    PAPER = "🟡"
    ERROR = "🔴"
    WARNING = "⚠️"
    SUCCESS = "✅"

    # Actions
    BUY = "🟢"
    SELL = "🔴"
    REFRESH = "🔄"
    SETTINGS = "⚙️"
    WALLET = "💳"
    CHART = "📊"

    # Navigation
    BACK = "◀️"
    FORWARD = "▶️"
    HOME = "🏠"
    CLOSE = "✖️"

    # Assets
    SOL = "◎"
    USD = "💵"
    COIN = "🪙"
    ROCKET = "🚀"
    FIRE = "🔥"
    GEM = "💎"

    # PnL
    PROFIT = "📈"
    LOSS = "📉"
    NEUTRAL = "➖"

    # Features
    SNIPE = "🎯"
    AUTO = "🤖"
    LOCK = "🔒"
    KEY = "🔑"
    COPY = "📋"

    # =========================================================================
    # BEAUTIFICATION V1.1 - Enhanced Visual Indicators
    # =========================================================================

    # Loading/Progress animations
    LOADING_FRAMES = ["⏳", "⌛"]
    PULSE_FRAMES = ["◉", "○"]
    SPIN_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Market mood spectrum (more nuanced than bull/bear)
    MOOD_EUPHORIC = "🌟"      # Extreme greed - careful!
    MOOD_BULLISH = "🚀"       # Strong uptrend
    MOOD_OPTIMISTIC = "💚"    # Mild bullish
    MOOD_NEUTRAL = "⚖️"       # Sideways
    MOOD_CAUTIOUS = "🔶"      # Mild bearish
    MOOD_FEARFUL = "😰"       # Strong downtrend
    MOOD_PANIC = "🆘"         # Extreme fear - opportunities!

    # Health indicators for positions
    HEALTH_EXCELLENT = "💪"   # > +20% PnL, healthy time
    HEALTH_GOOD = "🟢"        # +5% to +20% PnL
    HEALTH_FAIR = "🟡"        # -5% to +5% PnL
    HEALTH_WEAK = "🟠"        # -5% to -15% PnL
    HEALTH_CRITICAL = "🔴"    # < -15% PnL

    # AI confidence levels
    CONFIDENCE_HIGH = "🎯"    # > 80% confidence
    CONFIDENCE_MED = "📊"     # 60-80% confidence
    CONFIDENCE_LOW = "⚠️"     # < 60% confidence

    # Time indicators
    TIME_FRESH = "🆕"         # < 1 hour
    TIME_NORMAL = "⏰"        # 1-24 hours
    TIME_AGING = "📅"         # 1-7 days
    TIME_OLD = "🗓️"          # > 7 days

    @classmethod
    def get_health_indicator(cls, pnl_pct: float, hours_held: float = 0) -> str:
        """Get position health indicator based on PnL and time."""
        if pnl_pct >= 20:
            return cls.HEALTH_EXCELLENT
        elif pnl_pct >= 5:
            return cls.HEALTH_GOOD
        elif pnl_pct >= -5:
            return cls.HEALTH_FAIR
        elif pnl_pct >= -15:
            return cls.HEALTH_WEAK
        else:
            return cls.HEALTH_CRITICAL

    @classmethod
    def get_health_bar(cls, pnl_pct: float, width: int = 5) -> str:
        """Generate a visual health bar for position PnL."""
        # Normalize PnL to 0-100 scale (capped at -50% to +100%)
        normalized = min(100, max(0, (pnl_pct + 50) / 1.5))
        filled = int(normalized / 100 * width)
        empty = width - filled

        if pnl_pct >= 20:
            bar = "🟩" * filled + "⬜" * empty
        elif pnl_pct >= 0:
            bar = "🟨" * filled + "⬜" * empty
        elif pnl_pct >= -15:
            bar = "🟧" * filled + "⬜" * empty
        else:
            bar = "🟥" * filled + "⬜" * empty
        return bar

    @classmethod
    def get_time_indicator(cls, hours_held: float) -> str:
        """Get time held indicator."""
        if hours_held < 1:
            return cls.TIME_FRESH
        elif hours_held < 24:
            return cls.TIME_NORMAL
        elif hours_held < 168:  # 7 days
            return cls.TIME_AGING
        else:
            return cls.TIME_OLD

    @classmethod
    def get_market_mood(cls, fear_greed_score: float) -> Tuple[str, str]:
        """Get market mood emoji and label based on fear/greed score (0-100)."""
        if fear_greed_score >= 85:
            return cls.MOOD_EUPHORIC, "EUPHORIC"
        elif fear_greed_score >= 65:
            return cls.MOOD_BULLISH, "BULLISH"
        elif fear_greed_score >= 55:
            return cls.MOOD_OPTIMISTIC, "OPTIMISTIC"
        elif fear_greed_score >= 45:
            return cls.MOOD_NEUTRAL, "NEUTRAL"
        elif fear_greed_score >= 35:
            return cls.MOOD_CAUTIOUS, "CAUTIOUS"
        elif fear_greed_score >= 15:
            return cls.MOOD_FEARFUL, "FEARFUL"
        else:
            return cls.MOOD_PANIC, "PANIC"

    @classmethod
    def get_confidence_bar(cls, confidence: float, width: int = 10) -> str:
        """Generate an AI confidence bar (0.0 to 1.0)."""
        filled = int(confidence * width)
        empty = width - filled
        return "▰" * filled + "▱" * empty

    @classmethod
    def get_confidence_indicator(cls, confidence: float) -> str:
        """Get confidence level indicator."""
        if confidence >= 0.8:
            return cls.CONFIDENCE_HIGH
        elif confidence >= 0.6:
            return cls.CONFIDENCE_MED
        else:
            return cls.CONFIDENCE_LOW

    @classmethod
    def loading_text(cls, message: str = "Loading") -> str:
        """Generate loading text with animation hint."""
        return f"⏳ _{message}..._"

    @classmethod
    def format_pnl_styled(cls, pnl_pct: float, pnl_usd: float) -> str:
        """Format PnL with beautiful styling."""
        sign = "+" if pnl_pct >= 0 else ""
        emoji = cls.PROFIT if pnl_pct >= 0 else cls.LOSS
        health = cls.get_health_indicator(pnl_pct)
        bar = cls.get_health_bar(pnl_pct)

        return f"{emoji}{health} *{sign}{pnl_pct:.1f}%* ({sign}${abs(pnl_usd):.2f})\n{bar}"


__all__ = ["JarvisTheme"]
