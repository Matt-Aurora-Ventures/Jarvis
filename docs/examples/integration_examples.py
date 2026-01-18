#!/usr/bin/env python3
"""
JARVIS Integration Examples

This module demonstrates how to integrate with JARVIS services.

Examples:
1. Send custom analysis to Telegram
2. Query logs for audit trail
3. Generate financial reports
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# =============================================================================
# Example 1: Send Custom Analysis to Telegram
# =============================================================================

async def example_send_telegram_analysis():
    """
    Send a custom analysis report to Telegram.

    This example:
    1. Creates a custom analysis
    2. Formats it for Telegram (HTML)
    3. Sends to admin user
    """
    from telegram import Bot
    import os

    # Get bot token from environment
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    admin_id = os.environ.get("JARVIS_ADMIN_USER_ID")

    if not token or not admin_id:
        print("Telegram credentials not configured")
        print("Set TELEGRAM_BOT_TOKEN and JARVIS_ADMIN_USER_ID")
        return

    bot = Bot(token=token)

    # Create custom analysis
    analysis = {
        "title": "Custom Market Analysis",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tokens": [
            {"symbol": "SOL", "sentiment": 78, "signal": "BUY"},
            {"symbol": "BONK", "sentiment": 65, "signal": "HOLD"},
            {"symbol": "WIF", "sentiment": 72, "signal": "BUY"},
        ],
        "market_overview": "Bullish momentum continuing",
        "risk_level": "MODERATE"
    }

    # Format for Telegram (HTML)
    message = f"""<b>{analysis['title']}</b>
<i>{analysis['timestamp']}</i>

<b>Token Signals:</b>
"""

    for token in analysis['tokens']:
        emoji = "" if token['signal'] == "BUY" else ("" if token['signal'] == "SELL" else "")
        message += f"{emoji} {token['symbol']}: {token['sentiment']}/100 - {token['signal']}\n"

    message += f"""
<b>Market Overview:</b>
{analysis['market_overview']}

<b>Risk Level:</b> {analysis['risk_level']}
"""

    # Send to admin
    try:
        await bot.send_message(
            chat_id=admin_id,
            text=message,
            parse_mode="HTML"
        )
        print("Analysis sent to Telegram!")
    except Exception as e:
        print(f"Failed to send: {e}")


# =============================================================================
# Example 2: Query Logs for Audit Trail
# =============================================================================

def example_query_audit_logs():
    """
    Query JSONL audit logs for trading activity.

    This example:
    1. Reads audit log file
    2. Filters by event type
    3. Calculates statistics
    4. Returns formatted results
    """
    import json
    from pathlib import Path

    # Log file location
    log_file = Path.home() / ".lifeos" / "logs" / "trading.jsonl"

    # Alternative location
    if not log_file.exists():
        log_file = Path(__file__).resolve().parents[2] / "logs" / "trading.jsonl"

    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        print("Creating sample log for demonstration...")

        # Create sample log
        log_file.parent.mkdir(parents=True, exist_ok=True)
        sample_logs = [
            {"timestamp": "2026-01-18T10:00:00Z", "event": "TRADE_EXECUTED", "token": "SOL", "pnl_usd": 25.0},
            {"timestamp": "2026-01-18T11:00:00Z", "event": "TRADE_EXECUTED", "token": "BONK", "pnl_usd": -5.0},
            {"timestamp": "2026-01-18T12:00:00Z", "event": "TRADE_EXECUTED", "token": "WIF", "pnl_usd": 15.0},
        ]
        with open(log_file, "w") as f:
            for log in sample_logs:
                f.write(json.dumps(log) + "\n")

    # Read and parse logs
    trades = []
    with open(log_file, "r") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("event") == "TRADE_EXECUTED":
                    trades.append(entry)
            except json.JSONDecodeError:
                continue

    print(f"Found {len(trades)} trades in audit log")
    print("-" * 50)

    # Calculate statistics
    total_pnl = sum(t.get("pnl_usd", 0) for t in trades)
    winning = [t for t in trades if t.get("pnl_usd", 0) > 0]
    losing = [t for t in trades if t.get("pnl_usd", 0) < 0]

    print(f"Total Trades: {len(trades)}")
    print(f"Winning: {len(winning)}")
    print(f"Losing: {len(losing)}")
    print(f"Win Rate: {len(winning)/max(len(trades), 1)*100:.1f}%")
    print(f"Total PnL: ${total_pnl:+.2f}")

    # Recent trades
    print("\nRecent Trades:")
    for trade in trades[-5:]:
        print(f"  {trade.get('timestamp', 'N/A')} | {trade.get('token', 'N/A')} | ${trade.get('pnl_usd', 0):+.2f}")

    return trades


# =============================================================================
# Example 3: Generate Financial Report
# =============================================================================

async def example_generate_report():
    """
    Generate a comprehensive financial report.

    This example:
    1. Collects trading data
    2. Calculates metrics
    3. Generates formatted report
    4. Exports to file
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

    # Create report document
    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_content = f"""
================================================================================
                         JARVIS TRADING REPORT
                              {report_date}
================================================================================

EXECUTIVE SUMMARY
-----------------
Total Trades Executed: {report.total_trades}
Win Rate: {report.win_rate:.1f}%
Net Profit/Loss: ${report.total_pnl_usd:+.2f}

DETAILED METRICS
----------------
Winning Trades: {report.winning_trades}
Losing Trades: {report.losing_trades}

Best Trade: ${report.best_trade_pnl:+.2f}
Worst Trade: ${report.worst_trade_pnl:+.2f}
Average Trade: ${report.avg_trade_pnl:+.2f}

Average Win: ${report.average_win_usd:+.2f}
Average Loss: ${report.average_loss_usd:.2f}

CURRENT POSITIONS
-----------------
Open Positions: {report.open_positions}
Unrealized P&L: ${report.unrealized_pnl:+.2f}

RISK ASSESSMENT
---------------
Current Exposure: {'HIGH' if report.open_positions > 10 else 'MODERATE' if report.open_positions > 5 else 'LOW'}
Portfolio Heat: {'ELEVATED' if report.unrealized_pnl < 0 else 'NORMAL'}

RECOMMENDATIONS
---------------
1. {'Continue current strategy' if report.win_rate > 60 else 'Review losing trades for patterns'}
2. {'Consider taking profits' if report.unrealized_pnl > 100 else 'Monitor open positions'}
3. {'Risk management healthy' if report.open_positions < 10 else 'Consider reducing exposure'}

================================================================================
                         Generated by JARVIS
                      {datetime.now(timezone.utc).isoformat()}
================================================================================
"""

    # Save report
    reports_dir = Path(__file__).resolve().parents[2] / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_file = reports_dir / f"trading_report_{report_date}.txt"

    with open(report_file, "w") as f:
        f.write(report_content)

    print(f"Report saved to: {report_file}")
    print("\nReport Preview:")
    print(report_content[:1000] + "...")

    return report_file


# =============================================================================
# Example 4: WebSocket Price Feed
# =============================================================================

async def example_websocket_feed():
    """
    Connect to WebSocket for real-time updates.

    This example:
    1. Connects to JARVIS WebSocket
    2. Subscribes to trading channel
    3. Receives real-time updates
    4. Processes messages
    """
    import websockets

    ws_url = "ws://localhost:8766/ws/trading"

    print(f"Connecting to {ws_url}...")

    try:
        async with websockets.connect(ws_url) as ws:
            print("Connected! Listening for updates...")

            # Send ping to keep alive
            await ws.send("ping")

            # Listen for messages
            message_count = 0
            while message_count < 5:  # Receive 5 messages then exit
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    data = json.loads(message)

                    if data.get("type") == "pong":
                        print("  Received pong")
                    elif data.get("type") == "position_update":
                        print(f"  Position update: {data.get('data')}")
                    elif data.get("type") == "price_update":
                        print(f"  Price update: {data.get('data')}")
                    else:
                        print(f"  Message: {data}")

                    message_count += 1

                except asyncio.TimeoutError:
                    print("  Timeout - sending ping")
                    await ws.send("ping")

    except Exception as e:
        print(f"WebSocket error: {e}")
        print("Note: WebSocket server must be running (python api/fastapi_app.py)")


# =============================================================================
# Example 5: Event Bus Integration
# =============================================================================

async def example_event_bus():
    """
    Publish and subscribe to JARVIS event bus.

    This example:
    1. Gets event bus instance
    2. Subscribes to trading events
    3. Publishes custom event
    4. Processes received events
    """
    try:
        from core.event_bus.bus import EventBus

        bus = EventBus()

        # Subscribe to trading events
        events_received = []

        async def on_trade(event):
            print(f"Received event: {event}")
            events_received.append(event)

        await bus.subscribe("trade.*", on_trade)
        print("Subscribed to trade.* events")

        # Publish a test event
        await bus.publish("trade.executed", {
            "token": "SOL",
            "amount": 50.0,
            "price": 105.50,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        print("Published trade.executed event")

        # Wait for event processing
        await asyncio.sleep(1)

        print(f"Events received: {len(events_received)}")

    except ImportError:
        print("Event bus not available")
        print("This feature requires the core.event_bus module")


# =============================================================================
# Main - Run Examples
# =============================================================================

async def main():
    """Run all integration examples."""
    print("\n" + "=" * 60)
    print("JARVIS Integration Examples")
    print("=" * 60)

    # Example 1: Query Audit Logs
    print("\n--- Example 1: Query Audit Logs ---")
    try:
        example_query_audit_logs()
    except Exception as e:
        print(f"Error: {e}")

    # Example 2: Generate Report
    print("\n--- Example 2: Generate Financial Report ---")
    try:
        await example_generate_report()
    except Exception as e:
        print(f"Error: {e}")

    # Example 3: Event Bus (if available)
    print("\n--- Example 3: Event Bus ---")
    try:
        await example_event_bus()
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 60)
    print("Integration examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
