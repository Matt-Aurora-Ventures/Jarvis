"""Demo wallet intelligence logging for personalization and learning."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class DemoLatentEvent:
    event_type: str
    user_id: int
    timestamp: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DemoWalletIntelligence:
    """Minimal, lossy logging for demo wallet personalization."""

    def __init__(self, root: Optional[Path] = None) -> None:
        base = root or Path(__file__).resolve().parents[1] / "data" / "demo_wallet"
        self.root = Path(base)
        self.root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root / "latent_events.jsonl"

    def _hash_text(self, value: str) -> str:
        if not value:
            return ""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    def _write(self, event: DemoLatentEvent) -> None:
        with open(self.log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict()) + "\n")

    def record_picks_served(
        self,
        user_id: int,
        picks: Iterable[Dict[str, Any]],
        confidence_score: float,
        mode: str,
    ) -> None:
        payload: Dict[str, Any] = {
            "confidence_score": round(confidence_score, 2),
            "mode": mode,
            "picks": [],
        }
        for pick in picks:
            payload["picks"].append(
                {
                    "symbol": pick.get("symbol"),
                    "asset_class": pick.get("asset_class"),
                    "conviction_base": pick.get("conviction_base"),
                    "conviction_adjusted": pick.get("conviction_adjusted"),
                    "reasoning_hash": self._hash_text(pick.get("reasoning", "")),
                }
            )

        event = DemoLatentEvent(
            event_type="picks_served",
            user_id=user_id,
            timestamp=datetime.utcnow().isoformat(),
            payload=payload,
        )
        self._write(event)

    def record_pick_action(
        self,
        user_id: int,
        symbol: str,
        action: str,
        amount_sol: float,
        conviction: Optional[float],
    ) -> None:
        event = DemoLatentEvent(
            event_type="pick_action",
            user_id=user_id,
            timestamp=datetime.utcnow().isoformat(),
            payload={
                "symbol": symbol,
                "action": action,
                "amount_sol": amount_sol,
                "conviction": conviction,
            },
        )
        self._write(event)

    def record_trade_execution(
        self,
        user_id: int,
        symbol: str,
        action: str,
        amount_usd: float,
        pnl_usd: float,
        signal_strength: float,
    ) -> None:
        event = DemoLatentEvent(
            event_type="trade_execution",
            user_id=user_id,
            timestamp=datetime.utcnow().isoformat(),
            payload={
                "symbol": symbol,
                "action": action,
                "amount_usd": round(amount_usd, 4),
                "pnl_usd": round(pnl_usd, 4),
                "signal_strength": round(signal_strength, 2),
            },
        )
        self._write(event)
