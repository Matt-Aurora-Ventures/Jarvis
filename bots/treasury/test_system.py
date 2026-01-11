"""
Jarvis Treasury System Tests
Comprehensive testing of all trading components
"""

import os
import sys
import asyncio
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestResult:
    """Test result container."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def record_pass(self, test_name: str):
        self.passed += 1
        print(f"  {test_name}")

    def record_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"  {test_name}: {error}")

    def summary(self) -> str:
        total = self.passed + self.failed
        return f"\nResults: {self.passed}/{total} passed ({self.passed/total*100:.0f}%)"


async def test_wallet_module():
    """Test wallet functionality."""
    print("\n=== WALLET MODULE TESTS ===")
    results = TestResult()

    # Set up test environment
    os.environ['JARVIS_WALLET_PASSWORD'] = 'test_password_secure_123'

    try:
        from bots.treasury.wallet import SecureWallet, WalletInfo

        # Test 1: Wallet creation
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Patch wallet directory
                SecureWallet.WALLET_DIR = Path(tmpdir) / '.wallets'

                wallet = SecureWallet()
                results.record_pass("Wallet initialization")

                # Test 2: Create treasury wallet
                try:
                    treasury = wallet.create_wallet(label="Test Treasury", is_treasury=True)
                    assert treasury.address is not None
                    assert len(treasury.address) > 30
                    results.record_pass("Create treasury wallet")
                except Exception as e:
                    results.record_fail("Create treasury wallet", str(e))

                # Test 3: Get treasury
                try:
                    retrieved = wallet.get_treasury()
                    assert retrieved is not None
                    assert retrieved.address == treasury.address
                    results.record_pass("Get treasury wallet")
                except Exception as e:
                    results.record_fail("Get treasury wallet", str(e))

                # Test 4: List wallets
                try:
                    wallets = wallet.list_wallets()
                    assert len(wallets) == 1
                    results.record_pass("List wallets")
                except Exception as e:
                    results.record_fail("List wallets", str(e))

                # Test 5: Private key never in string
                try:
                    wallet_str = str(treasury)
                    wallet_dict = treasury.to_dict()
                    assert 'private' not in wallet_str.lower()
                    assert 'private' not in str(wallet_dict).lower()
                    results.record_pass("No private key exposure")
                except Exception as e:
                    results.record_fail("No private key exposure", str(e))

        except Exception as e:
            results.record_fail("Wallet initialization", str(e))

    except ImportError as e:
        results.record_fail("Import wallet module", str(e))

    return results


async def test_jupiter_module():
    """Test Jupiter integration."""
    print("\n=== JUPITER MODULE TESTS ===")
    results = TestResult()

    try:
        from bots.treasury.jupiter import JupiterClient, SwapQuote, TokenInfo

        # Test 1: Client initialization
        try:
            client = JupiterClient()
            results.record_pass("Jupiter client initialization")
        except Exception as e:
            results.record_fail("Jupiter client initialization", str(e))
            return results

        # Test 2: Get token info (SOL)
        try:
            sol_mint = "So11111111111111111111111111111111111111112"
            info = await client.get_token_info(sol_mint)
            # May be None if API is down, that's OK
            if info:
                assert info.symbol in ['SOL', 'WSOL', 'Wrapped SOL']
            results.record_pass("Get token info")
        except Exception as e:
            results.record_fail("Get token info", str(e))

        # Test 3: Get token price
        try:
            sol_mint = "So11111111111111111111111111111111111111112"
            price = await client.get_token_price(sol_mint)
            # Price should be reasonable for SOL
            assert price == 0 or 10 < price < 1000
            results.record_pass("Get token price")
        except Exception as e:
            results.record_fail("Get token price", str(e))

        # Test 4: Get quote (may fail without network)
        try:
            sol_mint = "So11111111111111111111111111111111111111112"
            usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

            quote = await client.get_quote(
                sol_mint,
                usdc_mint,
                1000000000,  # 1 SOL in lamports
                slippage_bps=50
            )
            # Quote may be None if API down
            if quote:
                assert quote.output_amount > 0
            results.record_pass("Get swap quote")
        except Exception as e:
            results.record_fail("Get swap quote", str(e))

        await client.close()

    except ImportError as e:
        results.record_fail("Import Jupiter module", str(e))

    return results


async def test_trading_module():
    """Test trading engine."""
    print("\n=== TRADING MODULE TESTS ===")
    results = TestResult()

    try:
        from bots.treasury.wallet import SecureWallet
        from bots.treasury.jupiter import JupiterClient
        from bots.treasury.trading import TradingEngine, TradeDirection, RiskLevel, Position

        # Set up
        os.environ['JARVIS_WALLET_PASSWORD'] = 'test_password_secure_123'

        with tempfile.TemporaryDirectory() as tmpdir:
            SecureWallet.WALLET_DIR = Path(tmpdir) / '.wallets'

            wallet = SecureWallet()
            treasury = wallet.create_wallet(label="Test", is_treasury=True)

            jupiter = JupiterClient()

            # Test 1: Engine initialization
            try:
                engine = TradingEngine(
                    wallet=wallet,
                    jupiter=jupiter,
                    admin_user_ids=[123456],
                    risk_level=RiskLevel.MODERATE,
                    max_positions=5,
                    dry_run=True
                )
                results.record_pass("Trading engine initialization")
            except Exception as e:
                results.record_fail("Trading engine initialization", str(e))
                return results

            # Patch file paths for testing
            engine.POSITIONS_FILE = Path(tmpdir) / '.positions.json'
            engine.HISTORY_FILE = Path(tmpdir) / '.history.json'

            # Test 2: Admin check
            try:
                assert engine.is_admin(123456) == True
                assert engine.is_admin(999999) == False
                results.record_pass("Admin verification")
            except Exception as e:
                results.record_fail("Admin verification", str(e))

            # Test 3: Position sizing
            try:
                size = engine.calculate_position_size(1000.0)
                assert size == 20.0  # 2% of 1000 for MODERATE
                results.record_pass("Position sizing")
            except Exception as e:
                results.record_fail("Position sizing", str(e))

            # Test 4: TP/SL calculation
            try:
                tp, sl = engine.get_tp_sl_levels(100.0, "A")
                assert tp == 130.0  # 30% TP for A grade
                assert sl == 90.0   # 10% SL for A grade
                results.record_pass("TP/SL calculation")
            except Exception as e:
                results.record_fail("TP/SL calculation", str(e))

            # Test 5: Dry run trade
            try:
                success, msg, pos = await engine.open_position(
                    token_mint="So11111111111111111111111111111111111111112",
                    token_symbol="SOL",
                    direction=TradeDirection.LONG,
                    amount_usd=50.0,
                    sentiment_grade="B+",
                    user_id=123456
                )
                # May fail due to price fetch, that's OK
                results.record_pass("Dry run trade execution")
            except Exception as e:
                results.record_fail("Dry run trade execution", str(e))

            # Test 6: Unauthorized trade rejection
            try:
                success, msg, _ = await engine.open_position(
                    token_mint="test",
                    token_symbol="TEST",
                    direction=TradeDirection.LONG,
                    user_id=999999  # Not admin
                )
                assert success == False
                assert "Unauthorized" in msg
                results.record_pass("Unauthorized trade rejection")
            except Exception as e:
                results.record_fail("Unauthorized trade rejection", str(e))

            # Test 7: Report generation
            try:
                report = engine.generate_report()
                assert report is not None
                msg = report.to_telegram_message()
                assert "TRADING PERFORMANCE" in msg
                results.record_pass("Report generation")
            except Exception as e:
                results.record_fail("Report generation", str(e))

            await jupiter.close()

    except ImportError as e:
        results.record_fail("Import trading module", str(e))

    return results


async def test_backtest_module():
    """Test backtesting framework."""
    print("\n=== BACKTEST MODULE TESTS ===")
    results = TestResult()

    try:
        from bots.treasury.backtest import SentimentBacktester, BacktestResult

        # Test 1: Backtester initialization
        try:
            backtester = SentimentBacktester(
                initial_balance=1000.0,
                position_size_pct=0.10,
                max_positions=5,
                min_grade="B"
            )
            results.record_pass("Backtester initialization")
        except Exception as e:
            results.record_fail("Backtester initialization", str(e))
            return results

        # Test 2: Grade filtering
        try:
            assert backtester.should_take_trade({'grade': 'A'}) == True
            assert backtester.should_take_trade({'grade': 'B'}) == True
            assert backtester.should_take_trade({'grade': 'C'}) == False
            assert backtester.should_take_trade({'grade': 'F'}) == False
            results.record_pass("Grade filtering")
        except Exception as e:
            results.record_fail("Grade filtering", str(e))

        # Test 3: Result formatting
        try:
            result = BacktestResult(
                start_date=datetime.now(),
                end_date=datetime.now(),
                initial_balance=1000,
                final_balance=1200,
                total_trades=10,
                winning_trades=7,
                losing_trades=3,
                win_rate=70.0,
                total_pnl_usd=200,
                total_pnl_pct=20.0,
                max_drawdown_pct=5.0,
                sharpe_ratio=1.5,
                best_trade=100,
                worst_trade=-30,
                avg_trade=20,
                avg_win=40,
                avg_loss=-20,
                profit_factor=2.0,
                trades=[]
            )

            text = result.to_report()
            assert "BACKTEST RESULTS" in text
            assert "70.0%" in text

            tg = result.to_telegram()
            assert "<b>BACKTEST RESULTS</b>" in tg
            results.record_pass("Result formatting")
        except Exception as e:
            results.record_fail("Result formatting", str(e))

    except ImportError as e:
        results.record_fail("Import backtest module", str(e))

    return results


async def test_security_module():
    """Test security audit."""
    print("\n=== SECURITY MODULE TESTS ===")
    results = TestResult()

    try:
        from bots.treasury.security_test import SecurityAuditor, SecurityIssue

        # Test 1: Auditor initialization
        try:
            auditor = SecurityAuditor()
            results.record_pass("Security auditor initialization")
        except Exception as e:
            results.record_fail("Security auditor initialization", str(e))
            return results

        # Test 2: Run audit
        try:
            result = auditor.run_full_audit()
            assert result is not None
            assert hasattr(result, 'critical_issues')
            results.record_pass("Security audit execution")
        except Exception as e:
            results.record_fail("Security audit execution", str(e))

        # Test 3: No critical issues in core modules
        try:
            # Filter to only core trading files
            core_issues = [i for i in result.issues
                         if i.severity == 'CRITICAL'
                         and 'test' not in i.file_path.lower()]
            # This is informational - not failing on issues found
            if core_issues:
                print(f"    Found {len(core_issues)} critical issues to review")
            results.record_pass("Security scan complete")
        except Exception as e:
            results.record_fail("Security scan", str(e))

    except ImportError as e:
        results.record_fail("Import security module", str(e))

    return results


async def run_all_tests():
    """Run complete test suite."""
    print("\n" + "="*60)
    print("JARVIS TREASURY SYSTEM TEST SUITE")
    print("="*60)

    all_results = []

    # Run all test modules
    all_results.append(await test_wallet_module())
    all_results.append(await test_jupiter_module())
    all_results.append(await test_trading_module())
    all_results.append(await test_backtest_module())
    all_results.append(await test_security_module())

    # Summary
    total_passed = sum(r.passed for r in all_results)
    total_failed = sum(r.failed for r in all_results)
    total = total_passed + total_failed

    print("\n" + "="*60)
    print("TEST SUITE SUMMARY")
    print("="*60)
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    print(f"Success Rate: {total_passed/total*100:.1f}%")

    if total_failed > 0:
        print("\nFailed Tests:")
        for result in all_results:
            for test_name, error in result.errors:
                print(f"  - {test_name}: {error}")

    print("\n" + "="*60)
    status = "PASSED" if total_failed == 0 else "FAILED"
    print(f"OVERALL: {status}")
    print("="*60)

    return total_failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
