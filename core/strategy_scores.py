"""
Strategy score tracking for adaptive trading decisions.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core import config as config_module

ROOT = Path(__file__).resolve().parents[1]
TRADER_DIR = ROOT / "data" / "trader"
SCORES_PATH = TRADER_DIR / "strategy_scores.json"

DEFAULT_SCORE = 100.0
MIN_SCORE = 50.0
MAX_SCORE = 200.0
WIN_REWARD = 5.0
LOSS_PENALTY = 10.0
LOSS_STREAK_LIMIT = 3
SORT_KEYS = {"score", "wins", "losses", "loss_streak", "execution_errors", "last_update"}


def _load_scores() -> Dict[str, Dict[str, Any]]:
    if not SCORES_PATH.exists():
        return {}
    try:
        with SCORES_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_scores(scores: Dict[str, Dict[str, Any]]) -> None:
    TRADER_DIR.mkdir(parents=True, exist_ok=True)
    with SCORES_PATH.open("w", encoding="utf-8") as handle:
        json.dump(scores, handle, indent=2)


def _default_record(strategy_id: str) -> Dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "score": DEFAULT_SCORE,
        "wins": 0,
        "losses": 0,
        "loss_streak": 0,
        "execution_errors": 0,
        "last_update": time.time(),
        "last_pnl": 0.0,
        "last_reason": "",
    }


def _get_config() -> Dict[str, Any]:
    cfg = config_module.load_config()
    return cfg.get("strategy_scores", {})


def get_record(strategy_id: str) -> Dict[str, Any]:
    scores = _load_scores()
    record = scores.get(strategy_id)
    if not isinstance(record, dict):
        record = _default_record(strategy_id)
        scores[strategy_id] = record
        _save_scores(scores)
    return record


def list_scores(
    *,
    limit: int = 20,
    min_score: Optional[float] = None,
    sort_key: str = "score",
    descending: bool = True,
) -> list[Dict[str, Any]]:
    scores = _load_scores()
    records: list[Dict[str, Any]] = []
    for key, record in scores.items():
        if not isinstance(record, dict):
            continue
        record.setdefault("strategy_id", key)
        record.setdefault("score", DEFAULT_SCORE)
        record.setdefault("wins", 0)
        record.setdefault("losses", 0)
        record.setdefault("loss_streak", 0)
        record.setdefault("execution_errors", 0)
        record.setdefault("last_update", 0)
        if min_score is not None and float(record.get("score", 0.0)) < min_score:
            continue
        records.append(record)

    key = sort_key if sort_key in SORT_KEYS else "score"
    records.sort(key=lambda item: float(item.get(key, 0.0)), reverse=descending)
    if limit and limit > 0:
        return records[:limit]
    return records


def update_score(
    strategy_id: str,
    pnl: float,
    *,
    execution_error: bool = False,
    reason: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scores = _load_scores()
    record = scores.get(strategy_id) or _default_record(strategy_id)

    cfg = _get_config()
    win_reward = float(cfg.get("win_reward", WIN_REWARD))
    loss_penalty = float(cfg.get("loss_penalty", LOSS_PENALTY))
    max_score = float(cfg.get("max_score", MAX_SCORE))

    if execution_error:
        record["execution_errors"] = int(record.get("execution_errors", 0)) + 1
        record["last_reason"] = reason or "execution_error"
    else:
        if pnl > 0:
            record["wins"] = int(record.get("wins", 0)) + 1
            record["score"] = float(record.get("score", DEFAULT_SCORE)) + win_reward
            record["loss_streak"] = 0
            record["last_reason"] = reason or "win"
        else:
            record["losses"] = int(record.get("losses", 0)) + 1
            record["score"] = float(record.get("score", DEFAULT_SCORE)) - loss_penalty
            record["loss_streak"] = int(record.get("loss_streak", 0)) + 1
            record["last_reason"] = reason or "loss"

    record["score"] = max(0.0, min(max_score, float(record.get("score", DEFAULT_SCORE))))
    record["last_pnl"] = float(pnl or 0.0)
    record["last_update"] = time.time()
    if metadata:
        record["last_metadata"] = metadata

    scores[strategy_id] = record
    _save_scores(scores)
    return record


def allow_strategy(strategy_id: str) -> Tuple[bool, str]:
    record = get_record(strategy_id)
    cfg = _get_config()
    min_score = float(cfg.get("min_score", MIN_SCORE))
    max_loss_streak = int(cfg.get("loss_streak_limit", LOSS_STREAK_LIMIT))

    score = float(record.get("score", DEFAULT_SCORE))
    loss_streak = int(record.get("loss_streak", 0))

    if score < min_score:
        return False, f"score_below_min:{score:.1f}<{min_score:.1f}"
    if loss_streak >= max_loss_streak:
        return False, f"loss_streak_limit:{loss_streak}>={max_loss_streak}"
    return True, "ok"
