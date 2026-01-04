"""Event and catalyst extraction for sentiment-driven trading."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List


EVENT_KEYWORDS = {
    "earnings": ["earnings", "guidance", "quarterly report"],
    "launch": ["launch", "release", "ship", "deployment"],
    "lawsuit": ["lawsuit", "court", "regulator", "sec"],
    "partnership": ["partnership", "collaboration", "integration"],
    "funding": ["funding", "raise", "series", "valuation"],
}

NAME_TO_TICKER = {
    "OPENAI": "OPENAI",
    "SPACEX": "SPACEX",
    "ANTHROPIC": "ANTHROPIC",
    "XAI": "XAI",
    "KRAKEN": "KRAKEN",
    "STRIPE": "STRIPE",
    "ANDURIL": "ANDURIL",
}


@dataclass
class CatalystEvent:
    text: str
    category: str
    ticker: str
    horizon: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _extract_tickers(text: str) -> List[str]:
    tickers = re.findall(r"(?:\\$|\\b)([A-Z][A-Z0-9]{1,7})\\b", text)
    for name, ticker in NAME_TO_TICKER.items():
        if name in text.upper():
            tickers.append(ticker)
    return list(dict.fromkeys(tickers))


def _horizon_for_category(category: str) -> str:
    if category in {"earnings", "launch", "lawsuit"}:
        return "days"
    return "hours"


def extract_events(text: str) -> List[CatalystEvent]:
    if not text:
        return []
    upper_text = text.upper()
    tickers = _extract_tickers(upper_text)
    events: List[CatalystEvent] = []

    for category, keywords in EVENT_KEYWORDS.items():
        if any(keyword in text.lower() for keyword in keywords):
            for ticker in tickers or ["UNKNOWN"]:
                events.append(
                    CatalystEvent(
                        text=text,
                        category=category,
                        ticker=ticker,
                        horizon=_horizon_for_category(category),
                        confidence=0.6,
                    )
                )
    return events


def map_events_to_universe(
    events: List[CatalystEvent],
    universe_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    mapped: List[Dict[str, Any]] = []
    for event in events:
        for item in universe_items:
            ticker = str(item.get("underlying_ticker") or item.get("symbol") or "").upper()
            if ticker and ticker == event.ticker:
                mapped.append(
                    {
                        "event": event.to_dict(),
                        "asset": item,
                        "horizon": event.horizon,
                        "catalyst_score": 0.7,
                    }
                )
    return mapped
