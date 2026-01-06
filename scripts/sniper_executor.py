#!/usr/bin/env python3
"""
Sniper Executor - Run MicroCapSniper with Execution Loop
=========================================================

Integrates micro_cap_sniper.py with savage_swap.py for live execution.
Handles:
- SOL reserve for transaction fees (minimum 0.01 SOL = ~$1.50)
- Slippage protection (2% default)
- Token balance management
- Continuous scan loop

Usage:
    python3 scripts/sniper_executor.py --scan         # Scan only, no trades
    python3 scripts/sniper_executor.py --paper        # Paper trade mode
    python3 scripts/sniper_executor.py --live         # LIVE EXECUTION (careful!)
    python3 scripts/sniper_executor.py --status       # Check current status
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.micro_cap_sniper import (
    MicroCapSniper,
    SniperConfig,
    TokenCandidate,
    get_sniper_status,
)

# =============================================================================
# Configuration
# =============================================================================

# Minimum SOL to keep for transaction fees (~3-5 transactions worth)
MIN_SOL_RESERVE = 0.01  # ~$1.50 at current prices

# Default slippage (2% for volatile memecoins)
DEFAULT_SLIPPAGE_BPS = 200

# Scan interval in seconds
SCAN_INTERVAL_SECONDS = 30

# Maximum price impact allowed (5%)
MAX_PRICE_IMPACT_PCT = 5.0


# =============================================================================
# Wallet Helpers
# =============================================================================

def _get_sol_price() -> float:
    """Get current SOL price from CoinGecko."""
    try:
        import requests
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("solana", {}).get("usd", 200.0)
    except Exception:
        pass
    return 200.0


def _get_token_price(mint: str) -> float:
    """Get token price from DexScreener."""
    if mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":
        return 1.0  # USDC
    try:
        import requests
        resp = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{mint}",
            timeout=10,
        )
        if resp.status_code == 200:
            pairs = resp.json().get("pairs", [])
            if pairs:
                return float(pairs[0].get("priceUsd", 0) or 0)
    except Exception:
        pass
    return 0.0


async def get_wallet_status() -> Dict[str, Any]:
    """Get current wallet balances including all tokens."""
    try:
        from solders.keypair import Keypair
        from solana.rpc.async_api import AsyncClient
        from solana.rpc.types import TokenAccountOpts
        from solana.rpc.commitment import Confirmed
        from solders.pubkey import Pubkey
        from core import solana_wallet, solana_execution
        
        keypair = solana_wallet.load_keypair()
        if not keypair:
            return {"error": "No keypair found"}
        
        pubkey = keypair.pubkey()
        endpoints = solana_execution.load_solana_rpc_endpoints()
        sol_price = _get_sol_price()
        
        async with AsyncClient(endpoints[0].url) as client:
            # Get SOL balance
            balance = await client.get_balance(pubkey)
            sol_balance = balance.value / 1e9
            sol_usd = sol_balance * sol_price
            
            # Get all token accounts
            total_token_usd = 0.0
            usdc_balance = 0.0
            token_holdings = []
            
            try:
                resp = await client.get_token_accounts_by_owner_json_parsed(
                    pubkey,
                    TokenAccountOpts(
                        program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
                    ),
                    Confirmed,
                )
                
                for ta in resp.value:
                    info = ta.account.data.parsed["info"]
                    mint = info["mint"]
                    amount = float(info["tokenAmount"]["uiAmount"] or 0)
                    
                    if amount <= 0:
                        continue
                    
                    price = _get_token_price(mint)
                    usd_value = amount * price
                    total_token_usd += usd_value
                    
                    if mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":
                        usdc_balance = amount
                    
                    token_holdings.append({
                        "mint": mint,
                        "amount": amount,
                        "price": price,
                        "usd": usd_value,
                    })
            except Exception as e:
                print(f"⚠️  Token fetch error: {e}")
            
            total_usd = sol_usd + total_token_usd
            available_usd = total_usd - (MIN_SOL_RESERVE * sol_price)
            
            return {
                "pubkey": str(pubkey),
                "sol_balance": sol_balance,
                "sol_price": sol_price,
                "sol_usd": sol_usd,
                "usdc_balance": usdc_balance,
                "total_token_usd": total_token_usd,
                "total_usd": total_usd,
                "available_for_trade_usd": max(0, available_usd),
                "sol_reserve_ok": sol_balance >= MIN_SOL_RESERVE,
                "token_holdings": token_holdings,
            }
    except Exception as e:
        return {"error": str(e)}


async def ensure_sol_reserve(min_reserve: float = MIN_SOL_RESERVE) -> bool:
    """
    Ensure we have enough SOL for transaction fees.
    Returns True if reserve is OK, False if we need to top up.
    """
    status = await get_wallet_status()
    if "error" in status:
        print(f"❌ Wallet error: {status['error']}")
        return False
    
    sol = status["sol_balance"]
    if sol < min_reserve:
        deficit = min_reserve - sol
        print(f"⚠️  Low SOL reserve: {sol:.4f} SOL (need {min_reserve:.4f})")
        print(f"   Need to swap ~${deficit * 140:.2f} USDC → SOL first")
        return False
    
    return True


async def swap_for_sol_reserve(amount_sol: float = 0.005) -> bool:
    """Swap USDC for SOL to maintain fee reserve."""
    try:
        from core import solana_wallet
        from scripts.savage_swap import execute_swap
        
        keypair = solana_wallet.load_keypair()
        if not keypair:
            return False
        
        # Swap USDC → SOL
        amount_usd = amount_sol * 140  # Approximate
        print(f"🔄 Swapping {amount_usd:.2f} USDC → SOL for fee reserve...")
        
        result = await execute_swap(
            input_token="USDC",
            output_token="SOL",
            amount_usd=amount_usd,
            keypair=keypair,
            slippage_bps=100,
        )
        
        return result.success
    except Exception as e:
        print(f"❌ SOL swap failed: {e}")
        return False


# =============================================================================
# Token Discovery
# =============================================================================

async def discover_best_tokens(limit: int = 5) -> list[TokenCandidate]:
    """
    Discover best snipe targets using multiple data sources.
    """
    sniper = MicroCapSniper(SniperConfig(is_paper=True))
    candidates = sniper.scan_candidates()
    
    if not candidates:
        # Fallback: try trending aggregator directly
        try:
            from core.trending_aggregator import fetch_trending_all_sources, filter_rising_velocity
            trending = fetch_trending_all_sources(limit=50)
            rising = filter_rising_velocity(trending, min_velocity=0.05)
            
            for t in rising[:limit]:
                candidates.append(TokenCandidate(
                    mint=t.mint,
                    symbol=t.symbol,
                    name=t.name,
                    price_usd=t.price_usd,
                    liquidity_usd=t.liquidity_usd,
                    volume_24h_usd=t.volume_24h_usd,
                    momentum_score=t.velocity,
                    composite_score=t.composite_rank / 100,
                    source="trending_aggregator",
                ))
        except Exception as e:
            print(f"⚠️  Trending aggregator fallback failed: {e}")
    
    return candidates[:limit]


# =============================================================================
# Trade Execution
# =============================================================================

async def execute_snipe_trade(
    candidate: TokenCandidate,
    amount_usd: float,
    is_paper: bool = True,
    slippage_bps: int = DEFAULT_SLIPPAGE_BPS,
) -> Dict[str, Any]:
    """
    Execute a snipe trade on a candidate token.
    
    Args:
        candidate: Token to buy
        amount_usd: USD amount to invest
        is_paper: If True, only simulate
        slippage_bps: Slippage tolerance
        
    Returns:
        Trade result dict
    """
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "token": candidate.symbol,
        "mint": candidate.mint,
        "amount_usd": amount_usd,
        "is_paper": is_paper,
        "success": False,
        "error": None,
    }
    
    # Pre-trade checks
    if not await ensure_sol_reserve():
        result["error"] = "Insufficient SOL reserve"
        return result
    
    if is_paper:
        # Paper trade - simulate
        print(f"📝 [PAPER] Would buy ${amount_usd:.2f} of {candidate.symbol}")
        print(f"   Mint: {candidate.mint[:20]}...")
        print(f"   Price: ${candidate.price_usd:.8f}")
        print(f"   Momentum: +{candidate.momentum_score*100:.1f}%")
        
        # Calculate expected output
        quantity = amount_usd / candidate.price_usd if candidate.price_usd > 0 else 0
        slippage_pct = slippage_bps / 10000
        quantity_after_slip = quantity * (1 - slippage_pct)
        
        result["success"] = True
        result["quantity"] = quantity_after_slip
        result["entry_price"] = candidate.price_usd
        result["take_profit_price"] = candidate.price_usd * 1.25
        result["stop_loss_price"] = candidate.price_usd * 0.88
        return result
    
    # Live execution
    print(f"🎯 EXECUTING LIVE TRADE: ${amount_usd:.2f} → {candidate.symbol}")
    
    try:
        from core import solana_wallet
        from scripts.savage_swap import execute_swap, create_exit_intent, persist_exit_intent
        
        keypair = solana_wallet.load_keypair()
        if not keypair:
            result["error"] = "No keypair"
            return result
        
        # Execute swap
        swap_result = await execute_swap(
            input_token="USDC",
            output_token=candidate.mint,  # Use mint address
            amount_usd=amount_usd,
            keypair=keypair,
            slippage_bps=slippage_bps,
        )
        
        if swap_result.success:
            result["success"] = True
            result["signature"] = swap_result.signature
            result["quantity"] = swap_result.output_amount
            result["entry_price"] = amount_usd / swap_result.output_amount if swap_result.output_amount > 0 else 0
            result["price_impact"] = swap_result.price_impact
            
            # Create exit intent
            position_id = f"snipe-{swap_result.signature[:8] if swap_result.signature else 'manual'}"
            intent = create_exit_intent(
                position_id=position_id,
                token=candidate.mint,
                entry_price=result["entry_price"],
                quantity=swap_result.output_amount,
            )
            persist_exit_intent(intent)
            
            print(f"✅ SNIPE SUCCESS!")
            print(f"   Got: {swap_result.output_amount:,.4f} {candidate.symbol}")
            print(f"   Entry: ${result['entry_price']:.8f}")
        else:
            result["error"] = swap_result.error
            print(f"❌ Swap failed: {swap_result.error}")
        
    except Exception as e:
        result["error"] = str(e)
        print(f"❌ Execution error: {e}")
    
    return result


# =============================================================================
# Main Loop
# =============================================================================

async def run_scan_loop(
    is_paper: bool = True,
    target_usd: float = 50.0,
    max_cycles: int = 100,
):
    """
    Main sniper loop - scans for opportunities and executes.
    """
    print("\n" + "=" * 60)
    print("🎯 MICRO-CAP SNIPER EXECUTOR")
    print("=" * 60)
    
    mode = "PAPER" if is_paper else "🔴 LIVE"
    print(f"Mode: {mode}")
    print(f"Target: ${target_usd:.2f}")
    print(f"Max cycles: {max_cycles}")
    print("=" * 60)
    
    # Get initial wallet status
    wallet = await get_wallet_status()
    if "error" in wallet:
        print(f"❌ Wallet error: {wallet['error']}")
        return
    
    starting_capital = wallet["available_for_trade_usd"]
    print(f"\n💰 Starting capital: ${starting_capital:.2f}")
    print(f"   SOL reserve: {wallet['sol_balance']:.4f} SOL")
    print(f"   USDC: ${wallet['usdc_balance']:.2f}")
    
    if starting_capital < 1.0:
        print("❌ Insufficient capital (< $1)")
        return
    
    sniper = MicroCapSniper(SniperConfig(
        starting_capital_usd=starting_capital,
        target_capital_usd=target_usd,
        is_paper=is_paper,
    ))
    
    cycle = 0
    while cycle < max_cycles:
        cycle += 1
        print(f"\n--- Cycle {cycle}/{max_cycles} ---")
        
        # Check if target reached
        status = sniper.get_status()
        current = sniper.state.current_capital_usd
        if current >= target_usd:
            print(f"\n🎉 TARGET REACHED! ${current:.2f} >= ${target_usd:.2f}")
            break
        
        # Discover candidates
        candidates = await discover_best_tokens(limit=5)
        print(f"Found {len(candidates)} candidates")
        
        if not candidates:
            print("No candidates, waiting...")
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)
            continue
        
        # Show top candidate
        best = candidates[0]
        print(f"Top candidate: {best.symbol}")
        print(f"  Score: {best.composite_score:.2f}")
        print(f"  Price: ${best.price_usd:.8f}")
        print(f"  Liquidity: ${best.liquidity_usd:,.0f}")
        if best.sentiment:
            sentiment_emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪", "mixed": "🟡"}.get(best.sentiment, "⚪")
            print(f"  Sentiment: {sentiment_emoji} {best.sentiment} (conf={best.sentiment_confidence:.0%})")
            if best.sentiment_market_relevance:
                print(f"  Market: {best.sentiment_market_relevance[:60]}...")
        
        # Check if we should enter
        should_enter, reason = sniper.should_enter(best)
        
        if should_enter:
            # Calculate position size
            trade_amount = min(current, wallet.get("usdc_balance", 0))
            
            if trade_amount < 1.0:
                print("Insufficient USDC balance")
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
                continue
            
            # Execute trade
            trade_result = await execute_snipe_trade(
                candidate=best,
                amount_usd=trade_amount,
                is_paper=is_paper,
            )
            
            if trade_result["success"]:
                # Update sniper state
                sniper.state.active_position = {
                    "mint": best.mint,
                    "symbol": best.symbol,
                    "entry_price": trade_result.get("entry_price", 0),
                    "quantity": trade_result.get("quantity", 0),
                    "entry_time": time.time(),
                    "is_paper": is_paper,
                }
                sniper._save_state()
        else:
            print(f"Skipping: {reason}")
        
        # Wait before next scan
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)
    
    print("\n--- Final Status ---")
    print(json.dumps(sniper.get_status(), indent=2))


# =============================================================================
# CLI
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Sniper Executor")
    parser.add_argument("--scan", action="store_true", help="Scan only, no trades")
    parser.add_argument("--paper", action="store_true", help="Paper trade mode")
    parser.add_argument("--live", action="store_true", help="LIVE execution (careful!)")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--target", type=float, default=50.0, help="Target USD (default: 50)")
    parser.add_argument("--cycles", type=int, default=100, help="Max scan cycles")
    
    args = parser.parse_args()
    
    if args.status:
        print("\n📊 Wallet Status")
        print("-" * 40)
        wallet = await get_wallet_status()
        if "error" in wallet:
            print(f"❌ Error: {wallet['error']}")
        else:
            print(f"  Pubkey: {wallet['pubkey'][:20]}...")
            print(f"  SOL: {wallet['sol_balance']:.4f} @ ${wallet.get('sol_price', 200):.2f} = ${wallet['sol_usd']:.2f}")
            print(f"  USDC: ${wallet['usdc_balance']:.2f}")
            if wallet.get('token_holdings'):
                for th in wallet['token_holdings']:
                    if th['mint'] != "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" and th['usd'] > 0.01:
                        print(f"  Token: {th['amount']:.2f} @ ${th['price']:.6f} = ${th['usd']:.2f}")
            print(f"  ─────────────────────────")
            print(f"  💵 Total: ${wallet.get('total_usd', 0):.2f}")
            print(f"  📈 Available: ${wallet['available_for_trade_usd']:.2f}")
            print(f"  SOL reserve OK: {'✅' if wallet['sol_reserve_ok'] else '❌'}")
        
        print("\n📈 Sniper Status")
        print("-" * 40)
        status = get_sniper_status()
        for k, v in status.items():
            print(f"  {k}: {v}")
        return
    
    if args.scan:
        print("\n🔍 Scanning for candidates...")
        candidates = await discover_best_tokens(limit=10)
        print(f"\nFound {len(candidates)} candidates:")
        for i, c in enumerate(candidates[:10], 1):
            sentiment_emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪", "mixed": "🟡"}.get(c.sentiment, "")
            sentiment_str = f" {sentiment_emoji}{c.sentiment}" if c.sentiment else ""
            print(f"{i}. {c.symbol} - Score: {c.composite_score:.2f}, Vol: ${c.volume_24h_usd:,.0f}{sentiment_str}")
            if c.sentiment_market_relevance:
                print(f"   └─ {c.sentiment_market_relevance[:70]}...")
        return
    
    if args.live:
        print("\n⚠️  LIVE MODE - Real trades will be executed!")
        print("Press Ctrl+C to cancel...")
        await asyncio.sleep(3)
        await run_scan_loop(is_paper=False, target_usd=args.target, max_cycles=args.cycles)
    else:
        # Default to paper mode
        await run_scan_loop(is_paper=True, target_usd=args.target, max_cycles=args.cycles)


if __name__ == "__main__":
    asyncio.run(main())
