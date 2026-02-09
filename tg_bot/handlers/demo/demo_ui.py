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
    import matplotlib.ticker as mticker
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
        # Align inputs (avoid exceptions from mismatched lengths).
        n = len(prices)
        if timestamps:
            n = min(n, len(timestamps))
        if volume:
            n = min(n, len(volume))
        if n < 2:
            logger.warning("Cannot generate chart - insufficient points")
            return None

        prices = [float(p) for p in prices[-n:]]
        if timestamps:
            timestamps = timestamps[-n:]
        if volume:
            volume = [float(v) for v in volume[-n:]]

        # Keep charts readable on Telegram: downsample if too many points.
        max_points = 96 if volume else 120
        if n > max_points:
            step = max(1, n // max_points)
            prices = prices[::step]
            if timestamps:
                timestamps = timestamps[::step]
            if volume:
                volume = volume[::step]
            n = len(prices)

        # Jarvis styling: dark, high-contrast, mobile-friendly.
        bg = "#0b0f14"
        grid = "#232833"
        text = "#e6e8ee"
        accent = "#00D4AA"
        vol_color = "#3b82f6"

        def _fmt_usd(x: float, _pos: int) -> str:
            ax = abs(x)
            if ax >= 1_000_000_000:
                return f"${x/1_000_000_000:.1f}B"
            if ax >= 1_000_000:
                return f"${x/1_000_000:.1f}M"
            if ax >= 10_000:
                return f"${x/1_000:.0f}K"
            if ax >= 1_000:
                return f"${x/1_000:.1f}K"
            if ax >= 1:
                return f"${x:,.2f}"
            if ax >= 0.01:
                return f"${x:.4f}"
            return f"${x:.6f}"

        with plt.style.context("dark_background"):
            if volume:
                fig, (ax1, ax2) = plt.subplots(
                    2,
                    1,
                    figsize=(12, 6),
                    dpi=90,
                    sharex=True,
                    gridspec_kw={"height_ratios": [3, 1]},
                )
                ax2.set_facecolor(bg)
            else:
                fig, ax1 = plt.subplots(figsize=(12, 5), dpi=90)
                ax2 = None

            fig.patch.set_facecolor(bg)
            ax1.set_facecolor(bg)

            x_data = timestamps if timestamps else list(range(len(prices)))

            # Y scaling: fill should not force us down to 0 (makes BTC/SOL charts look flat).
            ymin = min(prices)
            ymax = max(prices)
            span = max(1e-12, ymax - ymin)
            pad = span * 0.12
            if pad <= 0:
                pad = max(abs(ymax) * 0.01, 1e-6)
            y_bottom = ymin - pad
            y_top = ymax + pad

            ax1.set_ylim(y_bottom, y_top)
            ax1.plot(x_data, prices, color=accent, linewidth=2.6, zorder=3)
            ax1.fill_between(x_data, prices, y_bottom, alpha=0.14, color=accent, zorder=2)
            ax1.scatter([x_data[-1]], [prices[-1]], color=accent, s=18, zorder=4)

            # Title: include 24h change for quick scanning.
            change_pct = ((prices[-1] - prices[0]) / prices[0] * 100) if prices[0] else 0.0
            change_sign = "+" if change_pct >= 0 else ""
            ax1.set_title(
                f"{symbol} Price ({timeframe})  {change_sign}{change_pct:.2f}%",
                fontsize=13,
                fontweight="bold",
                color=text,
                pad=10,
            )
            ax1.set_ylabel("USD", fontsize=10, color=text, labelpad=6)
            ax1.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_usd))
            ax1.yaxis.set_major_locator(mticker.MaxNLocator(nbins=6))
            ax1.grid(True, alpha=0.18, linestyle="--", linewidth=0.9)

            # Subtle watermark + last price tag
            ax1.text(
                0.01,
                0.98,
                f"Last: {_fmt_usd(prices[-1], 0)}",
                transform=ax1.transAxes,
                va="top",
                ha="left",
                fontsize=9,
                color=text,
                alpha=0.9,
            )
            ax1.text(
                0.99,
                0.02,
                "JARVIS",
                transform=ax1.transAxes,
                va="bottom",
                ha="right",
                fontsize=8,
                color=text,
                alpha=0.25,
            )

            # X axis formatting
            if timestamps:
                locator = mdates.AutoDateLocator(minticks=4, maxticks=7)
                ax = ax2 if ax2 is not None else ax1
                ax.xaxis.set_major_locator(locator)
                ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
                fig.autofmt_xdate(rotation=0)
            else:
                ax1.set_xlabel("Time", fontsize=10, color=text)

            # Optional volume (keep it subtle)
            if ax2 is not None and volume:
                ax2.grid(True, alpha=0.12, linestyle="--", linewidth=0.9)
                ax2.yaxis.set_major_locator(mticker.MaxNLocator(nbins=3))
                ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _p: f"{v/1_000_000:.1f}M" if abs(v) >= 1_000_000 else f"{v/1_000:.0f}K"))
                ax2.set_ylabel("Vol", fontsize=9, color=text, labelpad=6)

                if timestamps and len(timestamps) >= 2:
                    dt = (timestamps[1] - timestamps[0]).total_seconds()
                    width_days = max(1 / 24 / 12, (dt / 86400) * 0.85)
                    ax2.bar(x_data, volume, width=width_days, color=vol_color, alpha=0.35)
                else:
                    ax2.fill_between(x_data, volume, 0, color=vol_color, alpha=0.25)

            # Axis + spine styling
            for ax in [ax1, ax2] if ax2 is not None else [ax1]:
                ax.tick_params(colors=text, labelsize=8)
                for side in ("top", "right"):
                    ax.spines[side].set_visible(False)
                for side in ("left", "bottom"):
                    ax.spines[side].set_color(grid)
                    ax.spines[side].set_alpha(0.7)

            fig.tight_layout(pad=1.0)

            buffer = BytesIO()
            fig.savefig(
                buffer,
                format="png",
                dpi=140,
                bbox_inches="tight",
                pad_inches=0.15,
                facecolor=fig.get_facecolor(),
            )
            buffer.seek(0)
            plt.close(fig)
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
