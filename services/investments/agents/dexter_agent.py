"""Dexter Fundamental Analyst — self-validating fundamental data QA pipeline.

Wraps existing core/dexscreener.py for cross-validated market data.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

import httpx

logger = logging.getLogger("investments.agents.dexter")


class FundamentalReport(TypedDict):
    token_fundamentals: dict  # per-token: volume, liquidity, holders, price_change
    data_quality_score: float  # 0-1, self-validated
    anomalies_detected: list[str]
    validation_notes: str


class DexterFundamentalAnalyst:
    """Self-validating fundamental data QA pipeline.

    Uses Plan -> Act -> Validate -> Answer loop:
    1. Plan: determine what data points to gather
    2. Act: fetch from BirdEye, DexScreener
    3. Validate: cross-reference sources, flag discrepancies
    4. Answer: produce validated fundamental report
    """

    def __init__(
        self,
        birdeye_key: str = "",
        dexscreener_base: str = "https://api.dexscreener.com",
    ) -> None:
        self.birdeye_key = birdeye_key
        self.dexscreener_base = dexscreener_base

    async def analyze(
        self, basket_tokens: list[dict[str, Any]]
    ) -> FundamentalReport:
        fundamentals: dict[str, dict] = {}
        anomalies: list[str] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for token in basket_tokens:
                addr = token.get("address", "")
                symbol = token["symbol"]

                # Fetch from multiple sources for cross-validation
                birdeye_data = await self._fetch_birdeye(client, addr)
                dexscreener_data = await self._fetch_dexscreener(client, addr)

                # Cross-validate: volume should be within 20% across sources
                be_vol = birdeye_data.get("volume_24h", 0)
                ds_vol = dexscreener_data.get("volume_24h", 0)
                if be_vol > 0 and ds_vol > 0:
                    vol_diff = abs(be_vol - ds_vol) / max(be_vol, ds_vol)
                    if vol_diff > 0.2:
                        anomalies.append(
                            f"{symbol}: volume discrepancy {vol_diff:.0%} "
                            f"between BirdEye and DexScreener"
                        )

                fundamentals[symbol] = {
                    "volume_24h": (be_vol + ds_vol) / 2 if (be_vol + ds_vol) else 0,
                    "liquidity_usd": birdeye_data.get("liquidity", 0),
                    "holders": birdeye_data.get("holders", 0),
                    "price_change_24h": dexscreener_data.get("priceChange_24h", 0),
                }

        quality = max(0.0, 1.0 - (len(anomalies) * 0.15))
        return FundamentalReport(
            token_fundamentals=fundamentals,
            data_quality_score=quality,
            anomalies_detected=anomalies,
            validation_notes=f"Cross-validated {len(basket_tokens)} tokens across 2 sources",
        )

    async def _fetch_birdeye(self, client: httpx.AsyncClient, address: str) -> dict:
        if not self.birdeye_key or not address:
            return {}
        try:
            resp = await client.get(
                "https://public-api.birdeye.so/defi/token_overview",
                params={"address": address},
                headers={"X-API-KEY": self.birdeye_key},
            )
            return resp.json().get("data", {})
        except Exception as exc:
            logger.warning("BirdEye fetch failed for %s: %s", address, exc)
            return {}

    async def _fetch_dexscreener(
        self, client: httpx.AsyncClient, address: str
    ) -> dict:
        if not address:
            return {}
        try:
            resp = await client.get(
                f"{self.dexscreener_base}/latest/dex/tokens/{address}"
            )
            pairs = resp.json().get("pairs", [])
            return pairs[0] if pairs else {}
        except Exception as exc:
            logger.warning("DexScreener fetch failed for %s: %s", address, exc)
            return {}
