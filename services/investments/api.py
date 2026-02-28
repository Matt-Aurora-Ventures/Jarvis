"""FastAPI routes for the investment service.

Runs as a standalone FastAPI app on its own port (default 8770).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger("investments.api")

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
    if not admin_key:
        return  # No key configured = open access (dev mode)
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
    basket = await _orchestrator._get_basket_state()
    return basket


@app.get("/api/investments/performance")
async def get_performance(
    hours: int = Query(default=168, ge=1, le=8760),
) -> dict:
    """NAV performance over time."""
    if _is_fallback_mode() and hasattr(_orchestrator, "get_performance"):
        return await _orchestrator.get_performance(hours)

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

    if len(points) >= 2 and points[0]["nav_usd"] != 0:
        change_pct = (points[-1]["nav_usd"] - points[0]["nav_usd"]) / points[0]["nav_usd"]
    else:
        change_pct = 0.0

    return {
        "basket_id": _orchestrator.cfg.basket_id,
        "hours": hours,
        "points": points,
        "change_pct": change_pct,
    }


# ── Decisions / Agent Logs ─────────────────────────────────────────────────

@app.get("/api/investments/decisions")
async def get_decisions(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    """Recent investment decisions with full audit trail."""
    if _is_fallback_mode() and hasattr(_orchestrator, "get_decisions"):
        return await _orchestrator.get_decisions(limit)

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
        {
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
        }
        for r in rows
    ]


@app.get("/api/investments/decisions/{decision_id}")
async def get_decision_detail(decision_id: int) -> dict:
    """Full decision detail including all agent reports and debate."""
    if _is_fallback_mode() and hasattr(_orchestrator, "get_decision_detail"):
        row = await _orchestrator.get_decision_detail(decision_id)
        if not row:
            raise HTTPException(404, "Decision not found")
        return row

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

    # Normalize to the UI-facing contract used by adapters.
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
            agent_reports.append(
                {
                    "agent": agent_name,
                    "recommendation": row["action"] or "HOLD",
                    "confidence": float(row["trader_confidence"] or 0),
                    "reasoning": str(payload)[:800],
                }
            )

    risk_assessment = {
        "overall_risk": "LOW" if row["risk_approved"] else "HIGH",
        "max_drawdown_pct": 0.0,
        "var_95": 0.0,
        "concentration_risk": "N/A",
        "liquidity_risk": row["risk_veto_reason"] or "N/A",
    }

    return {
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
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@app.get("/api/investments/reflections")
async def get_reflections(
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict]:
    """Recent reflection/calibration results."""
    if _is_fallback_mode() and hasattr(_orchestrator, "get_reflections"):
        return await _orchestrator.get_reflections(limit)

    rows = await _db.fetch(
        """
        SELECT id, decision_id, data, calibration_hint, created_at
        FROM inv_reflections
        ORDER BY created_at DESC LIMIT $1
        """,
        limit,
    )
    return [
        {
            "id": r["id"],
            "decision_id": r["decision_id"],
            "data": json.loads(r["data"]) if isinstance(r["data"], str) else r["data"],
            "calibration_hint": r["calibration_hint"],
            "ts": r["created_at"].isoformat(),
        }
        for r in rows
    ]


# ── Manual Trigger ─────────────────────────────────────────────────────────

@app.post("/api/investments/trigger-cycle", dependencies=[Depends(require_admin)])
async def trigger_cycle() -> dict:
    """Manually trigger an investment cycle. Use with caution."""
    result = await _orchestrator.run_cycle()
    return result


# ── Kill Switch ────────────────────────────────────────────────────────────

@app.get("/api/investments/kill-switch")
async def get_kill_switch() -> dict:
    killed = await _orchestrator.safety.is_killed()
    return {"active": killed}


@app.post("/api/investments/kill-switch/activate", dependencies=[Depends(require_admin)])
async def activate_kill_switch() -> dict:
    await _orchestrator.safety.activate_kill_switch("Manual activation via API")
    return {"status": "activated"}


@app.post("/api/investments/kill-switch/deactivate", dependencies=[Depends(require_admin)])
async def deactivate_kill_switch() -> dict:
    await _orchestrator.safety.deactivate_kill_switch()
    return {"status": "deactivated"}


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
            "id": r["id"],
            "state": str(r["state"] or "pending").lower(),
            "amount_usd": float(r["amount_usdc"]) if r["amount_usdc"] else 0,
            "token": "USDC",
            "source_chain": "base",
            "dest_chain": "solana",
            "source_tx": r["burn_tx_hash"] or "",
            "dest_tx": r["deposit_tx_hash"] or r["mint_tx_hash"] or "",
            "hook_attempts": int(r["retry_count"]) if r["retry_count"] is not None else None,
            "error": r["error"],
            "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
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
