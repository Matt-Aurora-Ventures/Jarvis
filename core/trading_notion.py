"""Compile Notion trading resources into strategy candidates."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import notes_manager


ROOT = Path(__file__).resolve().parents[1]
NOTION_DIR = ROOT / "data" / "trader" / "notion"
STRATEGIES_FILE = ROOT / "data" / "trader" / "strategies.json"
NOTION_EXEC_FILE = NOTION_DIR / "notion_execution_base.json"
NOTION_STRATEGIES_FILE = NOTION_DIR / "notion_strategies.json"
NOTION_ACTIONS_FILE = NOTION_DIR / "notion_actions.json"

STRATEGY_BLUEPRINTS = [
    {
        "id": "sol_meme_mean_reversion",
        "name": "Solana Meme Mean Reversion",
        "description": "Short meme coin blow-offs after extreme moves and weak follow-through.",
        "rules": {
            "strategy": "mean_reversion",
            "market": "solana_memes",
            "signals": [
                "price_zscore >= 2.0",
                "volume_spike >= 2.5x",
                "failed_breakout / rejection wick",
            ],
            "entry": "short after rejection candle",
            "exit": "cover at VWAP or 20-EMA mean",
            "risk": {"stop_loss_pct": 0.06, "take_profit_pct": 0.04},
        },
        "keywords": ["mean reversion", "reversion", "pull back", "overbought", "exhaustion"],
    },
    {
        "id": "sol_meme_trend_sma",
        "name": "Meme Trend SMA",
        "description": "Ride meme coin trends using SMA gating + liquidation trigger.",
        "rules": {
            "strategy": "trend_sma",
            "params": {"fast": 9, "slow": 21},
            "signals": ["price above fast SMA", "fast SMA above slow SMA"],
            "entry": "enter on liquidation sweep if price recovers above SMA",
            "exit": "close on SMA cross down or time stop",
        },
        "keywords": ["trend", "sma", "moving average", "liquidation", "momentum"],
    },
    {
        "id": "sol_meme_consolidation_zones",
        "name": "Meme Consolidation Zones",
        "description": "Market-maker style entries at supply/demand zones during ranges.",
        "rules": {
            "strategy": "range_reversion",
            "signals": ["low volatility", "range-bound", "supply/demand zones"],
            "entry": "buy demand, sell supply",
            "exit": "mid-range or opposite zone",
        },
        "keywords": ["consolidation", "supply", "demand", "range", "sideways"],
    },
    {
        "id": "open_interest_momentum",
        "name": "Open Interest Momentum",
        "description": "Trade with OI spikes confirming trend continuation or reversal.",
        "rules": {
            "strategy": "open_interest",
            "signals": ["oi spike", "price + oi divergence", "funding shift"],
            "entry": "trend continuation on rising OI",
            "exit": "oi drop or funding flip",
        },
        "keywords": ["open interest", "oi", "funding"],
    },
    {
        "id": "gap_up_reversion",
        "name": "Gap Up Mean Reversion",
        "description": "Fade large price gaps expecting regression to the mean.",
        "rules": {
            "strategy": "gap_reversion",
            "signals": ["gap >= 2 stdev", "volume fade"],
            "entry": "short after gap extension stalls",
            "exit": "gap fill or time stop",
        },
        "keywords": ["gap", "mean reversion", "gap up"],
    },
    {
        "id": "gap_and_go",
        "name": "Gap and Go",
        "description": "Trade breakaway gaps with momentum continuation.",
        "rules": {
            "strategy": "gap_momentum",
            "signals": ["breakaway gap", "volume expansion"],
            "entry": "enter in direction of gap",
            "exit": "trailing stop",
        },
        "keywords": ["gap and go", "breakaway gap", "momentum"],
    },
    {
        "id": "exhaustion_gap_reversal",
        "name": "Exhaustion Gap Reversal",
        "description": "Detect end-of-trend gaps and fade reversals.",
        "rules": {
            "strategy": "gap_exhaustion",
            "signals": ["late trend gap", "volume climax", "price stall"],
            "entry": "fade after confirmation",
            "exit": "mean reversion target",
        },
        "keywords": ["exhaustion gap", "reversal", "overbought"],
    },
    {
        "id": "whale_copy_trade",
        "name": "Whale Copy Trade",
        "description": "Follow top trader wallets and copy entries with risk limits.",
        "rules": {
            "strategy": "copy_trade",
            "signals": ["top trader wallet buy", "token trending"],
            "entry": "mirror wallet within 60s",
            "exit": "fixed % take profit",
        },
        "keywords": ["whale", "copy", "top traders", "gmgn"],
    },
    {
        "id": "new_listing_sniper",
        "name": "New Listing Sniper",
        "description": "Filter and enter newly launched Solana tokens with liquidity/volume checks.",
        "rules": {
            "strategy": "new_listing",
            "signals": ["new listing", "liquidity >= min", "volume spike"],
            "entry": "buy after initial dip",
            "exit": "time stop or trailing stop",
        },
        "keywords": ["new listing", "sniper", "new token"],
    },
]

SHORTLIST_IDS = [
    "sol_meme_trend_sma",
    "sol_meme_mean_reversion",
    "new_listing_sniper",
    "whale_copy_trade",
    "open_interest_momentum",
]


def compile_notion_strategies(
    exec_path: Optional[str] = None,
    *,
    seed_trader: bool = True,
) -> Dict[str, Any]:
    NOTION_DIR.mkdir(parents=True, exist_ok=True)
    exec_path = exec_path or str(NOTION_EXEC_FILE)
    payload = _load_json(exec_path)
    if not payload:
        return {"error": "No Notion execution payload found", "exec_path": exec_path}

    sections = payload.get("sections", {}) or {}
    action_items = payload.get("action_items", []) or []
    links = payload.get("links", []) or []
    lines = _flatten_sections(sections)

    strategies = _build_strategies(lines)
    shortlist = [s for s in strategies if s.get("id") in SHORTLIST_IDS]
    actions = _build_actions(action_items, links)

    with open(NOTION_STRATEGIES_FILE, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "source": payload.get("source"),
                "title": payload.get("title"),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "sections": sections,
                "action_items": action_items,
                "links": links,
                "strategies": strategies,
                "shortlist": shortlist,
            },
            handle,
            indent=2,
        )

    with open(NOTION_ACTIONS_FILE, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "actions": actions,
            },
            handle,
            indent=2,
        )

    if seed_trader:
        _seed_trader_strategies(strategies)

    digest = _render_digest(payload, strategies, shortlist, actions)
    note_path, summary_path, _ = notes_manager.save_note(
        topic="notion_strategy_compiler",
        content=digest,
        fmt="md",
        tags=["notion", "trading", "strategies"],
        source="trading_notion",
        metadata={"exec_path": exec_path},
    )

    return {
        "exec_path": exec_path,
        "strategies_path": str(NOTION_STRATEGIES_FILE),
        "actions_path": str(NOTION_ACTIONS_FILE),
        "note_path": str(note_path),
        "summary_path": str(summary_path),
        "strategies_added": len(strategies),
        "shortlist": len(shortlist),
        "actions": len(actions),
    }


def _build_strategies(lines: List[str]) -> List[Dict[str, Any]]:
    strategies: List[Dict[str, Any]] = []
    for blueprint in STRATEGY_BLUEPRINTS:
        evidence = _find_evidence(lines, blueprint.get("keywords", []))
        strategy = {
            "id": blueprint["id"],
            "name": blueprint["name"],
            "description": blueprint["description"],
            "rules": blueprint["rules"],
            "created_at": time.time(),
            "evidence": evidence,
        }
        strategies.append(strategy)
    return strategies


def _find_evidence(lines: List[str], keywords: List[str]) -> List[str]:
    if not lines or not keywords:
        return []
    evidence: List[str] = []
    for line in lines:
        lower = line.lower()
        if any(keyword.lower() in lower for keyword in keywords):
            evidence.append(line)
        if len(evidence) >= 8:
            break
    return evidence


def _build_actions(action_items: List[str], links: List[str]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for item in action_items:
        actions.append({"action": "research", "item": item})
    for link in links:
        actions.append({"action": "review", "item": link})
    return actions


def _flatten_sections(sections: Dict[str, List[str]]) -> List[str]:
    lines: List[str] = []
    for items in sections.values():
        for item in items:
            if item:
                lines.append(item)
    return lines


def _render_digest(
    payload: Dict[str, Any],
    strategies: List[Dict[str, Any]],
    shortlist: List[Dict[str, Any]],
    actions: List[Dict[str, Any]],
) -> str:
    lines = [
        "# Notion Strategy Compiler",
        f"Source: {payload.get('source', '')}",
        f"Title: {payload.get('title', '')}",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Strategy Shortlist",
    ]
    for strat in shortlist:
        lines.append(f"- {strat['name']}: {strat['description']}")

    lines.append("")
    lines.append("## Strategy Catalog")
    for strat in strategies:
        lines.append(f"- {strat['name']} ({strat['id']})")

    lines.append("")
    lines.append("## Actions")
    for action in actions[:20]:
        lines.append(f"- {action['action']}: {action['item']}")

    return "\n".join(lines).strip() + "\n"


def _seed_trader_strategies(strategies: List[Dict[str, Any]]) -> None:
    if not strategies:
        return
    existing = []
    if STRATEGIES_FILE.exists():
        try:
            with open(STRATEGIES_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                existing = data.get("strategies", [])
        except Exception:
            existing = []

    existing_ids = {item.get("id") for item in existing if isinstance(item, dict)}
    new_entries = []
    for strat in strategies:
        if strat.get("id") in existing_ids:
            continue
        new_entries.append({
            "id": strat.get("id"),
            "name": strat.get("name"),
            "description": strat.get("description", ""),
            "rules": strat.get("rules", {}),
            "created_at": strat.get("created_at", time.time()),
            "backtest_results": None,
            "paper_results": None,
            "approved_for_live": False,
        })

    if not new_entries:
        return

    merged = existing + new_entries
    STRATEGIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STRATEGIES_FILE, "w", encoding="utf-8") as handle:
        json.dump({"strategies": merged, "updated_at": time.time()}, handle, indent=2)


def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}
