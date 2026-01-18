"""
Sentiment Heatmap Generator

Creates matplotlib-based heatmap images showing token sentiment over time.
- X-axis: tokens (top 20 by volume)
- Y-axis: time (6h rolling window)
- Color intensity: sentiment score (red=bearish, green=bullish)
"""

import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Default output directory
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "twitter" / "heatmaps"

# Try to import matplotlib
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend for server use
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib not installed - heatmap generation disabled")


class HeatmapGenerator:
    """
    Generates sentiment heatmaps for Twitter posts.

    Usage:
        generator = HeatmapGenerator(output_dir=Path("./output"))
        sentiment_data = {"SOL": [0.8, 0.7, 0.6], "BTC": [0.5, 0.5, 0.6]}
        image_path = generator.generate_heatmap(sentiment_data)
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        max_tokens: int = 20,
        grok_client: Optional[Any] = None
    ):
        """
        Initialize heatmap generator.

        Args:
            output_dir: Directory to save generated images
            max_tokens: Maximum number of tokens to display (default 20)
            grok_client: Optional Grok client for caption generation
        """
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_tokens = max_tokens

        # Initialize Grok client for captions
        if grok_client:
            self._grok_client = grok_client
        else:
            try:
                from bots.twitter.grok_client import GrokClient
                self._grok_client = GrokClient()
            except ImportError:
                self._grok_client = None
                logger.warning("GrokClient not available for caption generation")

    def generate_heatmap(
        self,
        sentiment_data: Dict[str, List[float]],
        timestamps: Optional[List[str]] = None,
        title: Optional[str] = None
    ) -> Optional[Path]:
        """
        Generate a sentiment heatmap image.

        Args:
            sentiment_data: Dict mapping token symbols to list of sentiment scores
                           Sentiment scores should be in range [-1, 1] where:
                           -1 = max bearish, 0 = neutral, 1 = max bullish
            timestamps: Optional list of timestamp labels for Y-axis
            title: Optional custom title for the heatmap

        Returns:
            Path to generated PNG image, or None on failure
        """
        if not sentiment_data:
            logger.warning("No sentiment data provided for heatmap")
            return None

        if not HAS_MATPLOTLIB:
            logger.error("matplotlib not available - cannot generate heatmap")
            return None

        try:
            # Get tokens and limit to max_tokens
            tokens = list(sentiment_data.keys())[:self.max_tokens]

            # Get the number of time periods (assume all tokens have same length)
            time_periods = len(next(iter(sentiment_data.values())))

            # Create data matrix
            data = np.zeros((time_periods, len(tokens)))
            for i, token in enumerate(tokens):
                values = sentiment_data[token][:time_periods]
                for j, value in enumerate(values):
                    data[j, i] = value

            # Create figure
            fig, ax = plt.subplots(figsize=(12, 6))

            # Custom colormap: red (bearish) -> yellow (neutral) -> green (bullish)
            colors = ['#FF4444', '#FFAA00', '#44FF44']
            cmap = mcolors.LinearSegmentedColormap.from_list('sentiment', colors)

            # Create heatmap
            im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=-1, vmax=1)

            # Set labels
            ax.set_xticks(np.arange(len(tokens)))
            ax.set_xticklabels([f"${t}" for t in tokens], rotation=45, ha='right', fontsize=8)

            # Y-axis labels (timestamps)
            if timestamps:
                ax.set_yticks(np.arange(len(timestamps)))
                ax.set_yticklabels(timestamps, fontsize=8)
            else:
                # Default to generic time labels
                ax.set_yticks(np.arange(time_periods))
                ax.set_yticklabels([f"{i}h ago" for i in range(time_periods-1, -1, -1)], fontsize=8)

            # Title
            if title:
                ax.set_title(title, fontsize=12, fontweight='bold')
            else:
                ax.set_title(
                    f"Jarvis Sentiment Heatmap - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                    fontsize=12,
                    fontweight='bold'
                )

            # Add colorbar (legend)
            cbar = plt.colorbar(im, ax=ax, shrink=0.8)
            cbar.set_label('Sentiment (Bearish <-> Bullish)', fontsize=10)
            cbar.set_ticks([-1, -0.5, 0, 0.5, 1])
            cbar.set_ticklabels(['Very Bearish', 'Bearish', 'Neutral', 'Bullish', 'Very Bullish'])

            # Style
            ax.set_xlabel('Tokens', fontsize=10)
            ax.set_ylabel('Time', fontsize=10)

            # Dark theme
            fig.patch.set_facecolor('#1a1a2e')
            ax.set_facecolor('#16213e')
            ax.tick_params(colors='white')
            ax.xaxis.label.set_color('white')
            ax.yaxis.label.set_color('white')
            ax.title.set_color('white')
            cbar.ax.yaxis.set_tick_params(color='white')
            cbar.ax.yaxis.label.set_color('white')
            plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')

            # Add grid
            ax.set_xticks(np.arange(len(tokens) + 1) - 0.5, minor=True)
            ax.set_yticks(np.arange(time_periods + 1) - 0.5, minor=True)
            ax.grid(which='minor', color='#0f3460', linestyle='-', linewidth=0.5)

            # Adjust layout
            plt.tight_layout()

            # Save image
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            output_path = self.output_dir / f"heatmap_{timestamp}.png"
            fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
            plt.close(fig)

            logger.info(f"Heatmap generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate heatmap: {e}", exc_info=True)
            return None

    async def generate_caption(
        self,
        sentiment_data: Dict[str, List[float]],
        max_chars: int = 280
    ) -> Optional[str]:
        """
        Generate a tweet caption for the heatmap using Grok.

        Args:
            sentiment_data: The sentiment data used to generate the heatmap
            max_chars: Maximum characters for the caption (default 280)

        Returns:
            Generated caption string, or None on failure
        """
        if not self._grok_client:
            logger.warning("Grok client not available for caption generation")
            return None

        try:
            # Analyze sentiment data for caption context
            bullish_tokens = []
            bearish_tokens = []

            for token, scores in sentiment_data.items():
                avg_score = sum(scores) / len(scores) if scores else 0
                if avg_score > 0.3:
                    bullish_tokens.append((token, avg_score))
                elif avg_score < -0.3:
                    bearish_tokens.append((token, avg_score))

            # Sort by absolute sentiment strength
            bullish_tokens.sort(key=lambda x: x[1], reverse=True)
            bearish_tokens.sort(key=lambda x: x[1])

            # Build context
            context = f"""Sentiment heatmap showing {len(sentiment_data)} tokens.
Top bullish: {', '.join([f"${t[0]}" for t in bullish_tokens[:3]]) or 'none'}
Top bearish: {', '.join([f"${t[0]}" for t in bearish_tokens[:3]]) or 'none'}"""

            prompt = f"""Generate a short tweet caption (max {max_chars} chars) for this sentiment heatmap.

{context}

Rules:
- Casual lowercase voice
- Mention the standout tokens
- Include NFA naturally
- Make it engaging for crypto twitter
- No hashtags needed (will be added separately)

Return ONLY the caption text."""

            response = await self._grok_client.generate_tweet(
                prompt,
                max_tokens=100,
                temperature=0.8
            )

            if response.success:
                caption = response.content.strip()
                # Ensure under max_chars
                if len(caption) > max_chars:
                    caption = caption[:max_chars - 3] + "..."
                return caption

            logger.warning(f"Grok caption generation failed: {response.error}")
            return None

        except Exception as e:
            logger.error(f"Failed to generate caption: {e}")
            return None

    def cleanup_old_images(self, keep_last: int = 10):
        """
        Clean up old heatmap images, keeping only the most recent.

        Args:
            keep_last: Number of recent images to keep
        """
        try:
            images = sorted(self.output_dir.glob("heatmap_*.png"), reverse=True)
            for img in images[keep_last:]:
                img.unlink()
                logger.debug(f"Deleted old heatmap: {img}")
        except Exception as e:
            logger.error(f"Failed to cleanup old images: {e}")
