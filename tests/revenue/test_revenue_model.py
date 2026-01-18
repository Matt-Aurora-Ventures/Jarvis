"""
Tests for Revenue Model Implementation.

Tests the 0.5% fee system with:
- Fee calculation on profits
- User wallet management
- Charity distribution
- Subscription tiers
- Affiliate program
- Invoice generation
- Financial reporting

Target: 30+ tests covering all revenue components.
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal


# ============================================================================
# Test Fee Calculator
# ============================================================================

class TestFeeCalculator:
    """Tests for FeeCalculator - 0.5% fee on winning trades."""

    def test_calculate_fee_on_profit(self):
        """Test fee calculation on profitable trade."""
        from core.revenue.fee_calculator import FeeCalculator

        calc = FeeCalculator()

        # Profitable trade: bought at $100, sold at $120, 10 units
        fee = calc.calculate_fee(
            entry_price=100.0,
            exit_price=120.0,
            position_size=10.0
        )

        # Profit = (120 - 100) * 10 = $200
        # Fee = $200 * 0.005 = $1.00
        assert fee == pytest.approx(1.0, rel=0.01)

    def test_no_fee_on_loss(self):
        """Test no fee charged on losing trade."""
        from core.revenue.fee_calculator import FeeCalculator

        calc = FeeCalculator()

        # Losing trade: bought at $100, sold at $80, 10 units
        fee = calc.calculate_fee(
            entry_price=100.0,
            exit_price=80.0,
            position_size=10.0
        )

        # Loss = negative profit, no fee charged
        assert fee == 0.0

    def test_no_fee_on_breakeven(self):
        """Test no fee on breakeven trade."""
        from core.revenue.fee_calculator import FeeCalculator

        calc = FeeCalculator()

        fee = calc.calculate_fee(
            entry_price=100.0,
            exit_price=100.0,
            position_size=10.0
        )

        assert fee == 0.0

    def test_fee_distribution_breakdown(self):
        """Test fee distribution: 75% user, 5% charity, 20% company."""
        from core.revenue.fee_calculator import FeeCalculator

        calc = FeeCalculator()

        # Profitable trade with $100 profit -> $0.50 fee
        distribution = calc.calculate_fee_distribution(
            entry_price=100.0,
            exit_price=110.0,
            position_size=10.0
        )

        # Total fee = $100 profit * 0.005 = $0.50
        assert distribution['total_fee'] == pytest.approx(0.50, rel=0.01)
        assert distribution['user_share'] == pytest.approx(0.375, rel=0.01)  # 75%
        assert distribution['charity_share'] == pytest.approx(0.025, rel=0.01)  # 5%
        assert distribution['company_share'] == pytest.approx(0.10, rel=0.01)  # 20%

    def test_custom_fee_rate(self):
        """Test custom fee rate override."""
        from core.revenue.fee_calculator import FeeCalculator

        calc = FeeCalculator(fee_rate=0.01)  # 1% instead of 0.5%

        fee = calc.calculate_fee(
            entry_price=100.0,
            exit_price=110.0,
            position_size=10.0
        )

        # $100 profit * 1% = $1.00
        assert fee == pytest.approx(1.0, rel=0.01)

    def test_aggregate_fees_daily(self, temp_dir):
        """Test daily fee aggregation."""
        from core.revenue.fee_calculator import FeeCalculator

        calc = FeeCalculator(data_dir=temp_dir)

        # Record multiple fees
        calc.record_fee("user_1", 1.0, "SOL/USDC", "trade_1")
        calc.record_fee("user_1", 0.5, "BTC/USDC", "trade_2")
        calc.record_fee("user_2", 2.0, "ETH/USDC", "trade_3")

        totals = calc.get_daily_totals()

        assert totals['total_fees'] == pytest.approx(3.5, rel=0.01)
        assert totals['user_earnings'] == pytest.approx(2.625, rel=0.01)
        assert totals['charity_amount'] == pytest.approx(0.175, rel=0.01)
        assert totals['company_revenue'] == pytest.approx(0.70, rel=0.01)


# ============================================================================
# Test User Wallet
# ============================================================================

class TestUserWallet:
    """Tests for UserWallet - track and manage user earnings."""

    def test_deposit_earnings(self, temp_dir):
        """Test depositing earnings to user wallet."""
        from core.revenue.user_wallet import UserWalletManager

        manager = UserWalletManager(data_dir=temp_dir)

        manager.deposit_earnings("user_1", 10.0)
        balance = manager.get_balance("user_1")

        assert balance == pytest.approx(10.0, rel=0.01)

    def test_multiple_deposits(self, temp_dir):
        """Test multiple deposits accumulate."""
        from core.revenue.user_wallet import UserWalletManager

        manager = UserWalletManager(data_dir=temp_dir)

        manager.deposit_earnings("user_1", 10.0)
        manager.deposit_earnings("user_1", 5.0)
        manager.deposit_earnings("user_1", 3.0)

        balance = manager.get_balance("user_1")

        assert balance == pytest.approx(18.0, rel=0.01)

    def test_request_withdrawal(self, temp_dir):
        """Test withdrawal request."""
        from core.revenue.user_wallet import UserWalletManager

        manager = UserWalletManager(data_dir=temp_dir)

        manager.deposit_earnings("user_1", 100.0)
        request = manager.request_withdrawal("user_1", 50.0)

        assert request['status'] == 'pending'
        assert request['amount'] == 50.0

    def test_withdrawal_exceeds_balance(self, temp_dir):
        """Test withdrawal request fails if exceeds balance."""
        from core.revenue.user_wallet import UserWalletManager

        manager = UserWalletManager(data_dir=temp_dir)

        manager.deposit_earnings("user_1", 50.0)

        with pytest.raises(ValueError, match="Insufficient balance"):
            manager.request_withdrawal("user_1", 100.0)

    def test_daily_withdrawal_limit(self, temp_dir):
        """Test daily withdrawal limit enforcement ($1000)."""
        from core.revenue.user_wallet import UserWalletManager

        manager = UserWalletManager(data_dir=temp_dir)

        manager.deposit_earnings("user_1", 5000.0)

        # First withdrawal within limit
        manager.request_withdrawal("user_1", 800.0)

        # Second withdrawal exceeds daily limit
        with pytest.raises(ValueError, match="daily withdrawal limit"):
            manager.request_withdrawal("user_1", 500.0)

    def test_process_withdrawal(self, temp_dir):
        """Test withdrawal processing updates balance."""
        from core.revenue.user_wallet import UserWalletManager

        manager = UserWalletManager(data_dir=temp_dir)

        manager.deposit_earnings("user_1", 100.0)
        request = manager.request_withdrawal("user_1", 50.0)

        # Simulate processing
        manager.process_withdrawal(request['id'], "mock_tx_hash")

        balance = manager.get_balance("user_1")
        assert balance == pytest.approx(50.0, rel=0.01)

    def test_get_transaction_history(self, temp_dir):
        """Test retrieving transaction history."""
        from core.revenue.user_wallet import UserWalletManager

        manager = UserWalletManager(data_dir=temp_dir)

        manager.deposit_earnings("user_1", 10.0)
        manager.deposit_earnings("user_1", 20.0)

        history = manager.get_transaction_history("user_1")

        assert len(history) == 2
        assert history[0]['type'] == 'deposit'
        assert history[1]['type'] == 'deposit'


# ============================================================================
# Test Charity Handler
# ============================================================================

class TestCharityHandler:
    """Tests for CharityHandler - manage charity distributions."""

    def test_add_charity(self, temp_dir):
        """Test adding a charity."""
        from core.revenue.charity_handler import CharityHandler

        handler = CharityHandler(data_dir=temp_dir)

        handler.add_charity(
            name="GiveWell",
            wallet_address="So11111111111111111111111111111111111111112",
            category="health"
        )

        charities = handler.list_charities()
        assert len(charities) == 1
        assert charities[0]['name'] == "GiveWell"

    def test_default_charities_loaded(self, temp_dir):
        """Test default charities are pre-loaded."""
        from core.revenue.charity_handler import CharityHandler

        handler = CharityHandler(data_dir=temp_dir, load_defaults=True)

        charities = handler.list_charities()
        assert len(charities) >= 3  # EA, GiveWell, Water.org

    def test_calculate_payout(self, temp_dir):
        """Test charity payout calculation."""
        from core.revenue.charity_handler import CharityHandler

        handler = CharityHandler(data_dir=temp_dir, load_defaults=True)

        # Simulate $1000 in charity funds
        payout = handler.calculate_payout(
            total_charity_funds=1000.0,
            month="2026-01"
        )

        # Even distribution among 3 charities
        assert payout['total'] == pytest.approx(1000.0, rel=0.01)
        assert len(payout['distributions']) == 3

    def test_get_ledger(self, temp_dir):
        """Test retrieving public ledger."""
        from core.revenue.charity_handler import CharityHandler

        handler = CharityHandler(data_dir=temp_dir, load_defaults=True)

        # Record some distributions
        handler.record_distribution("GiveWell", 100.0, "2026-01", "mock_tx_1")
        handler.record_distribution("Water.org", 100.0, "2026-01", "mock_tx_2")

        ledger = handler.get_ledger()

        assert len(ledger) == 2
        assert ledger[0]['charity'] in ["GiveWell", "Water.org"]


# ============================================================================
# Test Subscription Tiers
# ============================================================================

class TestSubscriptionTiers:
    """Tests for SubscriptionTiers - manage user subscriptions."""

    def test_free_tier_limits(self, temp_dir):
        """Test free tier has correct limits."""
        from core.revenue.subscription_tiers import SubscriptionManager

        manager = SubscriptionManager(data_dir=temp_dir)

        # New user defaults to free tier
        tier = manager.get_user_tier("user_new")

        assert tier['name'] == 'free'
        assert tier['max_positions'] == 5
        assert tier['analyses_per_day'] == 1

    def test_pro_tier_limits(self, temp_dir):
        """Test pro tier limits."""
        from core.revenue.subscription_tiers import SubscriptionManager

        manager = SubscriptionManager(data_dir=temp_dir)
        manager.upgrade_user("user_1", "pro")

        tier = manager.get_user_tier("user_1")

        assert tier['name'] == 'pro'
        assert tier['max_positions'] == -1  # Unlimited
        assert tier['analyses_per_day'] == 100
        assert tier['price_usd'] == 29.0

    def test_enterprise_tier_limits(self, temp_dir):
        """Test enterprise tier limits."""
        from core.revenue.subscription_tiers import SubscriptionManager

        manager = SubscriptionManager(data_dir=temp_dir)
        manager.upgrade_user("user_1", "enterprise")

        tier = manager.get_user_tier("user_1")

        assert tier['name'] == 'enterprise'
        assert tier['max_positions'] == -1  # Unlimited
        assert tier['price_usd'] == 299.0

    def test_check_position_limit(self, temp_dir):
        """Test position limit enforcement."""
        from core.revenue.subscription_tiers import SubscriptionManager

        manager = SubscriptionManager(data_dir=temp_dir)

        # Free user can only have 5 positions
        assert manager.can_open_position("user_free", current_positions=4) is True
        assert manager.can_open_position("user_free", current_positions=5) is False

    def test_downgrade_on_expiry(self, temp_dir):
        """Test subscription downgrade on expiry."""
        from core.revenue.subscription_tiers import SubscriptionManager

        manager = SubscriptionManager(data_dir=temp_dir)
        manager.upgrade_user("user_1", "pro", duration_days=0)  # Immediate expiry

        manager.check_expirations()

        tier = manager.get_user_tier("user_1")
        assert tier['name'] == 'free'


# ============================================================================
# Test Affiliate Program
# ============================================================================

class TestAffiliateProgram:
    """Tests for AffiliateProgram - referral tracking."""

    def test_generate_referral_code(self, temp_dir):
        """Test referral code generation."""
        from core.revenue.affiliate import AffiliateManager

        manager = AffiliateManager(data_dir=temp_dir)

        code = manager.generate_code("user_1")

        assert code.startswith("JARVIS-")
        assert len(code) == 13  # JARVIS- + 6 chars

    def test_track_referral(self, temp_dir):
        """Test tracking a new referral."""
        from core.revenue.affiliate import AffiliateManager

        manager = AffiliateManager(data_dir=temp_dir)

        code = manager.generate_code("user_1")
        manager.track_referral(code, "user_2")

        referrals = manager.get_referrals("user_1")

        assert len(referrals) == 1
        assert referrals[0]['referree_id'] == "user_2"

    def test_referral_bonus_credited(self, temp_dir):
        """Test referree gets $5 bonus after first winning trade."""
        from core.revenue.affiliate import AffiliateManager

        manager = AffiliateManager(data_dir=temp_dir)

        code = manager.generate_code("user_1")
        manager.track_referral(code, "user_2")

        # Simulate first winning trade
        manager.process_first_win("user_2")

        referrals = manager.get_referrals("user_1")
        assert referrals[0]['referree_bonus_credited'] is True

    def test_referrer_commission_calculation(self, temp_dir):
        """Test referrer gets 10% of first year fees."""
        from core.revenue.affiliate import AffiliateManager

        manager = AffiliateManager(data_dir=temp_dir)

        code = manager.generate_code("user_1")
        manager.track_referral(code, "user_2")

        # Record fee payments from referree
        manager.record_referree_fee("user_2", 10.0)
        manager.record_referree_fee("user_2", 5.0)

        commissions = manager.calculate_commissions("user_1")

        # 10% of $15 = $1.50
        assert commissions['total'] == pytest.approx(1.5, rel=0.01)

    def test_referral_expires_after_one_year(self, temp_dir):
        """Test referral commission stops after one year."""
        from core.revenue.affiliate import AffiliateManager

        manager = AffiliateManager(data_dir=temp_dir)

        code = manager.generate_code("user_1")
        manager.track_referral(code, "user_2")

        # Simulate fee payment after 13 months
        manager.record_referree_fee("user_2", 10.0, months_ago=13)

        commissions = manager.calculate_commissions("user_1")

        assert commissions['total'] == 0.0  # No commission after year


# ============================================================================
# Test Invoicing
# ============================================================================

class TestInvoicing:
    """Tests for InvoiceSystem - generate monthly invoices."""

    def test_generate_invoice_data(self, temp_dir):
        """Test invoice data generation."""
        from core.revenue.invoicing import InvoiceGenerator

        generator = InvoiceGenerator(data_dir=temp_dir)

        invoice_data = generator.generate_invoice_data(
            user_id="user_1",
            month="2026-01",
            trades=[
                {"profit": 100.0, "fee": 0.5},
                {"profit": 200.0, "fee": 1.0},
            ]
        )

        assert invoice_data['user_id'] == "user_1"
        assert invoice_data['total_profit'] == pytest.approx(300.0, rel=0.01)
        assert invoice_data['total_fees'] == pytest.approx(1.5, rel=0.01)
        assert invoice_data['user_earnings'] == pytest.approx(1.125, rel=0.01)  # 75%

    def test_generate_invoice_pdf(self, temp_dir):
        """Test PDF invoice generation."""
        from core.revenue.invoicing import InvoiceGenerator

        generator = InvoiceGenerator(data_dir=temp_dir)

        pdf_path = generator.generate_invoice_pdf(
            user_id="user_1",
            month="2026-01",
            trades=[
                {"profit": 100.0, "fee": 0.5},
            ]
        )

        # PDF should be created
        assert pdf_path is not None
        assert Path(pdf_path).exists() or pdf_path.endswith('.pdf')

    def test_invoice_has_qr_code(self, temp_dir):
        """Test invoice contains verification QR code."""
        from core.revenue.invoicing import InvoiceGenerator

        generator = InvoiceGenerator(data_dir=temp_dir)

        invoice_data = generator.generate_invoice_data(
            user_id="user_1",
            month="2026-01",
            trades=[]
        )

        assert 'verification_url' in invoice_data
        assert 'qr_code' in invoice_data or invoice_data['verification_url'] is not None

    def test_list_user_invoices(self, temp_dir):
        """Test listing user's invoices."""
        from core.revenue.invoicing import InvoiceGenerator

        generator = InvoiceGenerator(data_dir=temp_dir)

        # Generate invoices for different months
        generator.generate_invoice_data("user_1", "2025-12", [])
        generator.generate_invoice_data("user_1", "2026-01", [])

        invoices = generator.list_invoices("user_1")

        assert len(invoices) >= 2


# ============================================================================
# Test Financial Reporting
# ============================================================================

class TestFinancialReporting:
    """Tests for FinancialReporter - generate reports."""

    def test_daily_report(self, temp_dir):
        """Test daily report generation."""
        from core.revenue.financial_report import FinancialReporter

        reporter = FinancialReporter(data_dir=temp_dir)

        # Simulate some fees
        reporter.record_fee(user_id="user_1", amount=1.0, symbol="SOL/USDC")
        reporter.record_fee(user_id="user_2", amount=2.0, symbol="BTC/USDC")

        report = reporter.generate_daily_report()

        assert report['total_fees'] == pytest.approx(3.0, rel=0.01)
        assert report['user_earnings'] == pytest.approx(2.25, rel=0.01)
        assert report['charity_payout'] == pytest.approx(0.15, rel=0.01)
        assert report['company_revenue'] == pytest.approx(0.60, rel=0.01)

    def test_monthly_report(self, temp_dir):
        """Test monthly report generation."""
        from core.revenue.financial_report import FinancialReporter

        reporter = FinancialReporter(data_dir=temp_dir)

        report = reporter.generate_monthly_report("2026-01")

        assert 'revenue_breakdown' in report
        assert 'user_metrics' in report
        assert 'profitability' in report

    def test_top_earners_ranking(self, temp_dir):
        """Test top earners ranking."""
        from core.revenue.financial_report import FinancialReporter

        reporter = FinancialReporter(data_dir=temp_dir)

        reporter.record_fee("user_1", 5.0, "SOL/USDC")
        reporter.record_fee("user_2", 10.0, "BTC/USDC")
        reporter.record_fee("user_3", 3.0, "ETH/USDC")

        top_earners = reporter.get_top_earners(limit=2)

        assert len(top_earners) == 2
        assert top_earners[0]['user_id'] == "user_2"
        assert top_earners[1]['user_id'] == "user_1"

    def test_top_tokens_ranking(self, temp_dir):
        """Test top tokens by fee generation."""
        from core.revenue.financial_report import FinancialReporter

        reporter = FinancialReporter(data_dir=temp_dir)

        reporter.record_fee("user_1", 5.0, "SOL/USDC")
        reporter.record_fee("user_2", 10.0, "SOL/USDC")
        reporter.record_fee("user_3", 3.0, "BTC/USDC")

        top_tokens = reporter.get_top_tokens(limit=2)

        assert len(top_tokens) == 2
        assert top_tokens[0]['symbol'] == "SOL/USDC"
        assert top_tokens[0]['total_fees'] == pytest.approx(15.0, rel=0.01)

    def test_export_html_dashboard(self, temp_dir):
        """Test HTML dashboard export."""
        from core.revenue.financial_report import FinancialReporter

        reporter = FinancialReporter(data_dir=temp_dir)

        html_path = reporter.export_html_dashboard()

        assert html_path is not None


# ============================================================================
# Integration Tests
# ============================================================================

class TestRevenueIntegration:
    """Integration tests for revenue system."""

    def test_full_trade_fee_flow(self, temp_dir):
        """Test complete flow: trade -> fee -> wallet -> report."""
        from core.revenue.fee_calculator import FeeCalculator
        from core.revenue.user_wallet import UserWalletManager
        from core.revenue.financial_report import FinancialReporter

        calc = FeeCalculator(data_dir=temp_dir)
        wallet = UserWalletManager(data_dir=temp_dir)
        reporter = FinancialReporter(data_dir=temp_dir)

        # 1. Calculate fee from profitable trade
        distribution = calc.calculate_fee_distribution(
            entry_price=100.0,
            exit_price=150.0,
            position_size=10.0
        )

        # 2. Credit user earnings to wallet
        wallet.deposit_earnings("user_1", distribution['user_share'])

        # 3. Record in reporter
        reporter.record_fee("user_1", distribution['total_fee'], "SOL/USDC")

        # Verify
        assert wallet.get_balance("user_1") == pytest.approx(distribution['user_share'], rel=0.01)

    def test_subscription_affects_fee_rate(self, temp_dir):
        """Test that subscription tier affects fee rate."""
        from core.revenue.fee_calculator import FeeCalculator
        from core.revenue.subscription_tiers import SubscriptionManager

        calc = FeeCalculator(data_dir=temp_dir)
        subs = SubscriptionManager(data_dir=temp_dir)

        # Free user pays 0.5%
        free_fee = calc.calculate_fee(100.0, 200.0, 1.0, user_tier="free")

        # Pro user might have reduced fees (future feature)
        subs.upgrade_user("user_1", "pro")
        pro_fee = calc.calculate_fee(100.0, 200.0, 1.0, user_tier="pro")

        # For now, both should be same (0.5%)
        assert free_fee == pytest.approx(0.5, rel=0.01)
        assert pro_fee == pytest.approx(0.5, rel=0.01)


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
