"""
Social Module Configuration

Configuration settings for image generation, viral optimization, and trending tracking.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class ImageSettings:
    """Image generation settings."""

    # Dimensions
    default_width: int = 1080
    default_height: int = 720
    twitter_width: int = 1200  # Twitter optimal
    twitter_height: int = 675  # 16:9 aspect ratio
    dpi: int = 150

    # Theme
    theme: str = "dark"  # "dark" or "light"

    # Branding
    branding_text: str = "@Jarvis_lifeos"
    show_branding: bool = True
    branding_position: str = "bottom_right"

    # Colors (dark theme)
    dark_theme: Dict[str, str] = field(default_factory=lambda: {
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

    # Colors (light theme)
    light_theme: Dict[str, str] = field(default_factory=lambda: {
        "background": "#ffffff",
        "surface": "#f5f5f5",
        "text": "#1a1a1a",
        "text_secondary": "#666666",
        "bullish": "#00aa55",
        "bearish": "#cc3333",
        "neutral": "#ff9900",
        "grid": "#dddddd",
        "accent": "#5a1d99",
    })

    # Chart settings
    max_tokens_heatmap: int = 20
    max_tokens_chart: int = 10
    candlestick_body_width: float = 0.6

    # Cleanup
    keep_images: int = 50  # Number of images to keep


@dataclass
class ViralSettings:
    """Viral optimization settings."""

    # Hashtag limits
    max_hashtags: int = 5
    min_hashtags: int = 2

    # Core hashtags (always included in pool)
    core_hashtags: List[str] = field(default_factory=lambda: [
        "#crypto",
        "#defi",
        "#trading",
        "#nfa",
        "#dyor"
    ])

    # Posting schedule (UTC hours)
    peak_hours: List[int] = field(default_factory=lambda: [
        9, 10,      # EU market open
        13, 14, 15, 16,  # US market hours
        20, 21,     # Evening engagement
    ])

    # Best days (0=Monday, 6=Sunday)
    best_days: List[int] = field(default_factory=lambda: [1, 2, 3, 4])  # Tue-Fri

    # Hook settings
    hook_probability: float = 0.3  # 30% of tweets get hooks
    preferred_hook_type: str = "question"  # question, cta, curiosity

    # Scoring weights
    length_optimal_min: int = 100
    length_optimal_max: int = 200
    question_bonus: float = 10.0
    hashtag_bonus: float = 5.0


@dataclass
class TrendingSettings:
    """Trending tracking settings."""

    # Exchange monitoring
    monitored_exchanges: List[str] = field(default_factory=lambda: [
        "jupiter",
        "raydium",
        "orca"
    ])

    # Refresh intervals (seconds)
    trending_refresh_interval: int = 300  # 5 minutes
    mentions_refresh_interval: int = 900  # 15 minutes

    # Detection thresholds
    pump_threshold: float = 0.5  # 50% price increase
    dump_threshold: float = 0.3  # 30% price decrease
    volume_spike_multiplier: float = 3.0

    # Mention spike
    mention_spike_multiplier: float = 5.0
    mention_baseline_hours: int = 24

    # Cache settings
    cache_ttl_hours: int = 1
    max_cached_tokens: int = 100

    # Alerts
    enable_alerts: bool = True
    alert_cooldown_minutes: int = 30  # Min time between same alert


@dataclass
class SocialConfig:
    """Combined social module configuration."""

    # Data directories
    data_dir: Optional[Path] = None

    # Subconfigs
    images: ImageSettings = field(default_factory=ImageSettings)
    viral: ViralSettings = field(default_factory=ViralSettings)
    trending: TrendingSettings = field(default_factory=TrendingSettings)

    # Twitter settings
    twitter_max_chars: int = 280
    twitter_media_enabled: bool = True
    twitter_thread_max_tweets: int = 5

    def __post_init__(self):
        if self.data_dir is None:
            self.data_dir = Path(__file__).resolve().parents[2] / "data" / "social"


# Default configuration instance
default_config = SocialConfig()


def get_config() -> SocialConfig:
    """Get the social configuration."""
    return default_config


def load_config_from_env() -> SocialConfig:
    """
    Load configuration from environment variables.

    Environment variables:
    - SOCIAL_THEME: dark/light
    - SOCIAL_MAX_HASHTAGS: int
    - SOCIAL_PUMP_THRESHOLD: float
    - SOCIAL_MENTION_SPIKE: float
    """
    import os

    config = SocialConfig()

    # Theme
    theme = os.getenv("SOCIAL_THEME")
    if theme in ["dark", "light"]:
        config.images.theme = theme

    # Hashtags
    max_hashtags = os.getenv("SOCIAL_MAX_HASHTAGS")
    if max_hashtags:
        try:
            config.viral.max_hashtags = int(max_hashtags)
        except ValueError:
            pass

    # Pump threshold
    pump_threshold = os.getenv("SOCIAL_PUMP_THRESHOLD")
    if pump_threshold:
        try:
            config.trending.pump_threshold = float(pump_threshold)
        except ValueError:
            pass

    # Mention spike
    mention_spike = os.getenv("SOCIAL_MENTION_SPIKE")
    if mention_spike:
        try:
            config.trending.mention_spike_multiplier = float(mention_spike)
        except ValueError:
            pass

    return config
