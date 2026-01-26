"""
Demo Bot - UI Components Module

Contains:
- JarvisTheme: Beautiful emoji theme constants
- DemoMenuBuilder: Static methods for building Telegram menus
- safe_symbol: Token symbol sanitization
- generate_price_chart: Optional chart renderer (matplotlib)

This module re-exports from the new ui/ package structure.
"""

import logging
from io import BytesIO
from typing import Optional, List
from datetime import datetime

# Chart generation imports (optional - fallback if not available)
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend for servers
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logging.warning("Matplotlib not available - chart features disabled")

logger = logging.getLogger(__name__)

# Re-export UI components from the ui package
from tg_bot.handlers.demo.ui import (
    JarvisTheme,
    DemoMenuBuilder,
)


def safe_symbol(symbol: str) -> str:
    """
    Sanitize token symbol for safe display in Telegram messages.

    Removes special characters that could break Telegram Markdown formatting
    or cause display issues. Only allows alphanumeric, hyphen, and underscore.
    """
    if not symbol:
        return "UNKNOWN"
    sanitized = ''.join(c for c in str(symbol) if c.isalnum() or c in ['_', '-'])
    return sanitized[:10].upper() if sanitized else "UNKNOWN"


def generate_price_chart(
    prices: List[float],
    timestamps: Optional[List[datetime]] = None,
    symbol: str = "TOKEN",
    timeframe: str = "24H",
    volume: Optional[List[float]] = None,
) -> Optional[BytesIO]:
    """
    Generate a price chart image using matplotlib.

    Returns BytesIO buffer with PNG data, or None if matplotlib unavailable.
    """
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("Cannot generate chart - matplotlib not available")
        return None

    if not prices:
        logger.warning("Cannot generate chart - no price data")
        return None

    try:
        if volume:
            fig, (ax1, ax2) = plt.subplots(
                2, 1, figsize=(10, 7),
                gridspec_kw={'height_ratios': [3, 1]}
            )
        else:
            fig, ax1 = plt.subplots(figsize=(10, 6))

        x_data = timestamps if timestamps else list(range(len(prices)))

        ax1.plot(x_data, prices, color='#00D4AA', linewidth=2, label='Price')
        ax1.fill_between(x_data, prices, alpha=0.1, color='#00D4AA')
        ax1.set_title(f'{symbol} Price Chart ({timeframe})', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Price (USD)', fontsize=11)
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.legend(loc='upper left')

        if timestamps:
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        if volume and volume:
            ax2.bar(x_data, volume, color='#4A90E2', alpha=0.6)
            ax2.set_ylabel('Volume', fontsize=11)
            ax2.set_xlabel('Time', fontsize=11)
            ax2.grid(True, alpha=0.3, linestyle='--')
            if timestamps:
                ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        buffer = BytesIO()
        plt.tight_layout()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buffer.seek(0)
        return buffer
    except Exception as exc:
        logger.warning(f"Failed to generate chart: {exc}")
        return None

__all__ = [
    "JarvisTheme",
    "DemoMenuBuilder",
    "safe_symbol",
    "generate_price_chart",
    "MATPLOTLIB_AVAILABLE",
]
