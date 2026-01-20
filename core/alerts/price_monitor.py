"""
Price Alert Monitor

Continuously monitors token prices and triggers alerts when thresholds are met.
Supports:
- Price threshold alerts (above/below)
- Percentage change alerts (up/down from baseline)
- Volume spike detection
- Automatic baseline tracking for percentage alerts
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PriceBaseline:
    """Baseline price for percentage change tracking"""
    token: str
    price: float
    timestamp: datetime = field(default_factory=datetime.now)

    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Check if baseline is too old"""
        age = datetime.now() - self.timestamp
        return age > timedelta(hours=max_age_hours)


class PriceAlertMonitor:
    """
    Monitors token prices and triggers alerts.

    Features:
    - Continuous price monitoring
    - Price threshold detection
    - Percentage change detection
    - Volume spike detection
    - Alert cooldown to prevent spam
    """

    def __init__(
        self,
        alert_engine,
        price_fetcher_func,
        check_interval_seconds: int = 30,
        alert_cooldown_seconds: int = 300,  # 5 minutes
    ):
        """
        Initialize price monitor.

        Args:
            alert_engine: AlertEngine instance
            price_fetcher_func: Async function to fetch price (token_symbol) -> dict
            check_interval_seconds: How often to check prices
            alert_cooldown_seconds: Min time between alerts for same condition
        """
        self.alert_engine = alert_engine
        self.price_fetcher = price_fetcher_func
        self.check_interval = check_interval_seconds
        self.alert_cooldown = alert_cooldown_seconds

        # Track baselines for percentage alerts
        self.baselines: Dict[str, PriceBaseline] = {}

        # Track last alert times (prevent spam)
        self.last_alerts: Dict[str, datetime] = {}

        # Tokens to monitor (derived from active subscriptions)
        self.monitored_tokens: Set[str] = set()

        # Control
        self.running = False

    async def start(self):
        """Start monitoring prices"""
        self.running = True
        logger.info("Price alert monitor started")

        while self.running:
            try:
                await self._check_all_alerts()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Price monitor error: {e}")
                await asyncio.sleep(self.check_interval)

    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Price alert monitor stopped")

    async def _check_all_alerts(self):
        """Check all active alerts"""
        # Get all subscribed tokens
        tokens = self._get_monitored_tokens()

        if not tokens:
            logger.debug("No tokens to monitor")
            return

        # Fetch current prices
        prices = await self._fetch_prices(tokens)

        # Check each subscription
        for user_id, subscriptions in self.alert_engine.subscriptions.items():
            for sub in subscriptions:
                if not sub.enabled:
                    continue

                # Only handle price threshold alerts
                from core.alerts import AlertType
                if sub.alert_type != AlertType.PRICE_THRESHOLD:
                    continue

                # Get token from filters
                token_list = sub.filters.get("tokens", [])
                if not token_list:
                    continue

                token = token_list[0]
                current_price = prices.get(token)

                if current_price is None:
                    logger.debug(f"No price data for {token}")
                    continue

                # Check if alert should trigger
                await self._check_subscription_alert(
                    user_id=user_id,
                    subscription=sub,
                    token=token,
                    current_price=current_price,
                )

    def _get_monitored_tokens(self) -> Set[str]:
        """Get set of all tokens with active alerts"""
        tokens = set()

        for subscriptions in self.alert_engine.subscriptions.values():
            for sub in subscriptions:
                if sub.enabled:
                    token_list = sub.filters.get("tokens", [])
                    tokens.update(token_list)

        return tokens

    async def _fetch_prices(self, tokens: Set[str]) -> Dict[str, float]:
        """Fetch current prices for tokens"""
        prices = {}

        for token in tokens:
            try:
                price_data = await self.price_fetcher(token)
                if isinstance(price_data, dict):
                    price = price_data.get("price_usd") or price_data.get("price")
                else:
                    price = float(price_data)

                if price and price > 0:
                    prices[token] = price

            except Exception as e:
                logger.debug(f"Failed to fetch price for {token}: {e}")

        return prices

    async def _check_subscription_alert(
        self,
        user_id: str,
        subscription,
        token: str,
        current_price: float,
    ):
        """Check if a subscription's conditions are met"""
        filters = subscription.filters

        # Price threshold alert
        if "price_threshold" in filters:
            threshold = filters["price_threshold"]
            direction = filters.get("direction", "above")

            should_alert = False
            if direction == "above" and current_price >= threshold:
                should_alert = True
            elif direction == "below" and current_price <= threshold:
                should_alert = True

            if should_alert:
                alert_key = f"{user_id}:{token}:price:{threshold}:{direction}"
                if self._can_send_alert(alert_key):
                    await self.alert_engine.trigger_price_alert(
                        token=token,
                        current_price=current_price,
                        threshold_price=threshold,
                        direction=direction,
                    )
                    self.last_alerts[alert_key] = datetime.now()

        # Percentage change alert
        if "percentage_change" in filters:
            percentage = filters["percentage_change"]
            direction = filters.get("direction", "up")

            # Get or create baseline
            if token not in self.baselines or self.baselines[token].is_stale():
                self.baselines[token] = PriceBaseline(token=token, price=current_price)
                logger.debug(f"Set baseline for {token}: ${current_price:.6f}")
                return

            baseline = self.baselines[token]
            price_change = ((current_price - baseline.price) / baseline.price) * 100

            should_alert = False
            if direction == "up" and price_change >= percentage:
                should_alert = True
            elif direction == "down" and price_change <= -percentage:
                should_alert = True

            if should_alert:
                alert_key = f"{user_id}:{token}:pct:{percentage}:{direction}"
                if self._can_send_alert(alert_key):
                    await self.alert_engine.trigger_percentage_alert(
                        token=token,
                        current_price=current_price,
                        baseline_price=baseline.price,
                        percentage_change=price_change,
                        direction=direction,
                    )
                    self.last_alerts[alert_key] = datetime.now()

                    # Reset baseline after alert
                    self.baselines[token] = PriceBaseline(token=token, price=current_price)

    def _can_send_alert(self, alert_key: str) -> bool:
        """Check if enough time has passed since last alert"""
        if alert_key not in self.last_alerts:
            return True

        time_since = datetime.now() - self.last_alerts[alert_key]
        return time_since.total_seconds() >= self.alert_cooldown

    def set_baseline(self, token: str, price: float):
        """Manually set baseline price for percentage alerts"""
        self.baselines[token] = PriceBaseline(token=token, price=price)
        logger.info(f"Baseline set for {token}: ${price:.6f}")

    def reset_baseline(self, token: str):
        """Reset baseline for a token"""
        if token in self.baselines:
            del self.baselines[token]
            logger.info(f"Baseline reset for {token}")

    def get_status(self) -> Dict[str, any]:
        """Get monitor status"""
        return {
            "running": self.running,
            "monitored_tokens": len(self._get_monitored_tokens()),
            "baselines_tracked": len(self.baselines),
            "check_interval": self.check_interval,
            "alert_cooldown": self.alert_cooldown,
        }


# Singleton instance
_monitor: Optional[PriceAlertMonitor] = None


def get_price_monitor(
    alert_engine=None,
    price_fetcher=None,
) -> PriceAlertMonitor:
    """Get price monitor singleton"""
    global _monitor

    if _monitor is None:
        if alert_engine is None or price_fetcher is None:
            raise ValueError("Must provide alert_engine and price_fetcher on first call")

        _monitor = PriceAlertMonitor(
            alert_engine=alert_engine,
            price_fetcher_func=price_fetcher,
        )

    return _monitor
