#!/usr/bin/env python3
"""Run a single paper-trade cycle for Solana DEX bots."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import trading_pipeline
from core.geckoterminal import fetch_pool_ohlcv, normalize_ohlcv_list


BOT_DIR = ROOT / "data" / "trader" / "solana_dex" / "bots"


def main() -> None:
    args = parse_args()
    bots = load_bots()
    if not bots:
        print("No bot configs found. Run scripts/solana_dex_backtest.py first.")
        return

    for bot in bots:
        token = bot.get("token", {})
        pool = token.get("pool_address")
        timeframe = bot.get("timeframe", "hour")
        if not pool:
            continue

        candles = fetch_recent_candles(
            pool_address=pool,
            timeframe=timeframe,
            limit=args.lookback,
        )
        if not candles:
            print(f"{token.get('symbol', 'UNKNOWN')}: missing candles")
            continue

        strategy_cfg = build_strategy(bot)
        result = trading_pipeline.paper_trade_cycle(
            candles,
            symbol=token.get("symbol", "UNKNOWN"),
            interval=timeframe,
            strategy=strategy_cfg,
        )
        print(trading_pipeline.format_paper_summary(result))
        time.sleep(args.sleep_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper bots for Solana DEX")
    parser.add_argument("--lookback", type=int, default=400)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    return parser.parse_args()


def load_bots() -> List[Dict[str, Any]]:
    if not BOT_DIR.exists():
        return []
    bots = []
    for path in sorted(BOT_DIR.glob("*.json")):
        try:
            bots.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue
    return bots


def fetch_recent_candles(pool_address: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    payload = fetch_pool_ohlcv(
        "solana",
        pool_address,
        timeframe,
        limit=limit,
    )
    if not payload:
        return []
    ohlcv_list = payload.get("data", {}).get("attributes", {}).get("ohlcv_list", []) or []
    if not ohlcv_list:
        return []
    merged = sorted(ohlcv_list, key=lambda row: row[0])
    return normalize_ohlcv_list(merged)


def build_strategy(bot: Dict[str, Any]) -> trading_pipeline.StrategyConfig:
    strat = bot.get("strategy", {}).get("strategy", {})
    return trading_pipeline.StrategyConfig(
        kind=strat.get("kind", "sma_cross"),
        params=strat.get("params", {}),
        fee_bps=strat.get("fee_bps", 30.0),
        slippage_bps=strat.get("slippage_bps", 20.0),
        risk_per_trade=strat.get("risk_per_trade", 0.02),
        stop_loss_pct=strat.get("stop_loss_pct", 0.03),
        take_profit_pct=strat.get("take_profit_pct", 0.06),
        max_position_pct=strat.get("max_position_pct", 0.25),
        capital_usd=strat.get("capital_usd", 10.0),
    )


if __name__ == "__main__":
    main()
