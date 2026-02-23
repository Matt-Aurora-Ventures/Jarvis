"""Grok Sentiment Analyst — uses x_search for real-time X/Twitter sentiment."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

import httpx

logger = logging.getLogger("investments.agents.grok")


class SentimentReport(TypedDict):
    token: str
    sentiment_score: float  # -1.0 to 1.0
    volume_24h: int
    notable_mentions: list[str]
    trend: str  # DECLINING | STABLE | RISING
    confidence: float  # 0.0 to 1.0


class GrokSentimentAnalyst:
    """Produces sentiment reports for each basket token using Grok's x_search."""

    def __init__(self, api_key: str, model: str = "grok-4-1-fast-non-reasoning") -> None:
        self.api_key = api_key
        self.model = model
        self.client = httpx.AsyncClient(
            base_url="https://api.x.ai/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    async def analyze_token(
        self, token_symbol: str, token_name: str
    ) -> SentimentReport:
        """Query Grok x_search for token sentiment over last 24h."""
        response = await self.client.post(
            "/responses",
            json={
                "model": self.model,
                "tools": [
                    {
                        "type": "x_search",
                        "x_search": {"from_date": self._24h_ago_iso()},
                    }
                ],
                "input": (
                    f"Analyze the current sentiment for {token_name} ({token_symbol}) "
                    f"on X/Twitter over the last 24 hours. Focus on: "
                    f"1) Overall sentiment direction and strength "
                    f"2) Notable mentions from high-influence accounts "
                    f"3) Volume of discussion "
                    f"4) Any significant narrative shifts or events "
                    f"Return your analysis as structured data."
                ),
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "sentiment_report",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "sentiment_score": {"type": "number"},
                                "volume_24h": {"type": "integer"},
                                "notable_mentions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "trend": {
                                    "type": "string",
                                    "enum": ["DECLINING", "STABLE", "RISING"],
                                },
                                "confidence": {"type": "number"},
                            },
                            "required": [
                                "sentiment_score",
                                "volume_24h",
                                "notable_mentions",
                                "trend",
                                "confidence",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        parsed = self._extract_json(data)
        return SentimentReport(token=token_symbol, **parsed)

    async def analyze_basket(
        self, tokens: list[dict[str, Any]]
    ) -> list[SentimentReport | Exception]:
        """Analyze sentiment for all basket tokens in parallel."""
        import asyncio

        tasks = [
            self.analyze_token(t["symbol"], t.get("name", t["symbol"])) for t in tokens
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self) -> None:
        await self.client.aclose()

    def _24h_ago_iso(self) -> str:
        return (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    def _extract_json(self, response_data: dict) -> dict:
        for item in response_data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return json.loads(content["text"])
        raise ValueError("No structured output found in Grok response")
