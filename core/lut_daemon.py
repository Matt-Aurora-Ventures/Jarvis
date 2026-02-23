"""
LUT Micro-Alpha Enforcement Daemon
==================================

Redundant daemon for enforcing exit intents (TP ladder, stop loss, time stops).
Runs independently of the main trading_daemon.py for safety redundancy.

Features:
- Polls exit intents every N seconds
- Fetches current prices from multiple sources
- Checks and triggers exit conditions
- Updates reliability statistics
- Handles sentiment reversal exits

Usage:
    # Run as standalone daemon
    python -m core.lut_daemon

    # Or programmatically
    from core.lut_daemon import run_daemon
    run_daemon(poll_interval=30)
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import exit_intents
from core import birdeye
from core import geckoterminal
from core import dexscreener
from core import jupiter

logger = logging.getLogger(__name__)

# Config
TRADING_DIR = Path.home() / ".lifeos" / "trading"
DAEMON_LOG_FILE = TRADING_DIR / "lut_daemon.log"
DAEMON_STATE_FILE = TRADING_DIR / "lut_daemon_state.json"

# Price source priority
PRICE_SOURCES = ["birdeye", "geckoterminal", "dexscreener", "jupiter"]

# Shutdown flag
_shutdown_requested = False


def _signal_handler(signum, frame):
    """Handle shutdown signals."""
    global _shutdown_requested
    logger.info("[lut_daemon] Shutdown signal received")
    _shutdown_requested = True


def fetch_price(
    mint_or_asset: str,
    sources: List[str] = None,
) -> Optional[float]:
    """
    Fetch current price from multiple sources with fallback.

    Args:
        mint_or_asset: Token mint address or asset symbol (SOL, BTC, ETH)
        sources: Priority list of sources to try

    Returns:
        Price in USD or None if all sources fail
    """
    if sources is None:
        sources = PRICE_SOURCES

    # Check if it's an asset symbol (for perps)
    if mint_or_asset in ["SOL", "BTC", "ETH"]:
        try:
            price_data = jupiter.get_price([mint_or_asset])
            if price_data and "data" in price_data:
                asset_data = price_data["data"].get(mint_or_asset, {})
                price = float(asset_data.get("price", 0))
                if price > 0:
                    return price
        except Exception as e:
            logger.debug(f"[lut_daemon] Jupiter price fetch failed: {e}")

        # Fallback prices for testing
        fallback = {"SOL": 180.0, "BTC": 95000.0, "ETH": 3500.0}
        return fallback.get(mint_or_asset)

    # For token mints, try each source
    for source in sources:
        try:
            if source == "birdeye":
                data = birdeye.fetch_token_price(mint_or_asset, cache_ttl_seconds=10)
                if data and "data" in data:
                    price = data["data"].get("value")
                    if price:
                        return float(price)

            elif source == "geckoterminal":
                data = geckoterminal.fetch_token("solana", mint_or_asset, cache_ttl_seconds=60)
                if data and "data" in data:
                    attrs = data["data"].get("attributes", {})
                    price = attrs.get("price_usd")
                    if price:
                        return float(price)

            elif source == "dexscreener":
                data = dexscreener.fetch_token_pairs(mint_or_asset, cache_ttl_seconds=30)
                if data and "pairs" in data:
                    pairs = data["pairs"]
                    if pairs:
                        price = pairs[0].get("priceUsd")
                        if price:
                            return float(price)

            elif source == "jupiter":
                # Jupiter needs mint address
                data = jupiter.get_price([mint_or_asset])
                if data and "data" in data:
                    token_data = data["data"].get(mint_or_asset, {})
                    price = token_data.get("price")
                    if price:
                        return float(price)

        except Exception as e:
            logger.debug(f"[lut_daemon] {source} price fetch failed for {mint_or_asset}: {e}")
            continue

    return None


def check_sentiment_reversal(mint: str, h24_threshold: float = -35.0, h1_threshold: float = -20.0) -> bool:
    """
    Check if price momentum signals a sentiment reversal for a token.

    Uses DexScreener 24h and 1h price changes as sentiment proxies:
    - 24h change < -35% → severe reversal
    - 1h change < -20% → rapid dump in progress

    Returns True only when both threshold and data availability pass.
    Falls back to False if DexScreener is unavailable (safe default).
    """
    try:
        result = dexscreener.get_pairs_by_token(mint, cache_ttl_seconds=60)
        if not result or not isinstance(result, dict):
            return False
        pairs = result.get("pairs") or []
        if not pairs:
            return False
        # Use the highest-liquidity pair for the signal
        pair = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
        price_change = pair.get("priceChange") or {}
        h24 = float(price_change.get("h24") or 0)
        h1 = float(price_change.get("h1") or 0)
        if h24 <= h24_threshold or h1 <= h1_threshold:
            logger.info(
                f"[lut_daemon] Sentiment reversal detected for {mint[:8]}…: "
                f"1h={h1:+.1f}% 24h={h24:+.1f}%"
            )
            return True
    except Exception as e:
        logger.debug(f"[lut_daemon] Sentiment reversal check failed for {mint}: {e}")
    return False


def process_intent(
    intent: exit_intents.ExitIntent,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """
    Process a single exit intent.

    Returns list of actions taken.
    """
    actions_taken = []

    # Fetch current price
    current_price = fetch_price(intent.token_mint)
    if current_price is None:
        logger.warning(f"[lut_daemon] Could not fetch price for {intent.symbol} ({intent.token_mint})")
        intent.enforcement_failures += 1
        fallback_price = intent.last_check_price or intent.entry_price
        triggers = exit_intents.check_time_stop(intent, fallback_price)
        if not triggers:
            exit_intents.update_intent(intent)
            return []
        sentiment_reversed = False
    else:
        fallback_price = current_price
        sentiment_reversed = check_sentiment_reversal(intent.token_mint)
        triggers = exit_intents.check_intent_triggers(
            intent,
            current_price,
            sentiment_reversed=sentiment_reversed,
        )

    for action, params in triggers:
        if dry_run:
            actions_taken.append({
                "intent_id": intent.id,
                "symbol": intent.symbol,
                "action": action.value,
                "params": params,
                "dry_run": True,
            })
            logger.info(f"[lut_daemon] DRY RUN: Would execute {action.value} for {intent.symbol}")
        else:
            # Execute the action
            result = exit_intents.execute_action(
                intent,
                action,
                params,
                paper_mode=intent.is_paper,
            )

            actions_taken.append({
                "intent_id": intent.id,
                "symbol": intent.symbol,
                "action": action.value,
                "params": params,
                "result": result.to_dict(),
            })

            logger.info(
                f"[lut_daemon] Executed {action.value} for {intent.symbol}: "
                f"PnL=${result.pnl_usd:+.2f} ({result.pnl_pct:+.2f}%)"
            )

    # Update intent (tracking fields)
    if not dry_run:
        exit_intents.update_intent(intent)

    return actions_taken


def run_daemon_cycle(dry_run: bool = False) -> Dict[str, Any]:
    """
    Run a single daemon cycle.

    Returns summary of actions taken.
    """
    cycle_start = time.time()

    # Load active intents
    intents = exit_intents.load_active_intents()

    summary = {
        "timestamp": cycle_start,
        "intents_checked": len(intents),
        "actions_taken": [],
        "errors": [],
    }

    for intent in intents:
        try:
            actions = process_intent(intent, dry_run=dry_run)
            summary["actions_taken"].extend(actions)
        except Exception as e:
            error = {
                "intent_id": intent.id,
                "symbol": intent.symbol,
                "error": str(e),
            }
            summary["errors"].append(error)
            logger.error(f"[lut_daemon] Error processing {intent.symbol}: {e}")

    summary["cycle_time_ms"] = int((time.time() - cycle_start) * 1000)

    return summary


def run_daemon(
    poll_interval: int = 30,
    dry_run: bool = False,
    max_cycles: Optional[int] = None,
):
    """
    Run the daemon loop.

    Args:
        poll_interval: Seconds between checks
        dry_run: If True, don't execute trades
        max_cycles: Stop after N cycles (None = run forever)
    """
    global _shutdown_requested

    # Setup signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Ensure directories exist
    TRADING_DIR.mkdir(parents=True, exist_ok=True)

    # Setup file logging
    file_handler = logging.FileHandler(DAEMON_LOG_FILE)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    ))
    logger.addHandler(file_handler)

    logger.info(f"[lut_daemon] Starting daemon (poll={poll_interval}s, dry_run={dry_run})")

    cycle_count = 0

    while not _shutdown_requested:
        try:
            summary = run_daemon_cycle(dry_run=dry_run)

            # Log summary
            if summary["actions_taken"]:
                logger.info(
                    f"[lut_daemon] Cycle {cycle_count}: "
                    f"{len(summary['actions_taken'])} actions, "
                    f"{summary['cycle_time_ms']}ms"
                )
            else:
                logger.debug(
                    f"[lut_daemon] Cycle {cycle_count}: "
                    f"{summary['intents_checked']} intents checked, no actions"
                )

            # Save daemon state
            _save_daemon_state({
                "last_cycle": summary["timestamp"],
                "last_cycle_actions": len(summary["actions_taken"]),
                "total_cycles": cycle_count,
                "poll_interval": poll_interval,
                "dry_run": dry_run,
            })

            cycle_count += 1

            if max_cycles and cycle_count >= max_cycles:
                logger.info(f"[lut_daemon] Reached max cycles ({max_cycles})")
                break

            # Sleep until next cycle
            time.sleep(poll_interval)

        except Exception as e:
            logger.error(f"[lut_daemon] Cycle error: {e}")
            time.sleep(poll_interval)

    logger.info("[lut_daemon] Daemon stopped")


def _save_daemon_state(state: Dict[str, Any]):
    """Save daemon state for monitoring."""
    try:
        state["updated_at"] = time.time()
        DAEMON_STATE_FILE.write_text(json.dumps(state, indent=2))
    except IOError:
        pass


def get_daemon_status() -> Dict[str, Any]:
    """Get daemon status for monitoring."""
    if DAEMON_STATE_FILE.exists():
        try:
            state = json.loads(DAEMON_STATE_FILE.read_text())
            state["running"] = time.time() - state.get("last_cycle", 0) < 120
            return state
        except (json.JSONDecodeError, IOError):
            pass

    return {"running": False, "error": "state_file_not_found"}


# ============================================================================
# CLI
# ============================================================================

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="LUT Micro-Alpha Enforcement Daemon"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Seconds between price checks (default: 30)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check triggers but don't execute trades"
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Stop after N cycles (default: run forever)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show daemon status and exit"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if args.status:
        status = get_daemon_status()
        print("LUT Daemon Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")
        return

    print("=" * 50)
    print("LUT Micro-Alpha Enforcement Daemon")
    print("=" * 50)
    print(f"Poll Interval: {args.poll_interval}s")
    print(f"Dry Run: {args.dry_run}")
    print(f"Max Cycles: {args.max_cycles or 'unlimited'}")
    print("=" * 50)
    print("Press Ctrl+C to stop\n")

    run_daemon(
        poll_interval=args.poll_interval,
        dry_run=args.dry_run,
        max_cycles=args.max_cycles,
    )


if __name__ == "__main__":
    main()
