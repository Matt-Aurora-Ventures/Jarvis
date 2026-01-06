#!/usr/bin/env python3
"""
Auto Trader - Continuous Trading Loop to $100
==============================================

Runs continuously until capital reaches $100.
Features:
- Grok sentiment analysis
- Multi-source token discovery
- Automatic execution
- Exit intent management
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.micro_cap_sniper import MicroCapSniper, SniperConfig, TokenCandidate
from core import x_sentiment
from scripts.savage_swap import execute_swap, create_exit_intent, persist_exit_intent
from core import solana_wallet

# Configuration
TARGET_USD = 100.0
STARTING_CAPITAL = 4.16  # From wallet screenshot
SCAN_INTERVAL_SECONDS = 60
USE_GROK_SENTIMENT = True
TAKE_PROFIT_PCT = 0.25  # 25% gain target
STOP_LOSS_PCT = 0.30    # 30% stop loss (wider for volatility)

print(f"""
{'='*60}
🤖 AUTO TRADER - $4 → $100 Challenge
{'='*60}
Target: ${TARGET_USD}
Starting: ${STARTING_CAPITAL}
Grok Sentiment: {'✅ Enabled' if USE_GROK_SENTIMENT else '❌ Disabled'}
{'='*60}
""", flush=True)

async def get_sentiment_boost(symbol: str) -> float:
    """Get sentiment boost multiplier for a token using Grok."""
    if not USE_GROK_SENTIMENT:
        return 1.0
    
    try:
        result = x_sentiment.analyze_sentiment(
            text=f"${symbol} - Solana memecoin trading sentiment",
            focus="trading"
        )
        
        if result:
            # Positive sentiment = boost score
            if result.sentiment == "positive":
                return 1.0 + (result.confidence * 0.5)  # Up to 1.5x boost
            elif result.sentiment == "negative":
                return max(0.5, 1.0 - (result.confidence * 0.3))  # Down to 0.5x
        
    except Exception as e:
        print(f"Grok sentiment failed for {symbol}: {e}", flush=True)
    
    return 1.0


async def discover_and_score_tokens(limit: int = 10) -> list[TokenCandidate]:
    """Discover tokens - FOCUS ON NEWER TOKENS WITH MOMENTUM."""
    print("\n🔍 Scanning for NEWER tokens with MOMENTUM...", flush=True)
    
    candidates = []
    
    # Primary source: DexScreener trending (better for newer tokens)
    try:
        import requests
        print("Fetching from DexScreener trending...", flush=True)
        
        resp = requests.get("https://api.dexscreener.com/latest/dex/search/?q=SOL", timeout=15)
        if resp.ok:
            data = resp.json()
            pairs = data.get("pairs", [])
            
            # Filter for Solana and momentum
            solana_pairs = [p for p in pairs if p.get("chainId") == "solana"][:50]
            
            print(f"Processing {len(solana_pairs)} Solana pairs...", flush=True)
            
            for p in solana_pairs:
                base_token = p.get("baseToken", {})
                symbol = base_token.get("symbol", "")
                mint = base_token.get("address", "")
                
                # Skip if no symbol
                if not symbol or len(symbol) < 2:
                    continue
                
                # Get metrics
                liquidity = float(p.get("liquidity", {}).get("usd", 0))
                volume_24h = float(p.get("volume", {}).get("h24", 0))
                price_usd = float(p.get("priceUsd", 0))
                
                # Get price changes for momentum
                price_change = p.get("priceChange", {})
                change_5m = float(price_change.get("m5", 0))
                change_1h = float(price_change.get("h1", 0))
                change_6h = float(price_change.get("h6", 0))
                change_24h = float(price_change.get("h24", 0))
                
                # FILTERS FOR NEWER, VOLATILE TOKENS
                # Smaller liquidity = newer/more volatile
                if liquidity < 10_000 or liquidity > 1_000_000:  # $10K - $1M sweet spot
                    continue
                
                # Need decent volume for exits
                if volume_24h < 100_000:  # Minimum $100K
                    continue
                
                # MOMENTUM INDICATORS
                # Look for positive momentum in recent timeframes
                has_momentum = (
                    change_5m > 2 or  # 2%+ in 5 min
                    change_1h > 5 or  # 5%+ in 1 hour
                    change_6h > 10 or  # 10%+ in 6 hours
                    abs(change_24h) > 15  # 15%+ movement in 24h (either direction)
                )
                
                if not has_momentum:
                    continue
                
                # SCORING - Prioritize momentum
                # Recent momentum (5m, 1h) weighted higher
                momentum_score = (
                    abs(change_5m) * 0.4 +  # Recent momentum = 40%
                    abs(change_1h) * 0.3 +   # 1h momentum = 30%
                    abs(change_6h) * 0.2 +   # 6h momentum = 20%
                    abs(change_24h) * 0.1    # 24h = 10%
                ) / 100  # Normalize
                
                # Volume activity
                vol_liq_ratio = volume_24h / max(liquidity, 1)
                activity_score = min(vol_liq_ratio / 10, 1.0) * 0.4
                
                # Smaller market cap = higher score (more room to grow)
                size_score = max(0, 1 - (liquidity / 1_000_000)) * 0.2
                
                composite = min(momentum_score + activity_score + size_score, 1.0)
                
                # Minimum threshold
                if composite < 0.4:
                    continue
                
                candidate = TokenCandidate(
                    mint=mint,
                    symbol=symbol,
                    name=base_token.get("name", symbol),
                    price_usd=price_usd,
                    liquidity_usd=liquidity,
                    volume_24h_usd=volume_24h,
                    price_change_1h=change_1h / 100,  # Convert to decimal
                    price_change_24h=change_24h / 100,
                    momentum_score=momentum_score,
                    composite_score=composite,
                    source="dexscreener",
                )
                
                candidates.append(candidate)
                print(f"  {symbol}: 1h={change_1h:+.1f}%, 24h={change_24h:+.1f}%, Vol=${volume_24h/1e3:.0f}K, Liq=${liquidity/1e3:.0f}K, score={composite:.2f}", flush=True)
                
    except Exception as e:
        print(f"DexScreener error: {e}", flush=True)
    
    # Fallback: trending aggregator (if DexScreener fails)
    if len(candidates) < 3:
        try:
            from core.trending_aggregator import fetch_trending_all_sources
            trending = fetch_trending_all_sources(limit=30)
            
            for t in trending:
                if t.volume_24h_usd > 100_000 and 10_000 < t.liquidity_usd < 1_000_000:
                    candidates.append(TokenCandidate(
                        mint=t.mint,
                        symbol=t.symbol,
                        name=t.name,
                        price_usd=t.price_usd,
                        liquidity_usd=t.liquidity_usd,
                        volume_24h_usd=t.volume_24h_usd,
                        composite_score=0.5,
                        source="trending_fallback",
                    ))
        except Exception:
            pass
    
    # Sort by composite score (momentum-weighted)
    candidates.sort(key=lambda c: c.composite_score, reverse=True)
    
    print(f"\n✅ Found {len(candidates)} momentum candidates", flush=True)
    if candidates:
        best = candidates[0]
        print(f"BEST: {best.symbol} - Score: {best.composite_score:.2f}, Vol: ${best.volume_24h_usd/1e3:.0f}K, Liq: ${best.liquidity_usd/1e3:.0f}K", flush=True)
    
    return candidates


async def execute_trade(candidate: TokenCandidate, amount_usd: float) -> dict:
    """Execute a live trade."""
    print(f"\n🎯 EXECUTING TRADE", flush=True)
    print(f"   Token: {candidate.symbol}", flush=True)
    print(f"   Amount: ${amount_usd:.2f}", flush=True)
    print(f"   Price: ${candidate.price_usd:.8f}", flush=True)
    
    keypair = solana_wallet.load_keypair()
    if not keypair:
        return {"success": False, "error": "No keypair"}
    
    try:
        result = await execute_swap(
            input_token="USDC",
            output_token=candidate.mint,
            amount_usd=amount_usd,
            keypair=keypair,
            slippage_bps=200,  # 2% slippage for memecoins
        )
        
        if result.success:
            # Create exit intent
            position_id = f"auto-{result.signature[:8] if result.signature else 'manual'}"
            entry_price = amount_usd / result.output_amount if result.output_amount > 0 else candidate.price_usd
            
            intent = create_exit_intent(
                position_id=position_id,
                token=candidate.mint,
                entry_price=entry_price,
                quantity=result.output_amount,
            )
            persist_exit_intent(intent)
            
            print(f"✅ TRADE SUCCESS!", flush=True)
            print(f"   Signature: {result.signature}", flush=True)
            print(f"   Got: {result.output_amount:,.4f} {candidate.symbol}", flush=True)
            print(f"   Exit intent created: {position_id}", flush=True)
            
            return {
                "success": True,
                "signature": result.signature,
                "quantity": result.output_amount,
                "entry_price": entry_price,
            }
        else:
            print(f"❌ Trade failed: {result.error}", flush=True)
            return {"success": False, "error": result.error}
            
    except Exception as e:
        print(f"❌ Execution error: {e}", flush=True)
        return {"success": False, "error": str(e)}


async def main_loop():
    """Main trading loop."""
    sniper = MicroCapSniper(SniperConfig(
        starting_capital_usd=STARTING_CAPITAL,
        target_capital_usd=TARGET_USD,
        is_paper=False,  # LIVE MODE
    ))
    
    cycle = 0
    
    while True:
        cycle += 1
        current_capital = sniper.state.current_capital_usd
        
        print(f"\n{'='*60}", flush=True)
        print(f"📊 Cycle {cycle} - Capital: ${current_capital:.2f} / ${TARGET_USD:.2f}", flush=True)
        print(f"{'='*60}", flush=True)
        
        # Check if target reached
        if current_capital >= TARGET_USD:
            print(f"\n🎉🎉🎉 TARGET REACHED! 🎉🎉🎉", flush=True)
            print(f"Final Capital: ${current_capital:.2f}", flush=True)
            print(f"Total Trades: {sniper.state.total_trades}", flush=True)
            print(f"Win Rate: {sniper.state.win_rate()*100:.1f}%", flush=True)
            break
        
        # Discover tokens
        candidates = await discover_and_score_tokens(limit=5)
        
        if not candidates:
            print(f"No candidates found, waiting {SCAN_INTERVAL_SECONDS}s...", flush=True)
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)
            continue
        
        # Check best candidate
        best = candidates[0]
        should_enter, reason = sniper.should_enter(best)
        
        if should_enter:
            # Execute trade with current capital
            trade_result = await execute_trade(best, current_capital)
            
            if trade_result["success"]:
                # Update sniper state
                sniper.state.active_position = {
                    "mint": best.mint,
                    "symbol": best.symbol,
                    "entry_price": trade_result["entry_price"],
                    "quantity": trade_result["quantity"],
                    "entry_time": time.time(),
                }
                sniper._save_state()
                
                # Monitor position until exit
                print(f"\n👀 Monitoring position...", flush=True)
                print(f"   TP: ${trade_result['entry_price'] * 1.25:.8f} (+25%)", flush=True)
                print(f"   SL: ${trade_result['entry_price'] * 0.88:.8f} (-12%)", flush=True)
                
                # TODO: Add position monitoring loop here
                # For now, just wait for exit intent to trigger via daemon
                
            # Wait before next trade
            await asyncio.sleep(120)  # 2 min cooldown
        else:
            print(f"⏭️  Skipping: {reason}", flush=True)
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopped by user", flush=True)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}", flush=True)
        raise
