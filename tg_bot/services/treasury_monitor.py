"""
Treasury Monitor - US-004 Treasury Integration

Real-time monitoring of treasury positions with live PnL updates.

Architecture:
- WebSocket connection for real-time price feeds
- 5-second update interval for live PnL
- Tracks all open positions from positions.json
- Sends Telegram alerts on significant PnL changes
- Provides recent trading signals display

Data Sources:
- Position data: ~/.lifeos/trading/demo_positions.json
- Price feeds: bags.fm WebSocket API
- Treasury signals: bots/treasury/.signals.json

Features:
- Live PnL tracking (updates every 5s)
- Alert thresholds: +10% gain, -5% loss
- Copy trading integration
- Recent signals history

Storage: Updates positions.json with current_price
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import traceback

logger = logging.getLogger(__name__)

# File paths
POSITIONS_FILE = Path.home() / ".lifeos" / "trading" / "demo_positions.json"
TREASURY_SIGNALS_FILE = Path("bots") / "treasury" / ".signals.json"


# =============================================================================
# Position Loader
# =============================================================================

def load_treasury_positions() -> List[Dict[str, Any]]:
    """Load open treasury positions from disk."""
    if not POSITIONS_FILE.exists():
        return []

    try:
        with open(POSITIONS_FILE, 'r') as f:
            data = json.load(f)
            positions = data.get("positions", [])

            # Filter to only open positions
            return [p for p in positions if p.get("status") == "open"]

    except Exception as e:
        logger.error(f"Failed to load treasury positions: {e}")
        return []


def update_position_price(position_id: str, current_price: float):
    """Update current price for a position."""
    try:
        if not POSITIONS_FILE.exists():
            return

        with open(POSITIONS_FILE, 'r') as f:
            data = json.load(f)

        positions = data.get("positions", [])

        for pos in positions:
            if pos.get("id") == position_id:
                pos["current_price"] = current_price
                pos["last_updated"] = datetime.now(timezone.utc).isoformat()
                break

        with open(POSITIONS_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    except Exception as e:
        logger.error(f"Failed to update position price: {e}")


# =============================================================================
# Treasury Signals Loader
# =============================================================================

def load_treasury_signals(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Load recent trading signals from treasury bot.

    Args:
        limit: Max number of signals to return

    Returns:
        List of recent signals
    """
    if not TREASURY_SIGNALS_FILE.exists():
        return []

    try:
        with open(TREASURY_SIGNALS_FILE, 'r') as f:
            data = json.load(f)
            signals = data.get("signals", [])

            # Sort by timestamp (newest first)
            signals.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            return signals[:limit]

    except Exception as e:
        logger.error(f"Failed to load treasury signals: {e}")
        return []


# =============================================================================
# Price Fetcher
# =============================================================================

async def get_current_price(token_address: str) -> Optional[float]:
    """
    Get current token price from bags.fm API.

    Args:
        token_address: Token mint address

    Returns:
        Current price in USD, or None if unavailable
    """
    try:
        from core.bags_api import get_bags_api

        api = get_bags_api()
        token_info = await api.get_token_info(token_address)

        if token_info:
            return float(token_info.get("price_usd", 0) or token_info.get("price", 0) or 0)

        return None

    except Exception as e:
        logger.error(f"Failed to get price for {token_address}: {e}")
        return None


# =============================================================================
# Alert System
# =============================================================================

async def send_pnl_alert(
    position: Dict[str, Any],
    pnl_pct: float,
    alert_type: str
):
    """
    Send Telegram alert for significant PnL changes.

    Args:
        position: Position dict
        pnl_pct: Current PnL percentage
        alert_type: "gain" or "loss"
    """
    try:
        from tg_bot.bot_core import application
        from core.config.loader import load_config

        config = load_config()
        admin_ids = config.get("telegram", {}).get("admin_ids", [])

        if not admin_ids or not application:
            return

        # Format alert message
        emoji = "🚀" if alert_type == "gain" else "⚠️"
        symbol = position.get("symbol", "TOKEN")
        entry_price = position.get("entry_price", 0)
        current_price = position.get("current_price", 0)

        message = (
            f"{emoji} **Treasury Alert: {alert_type.upper()}**\n\n"
            f"**Token:** {symbol}\n"
            f"**Entry:** ${entry_price:.6f}\n"
            f"**Current:** ${current_price:.6f}\n"
            f"**PnL:** {pnl_pct:+.1f}%\n"
            f"**Amount:** {position.get('amount', 0):,.0f} tokens\n"
        )

        # Send to all admins
        for admin_id in admin_ids:
            try:
                await application.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to send alert to {admin_id}: {e}")

    except Exception as e:
        logger.error(f"Failed to send PnL alert: {e}")


# =============================================================================
# Treasury Monitor Service
# =============================================================================

class TreasuryMonitor:
    """
    Background service monitoring treasury positions with live PnL.

    Usage:
        monitor = TreasuryMonitor()
        await monitor.start()  # Runs forever
    """

    def __init__(self, update_interval: int = 5):
        """
        Initialize treasury monitor.

        Args:
            update_interval: Seconds between price updates (default 5s)
        """
        self.update_interval = update_interval
        self.running = False
        self.last_alerts = {}  # Track when alerts were sent

    async def start(self):
        """Start monitoring loop (runs forever)."""
        self.running = True
        logger.info(f"💼 Treasury monitor started (updating every {self.update_interval}s)")

        while self.running:
            try:
                await self.update_all_positions()

            except Exception as e:
                logger.error(f"Treasury monitor error: {e}")
                logger.error(traceback.format_exc())

            # Wait for next update
            await asyncio.sleep(self.update_interval)

    async def update_all_positions(self):
        """Update prices and PnL for all open positions."""
        positions = load_treasury_positions()

        if not positions:
            return  # Nothing to monitor

        logger.debug(f"Updating {len(positions)} treasury positions")

        for position in positions:
            try:
                await self.update_position(position)
            except Exception as e:
                logger.error(f"Failed to update position {position.get('id')}: {e}")

    async def update_position(self, position: Dict[str, Any]):
        """
        Update a single position with current price and check alerts.

        Args:
            position: Position dict
        """
        position_id = position.get("id")
        token_address = position.get("address")
        entry_price = float(position.get("entry_price", 0) or 0)

        if not token_address or entry_price <= 0:
            return

        # Get current price
        current_price = await get_current_price(token_address)

        if current_price is None:
            return

        # Update position file
        update_position_price(position_id, current_price)

        # Calculate PnL
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Check alert thresholds
        await self.check_alerts(position, pnl_pct)

    async def check_alerts(self, position: Dict[str, Any], pnl_pct: float):
        """
        Check if position meets alert thresholds.

        Args:
            position: Position dict
            pnl_pct: Current PnL percentage
        """
        position_id = position.get("id")

        # Alert thresholds
        GAIN_THRESHOLD = 10.0  # +10% gain
        LOSS_THRESHOLD = -5.0  # -5% loss

        # Check if we already sent alert for this position
        last_alert_time = self.last_alerts.get(position_id)

        # Don't send duplicate alerts within 1 hour
        if last_alert_time:
            elapsed = (datetime.now(timezone.utc) - last_alert_time).total_seconds()
            if elapsed < 3600:  # 1 hour
                return

        # Check thresholds
        if pnl_pct >= GAIN_THRESHOLD:
            await send_pnl_alert(position, pnl_pct, "gain")
            self.last_alerts[position_id] = datetime.now(timezone.utc)
            logger.info(f"🚀 Gain alert: {position.get('symbol')} @ {pnl_pct:+.1f}%")

        elif pnl_pct <= LOSS_THRESHOLD:
            await send_pnl_alert(position, pnl_pct, "loss")
            self.last_alerts[position_id] = datetime.now(timezone.utc)
            logger.info(f"⚠️ Loss alert: {position.get('symbol')} @ {pnl_pct:+.1f}%")

    def stop(self):
        """Stop the monitoring loop."""
        self.running = False
        logger.info("Treasury monitor stopped")


# =============================================================================
# Singleton Instance
# =============================================================================

_monitor_instance: Optional[TreasuryMonitor] = None


def get_treasury_monitor() -> TreasuryMonitor:
    """Get singleton treasury monitor instance."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = TreasuryMonitor()
    return _monitor_instance


async def start_treasury_monitor():
    """Start the treasury monitor service (for use in supervisor)."""
    monitor = get_treasury_monitor()
    await monitor.start()


# =============================================================================
# Query API (for demo.py UI)
# =============================================================================

def get_live_treasury_summary() -> Dict[str, Any]:
    """
    Get summary of treasury positions with live PnL.

    Returns:
        {
            "total_positions": 5,
            "total_value_sol": 10.5,
            "total_pnl_usd": 250.0,
            "total_pnl_pct": 12.5,
            "top_gainers": [...],
            "top_losers": [...],
        }
    """
    try:
        positions = load_treasury_positions()

        if not positions:
            return {
                "total_positions": 0,
                "total_value_sol": 0.0,
                "total_pnl_usd": 0.0,
                "total_pnl_pct": 0.0,
                "top_gainers": [],
                "top_losers": [],
            }

        # Calculate totals
        total_value_sol = sum(p.get("amount_sol", 0) for p in positions)
        total_pnl_usd = 0.0
        pnl_list = []

        for pos in positions:
            entry_price = float(pos.get("entry_price", 0) or 0)
            current_price = float(pos.get("current_price", 0) or 0)
            amount = float(pos.get("amount", 0) or 0)

            if entry_price > 0 and current_price > 0:
                pnl_usd = (current_price - entry_price) * amount
                pnl_pct = ((current_price - entry_price) / entry_price) * 100

                total_pnl_usd += pnl_usd
                pnl_list.append({
                    "symbol": pos.get("symbol", "TOKEN"),
                    "pnl_pct": pnl_pct,
                    "pnl_usd": pnl_usd,
                })

        # Calculate average PnL percentage
        total_pnl_pct = (total_pnl_usd / total_value_sol * 100) if total_value_sol > 0 else 0.0

        # Sort for top gainers/losers
        pnl_list.sort(key=lambda x: x["pnl_pct"], reverse=True)
        top_gainers = pnl_list[:3]
        top_losers = list(reversed(pnl_list[-3:]))

        return {
            "total_positions": len(positions),
            "total_value_sol": total_value_sol,
            "total_pnl_usd": total_pnl_usd,
            "total_pnl_pct": total_pnl_pct,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
        }

    except Exception as e:
        logger.error(f"Failed to get treasury summary: {e}")
        return {
            "total_positions": 0,
            "total_value_sol": 0.0,
            "total_pnl_usd": 0.0,
            "total_pnl_pct": 0.0,
            "top_gainers": [],
            "top_losers": [],
        }


# =============================================================================
# Manual Testing
# =============================================================================

if __name__ == "__main__":
    # Test the treasury monitor
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    async def test():
        """Test treasury monitor."""
        monitor = TreasuryMonitor(update_interval=5)  # 5 seconds

        print("Starting treasury monitor test...")
        print("Add positions to ~/.lifeos/trading/demo_positions.json to see live updates")
        print("Press Ctrl+C to stop\n")

        try:
            await monitor.start()
        except KeyboardInterrupt:
            print("\nStopping...")
            monitor.stop()

    asyncio.run(test())
