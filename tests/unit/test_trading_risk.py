import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from bots.treasury.trading.trading_risk import RiskChecker
from bots.treasury.trading.types import RiskLevel
from bots.treasury.trading.constants import (
    ESTABLISHED_TOKENS,
    BLOCKED_TOKENS,
    BLOCKED_SYMBOLS,
    HIGH_RISK_PATTERNS,
    MAX_HIGH_RISK_POSITION_PCT,
    MAX_UNVETTED_POSITION_PCT,
    MAX_TRADE_USD,
    MAX_DAILY_USD,
    MAX_POSITION_PCT,
    TP_SL_CONFIG,
    POSITION_SIZE,
)


def test_classify_token_risk_established():
    mint = next(iter(ESTABLISHED_TOKENS.keys()))
    tier = RiskChecker.classify_token_risk(mint, ESTABLISHED_TOKENS[mint])
    assert tier == "ESTABLISHED"


def test_classify_token_risk_high_risk():
    tier = RiskChecker.classify_token_risk("pump_fun_token", "PUMP")
    assert tier == "HIGH_RISK"


def test_risk_adjusted_position_size_high_risk():
    base = 100.0
    adjusted, tier = RiskChecker.get_risk_adjusted_position_size("pump_token", "PUMP", base)
    assert tier == "HIGH_RISK"
    assert adjusted == pytest.approx(base * MAX_HIGH_RISK_POSITION_PCT)


def test_risk_adjusted_position_size_micro():
    base = 100.0
    adjusted, tier = RiskChecker.get_risk_adjusted_position_size("unknown_token", "ZZZ", base)
    assert tier == "MICRO"
    assert adjusted == pytest.approx(base * MAX_UNVETTED_POSITION_PCT)


def test_check_spending_limits_exceeds_single_trade():
    checker = RiskChecker(daily_volume_file=None)
    allowed, reason = checker.check_spending_limits(MAX_TRADE_USD + 1.0, portfolio_usd=10000)
    assert allowed is False
    assert "exceeds max single trade" in reason


def test_check_spending_limits_exceeds_daily(tmp_path):
    daily_file = tmp_path / "daily_volume.json"
    checker = RiskChecker(daily_volume_file=daily_file)

    checker.add_daily_volume(MAX_DAILY_USD - 10.0)
    allowed, reason = checker.check_spending_limits(20.0, portfolio_usd=10000)

    assert allowed is False
    assert "Daily limit reached" in reason


def test_check_spending_limits_position_pct(tmp_path):
    daily_file = tmp_path / "daily_volume.json"
    checker = RiskChecker(daily_volume_file=daily_file)
    checker.add_daily_volume(0.0)

    portfolio_usd = 100.0
    amount_usd = (MAX_POSITION_PCT * portfolio_usd) + 1.0

    allowed, reason = checker.check_spending_limits(amount_usd, portfolio_usd=portfolio_usd)
    assert allowed is False
    assert "exceeds max" in reason


def test_get_tp_sl_levels_defaults():
    entry_price = 100.0
    tp, sl = RiskChecker.get_tp_sl_levels(entry_price, "B")
    assert tp == pytest.approx(entry_price * (1 + TP_SL_CONFIG["B"]["take_profit"]))
    assert sl == pytest.approx(entry_price * (1 - TP_SL_CONFIG["B"]["stop_loss"]))


def test_get_tp_sl_levels_custom_override():
    entry_price = 200.0
    tp, sl = RiskChecker.get_tp_sl_levels(entry_price, "A", custom_tp=0.5, custom_sl=0.25)
    assert tp == pytest.approx(entry_price * 1.5)
    assert sl == pytest.approx(entry_price * 0.75)


# =============================================================================
# Token Safety Tests
# =============================================================================


class TestTokenSafety:
    """Test token safety and blocking methods."""

    def test_is_blocked_token_by_mint(self):
        """Test blocked token detection by mint address."""
        # Get a blocked token from BLOCKED_TOKENS
        blocked_mint = next(iter(BLOCKED_TOKENS.keys()))
        is_blocked, reason = RiskChecker.is_blocked_token(blocked_mint, "")

        assert is_blocked is True
        assert "stablecoin" in reason.lower() or "blocked" in reason.lower()

    def test_is_blocked_token_by_symbol(self):
        """Test blocked token detection by symbol."""
        # Get a blocked symbol from BLOCKED_SYMBOLS
        blocked_symbol = next(iter(BLOCKED_SYMBOLS))
        is_blocked, reason = RiskChecker.is_blocked_token("random_mint", blocked_symbol)

        assert is_blocked is True
        assert "stablecoin" in reason.lower()

    def test_is_blocked_token_not_blocked(self):
        """Test non-blocked token returns False."""
        is_blocked, reason = RiskChecker.is_blocked_token("normal_token_mint", "NORM")

        assert is_blocked is False
        assert reason == ""

    def test_is_high_risk_token_pump_fun(self):
        """Test high-risk token detection for pump.fun patterns."""
        # Use a HIGH_RISK_PATTERN if available
        if HIGH_RISK_PATTERNS:
            pattern = HIGH_RISK_PATTERNS[0]
            test_mint = f"xyz_{pattern}_abc123"
            assert RiskChecker.is_high_risk_token(test_mint) is True

    def test_is_high_risk_token_normal(self):
        """Test normal token is not high-risk."""
        assert RiskChecker.is_high_risk_token("normal_token_mint_without_patterns") is False

    def test_is_established_token_in_whitelist(self):
        """Test established token detection."""
        established_mint = next(iter(ESTABLISHED_TOKENS.keys()))
        assert RiskChecker.is_established_token(established_mint) is True

    def test_is_established_token_not_in_whitelist(self):
        """Test non-established token returns False."""
        assert RiskChecker.is_established_token("unknown_token") is False


# =============================================================================
# Token Classification Tests (Extended)
# =============================================================================


class TestTokenClassification:
    """Extended tests for token risk classification."""

    def test_classify_xs_prefix_pattern(self):
        """Test XStocks pattern (starts with Xs) classified as ESTABLISHED."""
        tier = RiskChecker.classify_token_risk("Xs12345", "TSLA")
        assert tier == "ESTABLISHED"

    def test_classify_major_symbol_mid_tier(self):
        """Test major symbols get MID tier."""
        tier = RiskChecker.classify_token_risk("unknown_mint", "BTC")
        assert tier == "MID"

        tier = RiskChecker.classify_token_risk("unknown_mint", "ETH")
        assert tier == "MID"

    def test_classify_tokenized_equity_mid_tier(self):
        """Test tokenized equity symbols (ends with X) get MID tier."""
        tier = RiskChecker.classify_token_risk("unknown_mint", "TSLAX")
        assert tier == "MID"

        tier = RiskChecker.classify_token_risk("unknown_mint", "AAPL X")
        assert tier == "MID"

    def test_classify_micro_tier_unknown_token(self):
        """Test unknown tokens get MICRO tier."""
        tier = RiskChecker.classify_token_risk("random_mint_123", "UNKN")
        assert tier == "MICRO"


# =============================================================================
# Risk-Adjusted Position Sizing (Extended)
# =============================================================================


class TestRiskAdjustedSizing:
    """Extended tests for risk-adjusted position sizing."""

    def test_established_token_full_size(self):
        """Test established tokens get full position size."""
        base = 100.0
        established_mint = next(iter(ESTABLISHED_TOKENS.keys()))
        adjusted, tier = RiskChecker.get_risk_adjusted_position_size(
            established_mint, ESTABLISHED_TOKENS[established_mint], base
        )

        assert tier == "ESTABLISHED"
        assert adjusted == pytest.approx(base)  # Full size

    def test_mid_tier_half_size(self):
        """Test MID tier tokens get 50% position size."""
        base = 100.0
        adjusted, tier = RiskChecker.get_risk_adjusted_position_size("unknown_mint", "BTC", base)

        assert tier == "MID"
        assert adjusted == pytest.approx(base * 0.50)


# =============================================================================
# Daily Volume Tracking Tests
# =============================================================================


class TestDailyVolume:
    """Test daily volume tracking with file I/O."""

    def test_get_daily_volume_file_not_exists(self, tmp_path):
        """Test get_daily_volume returns 0 when file doesn't exist."""
        daily_file = tmp_path / "daily_volume.json"
        checker = RiskChecker(daily_volume_file=daily_file)

        assert checker.get_daily_volume() == 0.0

    def test_get_daily_volume_reads_today(self, tmp_path):
        """Test get_daily_volume reads today's volume from file."""
        from datetime import datetime

        daily_file = tmp_path / "daily_volume.json"
        today = datetime.utcnow().strftime('%Y-%m-%d')

        # Write volume file
        with open(daily_file, 'w') as f:
            json.dump({'date': today, 'volume_usd': 500.0}, f)

        checker = RiskChecker(daily_volume_file=daily_file)
        assert checker.get_daily_volume() == 500.0

    def test_get_daily_volume_stale_date_returns_zero(self, tmp_path):
        """Test get_daily_volume returns 0 when date is old."""
        daily_file = tmp_path / "daily_volume.json"

        # Write stale volume file
        with open(daily_file, 'w') as f:
            json.dump({'date': '2020-01-01', 'volume_usd': 999.0}, f)

        checker = RiskChecker(daily_volume_file=daily_file)
        assert checker.get_daily_volume() == 0.0

    def test_add_daily_volume_creates_file(self, tmp_path):
        """Test add_daily_volume creates file when it doesn't exist."""
        from datetime import datetime

        daily_file = tmp_path / "daily_volume.json"
        checker = RiskChecker(daily_volume_file=daily_file)

        checker.add_daily_volume(100.0)

        assert daily_file.exists()
        with open(daily_file) as f:
            data = json.load(f)
            assert data['volume_usd'] == 100.0
            assert data['date'] == datetime.utcnow().strftime('%Y-%m-%d')

    def test_add_daily_volume_accumulates(self, tmp_path):
        """Test add_daily_volume accumulates to existing volume."""
        daily_file = tmp_path / "daily_volume.json"
        checker = RiskChecker(daily_volume_file=daily_file)

        checker.add_daily_volume(50.0)
        checker.add_daily_volume(75.0)

        assert checker.get_daily_volume() == 125.0

    def test_get_daily_volume_handles_corrupted_file(self, tmp_path):
        """Test get_daily_volume handles corrupted JSON gracefully."""
        daily_file = tmp_path / "daily_volume.json"

        # Write invalid JSON
        with open(daily_file, 'w') as f:
            f.write("not valid json{")

        checker = RiskChecker(daily_volume_file=daily_file)
        assert checker.get_daily_volume() == 0.0  # Should not crash


# =============================================================================
# Spending Limits (Extended)
# =============================================================================


class TestSpendingLimitsExtended:
    """Extended spending limits tests."""

    def test_check_spending_limits_portfolio_zero_edge_case(self, tmp_path):
        """Test check_spending_limits with zero portfolio skips percentage check."""
        daily_file = tmp_path / "daily_volume.json"
        checker = RiskChecker(daily_volume_file=daily_file)

        # Small trade with zero portfolio - should pass percentage check
        allowed, reason = checker.check_spending_limits(10.0, portfolio_usd=0.0)

        assert allowed is True
        assert reason == ""

    def test_check_spending_limits_all_pass(self, tmp_path):
        """Test check_spending_limits passes when all limits OK."""
        daily_file = tmp_path / "daily_volume.json"
        checker = RiskChecker(daily_volume_file=daily_file)

        # Valid trade
        allowed, reason = checker.check_spending_limits(100.0, portfolio_usd=10000.0)

        assert allowed is True
        assert reason == ""


# =============================================================================
# TP/SL Calculations (Extended)
# =============================================================================


class TestTPSLExtended:
    """Extended TP/SL calculation tests."""

    def test_get_tp_sl_levels_unknown_grade_default(self):
        """Test unknown grade falls back to default config."""
        entry_price = 100.0
        tp, sl = RiskChecker.get_tp_sl_levels(entry_price, "UNKNOWN_GRADE")

        # Should use default: +20% TP, -10% SL
        assert tp == pytest.approx(entry_price * 1.20)
        assert sl == pytest.approx(entry_price * 0.90)

    def test_get_tp_sl_levels_different_grades(self):
        """Test different sentiment grades produce different TP/SL."""
        entry_price = 100.0

        # Test each grade in config
        for grade, config in TP_SL_CONFIG.items():
            tp, sl = RiskChecker.get_tp_sl_levels(entry_price, grade)
            assert tp == pytest.approx(entry_price * (1 + config['take_profit']))
            assert sl == pytest.approx(entry_price * (1 - config['stop_loss']))


# =============================================================================
# Position Sizing Tests
# =============================================================================


class TestPositionSizing:
    """Test position sizing calculations."""

    def test_calculate_position_size_conservative(self):
        """Test position size for CONSERVATIVE risk level."""
        portfolio = 10000.0
        size = RiskChecker.calculate_position_size(portfolio, RiskLevel.CONSERVATIVE)
        assert size == pytest.approx(portfolio * POSITION_SIZE[RiskLevel.CONSERVATIVE])

    def test_calculate_position_size_moderate(self):
        """Test position size for MODERATE risk level."""
        portfolio = 10000.0
        size = RiskChecker.calculate_position_size(portfolio, RiskLevel.MODERATE)
        assert size == pytest.approx(portfolio * POSITION_SIZE[RiskLevel.MODERATE])

    def test_calculate_position_size_aggressive(self):
        """Test position size for AGGRESSIVE risk level."""
        portfolio = 10000.0
        size = RiskChecker.calculate_position_size(portfolio, RiskLevel.AGGRESSIVE)
        assert size == pytest.approx(portfolio * POSITION_SIZE[RiskLevel.AGGRESSIVE])
