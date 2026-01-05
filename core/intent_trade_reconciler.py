"""Compare exit intents against risk manager trades."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from core import exit_intents
from core.risk_manager import get_risk_manager

REPORT_PATH = Path.home() / ".lifeos" / "trading" / "intent_trade_report.json"


def reconcile(*, write_report: bool = True) -> Dict[str, Any]:
    now = time.time()
    intents = exit_intents.load_active_intents()
    rm = get_risk_manager()
    open_trades = rm.get_open_trades()

    intents_by_symbol: Dict[str, List[exit_intents.ExitIntent]] = {}
    for intent in intents:
        if intent.symbol:
            intents_by_symbol.setdefault(intent.symbol, []).append(intent)

    open_by_symbol = {trade.get("symbol") for trade in open_trades if trade.get("symbol")}
    intent_symbols = set(intents_by_symbol)

    intents_without_trades = sorted(intent_symbols - open_by_symbol)
    trades_without_intents = sorted(open_by_symbol - intent_symbols)

    overdue_time_stops = []
    for intent in intents:
        overdue_seconds = now - intent.time_stop.deadline_timestamp
        if overdue_seconds > 0:
            overdue_time_stops.append(
                {
                    "intent_id": intent.id,
                    "symbol": intent.symbol,
                    "overdue_hours": round(overdue_seconds / 3600, 2),
                    "remaining_qty": intent.remaining_quantity,
                    "status": intent.status,
                }
            )

    report: Dict[str, Any] = {
        "timestamp": now,
        "active_intents": len(intents),
        "open_trades": len(open_trades),
        "intents_without_trades": intents_without_trades,
        "trades_without_intents": trades_without_intents,
        "overdue_time_stops": overdue_time_stops,
        "policy": "exit_intents_canonical_no_auto_import",
    }

    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2))

    return report


if __name__ == "__main__":
    payload = reconcile(write_report=True)
    print(json.dumps(payload, indent=2))
