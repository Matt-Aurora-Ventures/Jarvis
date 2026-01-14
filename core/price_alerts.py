"""
Price Alerts System for JARVIS.

Monitors token prices and triggers alerts when conditions are met:
- Price crosses above/below threshold
- Percentage change alerts
- Volume spike detection
- Liquidity change alerts

Sends notifications via configured webhooks and Telegram.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
import aiohttp

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
ALERTS_CONFIG_PATH = ROOT / "data" / "price_alerts.json"
ALERTS_HISTORY_PATH = ROOT / "data" / "alerts_history.jsonl"


class AlertType(Enum):
    """Types of price alerts."""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PERCENT_CHANGE_UP = "percent_change_up"
    PERCENT_CHANGE_DOWN = "percent_change_down"
    VOLUME_SPIKE = "volume_spike"
    LIQUIDITY_CHANGE = "liquidity_change"


class AlertStatus(Enum):
    """Status of an alert."""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    PAUSED = "paused"


@dataclass
class PriceAlert:
    """Configuration for a price alert."""
    id: str
    token_symbol: str
    token_mint: str
    alert_type: AlertType
    threshold: float
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    triggered_at: Optional[float] = None
    last_price: Optional[float] = None
    repeat: bool = False  # Trigger again after reset period
    repeat_cooldown_minutes: int = 60
    notify_telegram: bool = True
    notify_webhook: bool = True
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "token_symbol": self.token_symbol,
            "token_mint": self.token_mint,
            "alert_type": self.alert_type.value,
            "threshold": self.threshold,
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "triggered_at": self.triggered_at,
            "last_price": self.last_price,
            "repeat": self.repeat,
            "repeat_cooldown_minutes": self.repeat_cooldown_minutes,
            "notify_telegram": self.notify_telegram,
            "notify_webhook": self.notify_webhook,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PriceAlert:
        return cls(
            id=data["id"],
            token_symbol=data["token_symbol"],
            token_mint=data["token_mint"],
            alert_type=AlertType(data["alert_type"]),
            threshold=data["threshold"],
            status=AlertStatus(data.get("status", "active")),
            created_at=data.get("created_at", time.time()),
            expires_at=data.get("expires_at"),
            triggered_at=data.get("triggered_at"),
            last_price=data.get("last_price"),
            repeat=data.get("repeat", False),
            repeat_cooldown_minutes=data.get("repeat_cooldown_minutes", 60),
            notify_telegram=data.get("notify_telegram", True),
            notify_webhook=data.get("notify_webhook", True),
            note=data.get("note", ""),
        )


@dataclass
class TokenPrice:
    """Current token price data."""
    mint: str
    symbol: str
    price_usd: float
    price_change_5m: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    volume_24h: float = 0.0
    liquidity_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)


class PriceAlertManager:
    """
    Manages price alerts and monitoring.

    Features:
    - Create/update/delete alerts
    - Price monitoring with configurable intervals
    - Multi-channel notifications
    - Alert history tracking
    """

    def __init__(self):
        self.alerts: Dict[str, PriceAlert] = {}
        self._price_cache: Dict[str, TokenPrice] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._on_alert_callbacks: List[Callable] = []
        self._load_alerts()

    def _load_alerts(self) -> None:
        """Load alerts from config file."""
        if not ALERTS_CONFIG_PATH.exists():
            return

        try:
            data = json.loads(ALERTS_CONFIG_PATH.read_text())
            for alert_data in data.get("alerts", []):
                alert = PriceAlert.from_dict(alert_data)
                self.alerts[alert.id] = alert
            logger.info(f"Loaded {len(self.alerts)} price alerts")
        except Exception as e:
            logger.error(f"Failed to load price alerts: {e}")

    def _save_alerts(self) -> None:
        """Save alerts to config file."""
        try:
            ALERTS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "alerts": [a.to_dict() for a in self.alerts.values()],
                "updated_at": time.time(),
            }
            ALERTS_CONFIG_PATH.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save price alerts: {e}")

    def add_alert(self, alert: PriceAlert) -> None:
        """Add a new price alert."""
        self.alerts[alert.id] = alert
        self._save_alerts()
        logger.info(f"Added alert: {alert.token_symbol} {alert.alert_type.value} @ {alert.threshold}")

    def remove_alert(self, alert_id: str) -> bool:
        """Remove an alert by ID."""
        if alert_id in self.alerts:
            del self.alerts[alert_id]
            self._save_alerts()
            logger.info(f"Removed alert: {alert_id}")
            return True
        return False

    def get_alert(self, alert_id: str) -> Optional[PriceAlert]:
        """Get alert by ID."""
        return self.alerts.get(alert_id)

    def list_alerts(self, status: Optional[AlertStatus] = None) -> List[PriceAlert]:
        """List all alerts, optionally filtered by status."""
        alerts = list(self.alerts.values())
        if status:
            alerts = [a for a in alerts if a.status == status]
        return alerts

    def pause_alert(self, alert_id: str) -> bool:
        """Pause an alert."""
        if alert_id in self.alerts:
            self.alerts[alert_id].status = AlertStatus.PAUSED
            self._save_alerts()
            return True
        return False

    def resume_alert(self, alert_id: str) -> bool:
        """Resume a paused alert."""
        if alert_id in self.alerts:
            self.alerts[alert_id].status = AlertStatus.ACTIVE
            self._save_alerts()
            return True
        return False

    def on_alert(self, callback: Callable) -> None:
        """Register callback for when alerts trigger."""
        self._on_alert_callbacks.append(callback)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._session

    async def fetch_token_price(self, mint: str) -> Optional[TokenPrice]:
        """Fetch current price for a token."""
        session = await self._get_session()

        try:
            # Try DexScreener API
            url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])

                    for pair in pairs:
                        if pair.get("chainId") == "solana":
                            price = TokenPrice(
                                mint=mint,
                                symbol=pair.get("baseToken", {}).get("symbol", "?"),
                                price_usd=float(pair.get("priceUsd", 0) or 0),
                                price_change_5m=float(pair.get("priceChange", {}).get("m5", 0) or 0),
                                price_change_1h=float(pair.get("priceChange", {}).get("h1", 0) or 0),
                                price_change_24h=float(pair.get("priceChange", {}).get("h24", 0) or 0),
                                volume_24h=float(pair.get("volume", {}).get("h24", 0) or 0),
                                liquidity_usd=float(pair.get("liquidity", {}).get("usd", 0) or 0),
                            )
                            self._price_cache[mint] = price
                            return price

        except Exception as e:
            logger.warning(f"Failed to fetch price for {mint}: {e}")

        return self._price_cache.get(mint)

    async def check_alerts(self) -> List[PriceAlert]:
        """Check all active alerts against current prices."""
        triggered = []
        now = time.time()

        for alert in list(self.alerts.values()):
            # Skip non-active alerts
            if alert.status != AlertStatus.ACTIVE:
                continue

            # Check expiration
            if alert.expires_at and now > alert.expires_at:
                alert.status = AlertStatus.EXPIRED
                continue

            # Check cooldown for repeating alerts
            if alert.triggered_at and alert.repeat:
                cooldown = alert.repeat_cooldown_minutes * 60
                if now - alert.triggered_at < cooldown:
                    continue

            # Fetch current price
            price_data = await self.fetch_token_price(alert.token_mint)
            if not price_data:
                continue

            current_price = price_data.price_usd
            alert.last_price = current_price

            # Check alert condition
            should_trigger = False

            if alert.alert_type == AlertType.PRICE_ABOVE:
                should_trigger = current_price >= alert.threshold

            elif alert.alert_type == AlertType.PRICE_BELOW:
                should_trigger = current_price <= alert.threshold

            elif alert.alert_type == AlertType.PERCENT_CHANGE_UP:
                should_trigger = price_data.price_change_24h >= alert.threshold

            elif alert.alert_type == AlertType.PERCENT_CHANGE_DOWN:
                should_trigger = price_data.price_change_24h <= -alert.threshold

            elif alert.alert_type == AlertType.VOLUME_SPIKE:
                # Volume > threshold * average (simplified)
                should_trigger = price_data.volume_24h >= alert.threshold

            elif alert.alert_type == AlertType.LIQUIDITY_CHANGE:
                # Liquidity change detection (simplified)
                should_trigger = abs(price_data.liquidity_usd) >= alert.threshold

            if should_trigger:
                alert.triggered_at = now
                if not alert.repeat:
                    alert.status = AlertStatus.TRIGGERED

                triggered.append(alert)
                await self._handle_triggered_alert(alert, price_data)

        self._save_alerts()
        return triggered

    async def _handle_triggered_alert(
        self,
        alert: PriceAlert,
        price_data: TokenPrice,
    ) -> None:
        """Handle a triggered alert."""
        logger.info(f"Alert triggered: {alert.token_symbol} {alert.alert_type.value}")

        # Log to history
        self._log_alert_trigger(alert, price_data)

        # Call registered callbacks
        for callback in self._on_alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert, price_data)
                else:
                    callback(alert, price_data)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

        # Send Telegram notification
        if alert.notify_telegram:
            await self._send_telegram_alert(alert, price_data)

        # Send webhook notifications
        if alert.notify_webhook:
            await self._send_webhook_alert(alert, price_data)

    def _log_alert_trigger(self, alert: PriceAlert, price_data: TokenPrice) -> None:
        """Log alert trigger to history file."""
        try:
            ALERTS_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": time.time(),
                "alert_id": alert.id,
                "token_symbol": alert.token_symbol,
                "token_mint": alert.token_mint,
                "alert_type": alert.alert_type.value,
                "threshold": alert.threshold,
                "triggered_price": price_data.price_usd,
                "price_change_24h": price_data.price_change_24h,
            }
            with open(ALERTS_HISTORY_PATH, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log alert: {e}")

    async def _send_telegram_alert(
        self,
        alert: PriceAlert,
        price_data: TokenPrice,
    ) -> None:
        """Send alert via Telegram."""
        import os

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID")

        if not bot_token or not chat_id:
            return

        # Format alert type
        type_emoji = {
            AlertType.PRICE_ABOVE: "📈",
            AlertType.PRICE_BELOW: "📉",
            AlertType.PERCENT_CHANGE_UP: "🚀",
            AlertType.PERCENT_CHANGE_DOWN: "💥",
            AlertType.VOLUME_SPIKE: "📊",
            AlertType.LIQUIDITY_CHANGE: "💧",
        }

        emoji = type_emoji.get(alert.alert_type, "🔔")
        direction = "above" if "up" in alert.alert_type.value or "above" in alert.alert_type.value else "below"

        message = f"""<b>{emoji} Price Alert: {alert.token_symbol}</b>

<b>Condition:</b> Price {direction} ${alert.threshold:.8f}
<b>Current Price:</b> ${price_data.price_usd:.8f}
<b>24h Change:</b> {price_data.price_change_24h:+.2f}%
<b>Volume 24h:</b> ${price_data.volume_24h:,.0f}

{f'<i>Note: {alert.note}</i>' if alert.note else ''}

<code>{alert.token_mint}</code>"""

        try:
            session = await self._get_session()
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            await session.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
            })
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    async def _send_webhook_alert(
        self,
        alert: PriceAlert,
        price_data: TokenPrice,
    ) -> None:
        """Send alert via webhooks."""
        try:
            from core.webhook_manager import get_webhook_manager, EventType

            manager = get_webhook_manager()
            await manager.notify_alert(
                symbol=alert.token_symbol,
                alert_type=alert.alert_type.value,
                message=f"Price alert triggered: {alert.alert_type.value}",
                price=price_data.price_usd,
            )
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")

    async def start_monitoring(self, interval_seconds: int = 30) -> None:
        """Start background price monitoring."""
        if self._monitoring_task and not self._monitoring_task.done():
            return

        async def monitor_loop():
            while True:
                try:
                    await self.check_alerts()
                except Exception as e:
                    logger.error(f"Alert monitoring error: {e}")
                await asyncio.sleep(interval_seconds)

        self._monitoring_task = asyncio.create_task(monitor_loop())
        logger.info(f"Started price alert monitoring (interval: {interval_seconds}s)")

    async def stop_monitoring(self) -> None:
        """Stop background price monitoring."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            logger.info("Stopped price alert monitoring")

    async def close(self) -> None:
        """Close resources."""
        await self.stop_monitoring()
        if self._session and not self._session.closed:
            await self._session.close()


# Singleton instance
_alert_manager: Optional[PriceAlertManager] = None


def get_alert_manager() -> PriceAlertManager:
    """Get the singleton PriceAlertManager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = PriceAlertManager()
    return _alert_manager


# Convenience functions
def create_price_alert(
    token_symbol: str,
    token_mint: str,
    alert_type: AlertType,
    threshold: float,
    note: str = "",
    repeat: bool = False,
) -> PriceAlert:
    """Create a new price alert."""
    import uuid

    alert = PriceAlert(
        id=str(uuid.uuid4())[:8],
        token_symbol=token_symbol,
        token_mint=token_mint,
        alert_type=alert_type,
        threshold=threshold,
        note=note,
        repeat=repeat,
    )
    get_alert_manager().add_alert(alert)
    return alert


def create_price_above_alert(
    symbol: str,
    mint: str,
    price: float,
    note: str = "",
) -> PriceAlert:
    """Convenience: Create alert when price goes above threshold."""
    return create_price_alert(symbol, mint, AlertType.PRICE_ABOVE, price, note)


def create_price_below_alert(
    symbol: str,
    mint: str,
    price: float,
    note: str = "",
) -> PriceAlert:
    """Convenience: Create alert when price goes below threshold."""
    return create_price_alert(symbol, mint, AlertType.PRICE_BELOW, price, note)


def create_pump_alert(
    symbol: str,
    mint: str,
    percent_threshold: float = 10.0,
    note: str = "",
) -> PriceAlert:
    """Convenience: Create alert when price pumps by X%."""
    return create_price_alert(symbol, mint, AlertType.PERCENT_CHANGE_UP, percent_threshold, note)


def create_dump_alert(
    symbol: str,
    mint: str,
    percent_threshold: float = 10.0,
    note: str = "",
) -> PriceAlert:
    """Convenience: Create alert when price dumps by X%."""
    return create_price_alert(symbol, mint, AlertType.PERCENT_CHANGE_DOWN, percent_threshold, note)


async def start_monitoring(interval_seconds: int = 30) -> None:
    """Start the global alert monitoring."""
    await get_alert_manager().start_monitoring(interval_seconds)


async def stop_monitoring() -> None:
    """Stop the global alert monitoring."""
    await get_alert_manager().stop_monitoring()
