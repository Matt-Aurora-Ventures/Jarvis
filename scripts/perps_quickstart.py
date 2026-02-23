"""perps_quickstart.py — Validate Jupiter Perps setup and run smoke tests.

Usage:
    python scripts/perps_quickstart.py            # validate + smoke test
    python scripts/perps_quickstart.py --dry-run   # test runner in dry-run mode (10s)
    python scripts/perps_quickstart.py --signals    # test AI signal extraction (needs XAI_API_KEY)

This script:
    1. Checks all imports work
    2. Verifies IDL integrity
    3. Runs position manager, cost gate, and self-adjuster smoke tests
    4. Optionally tests the full runner in dry-run mode
    5. Optionally tests live AI signal extraction
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def _header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _skip(msg: str) -> None:
    print(f"  [SKIP] {msg}")


def check_imports() -> bool:
    """Step 1: Verify all module imports work."""
    _header("Step 1: Import Check")
    all_ok = True

    modules = [
        ("core.jupiter_perps.intent", "Intent schema"),
        ("core.jupiter_perps.execution_service", "Execution service"),
        ("core.jupiter_perps.event_journal", "Event journal"),
        ("core.jupiter_perps.reconciliation", "Reconciliation"),
        ("core.jupiter_perps.position_manager", "Position manager"),
        ("core.jupiter_perps.cost_gate", "Cost gate"),
        ("core.jupiter_perps.self_adjuster", "Self-adjuster"),
        ("core.jupiter_perps.ai_signal_bridge", "AI signal bridge"),
        ("core.jupiter_perps.runner", "Runner"),
        ("core.backtesting.jupiter_fee_adapter", "Fee adapter"),
    ]

    for mod_path, desc in modules:
        try:
            __import__(mod_path)
            _ok(f"{desc} ({mod_path})")
        except Exception as e:
            _fail(f"{desc} ({mod_path}): {e}")
            all_ok = False

    return all_ok


def check_idl() -> bool:
    """Step 2: Verify IDL integrity."""
    _header("Step 2: IDL Integrity")
    try:
        from core.jupiter_perps.integrity import verify_idl
        verify_idl(fatal=False)
        _ok("IDL hash verification passed")
        return True
    except Exception as e:
        _fail(f"IDL verification: {e}")
        return False


def check_deps() -> bool:
    """Step 3: Check key dependencies."""
    _header("Step 3: Dependencies")
    all_ok = True

    deps = [
        ("anchorpy", "0.21.0"),
        ("solders", "0.26.0"),
        ("solana", "0.36.6"),
    ]

    for pkg, expected_version in deps:
        try:
            from importlib.metadata import version
            installed = version(pkg)
            if installed == expected_version:
                _ok(f"{pkg} {installed}")
            else:
                _fail(f"{pkg} {installed} (expected {expected_version})")
                all_ok = False
        except Exception:
            _fail(f"{pkg} not installed")
            all_ok = False

    # Optional deps
    for pkg in ["httpx"]:
        try:
            __import__(pkg)
            _ok(f"{pkg} (optional, installed)")
        except ImportError:
            _skip(f"{pkg} (optional, will use stdlib fallback)")

    return all_ok


def smoke_test_position_manager() -> bool:
    """Step 4: Smoke test position manager."""
    _header("Step 4: Position Manager Smoke Test")
    try:
        from core.jupiter_perps.position_manager import PositionManager, PositionManagerConfig

        pm = PositionManager(PositionManagerConfig())

        # Register a position
        pm.register_open(
            idempotency_key="smoke-test-1",
            market="SOL-USD",
            side="long",
            size_usd=500.0,
            collateral_usd=100.0,
            leverage=5.0,
            entry_price=150.0,
            source="smoke_test",
        )
        assert pm.get_position_count() == 1, "Position not registered"
        _ok("Position registered")

        # Update price (no exit expected)
        exits = pm.update_price("SOL-USD", 152.0)
        assert len(exits) == 0, f"Unexpected exits: {exits}"
        _ok("Price update (no exit)")

        # Trigger stop loss
        exits = pm.update_price("SOL-USD", 148.5)  # -5% P&L at 5x leverage
        assert len(exits) == 1, "Stop loss should fire"
        assert exits[0].trigger == "stop_loss"
        _ok(f"Stop loss triggered: {exits[0].reason}")

        # Mark closed
        closed = pm.mark_closed("smoke-test-1")
        assert closed is not None
        assert pm.get_position_count() == 0
        _ok("Position closed and removed")

        return True
    except Exception as e:
        _fail(f"Position manager: {e}")
        return False


def smoke_test_cost_gate() -> bool:
    """Step 5: Smoke test cost gate."""
    _header("Step 5: Cost Gate Smoke Test")
    try:
        from core.jupiter_perps.cost_gate import CostGate, CostGateConfig
        from core.jupiter_perps.position_manager import PositionManager, PositionManagerConfig

        gate = CostGate(CostGateConfig())
        pm = PositionManager(PositionManagerConfig())

        # Should pass with empty portfolio
        verdict = gate.evaluate(
            market="SOL-USD",
            side="long",
            size_usd=500.0,
            leverage=5.0,
            confidence=0.85,
            position_manager=pm,
        )
        assert verdict.passed, f"Should pass: {verdict.reason}"
        _ok(f"Trade approved (hurdle={verdict.hurdle_rate_pct:.2f}%, fees=${verdict.total_fees_usd:.2f})")

        # Fill up positions
        for i in range(5):
            pm.register_open(f"k{i}", f"{'SOL' if i < 2 else 'BTC' if i < 4 else 'ETH'}-USD",
                             "long", 800.0, 160.0, 5.0, 100.0, "test")

        # Should reject (max positions)
        verdict = gate.evaluate("SOL-USD", "short", 500.0, 5.0, 0.90, pm)
        assert not verdict.passed
        _ok(f"Correctly rejected: {verdict.reason}")

        return True
    except Exception as e:
        _fail(f"Cost gate: {e}")
        return False


def smoke_test_self_adjuster() -> bool:
    """Step 6: Smoke test self-adjuster."""
    _header("Step 6: Self-Adjuster Smoke Test")
    try:
        from core.jupiter_perps.self_adjuster import PerpsAutoTuner, TradeOutcome, TunerConfig

        tuner = PerpsAutoTuner(TunerConfig(min_trades=3))

        # Record some outcomes
        for i in range(5):
            tuner.record_outcome(TradeOutcome(
                source="grok_perps",
                asset="SOL",
                direction="long",
                confidence_at_entry=0.80,
                entry_price=100.0,
                exit_price=105.0 if i % 3 != 0 else 97.0,
                pnl_usd=50.0 if i % 3 != 0 else -30.0,
                pnl_pct=5.0 if i % 3 != 0 else -3.0,
                hold_hours=4.0,
                fees_usd=2.0,
                exit_trigger="take_profit" if i % 3 != 0 else "stop_loss",
            ))

        _ok(f"Recorded {len(tuner._outcomes)} outcomes")

        # Check weights updated
        weights = tuner.get_weights()
        _ok(f"Current weights: {', '.join(f'{k}={v:.3f}' for k, v in weights.items())}")

        # Check size multiplier
        mult = tuner.get_position_size_multiplier("grok_perps")
        _ok(f"Size multiplier for grok_perps: {mult:.3f}")

        # Summary
        summary = tuner.get_summary()
        _ok(f"Tuner summary: {summary['total_outcomes']} outcomes, "
            f"{summary['trades_since_tune']} since tune")

        return True
    except Exception as e:
        _fail(f"Self-adjuster: {e}")
        return False


def smoke_test_signal_bridge() -> bool:
    """Step 7: Smoke test signal bridge (signal->intent conversion)."""
    _header("Step 7: Signal Bridge Smoke Test")
    try:
        from core.jupiter_perps.ai_signal_bridge import (
            AISignal, signal_to_intent, merge_signals,
        )
        from core.jupiter_perps.intent import OpenPosition

        # Test single signal conversion
        signal = AISignal(
            asset="SOL", direction="long", confidence=0.85,
            regime="bull", source="grok_perps", rationale="Test signal",
        )
        intent = signal_to_intent(signal)
        assert intent is not None
        assert isinstance(intent, OpenPosition)
        _ok(f"Signal -> intent: {intent.market} {intent.side.value} {intent.leverage}x ${intent.size_usd:.0f}")

        # Test merge
        signals = [
            AISignal("SOL", "long", 0.80, "bull", "grok_perps", "Grok signal"),
            AISignal("SOL", "long", 0.75, "bull", "momentum", "Momentum signal"),
        ]
        merged = merge_signals(signals)
        assert len(merged) == 1
        _ok(f"Merge: 2 signals -> confidence={merged[0].confidence:.3f} source={merged[0].source}")

        # Test conflicting signals are dropped
        conflicting = [
            AISignal("BTC", "long", 0.80, "bull", "grok_perps", "Grok long"),
            AISignal("BTC", "short", 0.75, "bear", "momentum", "Momentum short"),
        ]
        merged = merge_signals(conflicting)
        assert len(merged) == 0
        _ok("Conflicting signals correctly dropped")

        # Below confidence threshold -> dropped
        weak = AISignal("SOL", "long", 0.50, "ranging", "aggregate", "Weak")
        assert signal_to_intent(weak) is None
        _ok("Sub-threshold signal correctly dropped")

        return True
    except Exception as e:
        _fail(f"Signal bridge: {e}")
        return False


async def test_live_signals() -> bool:
    """Test live AI signal extraction (requires XAI_API_KEY)."""
    _header("Live AI Signal Test (Grok)")

    xai_key = os.environ.get("XAI_API_KEY", "")
    if not xai_key:
        _skip("XAI_API_KEY not set — skipping live signal test")
        return True

    try:
        from core.jupiter_perps.ai_signal_bridge import _extract_perps_signals

        print("  Calling Grok API (this may take 10-20s)...")
        start = time.time()
        signals = await _extract_perps_signals()
        elapsed = time.time() - start

        if signals:
            for s in signals:
                _ok(f"{s.asset} {s.direction} conf={s.confidence:.2f} "
                    f"regime={s.regime} ({elapsed:.1f}s)")
        else:
            _skip(f"Grok returned no actionable signals ({elapsed:.1f}s)")

        return True
    except Exception as e:
        _fail(f"Live signal test: {e}")
        return False


async def test_dry_runner() -> bool:
    """Run the full runner in dry-run mode for 10 seconds."""
    _header("Dry-Run Runner Test (10s)")

    try:
        from core.jupiter_perps.runner import build_parser, run_runner

        args = build_parser().parse_args([
            "--dry-run",
            "--runtime-seconds=10",
            "--heartbeat-seconds=3",
        ])
        args.enable_macro = False
        args.enable_ai_bridge = False  # Skip AI for quick test

        print("  Starting runner (dry-run, 10s)...")
        start = time.time()
        await run_runner(args)
        elapsed = time.time() - start
        _ok(f"Runner completed in {elapsed:.1f}s")
        return True
    except Exception as e:
        _fail(f"Dry-run runner: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Jupiter Perps quickstart validator")
    parser.add_argument("--dry-run", action="store_true", help="Test the full runner in dry-run mode")
    parser.add_argument("--signals", action="store_true", help="Test live AI signal extraction")
    args = parser.parse_args()

    print("\nJupiter Perps Quickstart Validator")
    print("=" * 60)

    results: list[tuple[str, bool]] = []

    # Core checks
    results.append(("Imports", check_imports()))
    results.append(("IDL Integrity", check_idl()))
    results.append(("Dependencies", check_deps()))
    results.append(("Position Manager", smoke_test_position_manager()))
    results.append(("Cost Gate", smoke_test_cost_gate()))
    results.append(("Self-Adjuster", smoke_test_self_adjuster()))
    results.append(("Signal Bridge", smoke_test_signal_bridge()))

    # Optional live tests
    if args.signals:
        results.append(("Live Signals", asyncio.run(test_live_signals())))

    if args.dry_run:
        results.append(("Dry-Run Runner", asyncio.run(test_dry_runner())))

    # Summary
    _header("Summary")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\n  {passed}/{total} checks passed")

    if passed == total:
        print("\n  All checks passed! System is ready for testing.")
        print("\n  Next steps:")
        print("    1. Copy core/jupiter_perps/.env.example to .env")
        print("    2. Add your XAI_API_KEY")
        print("    3. Run: python scripts/perps_quickstart.py --dry-run")
        print("    4. Run: python scripts/perps_quickstart.py --signals")
        print("    5. Set PERPS_AI_MODE=alert for alert-only mode")
        print("    6. Full runner: python -m core.jupiter_perps.runner --dry-run --enable-ai-bridge")
    else:
        print("\n  Some checks failed. Fix the issues above before testing.")
        sys.exit(1)


if __name__ == "__main__":
    main()
