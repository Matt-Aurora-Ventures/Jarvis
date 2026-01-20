"""
Unit tests for the tax reporting system.

Tests the following components:
- Cost basis tracking (FIFO, LIFO, HIFO)
- Gain/loss calculation
- Wash sale detection
- Tax lot optimization
- Export to CSV/TurboTax format
"""
import pytest
import tempfile
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch, MagicMock


class TestCostBasisMethods:
    """Tests for different cost basis calculation methods."""

    def test_fifo_cost_basis_single_lot(self):
        """FIFO should use first purchased lot for cost basis."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy 10 SOL at $100
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1"
        )

        # Sell 5 SOL at $150
        result = reporter.record_sell(
            symbol="SOL",
            quantity=5.0,
            price=150.0,
            timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
            tx_id="sell1"
        )

        assert result.cost_basis == 500.0  # 5 * $100
        assert result.proceeds == 750.0    # 5 * $150
        assert result.gain_loss == 250.0   # $750 - $500
        assert result.is_long_term is False

    def test_fifo_cost_basis_multiple_lots(self):
        """FIFO should deplete oldest lots first."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy 10 SOL at $100 (Jan)
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1"
        )

        # Buy 10 SOL at $200 (Feb)
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=200.0,
            timestamp=datetime(2024, 2, 1, tzinfo=timezone.utc),
            tx_id="buy2"
        )

        # Sell 15 SOL at $250 (June)
        result = reporter.record_sell(
            symbol="SOL",
            quantity=15.0,
            price=250.0,
            timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
            tx_id="sell1"
        )

        # FIFO: 10 @ $100 + 5 @ $200 = $1000 + $1000 = $2000
        assert result.cost_basis == 2000.0
        assert result.proceeds == 3750.0   # 15 * $250
        assert result.gain_loss == 1750.0

    def test_lifo_cost_basis(self):
        """LIFO should use most recently purchased lot first."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.LIFO)

        # Buy 10 SOL at $100 (Jan)
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1"
        )

        # Buy 10 SOL at $200 (Feb)
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=200.0,
            timestamp=datetime(2024, 2, 1, tzinfo=timezone.utc),
            tx_id="buy2"
        )

        # Sell 5 SOL at $250 (June)
        result = reporter.record_sell(
            symbol="SOL",
            quantity=5.0,
            price=250.0,
            timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
            tx_id="sell1"
        )

        # LIFO: 5 @ $200 = $1000
        assert result.cost_basis == 1000.0
        assert result.gain_loss == 250.0  # $1250 - $1000

    def test_hifo_cost_basis(self):
        """HIFO should use highest cost lots first to minimize gains."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.HIFO)

        # Buy 10 SOL at $100 (Jan)
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1"
        )

        # Buy 10 SOL at $200 (Feb)
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=200.0,
            timestamp=datetime(2024, 2, 1, tzinfo=timezone.utc),
            tx_id="buy2"
        )

        # Sell 5 SOL at $250 (June)
        result = reporter.record_sell(
            symbol="SOL",
            quantity=5.0,
            price=250.0,
            timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
            tx_id="sell1"
        )

        # HIFO: 5 @ $200 = $1000 (highest cost first)
        assert result.cost_basis == 1000.0
        assert result.gain_loss == 250.0  # $1250 - $1000


class TestShortLongTermGains:
    """Tests for short-term vs long-term gain classification."""

    def test_short_term_gain_under_one_year(self):
        """Gains held less than 1 year should be short-term."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy Jan 1, 2024
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1"
        )

        # Sell June 1, 2024 (5 months later)
        result = reporter.record_sell(
            symbol="SOL",
            quantity=10.0,
            price=150.0,
            timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
            tx_id="sell1"
        )

        assert result.is_long_term is False
        assert result.holding_period_days < 365

    def test_long_term_gain_over_one_year(self):
        """Gains held more than 1 year should be long-term."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy Jan 1, 2024
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1"
        )

        # Sell Feb 1, 2025 (>1 year later)
        result = reporter.record_sell(
            symbol="SOL",
            quantity=10.0,
            price=150.0,
            timestamp=datetime(2025, 2, 1, tzinfo=timezone.utc),
            tx_id="sell1"
        )

        assert result.is_long_term is True
        assert result.holding_period_days > 365

    def test_mixed_holding_periods_multiple_lots(self):
        """Sales spanning multiple lots should track holding period per lot."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy 10 SOL Jan 1, 2024
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1"
        )

        # Buy 10 SOL Jun 1, 2024
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=150.0,
            timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
            tx_id="buy2"
        )

        # Sell 15 SOL on Feb 1, 2025
        # First 10 from Jan 2024 lot (long-term)
        # Next 5 from Jun 2024 lot (short-term)
        result = reporter.record_sell(
            symbol="SOL",
            quantity=15.0,
            price=200.0,
            timestamp=datetime(2025, 2, 1, tzinfo=timezone.utc),
            tx_id="sell1"
        )

        # Should have both long-term and short-term components
        assert result.long_term_gain_loss is not None
        assert result.short_term_gain_loss is not None
        assert result.long_term_gain_loss > 0  # 10 * (200-100) = 1000
        assert result.short_term_gain_loss > 0  # 5 * (200-150) = 250


class TestWashSaleDetection:
    """Tests for wash sale rule detection."""

    def test_wash_sale_detected_buy_after_loss(self):
        """Should detect wash sale when repurchasing within 30 days of loss."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy 10 SOL at $100
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1"
        )

        # Sell at loss - $50 (Jan 15)
        reporter.record_sell(
            symbol="SOL",
            quantity=10.0,
            price=50.0,
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            tx_id="sell1"
        )

        # Buy back within 30 days (Jan 20)
        result = reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=55.0,
            timestamp=datetime(2024, 1, 20, tzinfo=timezone.utc),
            tx_id="buy2"
        )

        # Check wash sale detected
        wash_sales = reporter.get_wash_sales(year=2024)
        assert len(wash_sales) > 0
        assert wash_sales[0].disallowed_loss == 500.0  # 10 * ($100 - $50)

    def test_wash_sale_detected_buy_before_loss(self):
        """Should detect wash sale when purchased within 30 days before loss sale."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy 10 SOL at $100 (Jan 1)
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1"
        )

        # Buy 10 more SOL at $60 (Jan 10 - within 30 days before sell)
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=60.0,
            timestamp=datetime(2024, 1, 10, tzinfo=timezone.utc),
            tx_id="buy2"
        )

        # Sell first lot at loss (Jan 15)
        reporter.record_sell(
            symbol="SOL",
            quantity=10.0,
            price=50.0,
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            tx_id="sell1"
        )

        wash_sales = reporter.get_wash_sales(year=2024)
        assert len(wash_sales) > 0

    def test_no_wash_sale_after_31_days(self):
        """Should not flag wash sale when repurchase is after 30 days."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy 10 SOL at $100
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1"
        )

        # Sell at loss (Jan 15)
        reporter.record_sell(
            symbol="SOL",
            quantity=10.0,
            price=50.0,
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            tx_id="sell1"
        )

        # Buy back after 31 days (Feb 20)
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=55.0,
            timestamp=datetime(2024, 2, 20, tzinfo=timezone.utc),
            tx_id="buy2"
        )

        wash_sales = reporter.get_wash_sales(year=2024)
        assert len(wash_sales) == 0

    def test_wash_sale_adjusts_cost_basis(self):
        """Wash sale disallowed loss should be added to replacement lot cost basis."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy 10 SOL at $100
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1"
        )

        # Sell at loss - $50
        reporter.record_sell(
            symbol="SOL",
            quantity=10.0,
            price=50.0,
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            tx_id="sell1"
        )

        # Buy back within 30 days at $55
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=55.0,
            timestamp=datetime(2024, 1, 20, tzinfo=timezone.utc),
            tx_id="buy2"
        )

        # New lot should have adjusted cost basis: $55 + $50 disallowed loss = $105
        lots = reporter.get_lots(symbol="SOL")
        assert len(lots) == 1
        assert lots[0].adjusted_cost_basis == 105.0  # $55 + $50 disallowed


class TestTaxLotOptimization:
    """Tests for tax lot optimization (specific identification)."""

    def test_optimize_for_minimum_tax_selects_highest_cost(self):
        """Optimization for min tax should select highest cost lots."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy lots at different prices
        reporter.record_buy("SOL", 10.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
        reporter.record_buy("SOL", 10.0, 200.0, datetime(2024, 2, 1, tzinfo=timezone.utc), "buy2")
        reporter.record_buy("SOL", 10.0, 150.0, datetime(2024, 3, 1, tzinfo=timezone.utc), "buy3")

        # Optimize for minimum tax when selling 10 SOL at $180
        optimized = reporter.optimize_lots(
            symbol="SOL",
            quantity=10.0,
            sale_price=180.0,
            strategy="min_tax"
        )

        # Should select the $200 lot (highest cost = lowest gain)
        assert optimized[0].cost_per_unit == 200.0

    def test_optimize_for_long_term_prioritizes_old_lots(self):
        """Optimization for long-term should prioritize lots held >1 year."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Old lot (>1 year)
        reporter.record_buy("SOL", 10.0, 100.0, datetime(2023, 1, 1, tzinfo=timezone.utc), "buy1")
        # Recent lots
        reporter.record_buy("SOL", 10.0, 150.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "buy2")
        reporter.record_buy("SOL", 10.0, 200.0, datetime(2024, 7, 1, tzinfo=timezone.utc), "buy3")

        # Optimize for long-term gains (selling in Jan 2025)
        optimized = reporter.optimize_lots(
            symbol="SOL",
            quantity=10.0,
            sale_price=250.0,
            sale_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
            strategy="long_term_priority"
        )

        # Should select the 2023 lot (long-term eligible)
        assert optimized[0].purchase_date.year == 2023


class TestGainLossCalculation:
    """Tests for gain/loss calculations."""

    def test_gain_calculation_positive(self):
        """Should correctly calculate positive gains."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        reporter.record_buy("SOL", 10.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
        result = reporter.record_sell("SOL", 10.0, 150.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell1")

        assert result.gain_loss == 500.0  # (150-100) * 10

    def test_loss_calculation_negative(self):
        """Should correctly calculate negative gains (losses)."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        reporter.record_buy("SOL", 10.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
        result = reporter.record_sell("SOL", 10.0, 50.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell1")

        assert result.gain_loss == -500.0  # (50-100) * 10

    def test_fees_included_in_cost_basis(self):
        """Fees should be included in cost basis calculations."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy with fees
        reporter.record_buy(
            symbol="SOL",
            quantity=10.0,
            price=100.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tx_id="buy1",
            fee=10.0
        )

        # Sell with fees
        result = reporter.record_sell(
            symbol="SOL",
            quantity=10.0,
            price=150.0,
            timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
            tx_id="sell1",
            fee=15.0
        )

        # Cost basis = (100 * 10) + 10 = 1010
        # Proceeds = (150 * 10) - 15 = 1485
        # Gain = 1485 - 1010 = 475
        assert result.cost_basis == 1010.0
        assert result.proceeds == 1485.0
        assert result.gain_loss == 475.0


class TestAnnualSummary:
    """Tests for annual tax summary generation."""

    def test_annual_summary_totals(self):
        """Annual summary should correctly total all gains and losses."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Multiple transactions in 2024
        reporter.record_buy("SOL", 10.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
        reporter.record_sell("SOL", 10.0, 150.0, datetime(2024, 3, 1, tzinfo=timezone.utc), "sell1")  # +500

        reporter.record_buy("ETH", 5.0, 2000.0, datetime(2024, 2, 1, tzinfo=timezone.utc), "buy2")
        reporter.record_sell("ETH", 5.0, 1800.0, datetime(2024, 4, 1, tzinfo=timezone.utc), "sell2")  # -1000

        summary = reporter.get_annual_summary(year=2024)

        assert summary.total_proceeds == 150*10 + 1800*5  # 1500 + 9000 = 10500
        assert summary.total_cost_basis == 100*10 + 2000*5  # 1000 + 10000 = 11000
        assert summary.net_gain_loss == -500.0  # 500 - 1000

    def test_annual_summary_separates_short_long_term(self):
        """Annual summary should separate short-term and long-term gains."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Long-term gain (held >1 year)
        reporter.record_buy("SOL", 10.0, 100.0, datetime(2023, 1, 1, tzinfo=timezone.utc), "buy1")
        reporter.record_sell("SOL", 10.0, 200.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell1")

        # Short-term gain (held <1 year)
        reporter.record_buy("ETH", 5.0, 2000.0, datetime(2024, 3, 1, tzinfo=timezone.utc), "buy2")
        reporter.record_sell("ETH", 5.0, 2500.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell2")

        summary = reporter.get_annual_summary(year=2024)

        assert summary.short_term_gain == 2500.0  # (2500-2000) * 5
        assert summary.long_term_gain == 1000.0   # (200-100) * 10


class TestExportFormats:
    """Tests for tax report export functionality."""

    def test_export_to_csv(self):
        """Should export transactions to CSV format."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        reporter.record_buy("SOL", 10.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
        reporter.record_sell("SOL", 10.0, 150.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell1")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name

        reporter.export_to_csv(csv_path, year=2024)

        # Read and verify CSV
        with open(csv_path, 'r') as f:
            content = f.read()

        assert "SOL" in content
        assert "150" in content  # Sale price
        assert "100" in content  # Cost basis per unit

    def test_export_to_turbotax_format(self):
        """Should export to TurboTax-compatible format."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        reporter.record_buy("SOL", 10.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
        reporter.record_sell("SOL", 10.0, 150.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell1")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name

        reporter.export_to_turbotax(csv_path, year=2024)

        with open(csv_path, 'r') as f:
            content = f.read()

        # TurboTax format should have specific columns
        assert "Description" in content or "description" in content.lower()
        assert "Date Acquired" in content or "date_acquired" in content.lower()
        assert "Date Sold" in content or "date_sold" in content.lower()
        assert "Proceeds" in content or "proceeds" in content.lower()
        assert "Cost Basis" in content or "cost_basis" in content.lower()

    def test_export_8949_format(self):
        """Should export in IRS Form 8949 format."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        reporter.record_buy("SOL", 10.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
        reporter.record_sell("SOL", 10.0, 150.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell1")

        report = reporter.generate_8949_report(year=2024)

        # Form 8949 should have Part I (short-term) or Part II (long-term)
        assert "part_i" in report or "part_ii" in report
        assert report.get("part_i") or report.get("part_ii")


class TestDatabasePersistence:
    """Tests for database storage and retrieval."""

    def test_transactions_persist_across_instances(self):
        """Transactions should persist and be retrievable in new instances."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "tax.db"

            # First instance - record transactions
            reporter1 = TaxReporter(
                cost_basis_method=CostBasisMethod.FIFO,
                db_path=db_path
            )
            reporter1.record_buy("SOL", 10.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
            reporter1.record_sell("SOL", 5.0, 150.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell1")

            # Second instance - verify data
            reporter2 = TaxReporter(
                cost_basis_method=CostBasisMethod.FIFO,
                db_path=db_path
            )

            lots = reporter2.get_lots(symbol="SOL")
            assert len(lots) == 1
            assert lots[0].remaining_quantity == 5.0

    def test_lot_tracking_accuracy(self):
        """Should accurately track remaining quantities in tax lots."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        reporter.record_buy("SOL", 10.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
        reporter.record_buy("SOL", 10.0, 150.0, datetime(2024, 2, 1, tzinfo=timezone.utc), "buy2")

        # Partial sell from first lot
        reporter.record_sell("SOL", 3.0, 200.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell1")

        lots = reporter.get_lots(symbol="SOL")
        assert len(lots) == 2

        # First lot should have 7 remaining
        first_lot = [l for l in lots if l.cost_per_unit == 100.0][0]
        assert first_lot.remaining_quantity == 7.0

        # Second lot should be untouched
        second_lot = [l for l in lots if l.cost_per_unit == 150.0][0]
        assert second_lot.remaining_quantity == 10.0


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_sell_more_than_available_raises_error(self):
        """Should raise error when selling more than available."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod, InsufficientLotsError

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        reporter.record_buy("SOL", 10.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")

        with pytest.raises(InsufficientLotsError):
            reporter.record_sell("SOL", 15.0, 150.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell1")

    def test_multiple_symbols_tracked_independently(self):
        """Different symbols should have independent lot tracking."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        reporter.record_buy("SOL", 10.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
        reporter.record_buy("ETH", 5.0, 2000.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy2")

        sol_lots = reporter.get_lots(symbol="SOL")
        eth_lots = reporter.get_lots(symbol="ETH")

        assert len(sol_lots) == 1
        assert len(eth_lots) == 1
        assert sol_lots[0].symbol == "SOL"
        assert eth_lots[0].symbol == "ETH"

    def test_zero_quantity_transaction_rejected(self):
        """Should reject transactions with zero quantity."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        with pytest.raises(ValueError):
            reporter.record_buy("SOL", 0.0, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")

    def test_negative_price_rejected(self):
        """Should reject transactions with negative prices."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        with pytest.raises(ValueError):
            reporter.record_buy("SOL", 10.0, -100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")

    def test_fractional_quantities_supported(self):
        """Should handle fractional quantities correctly."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        reporter.record_buy("SOL", 0.5, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
        result = reporter.record_sell("SOL", 0.25, 200.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell1")

        assert result.quantity == 0.25
        assert result.cost_basis == 25.0   # 0.25 * 100
        assert result.proceeds == 50.0     # 0.25 * 200
        assert result.gain_loss == 25.0

    def test_very_small_quantities_precision(self):
        """Should maintain precision for very small quantities (crypto decimals)."""
        from core.reporting.tax_reporter import TaxReporter, CostBasisMethod

        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Buy small amount
        reporter.record_buy("BTC", 0.00001, 50000.0, datetime(2024, 1, 1, tzinfo=timezone.utc), "buy1")
        result = reporter.record_sell("BTC", 0.00001, 60000.0, datetime(2024, 6, 1, tzinfo=timezone.utc), "sell1")

        assert abs(result.cost_basis - 0.5) < 0.0001   # 0.00001 * 50000
        assert abs(result.proceeds - 0.6) < 0.0001     # 0.00001 * 60000
        assert abs(result.gain_loss - 0.1) < 0.0001
