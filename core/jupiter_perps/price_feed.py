"""Oracle-backed market price feed for runtime position monitoring."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any


_PYTH_FEED_IDS: dict[str, str] = {
    "SOL-USD": "ef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d",
    "BTC-USD": "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
    "ETH-USD": "ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
}


@dataclass(frozen=True)
class OraclePriceFeedConfig:
    hermes_url: str = "https://hermes.pyth.network"
    timeout_seconds: float = 8.0
    max_staleness_seconds: int = 20
    cache_ttl_seconds: float = 1.0

    @classmethod
    def from_env(cls) -> OraclePriceFeedConfig:
        return cls(
            hermes_url=os.environ.get("PERPS_PYTH_HERMES_URL", "https://hermes.pyth.network").rstrip("/"),
            timeout_seconds=max(2.0, float(os.environ.get("PERPS_PRICE_TIMEOUT_SECONDS", "8.0"))),
            max_staleness_seconds=max(2, int(os.environ.get("PERPS_PRICE_MAX_STALENESS_SECONDS", "20"))),
            cache_ttl_seconds=max(0.2, float(os.environ.get("PERPS_PRICE_CACHE_TTL_SECONDS", "1.0"))),
        )


class OraclePriceFeed:
    """Fetches latest mark price from Pyth Hermes parsed updates."""

    def __init__(self, config: OraclePriceFeedConfig | None = None) -> None:
        self._config = config or OraclePriceFeedConfig.from_env()
        self._cache: dict[str, tuple[float, float]] = {}

    async def get_price(self, market: str) -> float:
        cached = self._cache.get(market)
        now = time.time()
        if cached and (now - cached[1]) <= self._config.cache_ttl_seconds:
            return cached[0]

        feed_id = _PYTH_FEED_IDS.get(market)
        if not feed_id:
            return 0.0

        payload = await self._fetch_latest(feed_id)
        price = self._parse_payload_price(payload, market)
        if price > 0.0:
            self._cache[market] = (price, now)
        return price

    async def _fetch_latest(self, feed_id: str) -> dict[str, Any]:
        url = f"{self._config.hermes_url}/v2/updates/price/latest?ids[]={feed_id}"
        try:
            import httpx  # noqa: PLC0415
        except ImportError:
            return await self._fetch_latest_urllib(url)

        async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def _fetch_latest_urllib(self, url: str) -> dict[str, Any]:
        import urllib.request  # noqa: PLC0415

        def _do() -> dict[str, Any]:
            request = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=self._config.timeout_seconds) as resp:  # noqa: S310
                return json.loads(resp.read())

        return await asyncio.to_thread(_do)

    def _parse_payload_price(self, payload: dict[str, Any], market: str) -> float:
        parsed = payload.get("parsed")
        if parsed is None:
            return 0.0

        if isinstance(parsed, list):
            if not parsed:
                return 0.0
            item = parsed[0]
        elif isinstance(parsed, dict):
            item = parsed
        else:
            return 0.0

        price_info = item.get("price", {})
        raw_price = price_info.get("price")
        raw_expo = price_info.get("expo")
        publish_time = int(price_info.get("publish_time", 0) or 0)
        if raw_price is None or raw_expo is None:
            return 0.0
        if publish_time <= 0:
            return 0.0

        now = int(time.time())
        if now - publish_time > self._config.max_staleness_seconds:
            return 0.0

        try:
            integer_price = int(str(raw_price))
            expo = int(raw_expo)
        except (TypeError, ValueError):
            return 0.0

        price = float(integer_price) * (10.0 ** expo)
        if price <= 0.0:
            return 0.0
        return price

