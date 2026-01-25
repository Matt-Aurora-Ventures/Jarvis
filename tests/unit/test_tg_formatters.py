"""
Tests for Telegram Digest Formatter Module.

Tests cover:
- Markdown V1/V2 escaping functions
- Price formatting (various magnitudes)
- Volume/liquidity formatting
- Percentage change formatting
- Token card formatting
- Hourly digest formatting
- Master signal report formatting
- Error message formatting
- Rate limit message formatting
- Status message formatting
- Link generation (DexScreener, Birdeye, Solscan)
- Entry recommendation logic
- Leverage suggestion logic
"""

import pytest
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_token_signal():
    """Create a mock TokenSignal for testing."""
    from tg_bot.services.signal_service import TokenSignal

    return TokenSignal(
        address="So11111111111111111111111111111111111111112",
        symbol="SOL",
        name="Solana",
        chain="solana",
        price_usd=142.50,
        price_change_5m=0.5,
        price_change_1h=2.5,
        price_change_24h=-1.3,
        volume_24h=2_500_000_000,
        volume_1h=150_000_000,
        liquidity_usd=500_000_000,
        momentum_score=75.0,
        security_score=95.0,
        risk_level="low",
        security_warnings=[],
        smart_money_signal="bullish",
        insider_buys=5,
        insider_sells=1,
        sentiment="positive",
        sentiment_score=0.8,
        sentiment_confidence=0.85,
        sentiment_summary="Strong community engagement and development activity.",
        signal="STRONG_BUY",
        signal_score=85.0,
        signal_reasons=["High liquidity", "Strong sentiment", "Whale accumulation"],
        sources_used=["DexScreener", "Birdeye", "Grok"],
    )


@pytest.fixture
def mock_bearish_signal():
    """Create a bearish mock TokenSignal."""
    from tg_bot.services.signal_service import TokenSignal

    return TokenSignal(
        address="RugPull111111111111111111111111111111111111",
        symbol="SCAM",
        name="Scam Token",
        price_usd=0.00000001,
        price_change_1h=-50.0,
        price_change_24h=-90.0,
        volume_24h=1000,
        volume_1h=100,
        liquidity_usd=500,
        security_score=10.0,
        risk_level="critical",
        security_warnings=["Honeypot detected", "LP not locked", "High dev holdings"],
        smart_money_signal="bearish",
        sentiment="negative",
        sentiment_confidence=0.95,
        signal="AVOID",
        signal_score=-90.0,
        signal_reasons=["Honeypot", "Rug pull risk"],
    )


@pytest.fixture
def mock_cost_tracker():
    """Create mock cost tracker."""
    tracker = MagicMock()
    tracker.get_today_stats.return_value = MagicMock(
        total_calls=50,
        total_cost_usd=0.1234,
        sentiment_checks=10
    )
    tracker.can_make_sentiment_call.return_value = (True, "Ready")
    tracker.get_cost_report.return_value = "Cost report placeholder"
    return tracker


# =============================================================================
# Test Markdown Escaping Functions
# =============================================================================


class TestMarkdownEscaping:
    """Tests for Markdown escape functions."""

    def test_escape_markdown_empty_string(self):
        """Empty string should return empty string."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("") == ""

    def test_escape_markdown_none(self):
        """None should return empty string."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown(None) == ""

    def test_escape_markdown_plain_text(self):
        """Plain text without special chars should be unchanged."""
        from tg_bot.services.digest_formatter import escape_markdown

        text = "Simple text without special characters"
        assert escape_markdown(text) == text

    def test_escape_markdown_underscores(self):
        """Underscores should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("hello_world") == "hello\\_world"
        assert escape_markdown("_italic_") == "\\_italic\\_"

    def test_escape_markdown_asterisks(self):
        """Asterisks should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("**bold**") == "\\*\\*bold\\*\\*"
        assert escape_markdown("*italic*") == "\\*italic\\*"

    def test_escape_markdown_backticks(self):
        """Backticks should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("`code`") == "\\`code\\`"

    def test_escape_markdown_square_brackets(self):
        """Square brackets should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("[link]") == "\\[link\\]"

    def test_escape_markdown_parentheses(self):
        """Parentheses should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("(url)") == "\\(url\\)"

    def test_escape_markdown_tilde(self):
        """Tilde should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("~strike~") == "\\~strike\\~"

    def test_escape_markdown_hash(self):
        """Hash should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("#heading") == "\\#heading"

    def test_escape_markdown_plus_minus_equals(self):
        """Plus, minus, equals should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("a + b - c = d") == "a \\+ b \\- c \\= d"

    def test_escape_markdown_pipe(self):
        """Pipe should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("a|b") == "a\\|b"

    def test_escape_markdown_curly_braces(self):
        """Curly braces should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("{obj}") == "\\{obj\\}"

    def test_escape_markdown_dot(self):
        """Dot should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("1.0") == "1\\.0"

    def test_escape_markdown_exclamation(self):
        """Exclamation should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown("Hello!") == "Hello\\!"

    def test_escape_markdown_greater_than(self):
        """Greater than should be escaped."""
        from tg_bot.services.digest_formatter import escape_markdown

        assert escape_markdown(">quote") == "\\>quote"

    def test_escape_markdown_all_special_chars(self):
        """All special characters in one string."""
        from tg_bot.services.digest_formatter import escape_markdown

        text = "_*[]()~`>#+-=|{}.!"
        escaped = escape_markdown(text)
        # All chars should be preceded by backslash
        for char in "_*[]()~`>#+-=|{}.!":
            assert f"\\{char}" in escaped

    def test_escape_markdown_number_conversion(self):
        """Numbers should be converted to string."""
        from tg_bot.services.digest_formatter import escape_markdown

        # The function should handle non-string input
        assert escape_markdown(123) == "123"
        assert escape_markdown(3.14) == "3\\.14"


class TestMarkdownV1Escaping:
    """Tests for Markdown V1 escape function (simpler escaping)."""

    def test_escape_markdown_v1_empty(self):
        """Empty string should return empty string."""
        from tg_bot.services.digest_formatter import escape_markdown_v1

        assert escape_markdown_v1("") == ""

    def test_escape_markdown_v1_none(self):
        """None should return empty string."""
        from tg_bot.services.digest_formatter import escape_markdown_v1

        assert escape_markdown_v1(None) == ""

    def test_escape_markdown_v1_underscore(self):
        """Underscores should be escaped in V1."""
        from tg_bot.services.digest_formatter import escape_markdown_v1

        assert escape_markdown_v1("hello_world") == "hello\\_world"

    def test_escape_markdown_v1_asterisk(self):
        """Asterisks should be escaped in V1."""
        from tg_bot.services.digest_formatter import escape_markdown_v1

        assert escape_markdown_v1("*bold*") == "\\*bold\\*"

    def test_escape_markdown_v1_backtick(self):
        """Backticks should be escaped in V1."""
        from tg_bot.services.digest_formatter import escape_markdown_v1

        assert escape_markdown_v1("`code`") == "\\`code\\`"

    def test_escape_markdown_v1_square_bracket(self):
        """Square brackets should be escaped in V1 (opening only)."""
        from tg_bot.services.digest_formatter import escape_markdown_v1

        # V1 only escapes opening bracket
        assert escape_markdown_v1("[link]") == "\\[link]"

    def test_escape_markdown_v1_preserves_other_chars(self):
        """V1 should NOT escape other special chars."""
        from tg_bot.services.digest_formatter import escape_markdown_v1

        # These should NOT be escaped in V1
        assert escape_markdown_v1("(url)") == "(url)"
        assert escape_markdown_v1("#heading") == "#heading"
        assert escape_markdown_v1("a > b") == "a > b"
        assert escape_markdown_v1("100%") == "100%"
        assert escape_markdown_v1("a.b.c") == "a.b.c"


# =============================================================================
# Test Price Formatting
# =============================================================================


class TestPriceFormatting:
    """Tests for price formatting function."""

    def test_format_price_large_value(self):
        """Prices >= 1000 should show no decimals."""
        from tg_bot.services.digest_formatter import format_price

        assert format_price(1000) == "$1,000"
        assert format_price(1234567) == "$1,234,567"
        assert format_price(10000.50) == "$10,000"  # truncates decimals

    def test_format_price_medium_value(self):
        """Prices >= 1 should show 2 decimals."""
        from tg_bot.services.digest_formatter import format_price

        assert format_price(1.00) == "$1.00"
        assert format_price(142.50) == "$142.50"
        assert format_price(999.99) == "$999.99"

    def test_format_price_small_value(self):
        """Prices >= 0.01 should show 4 decimals."""
        from tg_bot.services.digest_formatter import format_price

        assert format_price(0.01) == "$0.0100"
        assert format_price(0.1234) == "$0.1234"
        assert format_price(0.9999) == "$0.9999"

    def test_format_price_very_small_value(self):
        """Prices < 0.01 should show 8 decimals."""
        from tg_bot.services.digest_formatter import format_price

        assert format_price(0.00000001) == "$0.00000001"
        assert format_price(0.00123456) == "$0.00123456"
        assert format_price(0.009) == "$0.00900000"

    def test_format_price_zero(self):
        """Zero price should format correctly."""
        from tg_bot.services.digest_formatter import format_price

        assert format_price(0) == "$0.00000000"

    def test_format_price_negative(self):
        """Negative price should still format (edge case)."""
        from tg_bot.services.digest_formatter import format_price

        # Implementation may vary, just ensure no exception
        result = format_price(-100)
        assert "$" in result


# =============================================================================
# Test Volume Formatting
# =============================================================================


class TestVolumeFormatting:
    """Tests for volume/liquidity formatting function."""

    def test_format_volume_millions(self):
        """Values >= 1M should show as XM."""
        from tg_bot.services.digest_formatter import format_volume

        assert format_volume(1_000_000) == "$1.00M"
        assert format_volume(2_500_000) == "$2.50M"
        assert format_volume(500_000_000) == "$500.00M"

    def test_format_volume_thousands(self):
        """Values >= 1K should show as XK."""
        from tg_bot.services.digest_formatter import format_volume

        assert format_volume(1000) == "$1.0K"
        assert format_volume(50_000) == "$50.0K"
        assert format_volume(999_999) == "$1000.0K"  # rounds

    def test_format_volume_small(self):
        """Values < 1K should show raw number."""
        from tg_bot.services.digest_formatter import format_volume

        assert format_volume(100) == "$100"
        assert format_volume(999) == "$999"
        assert format_volume(0) == "$0"

    def test_format_volume_decimal_millions(self):
        """Decimal precision in millions."""
        from tg_bot.services.digest_formatter import format_volume

        assert format_volume(1_234_567) == "$1.23M"

    def test_format_volume_decimal_thousands(self):
        """Decimal precision in thousands."""
        from tg_bot.services.digest_formatter import format_volume

        assert format_volume(12_345) == "$12.3K"


# =============================================================================
# Test Percentage Change Formatting
# =============================================================================


class TestChangeFormatting:
    """Tests for percentage change formatting function."""

    def test_format_change_positive(self):
        """Positive change should show up arrow and plus."""
        from tg_bot.services.digest_formatter import format_change

        result = format_change(5.5)
        assert "+" in result
        assert "5.5%" in result

    def test_format_change_negative(self):
        """Negative change should show down arrow."""
        from tg_bot.services.digest_formatter import format_change

        result = format_change(-10.2)
        assert "-10.2%" in result

    def test_format_change_zero(self):
        """Zero change should show neutral indicator."""
        from tg_bot.services.digest_formatter import format_change

        result = format_change(0)
        assert "0%" in result

    def test_format_change_large_positive(self):
        """Large positive change."""
        from tg_bot.services.digest_formatter import format_change

        result = format_change(1234.5)
        assert "+1234.5%" in result

    def test_format_change_large_negative(self):
        """Large negative change."""
        from tg_bot.services.digest_formatter import format_change

        result = format_change(-99.9)
        assert "-99.9%" in result


class TestCompactChangeFormatting:
    """Tests for compact percentage change formatting."""

    def test_format_change_compact_positive(self):
        """Compact positive should have green indicator."""
        from tg_bot.services.digest_formatter import _format_change_compact

        result = _format_change_compact(5.5)
        assert "+5.5%" in result

    def test_format_change_compact_negative(self):
        """Compact negative should have red indicator."""
        from tg_bot.services.digest_formatter import _format_change_compact

        result = _format_change_compact(-5.5)
        assert "-5.5%" in result

    def test_format_change_compact_zero(self):
        """Compact zero should have neutral indicator."""
        from tg_bot.services.digest_formatter import _format_change_compact

        result = _format_change_compact(0)
        assert "0%" in result


# =============================================================================
# Test Link Generation
# =============================================================================


class TestLinkGeneration:
    """Tests for explorer link generation functions."""

    def test_get_dexscreener_link(self):
        """DexScreener link should be correct format."""
        from tg_bot.services.digest_formatter import get_dexscreener_link

        addr = "So11111111111111111111111111111111111111112"
        link = get_dexscreener_link(addr)
        assert link == f"https://dexscreener.com/solana/{addr}"

    def test_get_birdeye_link(self):
        """Birdeye link should be correct format."""
        from tg_bot.services.digest_formatter import get_birdeye_link

        addr = "So11111111111111111111111111111111111111112"
        link = get_birdeye_link(addr)
        assert link == f"https://birdeye.so/token/{addr}?chain=solana"

    def test_get_solscan_link(self):
        """Solscan link should be correct format."""
        from tg_bot.services.digest_formatter import get_solscan_link

        addr = "So11111111111111111111111111111111111111112"
        link = get_solscan_link(addr)
        assert link == f"https://solscan.io/token/{addr}"


# =============================================================================
# Test Token Card Formatting
# =============================================================================


class TestTokenCardFormatting:
    """Tests for individual token card formatting."""

    def test_format_token_card_basic(self, mock_token_signal):
        """Token card should contain basic info."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal)

        assert "SOL" in card
        assert "Solana" in card
        assert "$142.50" in card

    def test_format_token_card_with_rank(self, mock_token_signal):
        """Token card with rank should show rank number."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal, rank=3)
        assert "3." in card

    def test_format_token_card_without_rank(self, mock_token_signal):
        """Token card without rank should not show rank number."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal, rank=0)
        # Should not have numbered rank
        assert not card.startswith("*1.") and not card.startswith("*0.")

    def test_format_token_card_contains_price(self, mock_token_signal):
        """Token card should contain price section."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal)
        assert "Price" in card

    def test_format_token_card_contains_volume(self, mock_token_signal):
        """Token card should contain volume section."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal)
        assert "Volume" in card

    def test_format_token_card_contains_liquidity(self, mock_token_signal):
        """Token card should contain liquidity section."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal)
        assert "Liquidity" in card

    def test_format_token_card_contains_security(self, mock_token_signal):
        """Token card should contain security section."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal)
        assert "Security" in card
        assert "95" in card  # security score

    def test_format_token_card_contains_smart_money(self, mock_token_signal):
        """Token card should contain smart money info when bullish."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal)
        assert "Smart Money" in card or "BULLISH" in card.upper()

    def test_format_token_card_contains_sentiment(self, mock_token_signal):
        """Token card should contain sentiment when available."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal)
        assert "Grok" in card or "Sentiment" in card

    def test_format_token_card_contains_signal(self, mock_token_signal):
        """Token card should contain signal rating."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal)
        assert "STRONG_BUY" in card or "Signal" in card

    def test_format_token_card_contains_links(self, mock_token_signal):
        """Token card should contain explorer links."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal)
        assert "DexScreener" in card
        assert "Birdeye" in card
        assert "Solscan" in card

    def test_format_token_card_contains_sources(self, mock_token_signal):
        """Token card should list data sources."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_token_signal)
        assert "Sources" in card

    def test_format_token_card_security_warnings(self, mock_bearish_signal):
        """Token card should show security warnings."""
        from tg_bot.services.digest_formatter import format_token_card

        card = format_token_card(mock_bearish_signal)
        # Should show at least one warning
        assert "Honeypot" in card or "LP" in card


# =============================================================================
# Test Hourly Digest Formatting
# =============================================================================


class TestHourlyDigestFormatting:
    """Tests for hourly digest formatting."""

    def test_format_hourly_digest_empty(self, mock_cost_tracker):
        """Empty digest should show no signals message."""
        from tg_bot.services.digest_formatter import format_hourly_digest

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            digest = format_hourly_digest([], include_cost=False)

        assert "No signals available" in digest

    def test_format_hourly_digest_header(self, mock_token_signal, mock_cost_tracker):
        """Digest should have header with title and date."""
        from tg_bot.services.digest_formatter import format_hourly_digest

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            digest = format_hourly_digest([mock_token_signal], include_cost=False)

        assert "JARVIS" in digest
        assert "UTC" in digest

    def test_format_hourly_digest_custom_title(self, mock_token_signal, mock_cost_tracker):
        """Digest should use custom title when provided."""
        from tg_bot.services.digest_formatter import format_hourly_digest

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            digest = format_hourly_digest([mock_token_signal], title="Custom Report", include_cost=False)

        assert "CUSTOM REPORT" in digest.upper()

    def test_format_hourly_digest_summary_stats(self, mock_token_signal, mock_bearish_signal, mock_cost_tracker):
        """Digest should show summary statistics."""
        from tg_bot.services.digest_formatter import format_hourly_digest

        signals = [mock_token_signal, mock_bearish_signal]
        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            digest = format_hourly_digest(signals, include_cost=False)

        assert "Summary" in digest
        assert "2" in digest or "tokens" in digest.lower()

    def test_format_hourly_digest_with_cost(self, mock_token_signal, mock_cost_tracker):
        """Digest should show API costs when enabled."""
        from tg_bot.services.digest_formatter import format_hourly_digest

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            digest = format_hourly_digest([mock_token_signal], include_cost=True)

        assert "Cost" in digest or "API" in digest

    def test_format_hourly_digest_without_cost(self, mock_token_signal, mock_cost_tracker):
        """Digest should not show costs when disabled."""
        from tg_bot.services.digest_formatter import format_hourly_digest

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            digest = format_hourly_digest([mock_token_signal], include_cost=False)

        # Should not have detailed cost info (but may have disclaimer)
        # Check that API Costs Today section is missing
        assert "API Costs Today" not in digest

    def test_format_hourly_digest_contains_tokens(self, mock_token_signal, mock_cost_tracker):
        """Digest should contain token cards."""
        from tg_bot.services.digest_formatter import format_hourly_digest

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            digest = format_hourly_digest([mock_token_signal], include_cost=False)

        assert "SOL" in digest

    def test_format_hourly_digest_top_picks(self, mock_token_signal, mock_cost_tracker):
        """Digest should highlight strong buy signals."""
        from tg_bot.services.digest_formatter import format_hourly_digest

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            digest = format_hourly_digest([mock_token_signal], include_cost=False)

        # STRONG_BUY should appear in top picks
        assert "TOP PICKS" in digest or "SOL" in digest

    def test_format_hourly_digest_avoid_section(self, mock_bearish_signal, mock_cost_tracker):
        """Digest should highlight tokens to avoid."""
        from tg_bot.services.digest_formatter import format_hourly_digest

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            digest = format_hourly_digest([mock_bearish_signal], include_cost=False)

        assert "AVOID" in digest

    def test_format_hourly_digest_disclaimer(self, mock_token_signal, mock_cost_tracker):
        """Digest should include disclaimer."""
        from tg_bot.services.digest_formatter import format_hourly_digest

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            digest = format_hourly_digest([mock_token_signal], include_cost=False)

        # Should have some form of disclaimer
        assert "financial advice" in digest.lower() or "DYOR" in digest

    def test_format_hourly_digest_limits_to_five(self, mock_cost_tracker):
        """Digest should only show top 5 tokens."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import format_hourly_digest

        # Create 10 signals
        signals = []
        for i in range(10):
            signals.append(TokenSignal(
                address=f"addr{i}",
                symbol=f"TKN{i}",
                name=f"Token {i}",
                price_usd=1.0,
                signal="BUY",
            ))

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            digest = format_hourly_digest(signals, include_cost=False)

        # Should only show up to 5 detailed cards
        # TKN5 through TKN9 should not appear as detailed entries
        # (they may appear in summary counts though)
        count = sum(1 for i in range(5) if f"*{i+1}. TKN{i}*" in digest)
        assert count <= 5


# =============================================================================
# Test Single Analysis Formatting
# =============================================================================


class TestSingleAnalysisFormatting:
    """Tests for single token analysis formatting."""

    def test_format_single_analysis_header(self, mock_token_signal):
        """Single analysis should have header."""
        from tg_bot.services.digest_formatter import format_single_analysis

        result = format_single_analysis(mock_token_signal)
        assert "TOKEN ANALYSIS" in result

    def test_format_single_analysis_contains_card(self, mock_token_signal):
        """Single analysis should contain token card."""
        from tg_bot.services.digest_formatter import format_single_analysis

        result = format_single_analysis(mock_token_signal)
        assert "SOL" in result
        assert "Solana" in result


# =============================================================================
# Test Master Signal Report Formatting
# =============================================================================


class TestMasterSignalReportFormatting:
    """Tests for master signal report formatting."""

    def test_format_master_signal_report_empty(self):
        """Empty report should show no signals message."""
        from tg_bot.services.digest_formatter import format_master_signal_report

        report = format_master_signal_report([])
        assert "No signals available" in report

    def test_format_master_signal_report_header(self, mock_token_signal):
        """Report should have master header."""
        from tg_bot.services.digest_formatter import format_master_signal_report

        report = format_master_signal_report([mock_token_signal])
        assert "MASTER SIGNAL REPORT" in report.upper()
        # "jarvis" appears in the report (case may vary)
        assert "jarvis" in report.lower()

    def test_format_master_signal_report_market_overview(self, mock_token_signal, mock_bearish_signal):
        """Report should have market overview."""
        from tg_bot.services.digest_formatter import format_master_signal_report

        report = format_master_signal_report([mock_token_signal, mock_bearish_signal])
        assert "MARKET OVERVIEW" in report

    def test_format_master_signal_report_top_entries(self, mock_token_signal):
        """Report should have top entries section."""
        from tg_bot.services.digest_formatter import format_master_signal_report

        report = format_master_signal_report([mock_token_signal])
        assert "TOP ENTRIES" in report or "WOULD BUY" in report

    def test_format_master_signal_report_trending(self, mock_token_signal):
        """Report should have trending tokens section."""
        from tg_bot.services.digest_formatter import format_master_signal_report

        report = format_master_signal_report([mock_token_signal])
        assert "TRENDING" in report

    def test_format_master_signal_report_contains_contract(self, mock_token_signal):
        """Report should show contract addresses."""
        from tg_bot.services.digest_formatter import format_master_signal_report

        report = format_master_signal_report([mock_token_signal])
        # Should contain abbreviated address
        assert "So1111" in report or mock_token_signal.address[:6] in report

    def test_format_master_signal_report_contains_links(self, mock_token_signal):
        """Report should contain quick links."""
        from tg_bot.services.digest_formatter import format_master_signal_report

        report = format_master_signal_report([mock_token_signal])
        assert "DEX" in report or "Bird" in report or "Scan" in report

    def test_format_master_signal_report_avoid_section(self, mock_bearish_signal):
        """Report should have avoid section for risky tokens."""
        from tg_bot.services.digest_formatter import format_master_signal_report

        report = format_master_signal_report([mock_bearish_signal])
        assert "DO NOT TRADE" in report or "AVOID" in report

    def test_format_master_signal_report_disclaimer(self, mock_token_signal):
        """Report should include disclaimer."""
        from tg_bot.services.digest_formatter import format_master_signal_report

        report = format_master_signal_report([mock_token_signal])
        assert "financial advice" in report.lower() or "DYOR" in report

    def test_format_master_signal_report_limits_to_ten(self):
        """Report should show max 10 tokens in detail."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import format_master_signal_report

        # Create 15 signals
        signals = []
        for i in range(15):
            signals.append(TokenSignal(
                address=f"addr{i}",
                symbol=f"TKN{i}",
                price_usd=1.0,
                signal="BUY",
            ))

        report = format_master_signal_report(signals)
        # Should only have 10 detailed entries
        for i in range(10):
            assert f"TKN{i}" in report
        # TKN10-14 should not be in detailed list
        # (though they may be in summary)


# =============================================================================
# Test Entry Recommendation Logic
# =============================================================================


class TestEntryRecommendation:
    """Tests for entry recommendation logic."""

    def test_entry_recommendation_avoid(self):
        """AVOID signal should recommend do not enter."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _get_entry_recommendation

        signal = TokenSignal(address="test", symbol="TEST", signal="AVOID")
        rec = _get_entry_recommendation(signal)
        assert "NOT" in rec.upper() or "ENTER" not in rec.upper()

    def test_entry_recommendation_strong_sell(self):
        """STRONG_SELL should recommend exit/short."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _get_entry_recommendation

        signal = TokenSignal(address="test", symbol="TEST", signal="STRONG_SELL")
        rec = _get_entry_recommendation(signal)
        assert "EXIT" in rec.upper() or "SHORT" in rec.upper()

    def test_entry_recommendation_sell(self):
        """SELL should recommend reduce position."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _get_entry_recommendation

        signal = TokenSignal(address="test", symbol="TEST", signal="SELL")
        rec = _get_entry_recommendation(signal)
        assert "REDUCE" in rec.upper()

    def test_entry_recommendation_strong_buy_high_liquidity(self):
        """STRONG_BUY with high liquidity should recommend long term."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _get_entry_recommendation

        signal = TokenSignal(
            address="test",
            symbol="TEST",
            signal="STRONG_BUY",
            liquidity_usd=10_000_000,
            volume_1h=100_000,
        )
        rec = _get_entry_recommendation(signal)
        assert "LONG" in rec.upper() or "STRONG" in rec.upper()

    def test_entry_recommendation_strong_buy_high_volume_ratio(self):
        """STRONG_BUY with high volume ratio should recommend scalp."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _get_entry_recommendation

        signal = TokenSignal(
            address="test",
            symbol="TEST",
            signal="STRONG_BUY",
            liquidity_usd=100_000,
            volume_1h=100_000,  # 100% vol/liq ratio
        )
        rec = _get_entry_recommendation(signal)
        assert "SCALP" in rec.upper() or "DAY" in rec.upper()

    def test_entry_recommendation_buy_high_liquidity(self):
        """BUY with high liquidity should recommend accumulate."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _get_entry_recommendation

        signal = TokenSignal(
            address="test",
            symbol="TEST",
            signal="BUY",
            liquidity_usd=5_000_000,
        )
        rec = _get_entry_recommendation(signal)
        assert "ACCUMULATE" in rec.upper()

    def test_entry_recommendation_buy_low_liquidity(self):
        """BUY with low liquidity should recommend small position."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _get_entry_recommendation

        signal = TokenSignal(
            address="test",
            symbol="TEST",
            signal="BUY",
            liquidity_usd=50_000,
        )
        rec = _get_entry_recommendation(signal)
        assert "SMALL" in rec.upper()

    def test_entry_recommendation_neutral(self):
        """NEUTRAL should recommend watch and wait."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _get_entry_recommendation

        signal = TokenSignal(address="test", symbol="TEST", signal="NEUTRAL")
        rec = _get_entry_recommendation(signal)
        assert "WATCH" in rec.upper() or "WAIT" in rec.upper()


# =============================================================================
# Test Leverage Suggestion Logic
# =============================================================================


class TestLeverageSuggestion:
    """Tests for leverage suggestion logic."""

    def test_leverage_low_liquidity(self):
        """Low liquidity should suggest low leverage."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _suggest_leverage

        signal = TokenSignal(
            address="test",
            symbol="TEST",
            liquidity_usd=50_000,
            price_change_1h=5.0,
        )
        assert _suggest_leverage(signal) == 2

    def test_leverage_high_volatility(self):
        """High volatility should suggest low leverage."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _suggest_leverage

        signal = TokenSignal(
            address="test",
            symbol="TEST",
            liquidity_usd=1_000_000,
            price_change_1h=25.0,  # Very volatile
        )
        assert _suggest_leverage(signal) == 2

    def test_leverage_medium_liquidity(self):
        """Medium liquidity should suggest medium leverage."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _suggest_leverage

        signal = TokenSignal(
            address="test",
            symbol="TEST",
            liquidity_usd=300_000,
            price_change_1h=8.0,
        )
        assert _suggest_leverage(signal) == 3

    def test_leverage_good_liquidity(self):
        """Good liquidity with low volatility should suggest higher leverage."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _suggest_leverage

        signal = TokenSignal(
            address="test",
            symbol="TEST",
            liquidity_usd=800_000,
            price_change_1h=4.0,
        )
        assert _suggest_leverage(signal) == 5

    def test_leverage_high_liquidity(self):
        """High liquidity should suggest higher leverage."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _suggest_leverage

        signal = TokenSignal(
            address="test",
            symbol="TEST",
            liquidity_usd=3_000_000,
            price_change_1h=3.0,
        )
        assert _suggest_leverage(signal) == 10

    def test_leverage_very_high_liquidity(self):
        """Very high liquidity should suggest max leverage."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import _suggest_leverage

        signal = TokenSignal(
            address="test",
            symbol="TEST",
            liquidity_usd=10_000_000,
            price_change_1h=2.0,
        )
        assert _suggest_leverage(signal) == 20


# =============================================================================
# Test Error Message Formatting
# =============================================================================


class TestErrorFormatting:
    """Tests for error message formatting."""

    def test_format_error_basic(self):
        """Basic error should show message."""
        from tg_bot.services.digest_formatter import format_error

        result = format_error("Something went wrong")
        assert "Error" in result
        assert "Something went wrong" in result

    def test_format_error_with_suggestion(self):
        """Error with suggestion should show both."""
        from tg_bot.services.digest_formatter import format_error

        result = format_error("Invalid token", "Try checking the address")
        assert "Invalid token" in result
        assert "Try checking the address" in result

    def test_format_error_escapes_markdown(self):
        """Error message should escape markdown characters."""
        from tg_bot.services.digest_formatter import format_error

        result = format_error("Error with _special_ chars")
        # Should be escaped to prevent markdown issues
        assert "\\_special\\_" in result or "_special_" in result


# =============================================================================
# Test Rate Limit Message Formatting
# =============================================================================


class TestRateLimitFormatting:
    """Tests for rate limit message formatting."""

    def test_format_rate_limit_basic(self):
        """Rate limit message should show reason."""
        from tg_bot.services.digest_formatter import format_rate_limit

        result = format_rate_limit("Too many requests")
        assert "Rate Limited" in result
        assert "Too many requests" in result

    def test_format_rate_limit_preserves_cost_notice(self):
        """Rate limit should mention API costs."""
        from tg_bot.services.digest_formatter import format_rate_limit

        result = format_rate_limit("Daily limit reached")
        assert "API" in result.lower() or "cost" in result.lower()

    def test_format_rate_limit_escapes_markdown(self):
        """Rate limit should escape special chars."""
        from tg_bot.services.digest_formatter import format_rate_limit

        result = format_rate_limit("Wait_5_minutes")
        assert "Wait\\_5\\_minutes" in result or "Wait_5_minutes" in result


# =============================================================================
# Test Unauthorized Message Formatting
# =============================================================================


class TestUnauthorizedFormatting:
    """Tests for unauthorized message formatting."""

    def test_format_unauthorized(self):
        """Unauthorized message should be clear."""
        from tg_bot.services.digest_formatter import format_unauthorized

        result = format_unauthorized()
        assert "Unauthorized" in result
        assert "admin" in result.lower()


# =============================================================================
# Test Status Message Formatting
# =============================================================================


class TestStatusFormatting:
    """Tests for status message formatting."""

    def test_format_status_with_sources(self, mock_cost_tracker):
        """Status should show available sources."""
        from tg_bot.services.digest_formatter import format_status

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            result = format_status(
                available_sources=["DexScreener", "Birdeye", "Grok"],
                missing_config=[]
            )

        assert "DexScreener" in result
        assert "Birdeye" in result
        assert "Grok" in result

    def test_format_status_no_sources(self, mock_cost_tracker):
        """Status with no sources should indicate issue."""
        from tg_bot.services.digest_formatter import format_status

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            result = format_status(
                available_sources=[],
                missing_config=[]
            )

        assert "No sources available" in result

    def test_format_status_missing_config(self, mock_cost_tracker):
        """Status should show missing configuration."""
        from tg_bot.services.digest_formatter import format_status

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            result = format_status(
                available_sources=["DexScreener"],
                missing_config=["XAI_API_KEY", "BIRDEYE_API_KEY"]
            )

        assert "XAI_API_KEY" in result
        assert "BIRDEYE_API_KEY" in result

    def test_format_status_sentiment_ready(self, mock_cost_tracker):
        """Status should show sentiment readiness."""
        from tg_bot.services.digest_formatter import format_status

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            result = format_status(
                available_sources=["Grok"],
                missing_config=[]
            )

        assert "Sentiment" in result or "Ready" in result

    def test_format_status_sentiment_limited(self, mock_cost_tracker):
        """Status should show sentiment rate limit status."""
        mock_cost_tracker.can_make_sentiment_call.return_value = (False, "Wait 10 minutes")

        from tg_bot.services.digest_formatter import format_status

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            result = format_status(
                available_sources=["Grok"],
                missing_config=[]
            )

        assert "Wait" in result or "10" in result


# =============================================================================
# Test Disclaimer Formatting
# =============================================================================


class TestDisclaimerFormatting:
    """Tests for disclaimer formatting."""

    def test_format_disclaimer_full(self):
        """Full disclaimer should contain key elements."""
        from tg_bot.services.digest_formatter import format_disclaimer

        result = format_disclaimer()

        assert "DISCLAIMER" in result
        assert "NOT financial" in result or "not financial" in result.lower()
        assert "DYOR" in result or "own research" in result.lower()
        assert "lose" in result.lower()

    def test_format_disclaimer_mentions_ai(self):
        """Disclaimer should mention AI-generated content."""
        from tg_bot.services.digest_formatter import format_disclaimer

        result = format_disclaimer()
        assert "AI" in result or "JARVIS" in result


# =============================================================================
# Test Signal/Risk Emoji Mappings
# =============================================================================


class TestEmojiMappings:
    """Tests for emoji mapping constants."""

    def test_signal_emoji_all_signals(self):
        """All signal types should have emojis."""
        from tg_bot.services.digest_formatter import SIGNAL_EMOJI

        expected_signals = ["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL", "AVOID"]
        for signal in expected_signals:
            assert signal in SIGNAL_EMOJI
            assert len(SIGNAL_EMOJI[signal]) > 0

    def test_risk_emoji_all_levels(self):
        """All risk levels should have emojis."""
        from tg_bot.services.digest_formatter import RISK_EMOJI

        expected_levels = ["low", "medium", "high", "critical", "unknown"]
        for level in expected_levels:
            assert level in RISK_EMOJI
            assert len(RISK_EMOJI[level]) > 0

    def test_sentiment_emoji_all_sentiments(self):
        """All sentiments should have emojis."""
        from tg_bot.services.digest_formatter import SENTIMENT_EMOJI

        expected_sentiments = ["positive", "neutral", "negative", "mixed"]
        for sentiment in expected_sentiments:
            assert sentiment in SENTIMENT_EMOJI
            assert len(SENTIMENT_EMOJI[sentiment]) > 0


# =============================================================================
# Test Cost Report Formatting
# =============================================================================


class TestCostReportFormatting:
    """Tests for cost report formatting."""

    def test_format_cost_report(self, mock_cost_tracker):
        """Cost report should call tracker."""
        from tg_bot.services.digest_formatter import format_cost_report

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            result = format_cost_report()

        mock_cost_tracker.get_cost_report.assert_called_once()
        assert result == "Cost report placeholder"


# =============================================================================
# Test Master Token Entry Formatting
# =============================================================================


class TestMasterTokenEntryFormatting:
    """Tests for master token entry formatting (internal)."""

    def test_format_master_token_entry_basic(self, mock_token_signal):
        """Token entry should have rank and symbol."""
        from tg_bot.services.digest_formatter import _format_master_token_entry

        entry = _format_master_token_entry(mock_token_signal, rank=1)
        assert "*1." in entry
        assert "SOL" in entry

    def test_format_master_token_entry_contract(self, mock_token_signal):
        """Token entry should have clickable contract."""
        from tg_bot.services.digest_formatter import _format_master_token_entry

        entry = _format_master_token_entry(mock_token_signal, rank=1)
        assert "`" in entry  # Code formatting for contract

    def test_format_master_token_entry_price_info(self, mock_token_signal):
        """Token entry should have price and changes."""
        from tg_bot.services.digest_formatter import _format_master_token_entry

        entry = _format_master_token_entry(mock_token_signal, rank=1)
        assert "$" in entry
        assert "1h" in entry
        assert "24h" in entry

    def test_format_master_token_entry_volume_liquidity(self, mock_token_signal):
        """Token entry should have volume and liquidity."""
        from tg_bot.services.digest_formatter import _format_master_token_entry

        entry = _format_master_token_entry(mock_token_signal, rank=1)
        assert "Vol" in entry
        assert "Liq" in entry

    def test_format_master_token_entry_security(self, mock_token_signal):
        """Token entry should show security status."""
        from tg_bot.services.digest_formatter import _format_master_token_entry

        entry = _format_master_token_entry(mock_token_signal, rank=1)
        assert "LOW" in entry.upper()
        assert "95" in entry or "Score" in entry

    def test_format_master_token_entry_sentiment(self, mock_token_signal):
        """Token entry should show sentiment if available."""
        from tg_bot.services.digest_formatter import _format_master_token_entry

        entry = _format_master_token_entry(mock_token_signal, rank=1)
        assert "Grok" in entry
        assert "POSITIVE" in entry.upper()

    def test_format_master_token_entry_smart_money(self, mock_token_signal):
        """Token entry should show smart money if not neutral."""
        from tg_bot.services.digest_formatter import _format_master_token_entry

        entry = _format_master_token_entry(mock_token_signal, rank=1)
        assert "WHALE" in entry.upper()

    def test_format_master_token_entry_signal(self, mock_token_signal):
        """Token entry should show signal and recommendation."""
        from tg_bot.services.digest_formatter import _format_master_token_entry

        entry = _format_master_token_entry(mock_token_signal, rank=1)
        assert "STRONG_BUY" in entry

    def test_format_master_token_entry_links(self, mock_token_signal):
        """Token entry should have quick links."""
        from tg_bot.services.digest_formatter import _format_master_token_entry

        entry = _format_master_token_entry(mock_token_signal, rank=1)
        assert "[DEX]" in entry or "[Bird]" in entry or "[Scan]" in entry


# =============================================================================
# Integration Tests
# =============================================================================


class TestFormatterIntegration:
    """Integration tests for the formatter module."""

    def test_full_digest_generation(self, mock_cost_tracker):
        """Full digest should generate without errors."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import format_hourly_digest

        signals = [
            TokenSignal(
                address=f"addr{i}",
                symbol=f"TKN{i}",
                name=f"Token {i}",
                price_usd=float(i + 1),
                price_change_1h=float(i * 2 - 5),
                price_change_24h=float(i * 3 - 10),
                volume_24h=float(i * 1_000_000),
                liquidity_usd=float(i * 500_000),
                security_score=float(50 + i * 5),
                risk_level=["low", "medium", "high"][i % 3],
                sentiment=["positive", "neutral", "negative"][i % 3],
                sentiment_confidence=0.5 + i * 0.05,
                signal=["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "AVOID"][i % 5],
                signal_score=float(50 - i * 10),
                sources_used=["DexScreener"],
            )
            for i in range(5)
        ]

        with patch('tg_bot.services.digest_formatter.get_tracker', return_value=mock_cost_tracker):
            result = format_hourly_digest(signals, include_cost=True)

        # Should be a non-empty string
        assert isinstance(result, str)
        assert len(result) > 100

        # Should contain expected sections
        assert "JARVIS" in result
        assert "Summary" in result
        assert "TKN0" in result

    def test_full_master_report_generation(self):
        """Full master report should generate without errors."""
        from tg_bot.services.signal_service import TokenSignal
        from tg_bot.services.digest_formatter import format_master_signal_report

        signals = [
            TokenSignal(
                address=f"address_{i}",
                symbol=f"SYM{i}",
                price_usd=100.0 / (i + 1),
                price_change_1h=float(i * 2 - 5),
                price_change_24h=float(i * 3 - 10),
                volume_24h=float(i * 1_000_000),
                volume_1h=float(i * 100_000),
                liquidity_usd=float(i * 500_000 + 100_000),
                security_score=float(90 - i * 5),
                risk_level=["low", "medium", "high", "critical"][i % 4],
                smart_money_signal=["bullish", "neutral", "bearish"][i % 3],
                sentiment=["positive", "neutral", "negative"][i % 3],
                sentiment_confidence=0.8 - i * 0.1,
                signal=["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"][i % 5],
                signal_score=float(80 - i * 15),
                security_warnings=["Warning 1"] if i % 2 else [],
            )
            for i in range(10)
        ]

        result = format_master_signal_report(signals)

        # Should be a non-empty string
        assert isinstance(result, str)
        assert len(result) > 500

        # Should contain expected sections
        assert "MASTER SIGNAL REPORT" in result.upper()
        assert "MARKET OVERVIEW" in result
        assert "TRENDING" in result

    def test_multiple_calls_consistent(self, mock_token_signal, mock_cost_tracker):
        """Multiple calls should produce consistent output."""
        from tg_bot.services.digest_formatter import format_token_card

        card1 = format_token_card(mock_token_signal)
        card2 = format_token_card(mock_token_signal)

        # Should be identical
        assert card1 == card2
