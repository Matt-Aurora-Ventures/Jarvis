#!/usr/bin/env python3
"""
JARVIS Analysis Examples

This module demonstrates how to use JARVIS analysis APIs.

Examples:
1. Analyze a token's on-chain metrics
2. Get signals for multiple tokens
3. Compare Dexter vs sentiment pipeline
"""

import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# =============================================================================
# Example 1: Analyze Token On-Chain Metrics
# =============================================================================

async def example_analyze_token():
    """
    Analyze a token using multiple data sources.

    This example:
    1. Fetches price from Jupiter
    2. Gets market data from DexScreener
    3. Analyzes holder distribution
    4. Calculates risk score
    """
    from core.market_data_service import get_market_data_service
    from core.token_analyzer import TokenAnalyzer

    # Initialize services
    market_data = await get_market_data_service()
    analyzer = TokenAnalyzer()

    token_symbol = "SOL"
    token_mint = "So11111111111111111111111111111111111111112"

    print(f"Analyzing {token_symbol}...")

    # 1. Get price data
    price_data = await market_data.get_token_price(token_mint)
    print(f"\nPrice Data:")
    print(f"  Current Price: ${price_data.get('price', 0):.4f}")
    print(f"  24h Change: {price_data.get('change_24h', 0):+.2f}%")
    print(f"  Volume 24h: ${price_data.get('volume_24h', 0):,.0f}")

    # 2. Get market metrics
    metrics = await market_data.get_token_metrics(token_mint)
    print(f"\nMarket Metrics:")
    print(f"  Market Cap: ${metrics.get('market_cap', 0):,.0f}")
    print(f"  Liquidity: ${metrics.get('liquidity', 0):,.0f}")
    print(f"  Holders: {metrics.get('holders', 0):,}")

    # 3. Analyze risk
    risk_analysis = await analyzer.analyze_risk(token_mint)
    print(f"\nRisk Analysis:")
    print(f"  Risk Level: {risk_analysis.get('level', 'UNKNOWN')}")
    print(f"  Risk Score: {risk_analysis.get('score', 0)}/100")
    print(f"  Top 10 Holders: {risk_analysis.get('top_10_concentration', 0):.1f}%")

    # 4. Overall assessment
    overall_score = price_data.get('price', 0) > 0 and risk_analysis.get('score', 100) < 50
    print(f"\nOverall: {'SAFE' if overall_score else 'CAUTION'}")

    return {
        "price": price_data,
        "metrics": metrics,
        "risk": risk_analysis
    }


# =============================================================================
# Example 2: Get Signals for Multiple Tokens
# =============================================================================

async def example_multi_token_signals():
    """
    Get trading signals for multiple tokens.

    This example:
    1. Defines a watchlist
    2. Analyzes each token
    3. Ranks by signal strength
    4. Returns top opportunities
    """
    from core.sentiment_aggregator import get_aggregated_sentiment

    # Watchlist of tokens to analyze
    watchlist = ["SOL", "BONK", "WIF", "JUP", "PYTH"]

    print("Analyzing watchlist...")
    print("-" * 50)

    results = []

    for symbol in watchlist:
        try:
            # Get sentiment
            sentiment = await get_aggregated_sentiment(symbol)

            result = {
                "symbol": symbol,
                "score": sentiment.score,
                "grade": sentiment.grade,
                "signal": sentiment.recommendation,
                "confidence": sentiment.confidence
            }
            results.append(result)

            # Display
            emoji = "+" if sentiment.score >= 70 else ("=" if sentiment.score >= 50 else "-")
            print(f"{emoji} {symbol}: {sentiment.score}/100 ({sentiment.grade}) - {sentiment.recommendation}")

        except Exception as e:
            print(f"  {symbol}: Error - {e}")

    # Sort by score
    results.sort(key=lambda x: x["score"], reverse=True)

    # Top opportunities
    print("\n" + "-" * 50)
    print("TOP OPPORTUNITIES:")
    for i, r in enumerate(results[:3], 1):
        print(f"{i}. {r['symbol']}: {r['score']}/100 - {r['signal']}")

    return results


# =============================================================================
# Example 3: Compare Dexter vs Sentiment Pipeline
# =============================================================================

async def example_dexter_comparison():
    """
    Compare Dexter ReAct decision with simple sentiment.

    This example:
    1. Gets sentiment-only signal
    2. Gets Dexter ReAct decision
    3. Compares the two approaches
    4. Shows reasoning trace
    """
    from core.sentiment_aggregator import get_aggregated_sentiment
    from core.dexter.agent import DexterAgent

    token_symbol = "SOL"

    print(f"Comparing analysis methods for {token_symbol}")
    print("=" * 50)

    # Method 1: Simple Sentiment
    print("\n1. SIMPLE SENTIMENT PIPELINE")
    print("-" * 30)

    sentiment = await get_aggregated_sentiment(token_symbol)
    print(f"Score: {sentiment.score}/100")
    print(f"Grade: {sentiment.grade}")
    print(f"Signal: {sentiment.recommendation}")
    print(f"Confidence: {sentiment.confidence}%")

    # Method 2: Dexter ReAct
    print("\n2. DEXTER REACT AGENT")
    print("-" * 30)

    # Initialize Dexter (requires Grok client)
    try:
        from bots.twitter.grok_client import GrokClient
        grok = GrokClient()
        dexter = DexterAgent(grok_client=grok)

        decision = await dexter.analyze_trading_opportunity(token_symbol)

        print(f"Decision: {decision.decision.value}")
        print(f"Confidence: {decision.confidence}%")
        print(f"Grok Sentiment: {decision.grok_sentiment_score}/100")
        print(f"Iterations: {decision.iterations}")
        print(f"Cost: ${decision.cost_usd:.3f}")

        # Show reasoning trace
        print("\nReasoning Trace:")
        print(dexter.get_scratchpad())

    except Exception as e:
        print(f"Dexter unavailable: {e}")
        decision = None

    # Comparison
    print("\n3. COMPARISON")
    print("-" * 30)

    if decision:
        agree = (
            (sentiment.recommendation == "BUY" and decision.decision.value == "TRADE_BUY") or
            (sentiment.recommendation == "SELL" and decision.decision.value == "TRADE_SELL") or
            (sentiment.recommendation == "HOLD" and decision.decision.value == "HOLD")
        )
        print(f"Methods Agree: {'YES' if agree else 'NO'}")
        print(f"Sentiment Signal: {sentiment.recommendation}")
        print(f"Dexter Decision: {decision.decision.value}")

        if not agree:
            print("\nNote: Dexter considers more factors (whale activity, technicals)")
            print("      and may disagree with pure sentiment signals.")
    else:
        print("Dexter unavailable for comparison")

    return {
        "sentiment": sentiment,
        "dexter": decision
    }


# =============================================================================
# Example 4: Batch Token Analysis
# =============================================================================

async def example_batch_analysis():
    """
    Efficiently analyze multiple tokens in parallel.

    This example:
    1. Creates analysis tasks
    2. Runs them in parallel
    3. Aggregates results
    4. Returns sorted by opportunity score
    """
    from core.market_data_service import get_market_data_service

    market_data = await get_market_data_service()

    # Token mints to analyze
    tokens = [
        ("SOL", "So11111111111111111111111111111111111111112"),
        ("BONK", "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"),
        ("WIF", "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"),
        ("JUP", "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"),
        ("PYTH", "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3"),
    ]

    print("Running batch analysis...")

    async def analyze_one(symbol: str, mint: str):
        """Analyze a single token."""
        try:
            price_data = await market_data.get_token_price(mint)
            return {
                "symbol": symbol,
                "mint": mint,
                "price": price_data.get("price", 0),
                "change_24h": price_data.get("change_24h", 0),
                "volume": price_data.get("volume_24h", 0),
                "status": "success"
            }
        except Exception as e:
            return {
                "symbol": symbol,
                "mint": mint,
                "status": "error",
                "error": str(e)
            }

    # Run all analyses in parallel
    tasks = [analyze_one(symbol, mint) for symbol, mint in tokens]
    results = await asyncio.gather(*tasks)

    # Filter successful results
    successful = [r for r in results if r["status"] == "success"]

    # Sort by 24h change
    successful.sort(key=lambda x: x["change_24h"], reverse=True)

    print("\nResults (sorted by 24h change):")
    print("-" * 60)
    print(f"{'Symbol':<8} {'Price':>12} {'24h Change':>12} {'Volume':>15}")
    print("-" * 60)

    for r in successful:
        print(f"{r['symbol']:<8} ${r['price']:>10.4f} {r['change_24h']:>+11.2f}% ${r['volume']:>13,.0f}")

    return successful


# =============================================================================
# Example 5: Risk Assessment Pipeline
# =============================================================================

async def example_risk_assessment():
    """
    Full risk assessment for a token.

    This example:
    1. Checks liquidity
    2. Analyzes holder concentration
    3. Checks contract safety
    4. Calculates overall risk score
    """
    from bots.treasury.trading import TradingEngine
    from bots.treasury.wallet import SecureWallet
    from bots.treasury.jupiter import JupiterClient

    # Initialize
    wallet = SecureWallet()
    jupiter = JupiterClient()
    engine = TradingEngine(wallet=wallet, jupiter=jupiter, dry_run=True)

    # Token to assess
    token_mint = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK
    token_symbol = "BONK"

    print(f"Risk Assessment: {token_symbol}")
    print("=" * 50)

    # 1. Token classification
    risk_class = engine.classify_token_risk(token_mint, token_symbol)
    print(f"\n1. Token Classification: {risk_class}")

    # 2. Check if established
    is_established = engine.is_established_token(token_mint)
    print(f"2. Established Token: {'Yes' if is_established else 'No'}")

    # 3. Check if high risk
    is_high_risk = engine.is_high_risk_token(token_mint)
    print(f"3. High Risk Patterns: {'Yes' if is_high_risk else 'No'}")

    # 4. Position size recommendation
    base_position = 100  # $100 base
    adjusted = engine.get_risk_adjusted_position_size(
        token_mint=token_mint,
        token_symbol=token_symbol,
        base_position_usd=base_position
    )
    print(f"4. Position Size Adjustment:")
    print(f"   Base: ${base_position}")
    print(f"   Adjusted: ${adjusted:.2f}")
    print(f"   Reduction: {((base_position - adjusted) / base_position * 100):.0f}%")

    # 5. Risk summary
    print(f"\n5. Risk Summary:")
    if risk_class == "ESTABLISHED":
        print("   LOW RISK - Safe to trade with normal size")
    elif risk_class == "MID":
        print("   MEDIUM RISK - Trade with caution, reduced size")
    elif risk_class == "HIGH_RISK":
        print("   HIGH RISK - Very small positions only")
    else:
        print("   MICRO CAP - High risk, minimal exposure")


# =============================================================================
# Main - Run Examples
# =============================================================================

async def main():
    """Run all analysis examples."""
    print("\n" + "=" * 60)
    print("JARVIS Analysis Examples")
    print("=" * 60)

    # Example 1: Analyze Token
    print("\n--- Example 1: Token Analysis ---")
    try:
        await example_analyze_token()
    except Exception as e:
        print(f"Error: {e}")

    # Example 2: Multi-Token Signals
    print("\n--- Example 2: Multi-Token Signals ---")
    try:
        await example_multi_token_signals()
    except Exception as e:
        print(f"Error: {e}")

    # Example 3: Batch Analysis
    print("\n--- Example 3: Batch Analysis ---")
    try:
        await example_batch_analysis()
    except Exception as e:
        print(f"Error: {e}")

    # Example 4: Risk Assessment
    print("\n--- Example 4: Risk Assessment ---")
    try:
        await example_risk_assessment()
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 60)
    print("Analysis examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
