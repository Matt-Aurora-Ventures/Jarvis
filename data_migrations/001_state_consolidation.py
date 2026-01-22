#!/usr/bin/env python3
"""
State consolidation migration (idempotent).

Merges legacy/fragmented state into canonical stores:
- data/trader/positions.json
- data/trader/trade_history.json
- data/context_state.json

Leaves legacy files intact and writes a migration report.
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TRADER_DIR = DATA_DIR / "trader"
MIGRATION_REPORT = Path(__file__).resolve().parent / "migration_001_report.json"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _backup_if_exists(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak.{stamp}")
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup


def _record_key(record: Dict[str, Any]) -> str:
    key = record.get("id") or record.get("position_id") or record.get("trade_id")
    if key:
        return str(key)
    raw = json.dumps(record, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _merge_records(primary: List[Dict[str, Any]], others: Iterable[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for record in primary:
        merged[_record_key(record)] = record
    for dataset in others:
        for record in dataset:
            key = _record_key(record)
            if key not in merged:
                merged[key] = record
    return list(merged.values())


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _merge_timestamp(existing: Optional[str], candidate: Optional[str]) -> Optional[str]:
    if not candidate:
        return existing
    if not existing:
        return candidate
    existing_dt = _parse_dt(existing)
    candidate_dt = _parse_dt(candidate)
    if existing_dt and candidate_dt and candidate_dt > existing_dt:
        return candidate
    return existing


def migrate_trading_state(report: Dict[str, Any]) -> None:
    TRADER_DIR.mkdir(parents=True, exist_ok=True)

    canonical_positions = TRADER_DIR / "positions.json"
    canonical_history = TRADER_DIR / "trade_history.json"

    legacy_positions = [
        ROOT / "bots" / "treasury" / ".positions.json",
        ROOT / "bots" / "treasury" / ".positions.json.bak",
        Path.home() / ".lifeos" / "trading" / "positions.json",
    ]
    legacy_history = [
        ROOT / "bots" / "treasury" / ".trade_history.json",
        ROOT / "bots" / "treasury" / ".trade_history.json.bak",
        Path.home() / ".lifeos" / "trading" / "trade_history.json",
    ]

    canonical_positions_data = _load_json(canonical_positions, [])
    canonical_history_data = _load_json(canonical_history, [])

    legacy_positions_data = [_load_json(p, []) for p in legacy_positions if p.exists()]
    legacy_history_data = [_load_json(p, []) for p in legacy_history if p.exists()]

    merged_positions = _merge_records(canonical_positions_data, legacy_positions_data)
    merged_history = _merge_records(canonical_history_data, legacy_history_data)

    report["trading"] = {
        "canonical_positions": str(canonical_positions),
        "canonical_history": str(canonical_history),
        "positions_before": len(canonical_positions_data),
        "positions_after": len(merged_positions),
        "history_before": len(canonical_history_data),
        "history_after": len(merged_history),
        "legacy_positions_sources": [str(p) for p in legacy_positions if p.exists()],
        "legacy_history_sources": [str(p) for p in legacy_history if p.exists()],
    }

    _backup_if_exists(canonical_positions)
    _backup_if_exists(canonical_history)
    canonical_positions.write_text(json.dumps(merged_positions, indent=2), encoding="utf-8")
    canonical_history.write_text(json.dumps(merged_history, indent=2), encoding="utf-8")


def migrate_context_state(report: Dict[str, Any]) -> None:
    context_path = DATA_DIR / "context_state.json"
    context = _load_json(context_path, {})

    sentiment_state = ROOT / "bots" / "twitter" / ".sentiment_poster_state.json"
    twitter_bot_state = ROOT / "bots" / "twitter" / "bot_state.json"

    if sentiment_state.exists():
        data = _load_json(sentiment_state, {})
        context["last_tweet"] = _merge_timestamp(context.get("last_tweet"), data.get("last_post_time"))

    if twitter_bot_state.exists():
        data = _load_json(twitter_bot_state, {})
        context["last_tweet"] = _merge_timestamp(context.get("last_tweet"), data.get("last_tweet_time"))

    # Ensure required keys exist
    context.setdefault("last_sentiment_report", None)
    context.setdefault("last_tweet", None)
    context.setdefault("last_full_report", None)
    context.setdefault("startup_count_today", 0)
    context.setdefault("last_startup_date", None)
    context.setdefault("sentiment_cache_valid", False)

    report["context_state"] = {
        "canonical_context": str(context_path),
        "last_sentiment_report": context.get("last_sentiment_report"),
        "last_tweet": context.get("last_tweet"),
    }

    _backup_if_exists(context_path)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(json.dumps(context, indent=2), encoding="utf-8")


def main() -> int:
    report: Dict[str, Any] = {
        "migration": "001_state_consolidation",
        "timestamp": datetime.utcnow().isoformat(),
        "root": str(ROOT),
    }

    migrate_trading_state(report)
    migrate_context_state(report)

    MIGRATION_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
