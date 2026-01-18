#!/usr/bin/env python3
"""
JARVIS Trading Examples

This module demonstrates how to use JARVIS trading APIs programmatically.

Examples:
1. Execute a trade with sentiment signals
2. Monitor position in real-time
3. Set take-profit and stop-loss
4. Exit position manually
"""

import asyncio
import os
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# =============================================================================
# Example 1: Execute a Trade with Sentiment Signals
# =============================================================================

async def example_execute_trade():
    """
    Execute a trade based on sentiment analysis.

    This example:
    1. Analyzes token sentiment
    2. Checks if sentiment is favorable
    3. Calculates position size
    4. Executes the trade
    """
    from bots.treasury.trading import TradingEngine, TradeDirection, RiskLevel
    from bots.treasury.wallet import SecureWallet
    from bots.treasury.jupiter import JupiterClient

    # Initialize trading components
    wallet = SecureWallet()
    jupiter = JupiterClient()
    engine = TradingEngine(
        wallet=wallet,
        jupiter=jupiter,
        risk_level=RiskLevel.MODERATE,
        dry_run=True  # Set to False for live trading
    )

    # Token to trade
    token_mint = "So11111111111111111111111111111111111111112"  # SOL
    token_symbol = "SOL"
    amount_usd = 50.0

    # Get sentiment analysis
    from core.sentiment_aggregator import get_aggregated_sentiment

    sentiment = await get_aggregated_sentiment(token_symbol)
    print(f"Sentiment for {token_symbol}: {sentiment.score}/100 ({sentiment.grade})")

    # Only trade if sentiment is bullish (>65)
    if sentiment.score < 65:
        print("Sentiment too low, skipping trade")
        return None

    # Execute trade
    position = await engine.open_position(
        token_mint=token_mint,
        token_symbol=token_symbol,
        amount_usd=amount_usd,
        sentiment_grade=sentiment.grade,
        sentiment_score=sentiment.score
    )

    if position:
        print(f"Position opened: {position.id}")
        print(f"  Entry: ${position.entry_price:.4f}")
        print(f"  Amount: {position.amount} {token_symbol}")
        print(f"  TP: ${position.take_profit_price:.4f}")
        print(f"  SL: ${position.stop_loss_price:.4f}")

    return position


# =============================================================================
# Example 2: Monitor Position in Real-Time
# =============================================================================

async def example_monitor_position(position_id: str):
    """
    Monitor a position with real-time price updates.

    This example:
    1. Loads an existing position
    2. Fetches current price
    3. Calculates unrealized PnL
    4. Checks TP/SL levels
    """
    from bots.treasury.trading import TradingEngine
    from bots.treasury.wallet import SecureWallet
    from bots.treasury.jupiter import JupiterClient

    # Initialize
    wallet = SecureWallet()
    jupiter = JupiterClient()
    engine = TradingEngine(wallet=wallet, jupiter=jupiter, dry_run=True)

    # Get position
    position = engine.get_position(position_id)
    if not position:
        print(f"Position {position_id} not found")
        return

    print(f"Monitoring position: {position.token_symbol}")

    # Monitor loop
    while position.is_open:
        # Get current price
        current_price = await jupiter.get_token_price(position.token_mint)

        # Update position with current price
        position.current_price = current_price

        # Calculate PnL
        pnl_pct = position.unrealized_pnl_pct
        pnl_usd = position.unrealized_pnl

        print(f"  Price: ${current_price:.4f} | PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})")

        # Check TP/SL
        if current_price >= position.take_profit_price:
            print("  Take Profit hit!")
            break
        elif current_price <= position.stop_loss_price:
            print("  Stop Loss hit!")
            break

        # Wait before next update
        await asyncio.sleep(10)


# =============================================================================
# Example 3: Set Take-Profit and Stop-Loss
# =============================================================================

async def example_set_tp_sl():
    """
    Update take-profit and stop-loss for existing position.

    This example:
    1. Gets an existing position
    2. Updates TP/SL levels
    3. Places limit orders (if supported)
    """
    from bots.treasury.trading import TradingEngine
    from bots.treasury.wallet import SecureWallet
    from bots.treasury.jupiter import JupiterClient

    # Initialize
    wallet = SecureWallet()
    jupiter = JupiterClient()
    engine = TradingEngine(wallet=wallet, jupiter=jupiter, dry_run=True)

    # Get open positions
    positions = engine.get_open_positions()

    if not positions:
        print("No open positions")
        return

    # Update first position
    position = positions[0]
    print(f"Updating TP/SL for {position.token_symbol}")

    # Original levels
    print(f"  Original TP: ${position.take_profit_price:.4f}")
    print(f"  Original SL: ${position.stop_loss_price:.4f}")

    # Calculate new levels (e.g., 25% TP, 12% SL)
    entry = position.entry_price
    new_tp = entry * 1.25  # +25%
    new_sl = entry * 0.88  # -12%

    # Update position
    position.take_profit_price = new_tp
    position.stop_loss_price = new_sl
    engine._save_state()  # Persist changes

    print(f"  New TP: ${new_tp:.4f} (+25%)")
    print(f"  New SL: ${new_sl:.4f} (-12%)")


# =============================================================================
# Example 4: Exit Position Manually
# =============================================================================

async def example_exit_position(position_id: str):
    """
    Manually close a position.

    This example:
    1. Gets position by ID
    2. Fetches current market price
    3. Closes position at market
    4. Records PnL
    """
    from bots.treasury.trading import TradingEngine
    from bots.treasury.wallet import SecureWallet
    from bots.treasury.jupiter import JupiterClient

    # Initialize
    wallet = SecureWallet()
    jupiter = JupiterClient()
    engine = TradingEngine(wallet=wallet, jupiter=jupiter, dry_run=True)

    # Get position
    position = engine.get_position(position_id)
    if not position:
        print(f"Position {position_id} not found")
        return

    print(f"Closing position: {position.token_symbol}")
    print(f"  Entry: ${position.entry_price:.4f}")
    print(f"  Amount: {position.amount} tokens")

    # Close position
    closed_position = await engine.close_position(
        position_id=position_id,
        reason="Manual exit"
    )

    if closed_position:
        print(f"Position closed!")
        print(f"  Exit: ${closed_position.exit_price:.4f}")
        print(f"  PnL: ${closed_position.pnl_usd:+.2f} ({closed_position.pnl_pct:+.2f}%)")


# =============================================================================
# Example 5: Get Trading Report
# =============================================================================

async def example_trading_report():
    """
    Generate a trading performance report.

    This example:
    1. Gets all closed trades
    2. Calculates win rate
    3. Calculates total PnL
    4. Identifies best/worst trades
    """
    from bots.treasury.trading import TradingEngine
    from bots.treasury.wallet import SecureWallet
    from bots.treasury.jupiter import JupiterClient

    # Initialize
    wallet = SecureWallet()
    jupiter = JupiterClient()
    engine = TradingEngine(wallet=wallet, jupiter=jupiter, dry_run=True)

    # Generate report
    report = engine.generate_report()

    print("=" * 50)
    print("TRADING PERFORMANCE REPORT")
    print("=" * 50)
    print(f"Total Trades: {report.total_trades}")
    print(f"Win Rate: {report.win_rate:.1f}%")
    print(f"Winning: {report.winning_trades} | Losing: {report.losing_trades}")
    print()
    print(f"Total PnL: ${report.total_pnl_usd:+.2f}")
    print(f"Best Trade: ${report.best_trade_pnl:+.2f}")
    print(f"Worst Trade: ${report.worst_trade_pnl:+.2f}")
    print(f"Average: ${report.avg_trade_pnl:+.2f}")
    print()
    print(f"Open Positions: {report.open_positions}")
    print(f"Unrealized PnL: ${report.unrealized_pnl:+.2f}")


# =============================================================================
# Main - Run Examples
# =============================================================================

async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("JARVIS Trading Examples")
    print("=" * 60)

    # Example 1: Execute Trade
    print("\n--- Example 1: Execute Trade with Sentiment ---")
    try:
        position = await example_execute_trade()
    except Exception as e:
        print(f"Error: {e}")

    # Example 2: Trading Report
    print("\n--- Example 2: Trading Report ---")
    try:
        await example_trading_report()
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
