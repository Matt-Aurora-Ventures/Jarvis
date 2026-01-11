"""
Comprehensive Ape Button Test Suite

Tests:
1. All button combinations (9 buttons per token)
2. Validation edge cases
3. Execute trade validation
4. Backtest simulation (100 trades per profile)
5. Real trade simulation with 0.1 SOL treasury
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'c:/Users/lucid/OneDrive/Desktop/Projects/Jarvis')

import asyncio
from decimal import Decimal
from datetime import datetime
import random

from bots.buy_tracker.ape_buttons import (
    create_token_ape_keyboard,
    parse_ape_callback,
    create_trade_setup,
    execute_ape_trade,
    calculate_tp_sl_prices,
    TradeSetup,
    RiskProfile,
    RISK_PROFILE_CONFIG,
    APE_ALLOCATION_PCT,
)

TREASURY_BALANCE = 0.1  # SOL


def test_all_button_combinations():
    """Test all 9 button combinations for each token."""
    print("\n" + "=" * 70)
    print("TEST 1: ALL BUTTON COMBINATIONS (9 buttons per token)")
    print("=" * 70)

    test_tokens = [
        {"symbol": "BONK", "contract": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "price": 0.00001234, "grade": "B+"},
        {"symbol": "WIF", "contract": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "price": 2.45, "grade": "A-"},
        {"symbol": "POPCAT", "contract": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "price": 0.85, "grade": "B"},
    ]

    all_allocations = ["5", "2", "1"]
    all_profiles = ["s", "m", "d"]

    passed = 0
    failed = 0

    for token in test_tokens:
        print(f"\nToken: {token['symbol']} @ ${token['price']:.6f} (Grade: {token['grade']})")

        for alloc in all_allocations:
            for profile in all_profiles:
                callback = f"ape:{alloc}:{profile}:t:{token['symbol']}:{token['contract'][:10]}"
                parsed = parse_ape_callback(callback)

                if parsed:
                    setup = create_trade_setup(
                        parsed_callback=parsed,
                        entry_price=token['price'],
                        treasury_balance_sol=TREASURY_BALANCE,
                        direction='LONG',
                        grade=token['grade'],
                    )

                    is_valid, msg = setup.validate()

                    profile_name = {"s": "SAFE", "m": "MED", "d": "DEGEN"}[profile]
                    alloc_pct = APE_ALLOCATION_PCT[alloc]["percent"]

                    if is_valid:
                        passed += 1
                        status = "PASS"
                    else:
                        failed += 1
                        status = f"FAIL: {msg}"

                    print(f"  {alloc_pct}% {profile_name}: Amount={setup.amount_sol:.4f} SOL, TP=${setup.take_profit_price:.6f}, SL=${setup.stop_loss_price:.6f} [{status}]")
                else:
                    failed += 1
                    print(f"  {alloc}% {profile}: PARSE FAILED")

    print(f"\nButton Tests: {passed} passed, {failed} failed")
    return passed, failed


def test_validation_edge_cases():
    """Test validation edge cases."""
    print("\n" + "=" * 70)
    print("TEST 2: VALIDATION EDGE CASES (must reject invalid)")
    print("=" * 70)

    edge_cases = [
        {
            "name": "Zero TP price",
            "setup": TradeSetup(
                symbol="TEST", asset_type="token", direction="LONG",
                entry_price=1.0, take_profit_price=0, stop_loss_price=0.95,
                risk_profile=RiskProfile.SAFE, allocation_percent=5.0,
            ),
            "should_reject": True,
        },
        {
            "name": "Zero SL price",
            "setup": TradeSetup(
                symbol="TEST", asset_type="token", direction="LONG",
                entry_price=1.0, take_profit_price=1.15, stop_loss_price=0,
                risk_profile=RiskProfile.SAFE, allocation_percent=5.0,
            ),
            "should_reject": True,
        },
        {
            "name": "TP below entry (LONG)",
            "setup": TradeSetup(
                symbol="TEST", asset_type="token", direction="LONG",
                entry_price=1.0, take_profit_price=0.8, stop_loss_price=0.95,
                risk_profile=RiskProfile.SAFE, allocation_percent=5.0,
            ),
            "should_reject": True,
        },
        {
            "name": "SL above entry (LONG)",
            "setup": TradeSetup(
                symbol="TEST", asset_type="token", direction="LONG",
                entry_price=1.0, take_profit_price=1.15, stop_loss_price=1.05,
                risk_profile=RiskProfile.SAFE, allocation_percent=5.0,
            ),
            "should_reject": True,
        },
        {
            "name": "Allocation > 10%",
            "setup": TradeSetup(
                symbol="TEST", asset_type="token", direction="LONG",
                entry_price=1.0, take_profit_price=1.15, stop_loss_price=0.95,
                risk_profile=RiskProfile.SAFE, allocation_percent=15.0,
            ),
            "should_reject": True,
        },
        {
            "name": "Valid LONG trade",
            "setup": TradeSetup(
                symbol="TEST", asset_type="token", direction="LONG",
                entry_price=1.0, take_profit_price=1.30, stop_loss_price=0.90,
                risk_profile=RiskProfile.MEDIUM, allocation_percent=5.0,
            ),
            "should_reject": False,
        },
        {
            "name": "Valid SHORT trade",
            "setup": TradeSetup(
                symbol="TEST", asset_type="token", direction="SHORT",
                entry_price=1.0, take_profit_price=0.70, stop_loss_price=1.10,
                risk_profile=RiskProfile.MEDIUM, allocation_percent=5.0,
            ),
            "should_reject": False,
        },
    ]

    passed = 0
    failed = 0

    for case in edge_cases:
        is_valid, msg = case["setup"].validate()
        was_rejected = not is_valid

        if was_rejected == case["should_reject"]:
            passed += 1
            result = "PASS"
        else:
            failed += 1
            result = "FAIL"

        expected = "REJECT" if case["should_reject"] else "ACCEPT"
        actual = "REJECTED" if was_rejected else "ACCEPTED"

        print(f"  {case['name']}: Expected={expected}, Got={actual} [{result}]")
        if msg != "Valid":
            print(f"    Reason: {msg}")

    print(f"\nEdge Case Tests: {passed} passed, {failed} failed")
    return passed, failed


async def test_execute_trade():
    """Test execute trade validation."""
    print("\n" + "=" * 70)
    print("TEST 3: EXECUTE TRADE VALIDATION")
    print("=" * 70)

    tests = [
        {
            "name": "Valid trade execution",
            "callback": "ape:5:m:t:BONK:DezXAZ8z7P",
            "entry_price": 0.00001234,
            "should_validate": True,
        },
        {
            "name": "Missing entry price",
            "callback": "ape:5:m:t:BONK:DezXAZ8z7P",
            "entry_price": 0,
            "should_validate": False,
        },
        {
            "name": "Invalid callback",
            "callback": "invalid:data",
            "entry_price": 0.00001234,
            "should_validate": False,
        },
    ]

    passed = 0
    failed = 0

    for test in tests:
        result = await execute_ape_trade(
            callback_data=test["callback"],
            entry_price=test["entry_price"],
            treasury_balance_sol=TREASURY_BALANCE,
        )

        if test["should_validate"]:
            test_pass = result.trade_setup is not None or "not available" in result.error
        else:
            test_pass = "REJECTED" in result.error or "Invalid" in result.error

        if test_pass:
            passed += 1
            status = "PASS"
        else:
            failed += 1
            status = "FAIL"

        print(f"  {test['name']}: {status}")
        if result.error:
            print(f"    -> {result.error[:70]}...")
        if result.trade_setup:
            print(f"    -> TP: ${result.trade_setup.take_profit_price:.8f}, SL: ${result.trade_setup.stop_loss_price:.8f}")

    print(f"\nExecution Tests: {passed} passed, {failed} failed")
    return passed, failed


def test_backtest_simulation():
    """Run backtest simulation."""
    print("\n" + "=" * 70)
    print("TEST 4: BACKTEST SIMULATION (100 simulated trades)")
    print("=" * 70)

    def simulate_price_movement(entry_price, tp_price, sl_price, volatility=0.03):
        """Simulate price movement and determine outcome."""
        price = entry_price
        max_steps = 100

        for step in range(max_steps):
            change = random.gauss(0.002, volatility)
            price *= (1 + change)

            if price >= tp_price:
                return "WIN", step, price

            if price <= sl_price:
                return "LOSS", step, price

        if price > entry_price:
            return "PARTIAL_WIN", max_steps, price
        else:
            return "PARTIAL_LOSS", max_steps, price

    profiles = [RiskProfile.SAFE, RiskProfile.MEDIUM, RiskProfile.DEGEN]
    results_by_profile = {}

    for profile in profiles:
        config = RISK_PROFILE_CONFIG[profile]
        wins = 0
        losses = 0
        partial_wins = 0
        partial_losses = 0
        total_pnl = 0.0

        for _ in range(100):
            entry_price = 1.0
            tp_price, sl_price = calculate_tp_sl_prices(entry_price, profile, "LONG")

            outcome, steps, final_price = simulate_price_movement(entry_price, tp_price, sl_price)

            if outcome == "WIN":
                wins += 1
                pnl = config["tp_pct"]
            elif outcome == "LOSS":
                losses += 1
                pnl = -config["sl_pct"]
            elif outcome == "PARTIAL_WIN":
                partial_wins += 1
                pnl = ((final_price / entry_price) - 1) * 100
            else:
                partial_losses += 1
                pnl = ((final_price / entry_price) - 1) * 100

            total_pnl += pnl

        results_by_profile[profile] = {
            "wins": wins,
            "losses": losses,
            "partial_wins": partial_wins,
            "partial_losses": partial_losses,
            "total_pnl": total_pnl,
            "win_rate": (wins + partial_wins) / 100,
        }

    print("\nBacktest Results (100 trades per profile):")
    print("-" * 70)
    print(f"{'Profile':<10} {'Wins':<8} {'Losses':<8} {'Win Rate':<12} {'Total P&L':<12}")
    print("-" * 70)

    for profile, results in results_by_profile.items():
        config = RISK_PROFILE_CONFIG[profile]
        print(f"{config['label']:<10} {results['wins']:<8} {results['losses']:<8} {results['win_rate']*100:.1f}%{'':<7} {results['total_pnl']:>+.1f}%")

    return True


def test_real_trade_simulation():
    """Simulate real trades with 0.1 SOL treasury."""
    print("\n" + "=" * 70)
    print("TEST 5: REAL TRADE SIMULATION WITH 0.1 SOL TREASURY")
    print("=" * 70)

    print(f"\nTreasury Balance: {TREASURY_BALANCE} SOL (~$20 USD)")
    print("\nSimulated Trade Scenarios:")
    print("-" * 70)

    scenarios = [
        {"symbol": "BONK", "price": 0.00001234, "alloc": "5", "profile": "m", "grade": "B+"},
        {"symbol": "WIF", "price": 2.45, "alloc": "2", "profile": "s", "grade": "A-"},
        {"symbol": "POPCAT", "price": 0.85, "alloc": "1", "profile": "d", "grade": "B"},
    ]

    sol_price_usd = 200  # Approximate

    for scenario in scenarios:
        callback = f"ape:{scenario['alloc']}:{scenario['profile']}:t:{scenario['symbol']}:contract123"
        parsed = parse_ape_callback(callback)

        if parsed:
            setup = create_trade_setup(
                parsed_callback=parsed,
                entry_price=scenario['price'],
                treasury_balance_sol=TREASURY_BALANCE,
                direction='LONG',
                grade=scenario['grade'],
            )

            is_valid, msg = setup.validate()
            config = RISK_PROFILE_CONFIG[setup.risk_profile]

            amount_usd = setup.amount_sol * sol_price_usd
            max_gain_usd = amount_usd * config['tp_pct'] / 100
            max_loss_usd = amount_usd * config['sl_pct'] / 100

            print(f"\n{scenario['symbol']} ({scenario['grade']}) - {config['label']} {setup.allocation_percent}%:")
            print(f"  Entry:    ${setup.entry_price:.6f}")
            print(f"  Amount:   {setup.amount_sol:.4f} SOL (${amount_usd:.2f} USD)")
            print(f"  TP:       ${setup.take_profit_price:.6f} (+{config['tp_pct']}%)")
            print(f"  SL:       ${setup.stop_loss_price:.6f} (-{config['sl_pct']}%)")
            print(f"  Max Gain: ${max_gain_usd:.2f} USD")
            print(f"  Max Loss: ${max_loss_usd:.2f} USD")
            print(f"  R/R:      {config['tp_pct']/config['sl_pct']:.1f}:1")
            print(f"  Valid:    {'YES' if is_valid else 'NO - ' + msg}")


def main():
    print("=" * 70)
    print("COMPREHENSIVE APE BUTTON TEST SUITE")
    print("=" * 70)
    print(f"Treasury Balance: {TREASURY_BALANCE} SOL")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Run all tests
    btn_passed, btn_failed = test_all_button_combinations()
    edge_passed, edge_failed = test_validation_edge_cases()
    exec_passed, exec_failed = asyncio.run(test_execute_trade())
    test_backtest_simulation()
    test_real_trade_simulation()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    total_passed = btn_passed + edge_passed + exec_passed
    total_failed = btn_failed + edge_failed + exec_failed

    print(f"\nButton Combinations:  {btn_passed}/{btn_passed+btn_failed} passed")
    print(f"Edge Cases:           {edge_passed}/{edge_passed+edge_failed} passed")
    print(f"Execution Tests:      {exec_passed}/{exec_passed+exec_failed} passed")
    print(f"\nTOTAL:               {total_passed}/{total_passed+total_failed} passed")

    if total_failed == 0:
        print("\n[SUCCESS] ALL TESTS PASSED - TP/SL ENFORCEMENT WORKING CORRECTLY")
    else:
        print(f"\n[WARNING] {total_failed} tests failed - review needed")

    print("\n" + "=" * 70)

    return total_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
