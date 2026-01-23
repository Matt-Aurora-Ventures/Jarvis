"""
Demo Charts Handler (US-007)

Professional candlestick chart generation for the demo bot using mplfinance.
Features:
- Dark theme matching Telegram
- OHLCV candlestick charts
- Volume overlay
- 5-minute caching
"""

import io
import logging
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Check for mplfinance availability
try:
    import mplfinance as mpf
    import pandas as pd
    MPLFINANCE_AVAILABLE = True
except ImportError:
    MPLFINANCE_AVAILABLE = False
    mpf = None
    pd = None
    logger.warning("mplfinance not available - chart features disabled. Install with: pip install mplfinance pandas")


# =============================================================================
# Chart Style Configuration
# =============================================================================

def get_dark_style():
    """Create a dark theme chart style matching Telegram."""
    if not MPLFINANCE_AVAILABLE:
        return None

    mc = mpf.make_marketcolors(
        up='#00ff00',      # Green candles for price up
        down='#ff0000',    # Red candles for price down
        edge='inherit',
        wick='inherit',
        volume={'up': '#00ff0088', 'down': '#ff000088'},
        alpha=0.9
    )

    style = mpf.make_mpf_style(
        marketcolors=mc,
        gridcolor='#333333',
        gridstyle=':',
        y_on_right=False,
        rc={
            'axes.facecolor': '#1e1e1e',
            'figure.facecolor': '#1e1e1e',
            'axes.edgecolor': '#666666',
            'axes.labelcolor': '#ffffff',
            'xtick.color': '#ffffff',
            'ytick.color': '#ffffff',
            'text.color': '#ffffff'
        }
    )
    return style


# =============================================================================
# Cache Management
# =============================================================================

# Simple in-memory cache with 5-minute TTL
_chart_cache: Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cache_key(mint: str, interval: str) -> str:
    """Generate cache key for chart."""
    # Round to 5-minute intervals for caching
    timestamp_5min = int(time.time() // CACHE_TTL_SECONDS)
    return f"{mint}:{interval}:{timestamp_5min}"


def _get_cached_chart(mint: str, interval: str) -> Optional[io.BytesIO]:
    """Get chart from cache if available."""
    key = _get_cache_key(mint, interval)
    if key in _chart_cache:
        cached_time, chart_bytes = _chart_cache[key]
        if time.time() - cached_time < CACHE_TTL_SECONDS:
            # Return a copy of the BytesIO
            buf = io.BytesIO(chart_bytes)
            buf.seek(0)
            return buf
        else:
            # Expired
            del _chart_cache[key]
    return None


def _cache_chart(mint: str, interval: str, chart_buf: io.BytesIO):
    """Cache chart for 5 minutes."""
    key = _get_cache_key(mint, interval)
    chart_buf.seek(0)
    _chart_cache[key] = (time.time(), chart_buf.read())
    chart_buf.seek(0)


# =============================================================================
# Chart Generation
# =============================================================================

async def fetch_ohlcv_data(
    mint: str,
    interval: str = "1h",
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetch OHLCV data for a token.

    This is a placeholder that should be integrated with your data source.
    """
    # Try to get data from bags.fm or Jupiter
    try:
        from core.trading.bags_client import get_bags_client
        bags = get_bags_client()
        if bags:
            data = await bags.get_chart_data(mint, interval=interval, limit=limit)
            if data and data.get("candles"):
                return data["candles"]
    except Exception as e:
        logger.warning(f"Failed to fetch OHLCV from bags.fm: {e}")

    # Fallback: Generate demo data
    logger.info("Generating demo OHLCV data")
    import random
    candles = []
    now = datetime.now(timezone.utc)
    base_price = random.uniform(0.00001, 0.001)

    for i in range(limit):
        # Simple random walk
        change = random.uniform(-0.05, 0.05)
        open_price = base_price * (1 + change)
        close_price = open_price * (1 + random.uniform(-0.03, 0.03))
        high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.02))
        low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.02))
        volume = random.uniform(10000, 1000000)

        candles.append({
            "timestamp": int((now.timestamp() - (limit - i) * 3600)),
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
        })
        base_price = close_price

    return candles


async def generate_price_chart(
    mint: str,
    symbol: str,
    interval: str = "1h",
    timeframe: str = "24h"
) -> Optional[io.BytesIO]:
    """
    Generate professional candlestick chart for a token.

    Uses mplfinance for TradingView-quality charts with proper OHLCV rendering.

    Args:
        mint: Token mint address
        symbol: Token symbol for title
        interval: Candle interval (1m, 5m, 15m, 1h, 4h, 1d)
        timeframe: How much history to show

    Returns:
        BytesIO buffer containing PNG image, or None if generation fails.
    """
    if not MPLFINANCE_AVAILABLE:
        logger.error("mplfinance not available for chart generation")
        return None

    # Check cache first
    cached = _get_cached_chart(mint, interval)
    if cached:
        logger.debug(f"Returning cached chart for {symbol}")
        return cached

    try:
        # Fetch OHLCV data
        candles = await fetch_ohlcv_data(mint, interval=interval)

        if not candles or len(candles) < 2:
            logger.warning(f"Insufficient candle data for {symbol}")
            return None

        # Convert to pandas DataFrame (mplfinance requirement)
        df = pd.DataFrame(candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df.set_index('timestamp', inplace=True)
        df = df[['open', 'high', 'low', 'close', 'volume']]
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

        # Get style
        style = get_dark_style()
        if style is None:
            return None

        # Generate chart
        buf = io.BytesIO()

        mpf.plot(
            df,
            type='candle',
            style=style,
            volume=True,
            title=f'{symbol} ({interval} candles)',
            ylabel='Price (USD)',
            ylabel_lower='Volume',
            figsize=(12, 8),
            savefig=dict(fname=buf, dpi=150, bbox_inches='tight')
        )

        buf.seek(0)

        # Cache the result
        _cache_chart(mint, interval, buf)

        return buf

    except Exception as e:
        logger.error(f"Failed to generate chart for {symbol}: {e}")
        return None


async def generate_simple_line_chart(
    mint: str,
    symbol: str,
    prices: List[float] = None,
    timeframe: str = "24h"
) -> Optional[io.BytesIO]:
    """
    Generate a simple line chart when OHLCV data is not available.

    Uses matplotlib directly for a basic price line chart.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        if prices is None or len(prices) < 2:
            # Generate demo data
            import random
            base = random.uniform(0.00001, 0.001)
            prices = [base * (1 + random.uniform(-0.1, 0.1)) for _ in range(100)]

        # Create figure with dark theme
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(12, 6))
        fig.patch.set_facecolor('#1e1e1e')
        ax.set_facecolor('#1e1e1e')

        # Plot prices
        ax.plot(prices, color='#00ff00', linewidth=2)

        # Calculate change
        change_pct = ((prices[-1] / prices[0]) - 1) * 100
        color = '#00ff00' if change_pct >= 0 else '#ff0000'

        # Title with change
        ax.set_title(
            f'{symbol} Price ({timeframe}) - {change_pct:+.2f}%',
            color='white',
            fontsize=14
        )
        ax.set_ylabel('Price (USD)', color='white')
        ax.grid(True, alpha=0.3)

        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#1e1e1e')
        plt.close(fig)
        buf.seek(0)

        return buf

    except Exception as e:
        logger.error(f"Failed to generate line chart for {symbol}: {e}")
        return None


# =============================================================================
# Chart Callback Handler
# =============================================================================

async def handle_chart_callback(
    token_mint: str,
    token_symbol: str,
    interval: str = "1h"
) -> tuple:
    """
    Handle chart generation for callback.

    Returns:
        Tuple of (success, chart_buffer or error_message)
    """
    if not MPLFINANCE_AVAILABLE:
        return False, "Chart feature requires mplfinance. Install with: pip install mplfinance pandas"

    try:
        chart = await generate_price_chart(token_mint, token_symbol, interval)
        if chart:
            return True, chart
        else:
            # Fallback to simple line chart
            chart = await generate_simple_line_chart(token_mint, token_symbol)
            if chart:
                return True, chart
            return False, "Failed to generate chart. No data available."
    except Exception as e:
        logger.error(f"Chart callback error: {e}")
        return False, f"Chart generation failed: {str(e)[:50]}"
