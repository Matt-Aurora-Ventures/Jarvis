"""
Chart Handler for Telegram Token Analysis.

Generates chart images for tokens with:
- Price chart with moving averages
- Timeframe selection (1H, 4H, 1D, 1W)
- Signal overlays
"""

import logging
from datetime import datetime, timedelta
from io import BytesIO
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Check if matplotlib is available
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available - chart generation disabled")


class ChartHandler:
    """
    Generate and send chart images for token analysis.

    Uses matplotlib for chart generation, optimized for Telegram display.
    """

    # Chart styling
    DARK_THEME = {
        "bg": "#1a1a1a",
        "text": "#ffffff",
        "grid": "#333333",
        "bull": "#10b981",
        "bear": "#ef4444",
        "neutral": "#6b7280",
        "accent": "#3b82f6",
    }

    # Chart size (optimized for Telegram)
    WIDTH = 12
    HEIGHT = 6
    DPI = 80

    def __init__(self):
        """Initialize chart handler."""
        if MATPLOTLIB_AVAILABLE:
            self._setup_matplotlib_style()

    def _setup_matplotlib_style(self):
        """Configure matplotlib for dark theme charts."""
        if not MATPLOTLIB_AVAILABLE:
            return

        plt.style.use("dark_background")

        plt.rcParams.update({
            "figure.facecolor": self.DARK_THEME["bg"],
            "axes.facecolor": self.DARK_THEME["bg"],
            "axes.edgecolor": self.DARK_THEME["grid"],
            "text.color": self.DARK_THEME["text"],
            "axes.labelcolor": self.DARK_THEME["text"],
            "xtick.color": self.DARK_THEME["text"],
            "ytick.color": self.DARK_THEME["text"],
            "grid.color": self.DARK_THEME["grid"],
            "figure.edgecolor": self.DARK_THEME["grid"],
            "font.size": 9,
            "axes.labelsize": 10,
            "axes.titlesize": 12,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 9,
            "lines.linewidth": 2,
        })

    async def generate_price_chart(
        self,
        symbol: str,
        prices: List[float],
        times: List[datetime],
        ma_short: Optional[List[float]] = None,
        ma_long: Optional[List[float]] = None,
        timeframe: str = "1H",
    ) -> Optional[BytesIO]:
        """
        Generate price chart with moving averages.

        Args:
            symbol: Token symbol
            prices: List of prices
            times: List of timestamps
            ma_short: Short-term MA values
            ma_long: Long-term MA values
            timeframe: Chart timeframe label

        Returns:
            BytesIO with PNG image, or None if unavailable
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Cannot generate chart - matplotlib not available")
            return None

        if not prices or not times:
            logger.warning("No price data for chart generation")
            return None

        try:
            fig, ax = plt.subplots(figsize=(self.WIDTH, self.HEIGHT), dpi=self.DPI)

            # Plot prices
            ax.plot(
                times, prices,
                color=self.DARK_THEME["accent"],
                linewidth=2.5,
                label="Price",
                zorder=2
            )

            # Plot MAs if provided
            if ma_short and len(ma_short) == len(times):
                ax.plot(
                    times, ma_short,
                    color=self.DARK_THEME["bull"],
                    linewidth=1.5,
                    alpha=0.7,
                    label="MA(7)",
                    linestyle="--"
                )

            if ma_long and len(ma_long) == len(times):
                ax.plot(
                    times, ma_long,
                    color=self.DARK_THEME["bear"],
                    linewidth=1.5,
                    alpha=0.7,
                    label="MA(25)",
                    linestyle="--"
                )

            # Formatting
            ax.set_title(f"{symbol} Price Chart ({timeframe})", fontsize=14, fontweight="bold", pad=15)
            ax.set_xlabel("Time", fontsize=10)
            ax.set_ylabel("Price (USD)", fontsize=10)
            ax.grid(True, alpha=0.2)
            ax.legend(loc="upper left", framealpha=0.9)

            # Format x-axis based on timeframe
            if timeframe in ["1H", "4H"]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            else:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))

            fig.autofmt_xdate(rotation=45, ha="right")
            plt.tight_layout()

            # Save to BytesIO
            buffer = BytesIO()
            fig.savefig(buffer, format="png", facecolor=self.DARK_THEME["bg"])
            buffer.seek(0)
            plt.close(fig)

            return buffer

        except Exception as e:
            logger.error(f"Chart generation failed: {e}")
            return None

    async def generate_mini_chart(
        self,
        symbol: str,
        prices: List[float],
        positive: bool = True,
    ) -> Optional[BytesIO]:
        """
        Generate small inline chart for quick view.

        Args:
            symbol: Token symbol
            prices: List of recent prices
            positive: Whether overall trend is positive

        Returns:
            BytesIO with PNG image
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        if not prices or len(prices) < 2:
            return None

        try:
            fig, ax = plt.subplots(figsize=(4, 2), dpi=80)

            color = self.DARK_THEME["bull"] if positive else self.DARK_THEME["bear"]

            ax.plot(range(len(prices)), prices, color=color, linewidth=2)
            ax.fill_between(
                range(len(prices)),
                prices,
                min(prices),
                color=color,
                alpha=0.2
            )

            # Minimal styling
            ax.set_xticks([])
            ax.set_yticks([])
            ax.axis("off")

            plt.tight_layout(pad=0)

            buffer = BytesIO()
            fig.savefig(
                buffer,
                format="png",
                facecolor=self.DARK_THEME["bg"],
                bbox_inches="tight",
                pad_inches=0
            )
            buffer.seek(0)
            plt.close(fig)

            return buffer

        except Exception as e:
            logger.error(f"Mini chart generation failed: {e}")
            return None

    async def fetch_price_data(
        self,
        token_address: str,
        timeframe: str = "1H",
    ) -> Tuple[List[float], List[datetime]]:
        """
        Fetch price data for chart generation.

        Args:
            token_address: Token contract address
            timeframe: Chart timeframe (1H, 4H, 1D, 1W)

        Returns:
            Tuple of (prices, timestamps)
        """
        # Determine data points and interval
        timeframe_config = {
            "1H": {"points": 60, "interval_minutes": 1},
            "4H": {"points": 48, "interval_minutes": 5},
            "1D": {"points": 24, "interval_minutes": 60},
            "1W": {"points": 168, "interval_minutes": 60},
        }

        config = timeframe_config.get(timeframe, timeframe_config["1H"])

        try:
            # Try to fetch from DexScreener or similar
            from tg_bot.services.signal_service import get_signal_service

            service = get_signal_service()
            signal = await service.get_comprehensive_signal(
                token_address,
                include_sentiment=False
            )

            # Generate synthetic data based on current price
            # In production, this would fetch actual OHLC data
            current_price = signal.price_usd
            if current_price <= 0:
                return [], []

            # Generate price history (simulated)
            import random
            random.seed(hash(token_address) % 1000000)

            prices = []
            volatility = abs(signal.price_change_24h) / 100 if signal.price_change_24h else 0.05
            volatility = min(volatility, 0.1)  # Cap volatility

            price = current_price
            for i in range(config["points"]):
                # Random walk with trend
                change = random.uniform(-volatility, volatility)
                price = price * (1 + change)
                prices.insert(0, price)

            # Adjust to match current price
            scale = current_price / prices[-1] if prices[-1] > 0 else 1
            prices = [p * scale for p in prices]

            # Generate timestamps
            now = datetime.now()
            interval = timedelta(minutes=config["interval_minutes"])
            times = [now - interval * i for i in range(config["points"])]
            times.reverse()

            return prices, times

        except Exception as e:
            logger.warning(f"Failed to fetch price data: {e}")
            return [], []

    def calculate_moving_averages(
        self,
        prices: List[float],
        short_period: int = 7,
        long_period: int = 25,
    ) -> Tuple[List[float], List[float]]:
        """Calculate simple moving averages."""
        if not prices:
            return [], []

        def sma(data, period):
            result = []
            for i in range(len(data)):
                if i < period - 1:
                    result.append(None)
                else:
                    avg = sum(data[i - period + 1:i + 1]) / period
                    result.append(avg)
            return result

        ma_short = sma(prices, short_period)
        ma_long = sma(prices, long_period)

        # Replace None with first valid value for plotting
        for ma in [ma_short, ma_long]:
            first_valid = next((x for x in ma if x is not None), prices[0])
            for i in range(len(ma)):
                if ma[i] is None:
                    ma[i] = first_valid

        return ma_short, ma_long


__all__ = ["ChartHandler"]
