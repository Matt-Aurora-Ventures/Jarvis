"""
Chart Generator for Telegram Treasury Bot

Generate beautiful trading charts for real-time market visualization:
- Price action charts with moving averages
- Portfolio performance over time
- Trade history visualization
- Risk/return scatter plots
- Drawdown analysis
- Sentiment heatmaps

Charts are optimized for Telegram inline display (300-500px width).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from io import BytesIO

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.dates import DateFormatter
from matplotlib.gridspec import GridSpec
import numpy as np

logger = logging.getLogger(__name__)


class ChartGenerator:
    """Generate beautiful trading charts for Telegram."""

    # Chart styling
    DARK_THEME = {
        'bg': '#1a1a1a',
        'text': '#ffffff',
        'grid': '#333333',
        'bull': '#10b981',      # Emerald green
        'bear': '#ef4444',      # Red
        'neutral': '#6b7280',   # Gray
        'accent': '#3b82f6',    # Blue
    }

    # Chart size (optimized for Telegram)
    WIDTH = 12
    HEIGHT = 6
    DPI = 80  # 960x480px final size

    def __init__(self):
        """Initialize chart generator."""
        self._setup_matplotlib_style()

    def _setup_matplotlib_style(self):
        """Configure matplotlib for beautiful dark theme charts."""
        plt.style.use('dark_background')

        # Apply custom styling
        plt.rcParams.update({
            'figure.facecolor': self.DARK_THEME['bg'],
            'axes.facecolor': self.DARK_THEME['bg'],
            'axes.edgecolor': self.DARK_THEME['grid'],
            'text.color': self.DARK_THEME['text'],
            'axes.labelcolor': self.DARK_THEME['text'],
            'xtick.color': self.DARK_THEME['text'],
            'ytick.color': self.DARK_THEME['text'],
            'grid.color': self.DARK_THEME['grid'],
            'figure.edgecolor': self.DARK_THEME['grid'],
            'font.size': 9,
            'axes.labelsize': 10,
            'axes.titlesize': 12,
            'xtick.labelsize': 8,
            'ytick.labelsize': 8,
            'legend.fontsize': 9,
            'lines.linewidth': 2,
            'lines.markersize': 6,
        })

    # ==================== PRICE CHARTS ====================

    def generate_price_chart(
        self,
        symbol: str,
        prices: List[float],
        times: List[datetime],
        ma_short: Optional[List[float]] = None,
        ma_long: Optional[List[float]] = None,
        entry_price: Optional[float] = None,
        exit_price: Optional[float] = None,
    ) -> BytesIO:
        """
        Generate price chart with moving averages and entry/exit markers.

        Args:
            symbol: Token symbol (e.g., 'SOL')
            prices: List of prices
            times: List of timestamps
            ma_short: Short-term moving average
            ma_long: Long-term moving average
            entry_price: Entry price marker
            exit_price: Exit price marker

        Returns:
            BytesIO PNG image
        """
        fig, ax = plt.subplots(figsize=(self.WIDTH, self.HEIGHT), dpi=self.DPI)

        # Plot prices
        ax.plot(times, prices, color=self.DARK_THEME['accent'], linewidth=2.5, label='Price', zorder=2)

        # Plot moving averages
        if ma_short:
            ax.plot(times, ma_short, color=self.DARK_THEME['bull'], linewidth=1.5, alpha=0.7, label='MA(7)', linestyle='--')

        if ma_long:
            ax.plot(times, ma_long, color=self.DARK_THEME['bear'], linewidth=1.5, alpha=0.7, label='MA(25)', linestyle='--')

        # Mark entry
        if entry_price:
            ax.axhline(y=entry_price, color=self.DARK_THEME['bull'], linewidth=2, alpha=0.5, linestyle=':', label='Entry')
            ax.text(times[0], entry_price, f' Entry: ${entry_price:.6f}', color=self.DARK_THEME['bull'], fontsize=8, va='center')

        # Mark exit
        if exit_price:
            ax.axhline(y=exit_price, color=self.DARK_THEME['bear'], linewidth=2, alpha=0.5, linestyle=':', label='Target')
            ax.text(times[0], exit_price, f' Target: ${exit_price:.6f}', color=self.DARK_THEME['bear'], fontsize=8, va='center')

        # Formatting
        ax.set_title(f'{symbol} Price Chart', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Time', fontsize=10)
        ax.set_ylabel('Price (USD)', fontsize=10)
        ax.grid(True, alpha=0.2)
        ax.legend(loc='upper left', framealpha=0.9)

        # Format x-axis
        ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))
        fig.autofmt_xdate(rotation=45, ha='right')

        plt.tight_layout()

        # Save to BytesIO
        buffer = BytesIO()
        fig.savefig(buffer, format='png', facecolor=self.DARK_THEME['bg'])
        buffer.seek(0)
        plt.close(fig)

        return buffer

    # ==================== PORTFOLIO CHARTS ====================

    def generate_portfolio_chart(
        self,
        net_values: List[float],
        dates: List[datetime],
        benchmark: Optional[List[float]] = None,
    ) -> BytesIO:
        """Generate portfolio performance chart."""
        fig, ax = plt.subplots(figsize=(self.WIDTH, self.HEIGHT), dpi=self.DPI)

        # Calculate returns
        initial_value = net_values[0]
        returns = [(v - initial_value) / initial_value * 100 for v in net_values]

        # Plot portfolio
        ax.fill_between(dates, returns, alpha=0.3, color=self.DARK_THEME['accent'])
        ax.plot(dates, returns, color=self.DARK_THEME['accent'], linewidth=2.5, label='Portfolio', marker='o', markersize=3)

        # Plot benchmark if provided
        if benchmark:
            benchmark_returns = [(v - benchmark[0]) / benchmark[0] * 100 for v in benchmark]
            ax.plot(dates, benchmark_returns, color=self.DARK_THEME['neutral'], linewidth=1.5, alpha=0.7, label='Benchmark', linestyle='--')

        ax.set_title('Portfolio Performance', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Date', fontsize=10)
        ax.set_ylabel('Return (%)', fontsize=10)
        ax.axhline(y=0, color=self.DARK_THEME['text'], linewidth=0.5, linestyle='-', alpha=0.3)
        ax.grid(True, alpha=0.2)
        ax.legend(loc='upper left', framealpha=0.9)

        # Format x-axis
        ax.xaxis.set_major_formatter(DateFormatter('%m/%d'))
        fig.autofmt_xdate(rotation=45, ha='right')

        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format='png', facecolor=self.DARK_THEME['bg'])
        buffer.seek(0)
        plt.close(fig)

        return buffer

    # ==================== POSITION BREAKDOWN ====================

    def generate_position_allocation(
        self,
        positions: Dict[str, float],  # symbol -> allocation %
    ) -> BytesIO:
        """Generate pie chart of position allocation."""
        fig, ax = plt.subplots(figsize=(8, 8), dpi=self.DPI)

        # Sort by size
        sorted_pos = dict(sorted(positions.items(), key=lambda x: x[1], reverse=True))
        labels = list(sorted_pos.keys())
        sizes = list(sorted_pos.values())

        # Color palette
        colors = []
        for i, size in enumerate(sizes):
            if size > 20:
                colors.append(self.DARK_THEME['bull'])
            elif size > 10:
                colors.append(self.DARK_THEME['accent'])
            else:
                colors.append(self.DARK_THEME['neutral'])

        # Create pie
        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            textprops={'color': self.DARK_THEME['text'], 'fontsize': 9}
        )

        # Style percentage labels
        for autotext in autotexts:
            autotext.set_color(self.DARK_THEME['bg'])
            autotext.set_fontweight('bold')
            autotext.set_fontsize(8)

        ax.set_title('Position Allocation', fontsize=14, fontweight='bold', pad=15)

        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format='png', facecolor=self.DARK_THEME['bg'])
        buffer.seek(0)
        plt.close(fig)

        return buffer

    # ==================== DRAWDOWN CHART ====================

    def generate_drawdown_chart(
        self,
        net_values: List[float],
        dates: List[datetime],
    ) -> BytesIO:
        """Generate drawdown analysis chart."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(self.WIDTH, self.HEIGHT), dpi=self.DPI, gridspec_kw={'height_ratios': [3, 1]})

        # Calculate running maximum and drawdown
        running_max = np.maximum.accumulate(net_values)
        drawdown = (np.array(net_values) - running_max) / running_max * 100

        # Plot net value
        ax1.fill_between(dates, net_values, alpha=0.3, color=self.DARK_THEME['accent'])
        ax1.plot(dates, net_values, color=self.DARK_THEME['accent'], linewidth=2.5, label='Net Value')
        ax1.plot(dates, running_max, color=self.DARK_THEME['neutral'], linewidth=1.5, linestyle='--', alpha=0.5, label='Running Maximum')

        ax1.set_title('Portfolio Value & Drawdown', fontsize=14, fontweight='bold', pad=15)
        ax1.set_ylabel('Value (USD)', fontsize=10)
        ax1.grid(True, alpha=0.2)
        ax1.legend(loc='upper left', framealpha=0.9)

        # Plot drawdown
        colors = [self.DARK_THEME['bear'] if d < 0 else self.DARK_THEME['neutral'] for d in drawdown]
        ax2.bar(dates, drawdown, color=colors, alpha=0.7, width=np.timedelta64(1, 'h'))

        ax2.set_xlabel('Date', fontsize=10)
        ax2.set_ylabel('Drawdown (%)', fontsize=10)
        ax2.axhline(y=0, color=self.DARK_THEME['text'], linewidth=0.5, alpha=0.3)
        ax2.grid(True, alpha=0.2, axis='y')

        # Format x-axis
        ax2.xaxis.set_major_formatter(DateFormatter('%m/%d'))
        fig.autofmt_xdate(rotation=45, ha='right')

        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format='png', facecolor=self.DARK_THEME['bg'])
        buffer.seek(0)
        plt.close(fig)

        return buffer

    # ==================== TRADE ANALYSIS ====================

    def generate_trade_distribution(
        self,
        pnl_values: List[float],
    ) -> BytesIO:
        """Generate histogram of trade P&L distribution."""
        fig, ax = plt.subplots(figsize=(10, 6), dpi=self.DPI)

        # Separate wins and losses
        wins = [x for x in pnl_values if x > 0]
        losses = [x for x in pnl_values if x < 0]

        # Plot histogram
        ax.hist(wins, bins=15, alpha=0.7, color=self.DARK_THEME['bull'], label=f'Wins ({len(wins)})', edgecolor='white')
        ax.hist(losses, bins=15, alpha=0.7, color=self.DARK_THEME['bear'], label=f'Losses ({len(losses)})', edgecolor='white')

        ax.axvline(x=0, color=self.DARK_THEME['text'], linewidth=1, linestyle='--', alpha=0.5)
        ax.axvline(x=np.mean(pnl_values), color=self.DARK_THEME['accent'], linewidth=2, linestyle='-', alpha=0.7, label=f'Mean: ${np.mean(pnl_values):.2f}')

        ax.set_title('Trade P&L Distribution', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('P&L (USD)', fontsize=10)
        ax.set_ylabel('Frequency', fontsize=10)
        ax.grid(True, alpha=0.2, axis='y')
        ax.legend(loc='upper right', framealpha=0.9)

        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format='png', facecolor=self.DARK_THEME['bg'])
        buffer.seek(0)
        plt.close(fig)

        return buffer

    # ==================== RISK/RETURN SCATTER ====================

    def generate_risk_return_plot(
        self,
        positions: List[Dict[str, Any]],  # [{symbol, return%, volatility%}, ...]
    ) -> BytesIO:
        """Generate risk/return scatter plot."""
        fig, ax = plt.subplots(figsize=(10, 8), dpi=self.DPI)

        symbols = [p['symbol'] for p in positions]
        returns = [p['return'] for p in positions]
        volatilities = [p['volatility'] for p in positions]
        sizes = [p.get('allocation', 5) * 20 for p in positions]  # Size by allocation

        # Plot points
        scatter = ax.scatter(volatilities, returns, s=sizes, alpha=0.6, c=returns, cmap='RdYlGn', edgecolor='white', linewidth=1)

        # Annotate
        for i, symbol in enumerate(symbols):
            ax.annotate(symbol, (volatilities[i], returns[i]), fontsize=9, ha='center', va='center')

        ax.set_title('Risk/Return Profile', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Risk (Volatility %)', fontsize=10)
        ax.set_ylabel('Return (%)', fontsize=10)
        ax.axhline(y=0, color=self.DARK_THEME['text'], linewidth=0.5, linestyle='-', alpha=0.3)
        ax.grid(True, alpha=0.2)

        plt.colorbar(scatter, ax=ax, label='Return (%)')

        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format='png', facecolor=self.DARK_THEME['bg'])
        buffer.seek(0)
        plt.close(fig)

        return buffer

    # ==================== SENTIMENT HEATMAP ====================

    def generate_sentiment_heatmap(
        self,
        symbols: List[str],
        sentiment_scores: Dict[str, Dict[str, float]],  # {symbol: {source: score}}
        time_period: str = "24h",
    ) -> BytesIO:
        """
        Generate sentiment heatmap across multiple sources.

        Example sentiment_scores:
        {
            'SOL': {'grok': 75, 'twitter': 68, 'news': 72},
            'BTC': {'grok': 82, 'twitter': 71, 'news': 78},
        }
        """
        fig, ax = plt.subplots(figsize=(10, 6), dpi=self.DPI)

        # Build matrix
        sources = list(set().union(*[s.keys() for s in sentiment_scores.values()]))
        matrix = [[sentiment_scores.get(sym, {}).get(src, 0) for src in sources] for sym in symbols]

        # Plot heatmap
        im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=100)

        # Set ticks and labels
        ax.set_xticks(np.arange(len(sources)))
        ax.set_yticks(np.arange(len(symbols)))
        ax.set_xticklabels(sources)
        ax.set_yticklabels(symbols)

        # Rotate x labels
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right', rotation_mode='anchor')

        # Add text annotations
        for i in range(len(symbols)):
            for j in range(len(sources)):
                value = matrix[i][j]
                if value > 0:
                    text = ax.text(j, i, f'{int(value)}', ha='center', va='center', color='white', fontsize=10, fontweight='bold')

        ax.set_title(f'Sentiment Heatmap ({time_period})', fontsize=14, fontweight='bold', pad=15)

        # Colorbar
        cbar = plt.colorbar(im, ax=ax, label='Sentiment Score (0-100)')

        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format='png', facecolor=self.DARK_THEME['bg'])
        buffer.seek(0)
        plt.close(fig)

        return buffer
