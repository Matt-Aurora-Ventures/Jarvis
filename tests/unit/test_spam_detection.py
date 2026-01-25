"""
Unit tests for spam detection functionality.

Tests cover:
- 0.65 spam threshold
- Confidence tiers (0.8+ ban, 0.65-0.8 mute, <0.65 allow)
- Trusted user reduced sensitivity (0.3x multiplier)
- Scam wallet instant ban
- Flooding detection
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone


class TestSpamDetection:
    """Test spam detection and moderation in tg_bot.bot_core."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "test message"
        update.message.message_id = 12345
        update.effective_user = MagicMock()
        update.effective_user.id = 67890
        update.effective_user.username = "testuser"
        update.effective_chat = MagicMock()
        update.effective_chat.id = 99999
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock bot context."""
        context = MagicMock()
        context.bot = MagicMock()
        context.bot.delete_message = AsyncMock()
        context.bot.ban_chat_member = AsyncMock()
        context.bot.restrict_chat_member = AsyncMock()
        context.bot.send_message = AsyncMock()
        context.user_data = {}
        return context

    @pytest.fixture
    def mock_jarvis_admin(self):
        """Create mock JarvisAdmin."""
        admin = MagicMock()
        admin.record_message = MagicMock()
        admin.update_user = MagicMock()
        admin.track_engagement = MagicMock()
        admin.is_rate_limited = MagicMock(return_value=(False, 0))
        admin.check_scam_wallet = MagicMock(return_value=(False, None))
        admin.check_new_user_links = MagicMock(return_value=(False, None))
        admin.check_phishing_link = MagicMock(return_value=(False, None))
        admin.detect_command_attempt = MagicMock(return_value=(False, None))
        admin.detect_upgrade_opportunity = MagicMock(return_value=None)
        admin.get_random_response = MagicMock(return_value="Test response")
        admin.warn_user = MagicMock(return_value=1)
        admin.ban_user = MagicMock()
        admin.mute_user = MagicMock()
        admin.is_admin = MagicMock(return_value=False)
        return admin

    @pytest.mark.asyncio
    async def test_spam_threshold_at_065(self, mock_update, mock_context, mock_jarvis_admin):
        """Test that 0.65 confidence threshold triggers spam action."""
        mock_update.message.text = "buy crypto airdrop telegram"
        user_id = 67890

        # Set up admin to return spam with 0.67 confidence (above threshold)
        mock_jarvis_admin.analyze_spam.return_value = (True, 0.67, "keyword_spam")
        mock_jarvis_admin.get_user.return_value = MagicMock(warning_count=0)
        mock_jarvis_admin.get_user_reputation.return_value = {
            "is_trusted": False,
            "clean_messages": 0,
            "reputation_score": 0,
            "auto_trust_eligible": False
        }

        with patch('tg_bot.bot_core.get_jarvis_admin', return_value=mock_jarvis_admin):
            from tg_bot.bot_core import check_and_ban_spam
            is_spam = await check_and_ban_spam(mock_update, mock_context, mock_update.message.text, user_id)

        assert is_spam is True
        mock_context.bot.delete_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_below_spam_threshold_allows_message(self, mock_update, mock_context, mock_jarvis_admin):
        """Test that 0.60 confidence (below 0.65 threshold) allows message."""
        mock_update.message.text = "legitimate message"
        user_id = 67890

        # Set up admin to return not spam (0.60 < 0.65)
        mock_jarvis_admin.analyze_spam.return_value = (False, 0.60, "low_confidence")
        mock_jarvis_admin.get_user_reputation.return_value = {
            "is_trusted": False,
            "clean_messages": 5,
            "reputation_score": 50,
            "auto_trust_eligible": False
        }

        with patch('tg_bot.bot_core.get_jarvis_admin', return_value=mock_jarvis_admin):
            from tg_bot.bot_core import check_and_ban_spam
            is_spam = await check_and_ban_spam(mock_update, mock_context, mock_update.message.text, user_id)

        assert is_spam is False
        mock_context.bot.delete_message.assert_not_called()
        mock_context.bot.ban_chat_member.assert_not_called()

    @pytest.mark.asyncio
    async def test_high_confidence_triggers_ban(self, mock_update, mock_context, mock_jarvis_admin):
        """Test high confidence (>0.8) triggers auto-ban."""
        mock_update.message.text = "scam wallet address: 0x123456..."
        user_id = 67890

        # Set up admin to return high confidence spam (0.85 > 0.8)
        mock_jarvis_admin.analyze_spam.return_value = (True, 0.85, "scam_pattern")
        mock_jarvis_admin.get_user.return_value = MagicMock(warning_count=0)
        mock_jarvis_admin.get_user_reputation.return_value = {
            "is_trusted": False,
            "clean_messages": 0,
            "reputation_score": 0,
            "auto_trust_eligible": False
        }

        with patch('tg_bot.bot_core.get_jarvis_admin', return_value=mock_jarvis_admin):
            from tg_bot.bot_core import check_and_ban_spam
            is_spam = await check_and_ban_spam(mock_update, mock_context, mock_update.message.text, user_id)

        assert is_spam is True
        mock_context.bot.delete_message.assert_called_once()
        mock_context.bot.ban_chat_member.assert_called_once()

    @pytest.mark.asyncio
    async def test_medium_confidence_triggers_mute(self, mock_update, mock_context, mock_jarvis_admin):
        """Test medium confidence (0.65-0.8) triggers mute."""
        mock_update.message.text = "suspicious message"
        user_id = 67890

        # Set up admin to return medium confidence spam (0.70)
        mock_jarvis_admin.analyze_spam.return_value = (True, 0.70, "suspicious_pattern")
        mock_jarvis_admin.get_user.return_value = MagicMock(warning_count=0)
        mock_jarvis_admin.get_user_reputation.return_value = {
            "is_trusted": False,
            "clean_messages": 2,
            "reputation_score": 20,
            "auto_trust_eligible": False
        }

        with patch('tg_bot.bot_core.get_jarvis_admin', return_value=mock_jarvis_admin):
            from tg_bot.bot_core import check_and_ban_spam
            is_spam = await check_and_ban_spam(mock_update, mock_context, mock_update.message.text, user_id)

        assert is_spam is True
        mock_context.bot.delete_message.assert_called_once()
        # Medium confidence should mute, not ban
        mock_context.bot.restrict_chat_member.assert_called_once()

    @pytest.mark.asyncio
    async def test_scam_wallet_instant_ban(self, mock_update, mock_context, mock_jarvis_admin):
        """Test scam wallet address triggers instant ban."""
        mock_update.message.text = "send funds to: 0xSCAMWALLET123"
        user_id = 67890

        # Set up admin to detect scam wallet
        mock_jarvis_admin.check_scam_wallet.return_value = (True, "0xSCAMWALLET123")
        mock_jarvis_admin.get_user_reputation.return_value = {
            "is_trusted": False,
            "clean_messages": 0,
            "reputation_score": 0,
            "auto_trust_eligible": False
        }

        with patch('tg_bot.bot_core.get_jarvis_admin', return_value=mock_jarvis_admin):
            from tg_bot.bot_core import check_and_ban_spam
            is_spam = await check_and_ban_spam(mock_update, mock_context, mock_update.message.text, user_id)

        assert is_spam is True
        mock_context.bot.delete_message.assert_called_once()
        mock_context.bot.ban_chat_member.assert_called_once()
        mock_jarvis_admin.ban_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_phishing_link_instant_ban(self, mock_update, mock_context, mock_jarvis_admin):
        """Test phishing link triggers instant ban."""
        mock_update.message.text = "check out this link: phishing-site.com/wallet"
        user_id = 67890

        # Set up admin to detect phishing link
        mock_jarvis_admin.check_phishing_link.return_value = (True, "phishing-site.com")
        mock_jarvis_admin.get_user_reputation.return_value = {
            "is_trusted": False,
            "clean_messages": 0,
            "reputation_score": 0,
            "auto_trust_eligible": False
        }

        with patch('tg_bot.bot_core.get_jarvis_admin', return_value=mock_jarvis_admin):
            from tg_bot.bot_core import check_and_ban_spam
            is_spam = await check_and_ban_spam(mock_update, mock_context, mock_update.message.text, user_id)

        assert is_spam is True
        mock_context.bot.ban_chat_member.assert_called_once()

    @pytest.mark.asyncio
    async def test_flooding_auto_mute(self, mock_update, mock_context, mock_jarvis_admin):
        """Test flooding (15+ msgs) triggers auto-mute."""
        mock_update.message.text = "spam spam spam"
        user_id = 67890

        # Set up admin to detect rate limiting (flooding)
        mock_jarvis_admin.is_rate_limited.return_value = (True, 16)  # 16 messages in 60s
        mock_jarvis_admin.get_user_reputation.return_value = {
            "is_trusted": False,
            "clean_messages": 0,
            "reputation_score": 0,
            "auto_trust_eligible": False
        }

        with patch('tg_bot.bot_core.get_jarvis_admin', return_value=mock_jarvis_admin):
            from tg_bot.bot_core import check_and_ban_spam
            is_spam = await check_and_ban_spam(mock_update, mock_context, mock_update.message.text, user_id)

        assert is_spam is True
        mock_context.bot.restrict_chat_member.assert_called_once()
        mock_jarvis_admin.mute_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_repeat_offender_banned_on_third_warning(self, mock_update, mock_context, mock_jarvis_admin):
        """Test users with 3+ warnings get banned instead of warned."""
        mock_update.message.text = "borderline message"
        user_id = 67890

        # Set up admin to return medium spam with user having 3 warnings
        mock_jarvis_admin.analyze_spam.return_value = (True, 0.70, "repeat_pattern")
        mock_jarvis_admin.get_user.return_value = MagicMock(warning_count=3)
        mock_jarvis_admin.get_user_reputation.return_value = {
            "is_trusted": False,
            "clean_messages": 0,
            "reputation_score": -40,
            "auto_trust_eligible": False
        }

        with patch('tg_bot.bot_core.get_jarvis_admin', return_value=mock_jarvis_admin):
            from tg_bot.bot_core import check_and_ban_spam
            is_spam = await check_and_ban_spam(mock_update, mock_context, mock_update.message.text, user_id)

        assert is_spam is True
        # 3 warnings = should ban, not just mute
        mock_context.bot.ban_chat_member.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_user_link_restriction(self, mock_update, mock_context, mock_jarvis_admin):
        """Test new users can't post links."""
        mock_update.message.text = "check out https://somesite.com"
        user_id = 67890

        # Set up admin to detect new user link
        mock_jarvis_admin.check_new_user_links.return_value = (True, "new_user_link")
        mock_jarvis_admin.get_user_reputation.return_value = {
            "is_trusted": False,
            "clean_messages": 1,
            "reputation_score": 10,
            "auto_trust_eligible": False
        }

        with patch('tg_bot.bot_core.get_jarvis_admin', return_value=mock_jarvis_admin):
            from tg_bot.bot_core import check_and_ban_spam
            is_spam = await check_and_ban_spam(mock_update, mock_context, mock_update.message.text, user_id)

        assert is_spam is True
        mock_context.bot.delete_message.assert_called_once()
        # Should not ban, just delete
        mock_context.bot.ban_chat_member.assert_not_called()


class TestSpamPatternFallback:
    """Test fallback spam pattern matching when JarvisAdmin fails."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "test message"
        update.message.message_id = 12345
        update.effective_user = MagicMock()
        update.effective_user.id = 67890
        update.effective_user.username = "testuser"
        update.effective_chat = MagicMock()
        update.effective_chat.id = 99999
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock bot context."""
        context = MagicMock()
        context.bot = MagicMock()
        context.bot.delete_message = AsyncMock()
        context.bot.ban_chat_member = AsyncMock()
        context.bot.send_message = AsyncMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_fallback_pattern_matching(self, mock_update, mock_context):
        """Test fallback pattern matching when admin fails."""
        # Message with multiple spam patterns
        mock_update.message.text = "buy crypto airdrop free money"
        user_id = 67890

        # Make admin raise exception to trigger fallback
        with patch('tg_bot.bot_core.get_jarvis_admin', side_effect=Exception("Admin unavailable")):
            from tg_bot.bot_core import check_and_ban_spam
            is_spam = await check_and_ban_spam(mock_update, mock_context, mock_update.message.text, user_id)

        # Should detect spam via fallback patterns
        assert is_spam is True

    @pytest.mark.asyncio
    async def test_fallback_allows_clean_message(self, mock_update, mock_context):
        """Test fallback allows clean messages."""
        mock_update.message.text = "Hello, how are you today?"
        user_id = 67890

        with patch('tg_bot.bot_core.get_jarvis_admin', side_effect=Exception("Admin unavailable")):
            from tg_bot.bot_core import check_and_ban_spam
            is_spam = await check_and_ban_spam(mock_update, mock_context, mock_update.message.text, user_id)

        assert is_spam is False
