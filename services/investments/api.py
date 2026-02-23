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
    rows = await _db.fetch(
        """
        SELECT id, basket_id, action, final_weights, reasoning, confidence,
               nav_usd, tx_hash, created_at
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
            "final_weights": json.loads(r["final_weights"]) if r["final_weights"] else {},
            "reasoning": r["reasoning"],
            "confidence": float(r["confidence"]) if r["confidence"] else 0,
            "nav_usd": float(r["nav_usd"]) if r["nav_usd"] else 0,
            "tx_hash": r["tx_hash"],
            "ts": r["created_at"].isoformat(),
        }
        for r in rows
    ]


@app.get("/api/investments/decisions/{decision_id}")
async def get_decision_detail(decision_id: int) -> dict:
    """Full decision detail including all agent reports and debate."""
    row = await _db.fetchrow(
        "SELECT * FROM inv_decisions WHERE id = $1",
        decision_id,
    )
    if not row:
        raise HTTPException(404, "Decision not found")

    result = dict(row)
    # Parse JSON fields
    for field in [
        "final_weights", "grok_sentiment_report", "claude_risk_report",
        "chatgpt_macro_report", "dexter_fundamental_report",
        "debate_rounds", "risk_assessment",
    ]:
        if result.get(field) and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except json.JSONDecodeError:
                pass

    # Convert datetime to string
    if result.get("created_at"):
        result["created_at"] = result["created_at"].isoformat()

    return result


@app.get("/api/investments/reflections")
async def get_reflections(
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict]:
    """Recent reflection/calibration results."""
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
    rows = await _db.fetch(
        """
        SELECT id, state, amount_usdc, source_tx_hash, dest_tx_hash,
               error_message, created_at, updated_at
        FROM inv_bridge_jobs
        ORDER BY created_at DESC LIMIT $1
        """,
        limit,
    )
    return [
        {
            "id": r["id"],
            "state": r["state"],
            "amount_usdc": float(r["amount_usdc"]) if r["amount_usdc"] else 0,
            "source_tx_hash": r["source_tx_hash"],
            "dest_tx_hash": r["dest_tx_hash"],
            "error": r["error_message"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]


# ── Staking ────────────────────────────────────────────────────────────────

@app.get("/api/investments/staking/pool")
async def get_staking_pool() -> dict:
    """Current staking pool stats."""
    row = await _db.fetchrow(
        """
        SELECT tvl_usd, apy_pct, total_stakers, total_rewards_distributed_usd
        FROM inv_staking_pool_snapshots
        ORDER BY ts DESC LIMIT 1
        """
    )
    if not row:
        return {"tvl_usd": 0, "apy_pct": 0, "total_stakers": 0, "total_rewards_distributed_usd": 0}
    return dict(row)


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
