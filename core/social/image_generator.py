"""
Image Generator for Twitter/X Bot

Generates visual content for tweets:
- Sentiment visualization (bull/bear charts)
- Price action visualization (candlesticks)
- Portfolio composition charts

Uses matplotlib for chart generation with PIL for image processing.
"""

import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default output directory
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "social" / "images"

# Try to import visualization libraries
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib not installed - chart generation disabled")

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("PIL not installed - image processing disabled")


@dataclass
class ImageConfig:
    """Configuration for image generation."""

    width: int = 1080
    height: int = 720
    dpi: int = 150
    theme: str = "dark"
    font_family: str = "sans-serif"
    branding_text: str = "@Jarvis_lifeos"

    # Color schemes
    dark_colors: Dict[str, str] = field(default_factory=lambda: {
        "background": "#1a1a2e",
        "surface": "#16213e",
        "text": "#ffffff",
        "text_secondary": "#a0a0a0",
        "bullish": "#00ff88",
        "bearish": "#ff4444",
        "neutral": "#ffaa00",
        "grid": "#0f3460",
        "accent": "#7b2cbf",
    })

    light_colors: Dict[str, str] = field(default_factory=lambda: {
        "background": "#ffffff",
        "surface": "#f0f0f0",
        "text": "#1a1a1a",
        "text_secondary": "#666666",
        "bullish": "#00aa55",
        "bearish": "#cc3333",
        "neutral": "#ff9900",
        "grid": "#dddddd",
        "accent": "#5a1d99",
    })

    def get_colors(self) -> Dict[str, str]:
        """Get color palette for current theme."""
        return self.dark_colors if self.theme == "dark" else self.light_colors


class ImageGenerator:
    """
    Generates chart images for Twitter posts.

    Usage:
        generator = ImageGenerator(output_dir=Path("./output"))
        sentiment_data = {"SOL": 0.8, "BTC": 0.5}
        image_path = generator.generate_sentiment_chart(sentiment_data)
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        config: Optional[ImageConfig] = None
    ):
        """
        Initialize image generator.

        Args:
            output_dir: Directory to save generated images
            config: Image configuration settings
        """
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or ImageConfig()

    def generate_sentiment_chart(
        self,
        sentiment_data: Dict[str, float],
        title: Optional[str] = None
    ) -> Optional[Path]:
        """
        Generate a sentiment bar chart showing bullish/bearish tokens.

        Args:
            sentiment_data: Dict mapping token symbols to sentiment scores (-1 to 1)
            title: Optional chart title

        Returns:
            Path to generated PNG image, or None on failure
        """
        if not sentiment_data:
            logger.warning("No sentiment data provided")
            return None

        if not HAS_MATPLOTLIB:
            logger.error("matplotlib not available")
            return None

        try:
            colors = self.config.get_colors()

            # Sort tokens by sentiment
            sorted_tokens = sorted(
                sentiment_data.items(),
                key=lambda x: x[1],
                reverse=True
            )

            tokens = [t[0] for t in sorted_tokens]
            scores = [t[1] for t in sorted_tokens]

            # Create figure
            fig_width = self.config.width / self.config.dpi
            fig_height = self.config.height / self.config.dpi
            fig, ax = plt.subplots(figsize=(fig_width, fig_height))

            # Color bars based on sentiment
            bar_colors = []
            for score in scores:
                if score > 0.2:
                    bar_colors.append(colors["bullish"])
                elif score < -0.2:
                    bar_colors.append(colors["bearish"])
                else:
                    bar_colors.append(colors["neutral"])

            # Create horizontal bar chart
            y_pos = np.arange(len(tokens))
            bars = ax.barh(y_pos, scores, color=bar_colors, edgecolor='none', height=0.7)

            # Styling
            ax.set_yticks(y_pos)
            ax.set_yticklabels([f"${t}" for t in tokens])
            ax.set_xlim(-1.1, 1.1)
            ax.axvline(x=0, color=colors["text_secondary"], linewidth=0.5)

            # Labels
            ax.set_xlabel("Sentiment Score", color=colors["text"])
            ax.set_ylabel("Token", color=colors["text"])

            if title:
                ax.set_title(title, color=colors["text"], fontweight='bold')
            else:
                ax.set_title(
                    f"Jarvis Sentiment Analysis - {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                    color=colors["text"],
                    fontweight='bold'
                )

            # Theme colors
            fig.patch.set_facecolor(colors["background"])
            ax.set_facecolor(colors["surface"])
            ax.tick_params(colors=colors["text"])
            ax.spines['bottom'].set_color(colors["grid"])
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color(colors["grid"])

            # Add value labels
            for bar, score in zip(bars, scores):
                width = bar.get_width()
                label_x = width + 0.02 if width >= 0 else width - 0.02
                ax.text(
                    label_x, bar.get_y() + bar.get_height()/2,
                    f'{score:.2f}',
                    ha='left' if width >= 0 else 'right',
                    va='center',
                    color=colors["text"],
                    fontsize=8
                )

            # Add legend
            bullish_patch = mpatches.Patch(color=colors["bullish"], label='Bullish')
            bearish_patch = mpatches.Patch(color=colors["bearish"], label='Bearish')
            neutral_patch = mpatches.Patch(color=colors["neutral"], label='Neutral')
            ax.legend(
                handles=[bullish_patch, neutral_patch, bearish_patch],
                loc='lower right',
                framealpha=0.8,
                facecolor=colors["surface"],
                edgecolor=colors["grid"],
                labelcolor=colors["text"]
            )

            plt.tight_layout()

            # Save image
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            output_path = self.output_dir / f"sentiment_{timestamp}.png"
            fig.savefig(
                output_path,
                dpi=self.config.dpi,
                bbox_inches='tight',
                facecolor=fig.get_facecolor()
            )
            plt.close(fig)

            logger.info(f"Sentiment chart generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate sentiment chart: {e}", exc_info=True)
            return None

    def generate_sentiment_timeseries(
        self,
        sentiment_series: Dict[str, List[float]],
        timestamps: List[str],
        title: Optional[str] = None
    ) -> Optional[Path]:
        """
        Generate a sentiment time series chart.

        Args:
            sentiment_series: Dict mapping tokens to list of sentiment scores over time
            timestamps: List of timestamp labels
            title: Optional chart title

        Returns:
            Path to generated PNG image, or None on failure
        """
        if not sentiment_series or not timestamps:
            logger.warning("No sentiment series data provided")
            return None

        if not HAS_MATPLOTLIB:
            logger.error("matplotlib not available")
            return None

        try:
            colors = self.config.get_colors()

            fig_width = self.config.width / self.config.dpi
            fig_height = self.config.height / self.config.dpi
            fig, ax = plt.subplots(figsize=(fig_width, fig_height))

            # Plot each token's sentiment over time
            color_cycle = [colors["bullish"], colors["accent"], colors["neutral"], colors["bearish"]]

            for idx, (token, scores) in enumerate(sentiment_series.items()):
                color = color_cycle[idx % len(color_cycle)]
                ax.plot(
                    range(len(scores)),
                    scores,
                    label=f"${token}",
                    color=color,
                    linewidth=2,
                    marker='o',
                    markersize=4
                )

            # Styling
            ax.set_xticks(range(len(timestamps)))
            ax.set_xticklabels(timestamps, rotation=45, ha='right')
            ax.set_ylim(-1.1, 1.1)
            ax.axhline(y=0, color=colors["text_secondary"], linewidth=0.5, linestyle='--')

            ax.set_xlabel("Time", color=colors["text"])
            ax.set_ylabel("Sentiment", color=colors["text"])

            if title:
                ax.set_title(title, color=colors["text"], fontweight='bold')
            else:
                ax.set_title("Sentiment Over Time", color=colors["text"], fontweight='bold')

            # Theme
            fig.patch.set_facecolor(colors["background"])
            ax.set_facecolor(colors["surface"])
            ax.tick_params(colors=colors["text"])
            ax.grid(True, alpha=0.3, color=colors["grid"])

            ax.legend(
                loc='upper left',
                framealpha=0.8,
                facecolor=colors["surface"],
                edgecolor=colors["grid"],
                labelcolor=colors["text"]
            )

            plt.tight_layout()

            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            output_path = self.output_dir / f"sentiment_ts_{timestamp}.png"
            fig.savefig(
                output_path,
                dpi=self.config.dpi,
                bbox_inches='tight',
                facecolor=fig.get_facecolor()
            )
            plt.close(fig)

            logger.info(f"Sentiment timeseries chart generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate sentiment timeseries: {e}", exc_info=True)
            return None

    def generate_candlestick_chart(
        self,
        ohlc_data: List[Dict[str, float]],
        symbol: str,
        timeframe: str = "1h",
        include_volume: bool = False
    ) -> Optional[Path]:
        """
        Generate a candlestick chart for price action.

        Args:
            ohlc_data: List of OHLC dicts with open, high, low, close, (volume)
            symbol: Token symbol
            timeframe: Chart timeframe (e.g., "1h", "4h", "1d")
            include_volume: Whether to include volume bars

        Returns:
            Path to generated PNG image, or None on failure
        """
        if not ohlc_data:
            logger.warning("No OHLC data provided")
            return None

        if not HAS_MATPLOTLIB:
            logger.error("matplotlib not available")
            return None

        try:
            colors = self.config.get_colors()

            fig_width = self.config.width / self.config.dpi
            fig_height = self.config.height / self.config.dpi

            if include_volume:
                fig, (ax, ax_vol) = plt.subplots(
                    2, 1,
                    figsize=(fig_width, fig_height),
                    gridspec_kw={'height_ratios': [3, 1]},
                    sharex=True
                )
            else:
                fig, ax = plt.subplots(figsize=(fig_width, fig_height))
                ax_vol = None

            # Draw candlesticks
            for i, candle in enumerate(ohlc_data):
                open_price = candle["open"]
                high_price = candle["high"]
                low_price = candle["low"]
                close_price = candle["close"]

                is_bullish = close_price >= open_price
                color = colors["bullish"] if is_bullish else colors["bearish"]

                # Wick
                ax.plot(
                    [i, i],
                    [low_price, high_price],
                    color=color,
                    linewidth=1
                )

                # Body
                body_bottom = min(open_price, close_price)
                body_height = abs(close_price - open_price)

                rect = mpatches.Rectangle(
                    (i - 0.3, body_bottom),
                    0.6,
                    body_height if body_height > 0 else 0.01,
                    facecolor=color,
                    edgecolor=color
                )
                ax.add_patch(rect)

                # Volume bars
                if include_volume and ax_vol and "volume" in candle:
                    ax_vol.bar(
                        i,
                        candle["volume"],
                        color=color,
                        alpha=0.7,
                        width=0.6
                    )

            # Styling
            ax.set_xlim(-0.5, len(ohlc_data) - 0.5)
            ax.set_ylabel("Price", color=colors["text"])
            ax.set_title(
                f"${symbol} - {timeframe}",
                color=colors["text"],
                fontweight='bold'
            )

            # Theme
            fig.patch.set_facecolor(colors["background"])
            ax.set_facecolor(colors["surface"])
            ax.tick_params(colors=colors["text"])
            ax.grid(True, alpha=0.3, color=colors["grid"])
            ax.spines['bottom'].set_color(colors["grid"])
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color(colors["grid"])

            if ax_vol:
                ax_vol.set_ylabel("Volume", color=colors["text"])
                ax_vol.set_facecolor(colors["surface"])
                ax_vol.tick_params(colors=colors["text"])
                ax_vol.grid(True, alpha=0.3, color=colors["grid"])

            plt.tight_layout()

            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            output_path = self.output_dir / f"candles_{symbol}_{timestamp}.png"
            fig.savefig(
                output_path,
                dpi=self.config.dpi,
                bbox_inches='tight',
                facecolor=fig.get_facecolor()
            )
            plt.close(fig)

            logger.info(f"Candlestick chart generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate candlestick chart: {e}", exc_info=True)
            return None

    def generate_portfolio_chart(
        self,
        portfolio: Dict[str, Dict[str, Any]],
        chart_type: str = "pie",
        show_pnl: bool = False
    ) -> Optional[Path]:
        """
        Generate a portfolio composition chart.

        Args:
            portfolio: Dict mapping tokens to {value_usd, percentage, pnl_percent}
            chart_type: "pie" or "donut"
            show_pnl: Whether to show PnL coloring

        Returns:
            Path to generated PNG image, or None on failure
        """
        if not portfolio:
            logger.warning("No portfolio data provided")
            return None

        if not HAS_MATPLOTLIB:
            logger.error("matplotlib not available")
            return None

        try:
            colors = self.config.get_colors()

            fig_width = self.config.width / self.config.dpi
            fig_height = self.config.height / self.config.dpi
            fig, ax = plt.subplots(figsize=(fig_width, fig_height))

            tokens = list(portfolio.keys())
            percentages = [portfolio[t].get("percentage", 0) for t in tokens]

            # Generate colors
            if show_pnl:
                chart_colors = []
                for token in tokens:
                    pnl = portfolio[token].get("pnl_percent", 0)
                    if pnl > 0:
                        chart_colors.append(colors["bullish"])
                    elif pnl < 0:
                        chart_colors.append(colors["bearish"])
                    else:
                        chart_colors.append(colors["neutral"])
            else:
                # Generate a color palette
                cmap = plt.cm.get_cmap('viridis')
                chart_colors = [cmap(i / len(tokens)) for i in range(len(tokens))]

            # Create pie/donut chart
            wedgeprops = {'width': 0.5} if chart_type == "donut" else {}

            wedges, texts, autotexts = ax.pie(
                percentages,
                labels=[f"${t}" for t in tokens],
                autopct='%1.1f%%',
                colors=chart_colors,
                wedgeprops=wedgeprops,
                textprops={'color': colors["text"]}
            )

            # Style autotexts
            for autotext in autotexts:
                autotext.set_color(colors["background"])
                autotext.set_fontweight('bold')

            ax.set_title(
                "Portfolio Composition",
                color=colors["text"],
                fontweight='bold'
            )

            # Add total value in center for donut chart
            if chart_type == "donut":
                total_value = sum(portfolio[t].get("value_usd", 0) for t in tokens)
                ax.text(
                    0, 0,
                    f"${total_value:,.0f}",
                    ha='center',
                    va='center',
                    fontsize=14,
                    fontweight='bold',
                    color=colors["text"]
                )

            fig.patch.set_facecolor(colors["background"])

            plt.tight_layout()

            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            output_path = self.output_dir / f"portfolio_{timestamp}.png"
            fig.savefig(
                output_path,
                dpi=self.config.dpi,
                bbox_inches='tight',
                facecolor=fig.get_facecolor()
            )
            plt.close(fig)

            logger.info(f"Portfolio chart generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate portfolio chart: {e}", exc_info=True)
            return None

    def add_branding(self, image_path: Path) -> Optional[Path]:
        """
        Add Jarvis branding overlay to an image.

        Args:
            image_path: Path to the source image

        Returns:
            Path to branded image, or None on failure
        """
        if not HAS_PIL:
            logger.warning("PIL not available for branding")
            return image_path  # Return original

        try:
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)

            # Add branding text in corner
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except (OSError, IOError):
                font = ImageFont.load_default()

            text = self.config.branding_text
            colors = self.config.get_colors()

            # Position in bottom right
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = img.width - text_width - 10
            y = img.height - text_height - 10

            # Draw text with shadow
            draw.text((x+1, y+1), text, fill="#000000", font=font)
            draw.text((x, y), text, fill=colors["text"], font=font)

            # Save branded image
            branded_path = image_path.with_stem(f"{image_path.stem}_branded")
            img.save(branded_path)

            logger.info(f"Branding added: {branded_path}")
            return branded_path

        except Exception as e:
            logger.error(f"Failed to add branding: {e}")
            return image_path

    def cleanup_old_images(self, keep_last: int = 10):
        """
        Clean up old generated images, keeping only the most recent.

        Args:
            keep_last: Number of recent images to keep per type
        """
        try:
            # Group by prefix
            prefixes = ["sentiment_", "candles_", "portfolio_", "sentiment_ts_"]

            for prefix in prefixes:
                images = sorted(
                    self.output_dir.glob(f"{prefix}*.png"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True
                )
                for img in images[keep_last:]:
                    img.unlink()
                    logger.debug(f"Deleted old image: {img}")

        except Exception as e:
            logger.error(f"Failed to cleanup old images: {e}")

    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported output formats.

        Returns:
            List of format extensions
        """
        formats = ["png", "jpg"]
        if HAS_PIL:
            formats.extend(["webp", "gif"])
        return formats
