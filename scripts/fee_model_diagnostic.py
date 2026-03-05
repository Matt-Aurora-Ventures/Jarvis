"""
Fee Model Diagnostic - Apply realistic costs to all backtested strategies.

Reads strategy_recommendations.json (27 strategies with backtest metrics)
and backtest_trades.csv (126 individual trades), then re-calculates
net expectancy using the Phase 2A realistic fee model.

Reports:
  1. How many strategies now show negative expected value
  2. Minimum edge required per asset class tier
  3. Which strategies should be archived vs. ported to PyBroker
"""

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.trading.fee_model import (
    calculate_trade_cost,
    LiquidityTier,
    MINIMUM_EDGE_TO_COST_RATIO,
)
from core.data.asset_registry import AssetClass


# ---------------------------------------------------------------------------
# Strategy → Asset Class / Liquidity Tier mapping
# ---------------------------------------------------------------------------

# Map each strategy to (AssetClass, typical_pool_liquidity_usd, typical_trade_size_usd)
STRATEGY_CLASSIFICATION = {
    # xStock strategies
    "xstock_intraday":       (AssetClass.XSTOCK,           200_000,  500),
    "xstock_swing":          (AssetClass.XSTOCK,           200_000,  500),
    "index_intraday":        (AssetClass.XSTOCK,           200_000,  500),
    "index_leveraged":       (AssetClass.XSTOCK,           200_000,  500),
    "prestock_speculative":  (AssetClass.XSTOCK,           100_000,  300),

    # Large-cap / Blue-chip (SOL, JUP, RAY, BONK)
    "bluechip_trend_follow": (AssetClass.NATIVE_SOLANA,  5_000_000,  500),
    "bluechip_breakout":     (AssetClass.NATIVE_SOLANA,  5_000_000,  500),
    "sol_veteran":           (AssetClass.NATIVE_SOLANA,  5_000_000,  500),

    # Mid-cap / Utility tokens
    "utility_swing":         (AssetClass.MEMECOIN,         500_000,  500),
    "established_breakout":  (AssetClass.MEMECOIN,         500_000,  500),

    # General memecoin / mid strategies
    "micro_cap_surge":       (AssetClass.MEMECOIN,          50_000,  300),
    "momentum":              (AssetClass.MEMECOIN,         300_000,  500),
    "hybrid_b":              (AssetClass.MEMECOIN,         300_000,  500),
    "elite":                 (AssetClass.MEMECOIN,         300_000,  500),
    "let_it_ride":           (AssetClass.MEMECOIN,         200_000,  500),
    "meme_classic":          (AssetClass.MEMECOIN,         200_000,  500),
    "volume_spike":          (AssetClass.MEMECOIN,         200_000,  500),

    # Bags.fm strategies (post-graduation unless noted)
    "bags_dip_buyer":        (AssetClass.BAGS_GRADUATED,   100_000,  200),
    "bags_fresh_snipe":      (AssetClass.BAGS_BONDING_CURVE, 30_000, 100),
    "bags_momentum":         (AssetClass.BAGS_GRADUATED,    80_000,  200),
    "bags_aggressive":       (AssetClass.BAGS_BONDING_CURVE, 30_000, 150),
    "bags_value":            (AssetClass.BAGS_GRADUATED,   150_000,  200),
    "bags_conservative":     (AssetClass.BAGS_GRADUATED,   150_000,  200),
    "bags_elite":            (AssetClass.BAGS_GRADUATED,   200_000,  200),
    "bags_bluechip":         (AssetClass.BAGS_GRADUATED,   300_000,  300),

    # Pump.fun sniper
    "pump_fresh_tight":      (AssetClass.BAGS_BONDING_CURVE, 25_000, 100),
}

# From CSV analysis: old backtest fee model charged ~0.8% round-trip
OLD_BACKTEST_RT_COST_PCT = 0.008  # 0.8%


def load_strategies():
    """Load strategy recommendations from jarvis-sniper backtest results."""
    path = ROOT / "jarvis-sniper" / "backtest-data" / "results" / "strategy_recommendations.json"
    with open(path, "r") as f:
        return json.load(f)


def load_trades():
    """Load individual trade records from CSV."""
    path = ROOT / "jarvis-sniper" / "docs" / "backtest_trades.csv"
    trades = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)
    return trades


def analyze_old_fee_from_trades(trades):
    """Calculate average old fee from pnl_gross vs pnl_net differences."""
    diffs = []
    for t in trades:
        gross = float(t["pnl_gross_pct"])
        net = float(t["pnl_net_pct"])
        diff = gross - net
        diffs.append(diff)
    if diffs:
        return sum(diffs) / len(diffs)
    return 0.8  # fallback


def main():
    strategies = load_strategies()
    trades = load_trades()

    # Verify old fee model cost from actual trade data
    avg_old_fee = analyze_old_fee_from_trades(trades)
    print("=" * 80)
    print("  FEE MODEL DIAGNOSTIC - Phase 2A Realistic Cost Analysis")
    print("=" * 80)
    print()
    print(f"Old backtest fee model (avg pnl_gross - pnl_net): {avg_old_fee:.4f}% per trade")
    print(f"Using {avg_old_fee:.4f}% as old round-trip cost to recover gross expectancy")
    print()

    # -----------------------------------------------------------------------
    # Part 1: Minimum edge required per asset class tier
    # -----------------------------------------------------------------------
    print(f"\n{'-' * 80}")
    print("PART 1: Minimum Edge Required Per Asset Class (Phase 2A Fee Model)")
    print(f"{'-' * 80}")
    print()
    print(f"{'Tier':<25} {'Pool Size':>12} {'Trade Size':>12} {'RT Cost':>10} {'Min Edge':>10}")
    print(f"{'-'*25} {'-'*12} {'-'*12} {'-'*10} {'-'*10}")

    tier_scenarios = [
        ("HIGH (SOL/USDC)",    AssetClass.NATIVE_SOLANA,      5_000_000, 500),
        ("MID (memecoin >$100K)", AssetClass.MEMECOIN,           300_000, 500),
        ("MICRO (memecoin <$100K)", AssetClass.MEMECOIN,          50_000, 300),
        ("BAGS pre-grad",       AssetClass.BAGS_BONDING_CURVE,   30_000, 100),
        ("BAGS post-grad",      AssetClass.BAGS_GRADUATED,      100_000, 200),
        ("XSTOCK",              AssetClass.XSTOCK,              200_000, 500),
    ]

    tier_min_edges = {}
    for label, ac, pool, trade in tier_scenarios:
        cost = calculate_trade_cost(ac, pool, trade)
        min_edge = cost.total_round_trip_pct * MINIMUM_EDGE_TO_COST_RATIO
        tier_min_edges[label] = (cost.total_round_trip_pct, min_edge)
        print(f"{label:<25} ${pool:>10,} ${trade:>10,} {cost.total_round_trip_pct:>9.2%} {min_edge:>9.2%}")

    # -----------------------------------------------------------------------
    # Part 2: Per-strategy analysis
    # -----------------------------------------------------------------------
    print(f"\n{'-' * 80}")
    print("PART 2: Strategy-by-Strategy Impact Analysis")
    print(f"{'-' * 80}")
    print()

    header = (
        f"{'Strategy':<25} {'AssetClass':<18} {'Old Exp%':>8} {'RT Cost':>8} "
        f"{'New Exp%':>9} {'Status':>12} {'Verdict':>10}"
    )
    print(header)
    print("-" * len(header))

    results = []
    negative_count = 0
    marginal_count = 0
    viable_count = 0
    already_negative = 0

    for strat in strategies:
        algo_id = strat["algo_id"]
        old_exp_pct = strat["metrics"]["expectancy_pct"] / 100  # Convert from % to fraction
        old_wr = strat["metrics"]["win_rate"] / 100
        old_pf = strat["metrics"]["profit_factor"]
        n_trades = strat["metrics"]["trades"]

        # Get classification
        if algo_id not in STRATEGY_CLASSIFICATION:
            print(f"  WARNING: {algo_id} not in classification map, skipping")
            continue

        ac, pool_liq, trade_size = STRATEGY_CLASSIFICATION[algo_id]
        cost = calculate_trade_cost(ac, pool_liq, trade_size)

        # Recover gross expectancy by adding back old fee, then subtract new fee
        gross_exp = old_exp_pct + (avg_old_fee / 100)  # avg_old_fee is in pct points
        new_net_exp = gross_exp - cost.total_round_trip_pct

        # Classify verdict
        if old_exp_pct <= 0:
            verdict = "DEAD"
            status = "neg_before"
            already_negative += 1
        elif new_net_exp <= 0:
            verdict = "ARCHIVE"
            status = "neg_after"
            negative_count += 1
        elif new_net_exp < cost.total_round_trip_pct:
            # Edge exists but < cost → marginal (edge-to-cost < 1.0)
            verdict = "MARGINAL"
            status = "marginal"
            marginal_count += 1
        elif new_net_exp < cost.total_round_trip_pct * MINIMUM_EDGE_TO_COST_RATIO:
            # Edge > cost but < 2x cost → risky
            verdict = "RISKY"
            status = "risky"
            marginal_count += 1
        else:
            verdict = "VIABLE"
            status = "viable"
            viable_count += 1

        ac_label = ac.value.replace("_", " ")[:16]
        print(
            f"{algo_id:<25} {ac_label:<18} {old_exp_pct:>7.2%} {cost.total_round_trip_pct:>7.2%} "
            f"{new_net_exp:>8.2%} {status:>12} {verdict:>10}"
        )

        results.append({
            "algo_id": algo_id,
            "asset_class": ac.value,
            "pool_liquidity": pool_liq,
            "old_expectancy_pct": round(old_exp_pct * 100, 2),
            "round_trip_cost_pct": round(cost.total_round_trip_pct * 100, 2),
            "gross_expectancy_pct": round(gross_exp * 100, 2),
            "new_net_expectancy_pct": round(new_net_exp * 100, 2),
            "verdict": verdict,
            "n_trades": n_trades,
            "win_rate": old_wr,
            "profit_factor": old_pf,
        })

    # -----------------------------------------------------------------------
    # Part 3: Summary
    # -----------------------------------------------------------------------
    total = len(results)
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print()
    print(f"Total strategies analyzed:              {total}")
    print(f"Already negative EV (before fee fix):   {already_negative}")
    print(f"Flipped to NEGATIVE EV by realistic fees: {negative_count}")
    print(f"MARGINAL / RISKY (edge < 2x cost):      {marginal_count}")
    print(f"VIABLE (edge >= 2x cost):               {viable_count}")
    print()
    print(f"TOTAL with negative EV after fee fix:   {already_negative + negative_count} / {total} ({(already_negative + negative_count)/total:.0%})")
    print(f"TOTAL non-viable (neg + marginal):      {already_negative + negative_count + marginal_count} / {total} ({(already_negative + negative_count + marginal_count)/total:.0%})")
    print()

    # -----------------------------------------------------------------------
    # Part 4: Recommendations
    # -----------------------------------------------------------------------
    print(f"{'-' * 80}")
    print("RECOMMENDATIONS")
    print(f"{'-' * 80}")
    print()

    archive = [r for r in results if r["verdict"] in ("ARCHIVE", "DEAD")]
    marginals = [r for r in results if r["verdict"] in ("MARGINAL", "RISKY")]
    viables = [r for r in results if r["verdict"] == "VIABLE"]

    if archive:
        print("ARCHIVE IMMEDIATELY (negative EV after realistic fees):")
        for r in archive:
            print(f"  - {r['algo_id']}: exp={r['new_net_expectancy_pct']:.2f}%, cost={r['round_trip_cost_pct']:.2f}%, {r['n_trades']} trades")

    if marginals:
        print("\nMARGINAL - Require optimization before production:")
        for r in marginals:
            print(f"  - {r['algo_id']}: exp={r['new_net_expectancy_pct']:.2f}%, cost={r['round_trip_cost_pct']:.2f}%, edge/cost={r['new_net_expectancy_pct']/r['round_trip_cost_pct']:.2f}x")

    if viables:
        print("\nVIABLE - Port to PyBroker for walk-forward validation:")
        for r in viables:
            print(f"  - {r['algo_id']}: exp={r['new_net_expectancy_pct']:.2f}%, cost={r['round_trip_cost_pct']:.2f}%, edge/cost={r['new_net_expectancy_pct']/r['round_trip_cost_pct']:.2f}x")

    # Save results
    out_path = ROOT / "data" / "trader" / "fee_model_diagnostic.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({
            "old_avg_rt_cost_pct": round(avg_old_fee, 4),
            "strategies": results,
            "summary": {
                "total": total,
                "already_negative": already_negative,
                "flipped_negative": negative_count,
                "marginal_risky": marginal_count,
                "viable": viable_count,
            },
        }, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
