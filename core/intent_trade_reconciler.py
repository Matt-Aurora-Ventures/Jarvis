"""Compare exit intents against risk manager trades."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import exit_intents
from core.risk_manager import get_risk_manager

REPORT_PATH = Path.home() / ".lifeos" / "trading" / "intent_trade_report.json"


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _action_for_intent(intent: exit_intents.ExitIntent) -> str:
    if intent.position_type == "perps":
        symbol_upper = (intent.symbol or "").upper()
        if "SHORT" in symbol_upper:
            return "SELL"
        if "LONG" in symbol_upper:
            return "BUY"
        if intent.notes:
            direction = re.search(r"direction=([a-zA-Z]+)", intent.notes)
            if direction and direction.group(1).lower() == "short":
                return "SELL"
    return "BUY"


def _matches_trade(intent: exit_intents.ExitIntent, trade: Dict[str, Any]) -> bool:
    if trade.get("symbol") != intent.symbol:
        return False
    entry_price = _to_float(trade.get("entry_price"))
    quantity = _to_float(trade.get("quantity"))
    if entry_price and intent.entry_price:
        if abs(entry_price - intent.entry_price) / intent.entry_price > 0.02:
            return False
    if quantity and intent.remaining_quantity:
        if abs(quantity - intent.remaining_quantity) / max(intent.remaining_quantity, 1e-9) > 0.02:
            return False
    return True


def reconcile(
    *,
    write_report: bool = True,
    import_missing: bool = False,
    apply: bool = False,
) -> Dict[str, Any]:
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

    imported_trades: List[Dict[str, Any]] = []
    would_import: List[Dict[str, Any]] = []
    if import_missing:
        for intent in intents:
            if any(_matches_trade(intent, trade) for trade in open_trades):
                continue
            payload = {
                "intent_id": intent.id,
                "symbol": intent.symbol,
                "entry_price": intent.entry_price,
                "quantity": intent.remaining_quantity,
                "action": _action_for_intent(intent),
                "strategy": "exit_intent_mirror",
            }
            if apply:
                trade = rm.record_trade(
                    symbol=payload["symbol"],
                    action=payload["action"],
                    entry_price=payload["entry_price"],
                    quantity=payload["quantity"],
                    stop_loss=None,
                    take_profit=None,
                    strategy=payload["strategy"],
                )
                payload["trade_id"] = trade.id
                imported_trades.append(payload)
            else:
                would_import.append(payload)

    report: Dict[str, Any] = {
        "timestamp": now,
        "active_intents": len(intents),
        "open_trades": len(open_trades),
        "intents_without_trades": intents_without_trades,
        "trades_without_intents": trades_without_intents,
        "overdue_time_stops": overdue_time_stops,
        "policy": "exit_intents_canonical_no_auto_import",
        "import_missing": import_missing,
        "apply": apply,
        "imported_trades": imported_trades,
        "would_import": would_import,
    }

    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2))

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Reconcile exit intents against risk manager trades.")
    parser.add_argument("--import-missing", action="store_true", help="Mirror missing intents into risk manager.")
    parser.add_argument("--apply", action="store_true", help="Apply changes (writes trades).")
    parser.add_argument("--no-report", action="store_true", help="Skip writing the JSON report.")
    args = parser.parse_args()

    payload = reconcile(
        write_report=not args.no_report,
        import_missing=args.import_missing,
        apply=args.apply,
    )
    print(json.dumps(payload, indent=2))
