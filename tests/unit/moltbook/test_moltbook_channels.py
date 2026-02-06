"""
Unit tests for Moltbook channel configurations.

Tests the channel subscription configurations for each bot:
- Jarvis: m/bugtracker, m/devops, m/security, m/crypto, m/kr8tiv
- Friday: m/marketing, m/trending, m/copywriting, m/brand, m/kr8tiv
- Matt: m/strategy, m/synthesis, m/growth, m/operations, m/kr8tiv
"""
import pytest
from unittest.mock import patch, MagicMock


class TestChannelConfigurations:
    """Tests for channel configuration loading."""

    def test_jarvis_channels_exist(self):
        """Jarvis should have correct channel configuration."""
        from core.moltbook.channels import get_bot_channels, JARVIS_CHANNELS

        channels = get_bot_channels("jarvis")

        assert "m/bugtracker" in [c["channel"] for c in channels]
        assert "m/devops" in [c["channel"] for c in channels]
        assert "m/security" in [c["channel"] for c in channels]
        assert "m/crypto" in [c["channel"] for c in channels]
        assert "m/kr8tiv" in [c["channel"] for c in channels]

    def test_friday_channels_exist(self):
        """Friday should have correct channel configuration."""
        from core.moltbook.channels import get_bot_channels, FRIDAY_CHANNELS

        channels = get_bot_channels("friday")

        assert "m/marketing" in [c["channel"] for c in channels]
        assert "m/trending" in [c["channel"] for c in channels]
        assert "m/copywriting" in [c["channel"] for c in channels]
        assert "m/brand" in [c["channel"] for c in channels]
        assert "m/kr8tiv" in [c["channel"] for c in channels]

    def test_matt_channels_exist(self):
        """Matt should have correct channel configuration."""
        from core.moltbook.channels import get_bot_channels, MATT_CHANNELS

        channels = get_bot_channels("matt")

        assert "m/strategy" in [c["channel"] for c in channels]
        assert "m/synthesis" in [c["channel"] for c in channels]
        assert "m/growth" in [c["channel"] for c in channels]
        assert "m/operations" in [c["channel"] for c in channels]
        assert "m/kr8tiv" in [c["channel"] for c in channels]


class TestChannelPriority:
    """Tests for channel priority configuration."""

    def test_jarvis_bugtracker_high_priority(self):
        """Jarvis bugtracker should be HIGH priority."""
        from core.moltbook.channels import get_bot_channels

        channels = get_bot_channels("jarvis")
        bugtracker = next(c for c in channels if c["channel"] == "m/bugtracker")

        assert bugtracker["priority"] == "HIGH"

    def test_jarvis_kr8tiv_high_priority(self):
        """Jarvis kr8tiv should be HIGH priority."""
        from core.moltbook.channels import get_bot_channels

        channels = get_bot_channels("jarvis")
        kr8tiv = next(c for c in channels if c["channel"] == "m/kr8tiv")

        assert kr8tiv["priority"] == "HIGH"

    def test_friday_trending_high_priority(self):
        """Friday trending should be HIGH priority."""
        from core.moltbook.channels import get_bot_channels

        channels = get_bot_channels("friday")
        trending = next(c for c in channels if c["channel"] == "m/trending")

        assert trending["priority"] == "HIGH"


class TestChannelReadFrequency:
    """Tests for channel read frequency configuration."""

    def test_jarvis_bugtracker_hourly(self):
        """Jarvis should read bugtracker every hour."""
        from core.moltbook.channels import get_bot_channels

        channels = get_bot_channels("jarvis")
        bugtracker = next(c for c in channels if c["channel"] == "m/bugtracker")

        assert bugtracker["read_frequency"] == "every_hour"

    def test_jarvis_kr8tiv_frequent(self):
        """Jarvis should read kr8tiv frequently."""
        from core.moltbook.channels import get_bot_channels

        channels = get_bot_channels("jarvis")
        kr8tiv = next(c for c in channels if c["channel"] == "m/kr8tiv")

        assert kr8tiv["read_frequency"] == "every_30_minutes"

    def test_friday_copywriting_daily(self):
        """Friday should read copywriting daily."""
        from core.moltbook.channels import get_bot_channels

        channels = get_bot_channels("friday")
        copywriting = next(c for c in channels if c["channel"] == "m/copywriting")

        assert copywriting["read_frequency"] == "daily"


class TestChannelContributeFlag:
    """Tests for channel contribution settings."""

    def test_jarvis_can_contribute_to_bugtracker(self):
        """Jarvis should be able to contribute to bugtracker."""
        from core.moltbook.channels import get_bot_channels

        channels = get_bot_channels("jarvis")
        bugtracker = next(c for c in channels if c["channel"] == "m/bugtracker")

        assert bugtracker["contribute"] is True

    def test_jarvis_security_read_only(self):
        """Jarvis security channel should be read-only."""
        from core.moltbook.channels import get_bot_channels

        channels = get_bot_channels("jarvis")
        security = next(c for c in channels if c["channel"] == "m/security")

        assert security["contribute"] is False

    def test_friday_trending_read_only(self):
        """Friday trending channel should be read-only (observe trends)."""
        from core.moltbook.channels import get_bot_channels

        channels = get_bot_channels("friday")
        trending = next(c for c in channels if c["channel"] == "m/trending")

        assert trending["contribute"] is False


class TestPostingRules:
    """Tests for posting rules configuration."""

    def test_jarvis_no_approval_required(self):
        """Jarvis should not require approval for technical posts."""
        from core.moltbook.channels import get_posting_rules

        rules = get_posting_rules("jarvis")

        assert rules["require_approval"] is False

    def test_friday_approval_required(self):
        """Friday should require Matt approval for public posts."""
        from core.moltbook.channels import get_posting_rules

        rules = get_posting_rules("friday")

        assert rules["require_approval"] is True

    def test_matt_no_approval_required(self):
        """Matt (COO) should not require approval."""
        from core.moltbook.channels import get_posting_rules

        rules = get_posting_rules("matt")

        assert rules["require_approval"] is False

    def test_max_posts_per_day(self):
        """Should enforce max posts per day limit."""
        from core.moltbook.channels import get_posting_rules

        jarvis_rules = get_posting_rules("jarvis")
        friday_rules = get_posting_rules("friday")
        matt_rules = get_posting_rules("matt")

        assert jarvis_rules["max_posts_per_day"] == 5
        assert friday_rules["max_posts_per_day"] == 3
        assert matt_rules["max_posts_per_day"] == 4

    def test_min_confidence_threshold(self):
        """Should have minimum confidence threshold."""
        from core.moltbook.channels import get_posting_rules

        jarvis_rules = get_posting_rules("jarvis")
        friday_rules = get_posting_rules("friday")

        assert jarvis_rules["min_confidence"] == 0.8
        assert friday_rules["min_confidence"] == 0.85  # Higher bar for marketing


class TestChannelValidation:
    """Tests for channel validation functions."""

    def test_validate_channel_name_valid(self):
        """Should validate correct channel names."""
        from core.moltbook.channels import validate_channel_name

        assert validate_channel_name("m/bugtracker") is True
        assert validate_channel_name("m/kr8tiv") is True
        assert validate_channel_name("m/devops") is True

    def test_validate_channel_name_invalid(self):
        """Should reject invalid channel names."""
        from core.moltbook.channels import validate_channel_name

        assert validate_channel_name("bugtracker") is False  # Missing m/
        assert validate_channel_name("m/") is False  # Empty name
        assert validate_channel_name("") is False  # Empty string
        assert validate_channel_name("m/invalid channel") is False  # Space in name

    def test_get_channels_for_frequency(self):
        """Should filter channels by read frequency."""
        from core.moltbook.channels import get_channels_by_frequency

        hourly = get_channels_by_frequency("jarvis", "every_hour")

        assert all(c["read_frequency"] == "every_hour" for c in hourly)
        assert len(hourly) > 0


class TestSharedChannel:
    """Tests for shared team channel (m/kr8tiv)."""

    def test_all_bots_subscribe_to_kr8tiv(self):
        """All bots should subscribe to m/kr8tiv."""
        from core.moltbook.channels import get_bot_channels

        for bot in ["jarvis", "friday", "matt"]:
            channels = get_bot_channels(bot)
            channel_names = [c["channel"] for c in channels]
            assert "m/kr8tiv" in channel_names

    def test_all_bots_can_contribute_to_kr8tiv(self):
        """All bots should be able to contribute to m/kr8tiv."""
        from core.moltbook.channels import get_bot_channels

        for bot in ["jarvis", "friday", "matt"]:
            channels = get_bot_channels(bot)
            kr8tiv = next(c for c in channels if c["channel"] == "m/kr8tiv")
            assert kr8tiv["contribute"] is True

    def test_kr8tiv_high_frequency(self):
        """m/kr8tiv should be read frequently by all bots."""
        from core.moltbook.channels import get_bot_channels

        for bot in ["jarvis", "friday", "matt"]:
            channels = get_bot_channels(bot)
            kr8tiv = next(c for c in channels if c["channel"] == "m/kr8tiv")
            assert kr8tiv["read_frequency"] == "every_30_minutes"
