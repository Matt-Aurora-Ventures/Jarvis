"""FastAPI routes for the investment service.

Runs as a standalone FastAPI app on its own port (default 8770).
Includes adapter layer (Phase 4) that transforms backend responses to
match the frontend TypeScript interfaces in useInvestmentData.ts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger("investments.api")


# ── Phase 4 Adapters ─────────────────────────────────────────────────────────
# Transform backend data shapes → frontend TypeScript interfaces.


def _adapt_basket(raw: dict[str, Any]) -> dict[str, Any]:
    """Backend basket → frontend BasketData.

    Backend returns: {tokens: {SYM: {weight, price_usd, balance, address, ...}}, nav_usd}
    Frontend expects: {tokens: BasketToken[], total_nav, nav_per_share, last_rebalance, next_rebalance}
    """
    raw_tokens = raw.get("tokens", {})
    nav = float(raw.get("nav_usd", 0))

    tokens = []
    for symbol, info in (raw_tokens.items() if isinstance(raw_tokens, dict) else []):
        weight_frac = float(info.get("weight", 0))
        price = float(info.get("price_usd", 0))
        balance = float(info.get("balance", 0))
        usd_value = price * balance if balance else nav * weight_frac
        tokens.append({
            "symbol": symbol,
            "mint": info.get("address", ""),
            "weight": round(weight_frac * 100, 2),
            "usd_value": round(usd_value, 2),
            "quantity": balance,
            "price": price,
            "change_24h": float(info.get("change_24h", 0)),
        })

    # If tokens is already a list (some orchestrator versions), pass through
    if isinstance(raw_tokens, list):
        tokens = raw_tokens

    total_supply = float(raw.get("total_supply", 1))
    return {
        "tokens": tokens,
        "total_nav": nav,
        "nav_per_share": round(nav / total_supply, 4) if total_supply > 0 else nav,
        "last_rebalance": raw.get("last_rebalance", ""),
        "next_rebalance": raw.get("next_rebalance", ""),
    }


def _adapt_performance(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Backend performance → frontend PerformancePoint[].

    Backend returns: {basket_id, hours, points: [{ts, nav_usd}], change_pct}
    Frontend expects: [{timestamp, nav}]
    """
    points = raw.get("points", [])
    return [
        {"timestamp": p.get("ts", p.get("timestamp", "")), "nav": float(p.get("nav_usd", p.get("nav", 0)))}
        for p in points
    ]


def _adapt_decision(row: dict[str, Any]) -> dict[str, Any]:
    """Backend decision → frontend InvestmentDecision."""
    return {
        "id": str(row.get("id", "")),
        "timestamp": row.get("ts", row.get("timestamp", row.get("created_at", ""))),
        "action": row.get("action", "HOLD"),
        "confidence": float(row.get("confidence", 0)),
        "nav_at_decision": float(row.get("nav_usd", row.get("nav_at_decision", 0))),
        "summary": row.get("summary", row.get("reasoning", "")),
        "new_weights": row.get("final_weights", row.get("new_weights", {})),
        "agent_reports": row.get("agent_reports"),
        "debate_rounds": row.get("debate_rounds"),
        "risk_assessment": row.get("risk_assessment"),
    }


def _adapt_reflection(row: dict[str, Any]) -> dict[str, Any]:
    """Backend reflection → frontend Reflection."""
    data = row.get("data", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            data = {}

    hint = row.get("calibration_hint", "")
    adjustments = data.get("adjustments", [])
    if not adjustments and hint:
        adjustments = [hint]

    accuracy_pct = data.get("accuracy_pct")
    if accuracy_pct is None:
        scores = data.get("agent_accuracy_scores", {})
        if isinstance(scores, dict) and scores:
            accuracy_pct = round(
                sum(float(score) for score in scores.values()) / len(scores) * 100,
                1,
            )
        else:
            accuracy_pct = 0.0

    lessons = data.get("lessons", [])
    if not lessons:
        predicted_action = data.get("predicted_action")
        nav_change_pct = data.get("nav_change_pct")
        if predicted_action is not None and nav_change_pct is not None:
            lessons = [
                f"{predicted_action} led to {float(nav_change_pct) * 100:+.1f}% NAV change."
            ]

    return {
        "id": str(row.get("id", "")),
        "timestamp": row.get("ts", row.get("timestamp", "")),
        "accuracy_pct": float(accuracy_pct),
        "lessons": lessons,
        "adjustments": adjustments,
    }


def _adapt_kill_switch_response(activated: bool) -> dict[str, Any]:
    """Return KillSwitchStatus shape for activate/deactivate responses."""
    return {
        "active": activated,
        "activated_at": datetime.now(timezone.utc).isoformat() if activated else None,
        "reason": "Manual activation via API" if activated else None,
    }

# Populated by main.py at startup
_orchestrator: Any = None
_db: Any = None
_redis: Any = None


def _is_fallback_mode() -> bool:
    return _db is None or _redis is None


def set_dependencies(orchestrator: Any, db: Any, redis: Any) -> None:
    global _orchestrator, _db, _redis
    _orchestrator = orchestrator
    _db = db
    _redis = redis


app = FastAPI(
    title="Jarvis Investment Service",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def require_admin(authorization: Optional[str] = Header(None)) -> None:
    """Verify Bearer token for write endpoints."""
    admin_key = _orchestrator.cfg.admin_key if _orchestrator else None
    dry_run = bool(_orchestrator.cfg.dry_run) if _orchestrator else False
    if not admin_key:
        if dry_run:
            return  # Dry-run dev mode can remain open for local iteration.
        raise HTTPException(503, "Investment admin key is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    if authorization[7:] != admin_key:
        raise HTTPException(403, "Invalid admin key")


# ── Health ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "investments",
        "dry_run": _orchestrator.cfg.dry_run if _orchestrator else None,
        "fallback_mode": _is_fallback_mode(),
    }


# ── Basket ─────────────────────────────────────────────────────────────────

@app.get("/api/investments/basket")
async def get_basket() -> dict:
    """Current basket state (tokens, weights, NAV)."""
    raw = await _orchestrator._get_basket_state()
    # Inject last/next rebalance from decisions if available
    if hasattr(_orchestrator, "_last_cycle_ts") and _orchestrator._last_cycle_ts:
        raw.setdefault("last_rebalance", _orchestrator._last_cycle_ts)
    return _adapt_basket(raw)


@app.get("/api/investments/performance")
async def get_performance(
    hours: int = Query(default=168, ge=1, le=8760),
) -> list[dict]:
    """NAV performance over time. Returns PerformancePoint[]."""
    if _is_fallback_mode() and hasattr(_orchestrator, "get_performance"):
        raw = await _orchestrator.get_performance(hours)
        return _adapt_performance(raw)

    rows = await _db.fetch(
        """
        SELECT ts, nav_usd FROM inv_nav_snapshots
        WHERE basket_id = $1 AND ts > NOW() - make_interval(hours => $2)
        ORDER BY ts ASC
        """,
        _orchestrator.cfg.basket_id,
        hours,
    )
    points = [{"ts": r["ts"].isoformat(), "nav_usd": float(r["nav_usd"])} for r in rows]
    return _adapt_performance({"points": points})


# ── Decisions / Agent Logs ─────────────────────────────────────────────────

@app.get("/api/investments/decisions")
async def get_decisions(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    """Recent investment decisions. Returns InvestmentDecision[]."""
    if _is_fallback_mode() and hasattr(_orchestrator, "get_decisions"):
        raw = await _orchestrator.get_decisions(limit)
        return [_adapt_decision(d) for d in raw]

    rows = await _db.fetch(
        """
        SELECT id, action, final_weights, trader_reasoning, trader_confidence,
               basket_nav_usd, tx_hash, created_at
        FROM inv_decisions
        WHERE basket_id = $1
        ORDER BY created_at DESC LIMIT $2
        """,
        _orchestrator.cfg.basket_id,
        limit,
    )
    return [
        _adapt_decision({
            "id": r["id"],
            "action": r["action"],
            "final_weights": (
                json.loads(r["final_weights"])
                if isinstance(r["final_weights"], str)
                else (r["final_weights"] or {})
            ),
            "reasoning": r["trader_reasoning"] or "",
            "confidence": float(r["trader_confidence"]) if r["trader_confidence"] else 0,
            "nav_usd": float(r["basket_nav_usd"]) if r["basket_nav_usd"] else 0,
            "tx_hash": r["tx_hash"],
            "ts": r["created_at"].isoformat(),
        })
        for r in rows
    ]


@app.get("/api/investments/decisions/{decision_id}")
async def get_decision_detail(decision_id: int) -> dict:
    """Full decision detail. Returns InvestmentDecision."""
    if _is_fallback_mode() and hasattr(_orchestrator, "get_decision_detail"):
        row = await _orchestrator.get_decision_detail(decision_id)
        if not row:
            raise HTTPException(404, "Decision not found")
        return _adapt_decision(row)

    row = await _db.fetchrow(
        """
        SELECT id, basket_id, action, final_weights, previous_weights,
               basket_nav_usd, grok_sentiment_report, claude_risk_report,
               chatgpt_macro_report, dexter_fundamental_report, debate_rounds,
               risk_approved, risk_veto_reason, trader_confidence, trader_reasoning,
               tx_hash, execution_status, created_at
        FROM inv_decisions
        WHERE id = $1
        """,
        decision_id,
    )
    if not row:
        raise HTTPException(404, "Decision not found")

    def parse_json_field(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    final_weights = parse_json_field(row["final_weights"]) or {}
    previous_weights = parse_json_field(row["previous_weights"]) or {}

    agent_reports: list[dict[str, Any]] = []
    for agent_name, key in (
        ("Grok", "grok_sentiment_report"),
        ("Claude", "claude_risk_report"),
        ("ChatGPT", "chatgpt_macro_report"),
        ("Dexter", "dexter_fundamental_report"),
    ):
        payload = parse_json_field(row[key]) or {}
        if payload:
            agent_reports.append({
                "agent": agent_name,
                "recommendation": row["action"] or "HOLD",
                "confidence": float(row["trader_confidence"] or 0),
                "reasoning": str(payload)[:800],
            })

    risk_assessment = {
        "overall_risk": "LOW" if row["risk_approved"] else "HIGH",
        "max_drawdown_pct": 0.0,
        "var_95": 0.0,
        "concentration_risk": "N/A",
        "liquidity_risk": row["risk_veto_reason"] or "N/A",
    }

    return _adapt_decision({
        "id": row["id"],
        "action": row["action"],
        "summary": row["trader_reasoning"] or "",
        "reasoning": row["trader_reasoning"] or "",
        "confidence": float(row["trader_confidence"] or 0),
        "nav_usd": float(row["basket_nav_usd"] or 0),
        "final_weights": final_weights,
        "previous_weights": previous_weights,
        "debate_rounds": [],
        "agent_reports": agent_reports,
        "risk_assessment": risk_assessment,
        "tx_hash": row["tx_hash"],
        "execution_status": row["execution_status"],
        "ts": row["created_at"].isoformat() if row["created_at"] else None,
    })


@app.get("/api/investments/reflections")
async def get_reflections(
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict]:
    """Recent reflection/calibration results. Returns Reflection[]."""
    if _is_fallback_mode() and hasattr(_orchestrator, "get_reflections"):
        raw = await _orchestrator.get_reflections(limit)
        return [_adapt_reflection(r) for r in raw]

    rows = await _db.fetch(
        """
        SELECT id, decision_id, data, calibration_hint, created_at
        FROM inv_reflections
        ORDER BY created_at DESC LIMIT $1
        """,
        limit,
    )
    return [
        _adapt_reflection({
            "id": r["id"],
            "data": json.loads(r["data"]) if isinstance(r["data"], str) else r["data"],
            "calibration_hint": r["calibration_hint"],
            "ts": r["created_at"].isoformat(),
        })
        for r in rows
    ]


# ── Manual Trigger ─────────────────────────────────────────────────────────

@app.post("/api/investments/trigger-cycle", dependencies=[Depends(require_admin)])
async def trigger_cycle() -> dict:
    """Manually trigger an investment cycle. Use with caution."""
    result = await _orchestrator.run_cycle(trigger_type="manual")
    return result


# ── Kill Switch ────────────────────────────────────────────────────────────

@app.get("/api/investments/kill-switch")
async def get_kill_switch() -> dict:
    killed = await _orchestrator.safety.is_killed()
    return {"active": killed}


@app.post("/api/investments/kill-switch/activate", dependencies=[Depends(require_admin)])
async def activate_kill_switch() -> dict:
    await _orchestrator.safety.activate_kill_switch("Manual activation via API")
    return _adapt_kill_switch_response(True)


@app.post("/api/investments/kill-switch/deactivate", dependencies=[Depends(require_admin)])
async def deactivate_kill_switch() -> dict:
    await _orchestrator.safety.deactivate_kill_switch()
    return _adapt_kill_switch_response(False)


# ── Bridge ─────────────────────────────────────────────────────────────────

@app.get("/api/investments/bridge/jobs")
async def get_bridge_jobs(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    """Recent bridge jobs."""
    if _is_fallback_mode():
        return []

    rows = await _db.fetch(
        """
        SELECT id, state, amount_usdc, burn_tx_hash, mint_tx_hash, deposit_tx_hash,
               error, retry_count, created_at, updated_at
        FROM inv_bridge_jobs
        ORDER BY created_at DESC LIMIT $1
        """,
        limit,
    )
    return [
        {
            "id": str(r["id"]),
            "state": str(r["state"] or "pending").lower(),
            "amount_usd": float(r["amount_usdc"]) if r["amount_usdc"] else 0,
            "token": "USDC",
            "source_chain": "ethereum",
            "dest_chain": "solana",
            "source_tx": r["burn_tx_hash"] or "",
            "dest_tx": r["deposit_tx_hash"] or r["mint_tx_hash"] or "",
            "error": r["error"],
            "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


# ── Staking ────────────────────────────────────────────────────────────────

@app.get("/api/investments/staking/pool")
async def get_staking_pool() -> dict:
    """Current staking pool stats."""
    if _is_fallback_mode():
        return {"tvl_usd": 0, "apy_pct": 0, "total_stakers": 0, "tiers": []}

    row = await _db.fetchrow(
        """
        SELECT total_staked, total_stakers, reward_vault_balance, estimated_apy
        FROM inv_staking_pool_snapshots
        ORDER BY created_at DESC LIMIT 1
        """
    )
    if not row:
        return {"tvl_usd": 0, "apy_pct": 0, "total_stakers": 0, "tiers": []}

    tvl_usd = float(row["reward_vault_balance"] or 0)
    return {
        "tvl_usd": tvl_usd,
        "apy_pct": float(row["estimated_apy"] or 0),
        "total_stakers": int(row["total_stakers"] or 0),
        "tiers": [],
    }


# ── WebSocket ──────────────────────────────────────────────────────────────

_ws_connections: list[WebSocket] = []


@app.websocket("/ws/investments")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Real-time investment updates via WebSocket."""
    await websocket.accept()
    _ws_connections.append(websocket)
    logger.info("WebSocket client connected (%d total)", len(_ws_connections))
    try:
        while True:
            # Keep alive — client can also send commands
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        _ws_connections.remove(websocket)
        logger.info("WebSocket client disconnected (%d remaining)", len(_ws_connections))


async def broadcast_ws(message: dict) -> None:
    """Broadcast a message to all connected WebSocket clients."""
    dead = []
    text = json.dumps(message)
    for ws in list(_ws_connections):
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_connections.remove(ws)
