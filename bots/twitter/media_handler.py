"""
Media Handler for Twitter Bot

Support: GIF, video, image attachments
Generate GIF: price animation for top token
Generate video: sentiment animation (30s)
Fallback: static image with overlays
Test: media upload to Twitter API
"""

import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

# Default output directory
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "twitter" / "media"

# Supported formats
SUPPORTED_FORMATS = ["gif", "png", "jpg", "jpeg", "mp4", "mov"]

# Try to import PIL/Pillow
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("PIL/Pillow not installed - image generation limited")

# Try to import matplotlib
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib not installed - chart generation disabled")

# Try to import numpy
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class MediaHandler:
    """
    Handles media generation and upload for Twitter.

    Usage:
        handler = MediaHandler()

        # Generate price GIF
        gif_path = handler.generate_price_gif(price_data)

        # Upload to Twitter
        media_id = await handler.upload_media(gif_path)

        # Post with media
        await twitter.post_tweet("text", media_ids=[media_id])
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        twitter_client: Optional[Any] = None
    ):
        """
        Initialize media handler.

        Args:
            output_dir: Directory for storing generated media
            twitter_client: Optional Twitter client for uploads
        """
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if twitter_client:
            self._twitter_client = twitter_client
        else:
            try:
                from bots.twitter.twitter_client import TwitterClient
                self._twitter_client = TwitterClient()
            except ImportError:
                self._twitter_client = None

    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported media formats.

        Returns:
            List of format extensions
        """
        return SUPPORTED_FORMATS.copy()

    def generate_price_gif(
        self,
        price_data: Dict[str, Any],
        duration_seconds: int = 3,
        fps: int = 10
    ) -> Optional[Path]:
        """
        Generate animated GIF showing price movement.

        Args:
            price_data: Dict with symbol, prices, timestamps
            duration_seconds: GIF duration
            fps: Frames per second

        Returns:
            Path to generated GIF or PNG fallback
        """
        symbol = price_data.get("symbol", "TOKEN")
        prices = price_data.get("prices", [])
        timestamps = price_data.get("timestamps", [])

        if not prices:
            logger.warning("No price data provided")
            return None

        # Fallback to static image if matplotlib not available
        if not HAS_MATPLOTLIB or not HAS_NUMPY:
            return self.generate_static_image({
                "symbol": symbol,
                "price": prices[-1] if prices else 0,
                "change": ((prices[-1] - prices[0]) / prices[0] * 100) if len(prices) > 1 else 0
            })

        try:
            fig, ax = plt.subplots(figsize=(8, 4))

            # Style
            fig.patch.set_facecolor('#1a1a2e')
            ax.set_facecolor('#16213e')

            # Determine color based on price direction
            start_price = prices[0]
            end_price = prices[-1]
            color = '#44FF44' if end_price >= start_price else '#FF4444'

            line, = ax.plot([], [], color=color, linewidth=2)

            # Set axis
            ax.set_xlim(0, len(prices) - 1)
            y_margin = (max(prices) - min(prices)) * 0.1 or 1
            ax.set_ylim(min(prices) - y_margin, max(prices) + y_margin)

            # Labels
            ax.set_xlabel('Time', color='white')
            ax.set_ylabel('Price ($)', color='white')
            ax.set_title(f'${symbol} Price Movement', color='white', fontsize=14)
            ax.tick_params(colors='white')

            # Animation function
            def animate(frame):
                x = list(range(frame + 1))
                y = prices[:frame + 1]
                line.set_data(x, y)
                return line,

            # Create animation
            frames = len(prices)
            interval = (duration_seconds * 1000) / frames

            anim = animation.FuncAnimation(
                fig, animate, frames=frames,
                interval=interval, blit=True
            )

            # Save GIF
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            output_path = self.output_dir / f"price_{symbol}_{timestamp}.gif"

            anim.save(str(output_path), writer='pillow', fps=fps)
            plt.close(fig)

            logger.info(f"Price GIF generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate price GIF: {e}", exc_info=True)
            # Fallback to static image
            return self.generate_static_image({
                "symbol": symbol,
                "price": prices[-1] if prices else 0,
                "change": ((prices[-1] - prices[0]) / prices[0] * 100) if len(prices) > 1 else 0
            })

    def generate_sentiment_animation(
        self,
        sentiment_data: Dict[str, Any],
        duration_seconds: int = 5
    ) -> Optional[Path]:
        """
        Generate animated visualization of sentiment over time.

        Args:
            sentiment_data: Dict with timestamps and sentiment values
            duration_seconds: Animation duration

        Returns:
            Path to generated animation or static image fallback
        """
        timestamps = sentiment_data.get("timestamps", [])
        sentiments = sentiment_data.get("sentiments", [])

        if not sentiments:
            logger.warning("No sentiment data provided")
            return None

        if not HAS_MATPLOTLIB or not HAS_NUMPY:
            return self.generate_static_image({
                "symbol": "SENTIMENT",
                "price": sentiments[-1] if sentiments else 0,
                "change": 0
            })

        try:
            fig, ax = plt.subplots(figsize=(10, 5))

            # Style
            fig.patch.set_facecolor('#1a1a2e')
            ax.set_facecolor('#16213e')

            # Create colormap for sentiment
            colors = ['#FF4444', '#FFAA00', '#44FF44']

            # Plot as filled area
            x = np.arange(len(sentiments))
            sentiments_np = np.array(sentiments)

            # Fill above 0 green, below 0 red
            ax.fill_between(x, sentiments_np, 0,
                           where=(sentiments_np >= 0),
                           color='#44FF44', alpha=0.5, label='Bullish')
            ax.fill_between(x, sentiments_np, 0,
                           where=(sentiments_np < 0),
                           color='#FF4444', alpha=0.5, label='Bearish')

            # Plot line
            ax.plot(x, sentiments_np, color='white', linewidth=2)

            # Zero line
            ax.axhline(y=0, color='#888888', linestyle='--', linewidth=1)

            # Labels
            ax.set_xlabel('Time Period', color='white')
            ax.set_ylabel('Sentiment Score', color='white')
            ax.set_title('Market Sentiment Over Time', color='white', fontsize=14)
            ax.tick_params(colors='white')
            ax.set_ylim(-1.1, 1.1)

            # Legend
            ax.legend(loc='upper right', facecolor='#16213e', edgecolor='white',
                     labelcolor='white')

            plt.tight_layout()

            # Save as static image (GIF animation is complex for this)
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            output_path = self.output_dir / f"sentiment_{timestamp}.png"

            fig.savefig(str(output_path), dpi=150, facecolor=fig.get_facecolor())
            plt.close(fig)

            logger.info(f"Sentiment visualization generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate sentiment animation: {e}", exc_info=True)
            return None

    def generate_static_image(
        self,
        data: Dict[str, Any],
        with_overlay: bool = True
    ) -> Optional[Path]:
        """
        Generate a static image with data overlay.

        Args:
            data: Dict with symbol, price, change
            with_overlay: Whether to add text overlay

        Returns:
            Path to generated image
        """
        symbol = data.get("symbol", "TOKEN")
        price = data.get("price", 0)
        change = data.get("change", 0)

        # Determine if we can use PIL
        if HAS_PIL:
            return self._generate_pil_image(symbol, price, change, with_overlay)
        elif HAS_MATPLOTLIB:
            return self._generate_matplotlib_image(symbol, price, change)
        else:
            logger.error("No image generation library available")
            return None

    def _generate_pil_image(
        self,
        symbol: str,
        price: float,
        change: float,
        with_overlay: bool
    ) -> Optional[Path]:
        """Generate image using PIL."""
        try:
            # Ensure numeric types
            try:
                price = float(price) if price is not None else 0.0
            except (ValueError, TypeError):
                price = 0.0
            try:
                change = float(change) if change is not None else 0.0
            except (ValueError, TypeError):
                change = 0.0

            # Create dark background image
            width, height = 800, 400
            bg_color = (26, 26, 46)  # #1a1a2e
            image = Image.new('RGB', (width, height), bg_color)

            if with_overlay:
                draw = ImageDraw.Draw(image)

                # Use default font (may vary by system)
                try:
                    font_large = ImageFont.truetype("arial.ttf", 48)
                    font_medium = ImageFont.truetype("arial.ttf", 32)
                except (OSError, IOError):
                    font_large = ImageFont.load_default()
                    font_medium = font_large

                # Colors
                text_color = (255, 255, 255)
                change_color = (68, 255, 68) if change >= 0 else (255, 68, 68)

                # Draw symbol
                draw.text((50, 50), f"${symbol}", fill=text_color, font=font_large)

                # Draw price
                price_text = f"${price:,.2f}" if price >= 1 else f"${price:.6f}"
                draw.text((50, 150), price_text, fill=text_color, font=font_large)

                # Draw change
                change_text = f"{'+' if change >= 0 else ''}{change:.2f}%"
                draw.text((50, 250), change_text, fill=change_color, font=font_medium)

                # Draw timestamp
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                draw.text((50, 350), timestamp, fill=(136, 136, 136), font=font_medium)

            # Save
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            output_path = self.output_dir / f"static_{symbol}_{timestamp}.png"
            image.save(str(output_path))

            logger.info(f"Static image generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate PIL image: {e}")
            return None

    def _generate_matplotlib_image(
        self,
        symbol: str,
        price: float,
        change: float
    ) -> Optional[Path]:
        """Generate image using matplotlib."""
        try:
            fig, ax = plt.subplots(figsize=(8, 4))

            # Style
            fig.patch.set_facecolor('#1a1a2e')
            ax.set_facecolor('#1a1a2e')
            ax.axis('off')

            # Colors
            change_color = '#44FF44' if change >= 0 else '#FF4444'

            # Text
            price_text = f"${price:,.2f}" if price >= 1 else f"${price:.6f}"
            change_text = f"{'+' if change >= 0 else ''}{change:.2f}%"

            ax.text(0.5, 0.75, f"${symbol}", color='white',
                   fontsize=36, ha='center', fontweight='bold',
                   transform=ax.transAxes)

            ax.text(0.5, 0.45, price_text, color='white',
                   fontsize=48, ha='center', fontweight='bold',
                   transform=ax.transAxes)

            ax.text(0.5, 0.15, change_text, color=change_color,
                   fontsize=32, ha='center', fontweight='bold',
                   transform=ax.transAxes)

            # Save
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            output_path = self.output_dir / f"static_{symbol}_{timestamp}.png"

            fig.savefig(str(output_path), dpi=150, facecolor=fig.get_facecolor(),
                       bbox_inches='tight', pad_inches=0.5)
            plt.close(fig)

            logger.info(f"Static image generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate matplotlib image: {e}")
            return None

    async def upload_media(
        self,
        file_path: Union[str, Path],
        alt_text: Optional[str] = None
    ) -> Optional[str]:
        """
        Upload media file to Twitter.

        Args:
            file_path: Path to media file
            alt_text: Accessibility text

        Returns:
            Media ID string or None
        """
        if not self._twitter_client:
            logger.error("No Twitter client available for upload")
            return None

        try:
            # Connect if needed
            if hasattr(self._twitter_client, 'connect') and not getattr(self._twitter_client, 'is_connected', False):
                self._twitter_client.connect()

            # Upload
            media_id = await self._twitter_client.upload_media(
                str(file_path),
                alt_text=alt_text
            )

            logger.info(f"Media uploaded: {media_id}")
            return media_id

        except Exception as e:
            logger.error(f"Failed to upload media: {e}")
            return None

    def cleanup_old_media(self, keep_last: int = 20):
        """
        Clean up old media files.

        Args:
            keep_last: Number of recent files to keep
        """
        try:
            # Get all media files sorted by modification time
            media_files = sorted(
                self.output_dir.glob("*.*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # Delete old files
            for f in media_files[keep_last:]:
                if f.suffix.lower().lstrip('.') in SUPPORTED_FORMATS:
                    f.unlink()
                    logger.debug(f"Deleted old media: {f}")

        except Exception as e:
            logger.error(f"Failed to cleanup media: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get media handler statistics.

        Returns:
            Dict with stats
        """
        media_files = list(self.output_dir.glob("*.*"))
        total_size = sum(f.stat().st_size for f in media_files if f.is_file())

        return {
            "output_dir": str(self.output_dir),
            "file_count": len(media_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "has_pil": HAS_PIL,
            "has_matplotlib": HAS_MATPLOTLIB,
            "supported_formats": SUPPORTED_FORMATS
        }
