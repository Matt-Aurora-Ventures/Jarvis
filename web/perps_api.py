"""
Jarvis Perps API Blueprint
==========================
Flask blueprint mounted at /api/perps/ that surfaces the Jupiter Perps
runtime without requiring the runner to be running in-process.

Reads state from runtime files written by the runner/watchdog, and
forwards intents by writing to the intent queue file the runner polls.

Endpoints:
  GET  /api/perps/prices          — live SOL/BTC/ETH from Pyth Hermes
  GET  /api/perps/price/<market>  — single market price
  GET  /api/perps/history/<market>— 24h OHLC from Pyth Benchmarks
  GET  /api/perps/status          — runner health + arm state
  GET  /api/perps/positions       — tracked positions from state files
  GET  /api/perps/signal          — latest AI signal from runner
  GET  /api/perps/audit           — last 50 audit events
  GET  /api/perps/performance     — win rate / P&L from self_adjuster DB
  POST /api/perps/open            — queue OpenPosition intent
  POST /api/perps/close           — queue ClosePosition intent
  POST /api/perps/arm             — prepare + confirm arm sequence
  POST /api/perps/disarm          — disarm live trading
  POST /api/perps/limits          — update risk limits
  POST /api/perps/runner/start    — start the runner subprocess
  POST /api/perps/runner/stop     — stop the runner subprocess
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

perps_bp = Blueprint("perps", __name__, url_prefix="/api/perps")

_ROOT = Path(__file__).resolve().parents[1]
_RUNTIME_DIR = Path(
    os.environ.get(
        "JARVIS_RALPH_RUNTIME_DIR",
        str(Path(os.environ.get("LOCALAPPDATA", ".")) / "Jarvis" / "vanguard-standalone"),
    )
)
_INTENT_QUEUE = _RUNTIME_DIR / "intent_queue.jsonl"
_POSITIONS_STATE = _RUNTIME_DIR / "positions_state.json"
_INTENT_AUDIT = _RUNTIME_DIR / "intent_audit.log"
_PYTH_HERMES = os.environ.get("PERPS_PYTH_HERMES_URL", "https://hermes.pyth.network")
_PYTH_BENCHMARKS = "https://benchmarks.pyth.network"
_DEFAULT_COLLATERAL_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

_PYTH_FEED_IDS = {
    "SOL-USD": "0xef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d",
    "BTC-USD": "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
    "ETH-USD": "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
}

_MARKETS = list(_PYTH_FEED_IDS.keys())

# In-memory reference to spawned runner subprocess
_runner_proc: subprocess.Popen | None = None


def _safe_payload_snapshot(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    snapshot: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            snapshot[key] = value
        else:
            snapshot[key] = str(value)
    return snapshot


def _audit_intent(event: str, **fields: Any) -> None:
    try:
        _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"event": event, "timestamp": int(time.time()), **fields}
        with _INTENT_AUDIT.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception:
        logger.debug("Failed writing intent audit event=%s", event, exc_info=True)


# ── Price Feed ────────────────────────────────────────────────────────────────

def _fetch_price(market: str) -> dict[str, Any]:
    feed_id = _PYTH_FEED_IDS.get(market)
    if not feed_id:
        return {"error": f"Unknown market {market}"}
    url = f"{_PYTH_HERMES}/v2/updates/price/latest?ids[]={feed_id}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        parsed = data.get("parsed") or []
        if parsed:
            p = parsed[0].get("price", {})
            price_raw = int(p.get("price", 0))
            expo = int(p.get("expo", 0))
            price = price_raw * (10 ** expo)
            conf_raw = int(p.get("conf", 0))
            conf = conf_raw * (10 ** expo)
            pub_time = int(p.get("publish_time", 0))
            age = int(time.time()) - pub_time
            return {"market": market, "price": price, "confidence": conf, "age_seconds": age}
    except Exception as exc:
        logger.warning("Price fetch failed for %s: %s", market, exc)
    return {"market": market, "price": 0.0, "error": "fetch_failed"}


@perps_bp.route("/price/<market>")
def price(market: str):
    m = market.upper()
    if m not in _PYTH_FEED_IDS:
        return jsonify({"error": f"Unknown market. Valid: {_MARKETS}"}), 400
    return jsonify(_fetch_price(m))


@perps_bp.route("/prices")
def all_prices():
    return jsonify({m: _fetch_price(m) for m in _MARKETS})


# ── Price History (Pyth Benchmarks) ──────────────────────────────────────────

@perps_bp.route("/history/<market>")
def price_history(market: str):
    """Return 24h of 5-minute OHLC candles from Pyth Benchmarks."""
    m = market.upper()
    if m not in _PYTH_FEED_IDS:
        return jsonify({"error": f"Unknown market. Valid: {_MARKETS}"}), 400

    symbol_map = {"SOL-USD": "Crypto.SOL/USD", "BTC-USD": "Crypto.BTC/USD", "ETH-USD": "Crypto.ETH/USD"}
    symbol = symbol_map.get(m, f"Crypto.{m.replace('-', '/')}")

    now = int(time.time())
    from_ts = now - 86400  # 24 hours
    resolution = request.args.get("resolution", "5")

    url = (
        f"{_PYTH_BENCHMARKS}/v1/shims/tradingview/history"
        f"?symbol={urllib.request.quote(symbol)}"
        f"&resolution={resolution}&from={from_ts}&to={now}"
    )
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        # TradingView format: {t:[], o:[], h:[], l:[], c:[], v:[], s:"ok"}
        if data.get("s") == "ok":
            candles = []
            for i in range(len(data.get("t", []))):
                candles.append({
                    "time": data["t"][i],
                    "open": data["o"][i],
                    "high": data["h"][i],
                    "low": data["l"][i],
                    "close": data["c"][i],
                })
            return jsonify({"market": m, "resolution": resolution, "candles": candles})
        return jsonify({"market": m, "candles": [], "error": data.get("s", "no_data")})
    except Exception as exc:
        logger.warning("History fetch failed for %s: %s", m, exc)
        return jsonify({"market": m, "candles": [], "error": str(exc)})


# ── Runtime Status ────────────────────────────────────────────────────────────

def _read_pid(path: Path) -> int:
    try:
        return int(path.read_text().strip())
    except Exception:
        return 0


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
        except Exception:
            pass
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _get_control_state() -> dict[str, Any]:
    """Read the LiveControlState file directly (same path as live_control.py)."""
    state_path = _RUNTIME_DIR / "control_state.json"
    try:
        if state_path.exists():
            data = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "arm" in data:
                return data
    except Exception:
        pass
    return {}


def _runtime_health() -> dict[str, Any]:
    runner_pid = _read_pid(_RUNTIME_DIR / "runner.pid")
    watchdog_pid = _read_pid(_RUNTIME_DIR / "watchdog.pid")
    stop_flag = (_RUNTIME_DIR / "watchdog.stop").exists()
    runner_alive = _pid_alive(runner_pid)

    # Heartbeat from runner log
    heartbeat_age = None
    candidates = sorted(_RUNTIME_DIR.glob("runner_stderr_*.log"), key=lambda p: p.stat().st_mtime, reverse=True) if _RUNTIME_DIR.exists() else []
    if candidates:
        try:
            for line in reversed(candidates[0].read_text(errors="ignore").splitlines()[-500:]):
                try:
                    ev = json.loads(line.strip())
                    if ev.get("event") == "heartbeat":
                        heartbeat_age = int(time.time()) - int(ev.get("timestamp", 0))
                        break
                except Exception:
                    pass
        except Exception:
            pass

    if runner_alive and heartbeat_age is not None and heartbeat_age <= 30:
        health = "healthy"
    elif runner_alive:
        health = "degraded"
    else:
        health = "down"

    # Arm state
    ctrl = _get_control_state()
    arm_info = ctrl.get("arm", {})
    mode_info = ctrl.get("mode", {})
    limits_info = ctrl.get("limits", {})
    stats_info = ctrl.get("stats", {})

    return {
        "health": health,
        "runner": {"pid": runner_pid, "alive": runner_alive},
        "watchdog": {"pid": watchdog_pid, "alive": _pid_alive(watchdog_pid)},
        "stop_flag": stop_flag,
        "heartbeat_age_seconds": heartbeat_age,
        "arm": {
            "stage": arm_info.get("stage", "disarmed"),
            "expires_at": arm_info.get("expires_at", 0),
            "armed_by": arm_info.get("armed_by", ""),
            "last_reason": arm_info.get("last_reason", ""),
        },
        "desired_live": bool(mode_info.get("desired_live", False)),
        "limits": {
            "max_trades_per_day": limits_info.get("max_trades_per_day", 40),
            "daily_loss_limit_usd": limits_info.get("daily_loss_limit_usd", 500),
        },
        "stats": {
            "trades_today": stats_info.get("trades_today", 0),
            "realized_pnl_today": stats_info.get("realized_pnl_today", 0),
            "last_trade_at": stats_info.get("last_trade_at", 0),
        },
        "control_board_url": "http://127.0.0.1:8181",
    }


@perps_bp.route("/status")
def status():
    health = _runtime_health()
    positions = []
    try:
        if _POSITIONS_STATE.exists():
            raw = json.loads(_POSITIONS_STATE.read_text())
            positions = list(raw.values()) if isinstance(raw, dict) else raw
    except Exception:
        pass
    health["positions_count"] = len(positions)
    return jsonify(health)


# ── Positions ─────────────────────────────────────────────────────────────────

@perps_bp.route("/positions")
def positions():
    try:
        if _POSITIONS_STATE.exists():
            raw = json.loads(_POSITIONS_STATE.read_text())
            pos_list = list(raw.values()) if isinstance(raw, dict) else raw
        else:
            pos_list = []
        return jsonify({"positions": pos_list})
    except Exception as exc:
        return jsonify({"positions": [], "error": str(exc)})


# ── AI Signal ────────────────────────────────────────────────────────────────

@perps_bp.route("/signal")
def signal():
    """Return the latest AI signal from the runner's output files."""
    signal_file = _RUNTIME_DIR / "latest_signal.json"
    if signal_file.exists():
        try:
            data = json.loads(signal_file.read_text(encoding="utf-8"))
            age = int(time.time()) - int(data.get("timestamp", 0))
            data["age_seconds"] = age
            data["stale"] = age > 120  # signal older than 2 minutes
            return jsonify(data)
        except Exception as exc:
            return jsonify({"error": str(exc), "stale": True})

    # Fallback: scan recent runner log for last signal event
    candidates = sorted(
        _RUNTIME_DIR.glob("runner_stderr_*.log"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    ) if _RUNTIME_DIR.exists() else []
    if candidates:
        try:
            lines = candidates[0].read_text(errors="ignore").splitlines()[-200:]
            for line in reversed(lines):
                try:
                    ev = json.loads(line.strip())
                    if ev.get("event") in ("ai_signal", "signal_merge", "intent_created"):
                        ev["age_seconds"] = int(time.time()) - int(ev.get("timestamp", 0))
                        ev["stale"] = ev["age_seconds"] > 120
                        return jsonify(ev)
                except Exception:
                    pass
        except Exception:
            pass

    return jsonify({
        "market": None, "direction": None, "confidence": 0,
        "stale": True, "error": "no_signal_available",
        "hint": "Runner may not be running. Start it from the dashboard.",
    })


# ── ARM / DISARM ─────────────────────────────────────────────────────────────

def _get_live_control():
    """Lazy-import LiveControlState to avoid hard dependency on core module."""
    try:
        from core.jupiter_perps.live_control import LiveControlState
        return LiveControlState()
    except ImportError:
        return None


@perps_bp.route("/arm", methods=["POST"])
def arm():
    """Two-step arm: step=prepare returns a challenge, step=confirm arms."""
    data = request.get_json() or {}
    step = data.get("step", "prepare")
    actor = data.get("actor", "web_ui")

    ctrl = _get_live_control()
    if ctrl is None:
        return jsonify({"ok": False, "error": "LiveControlState not available (core module missing)"}), 500

    if step == "prepare":
        result = ctrl.prepare_arm(actor=actor)
        return jsonify(result)
    elif step == "confirm":
        challenge = data.get("challenge", "")
        if not challenge:
            return jsonify({"ok": False, "error": "challenge required for confirm step"}), 400
        ok, reason, snapshot = ctrl.confirm_arm(challenge=challenge, actor=actor)
        return jsonify({"ok": ok, "reason": reason, **snapshot})
    else:
        return jsonify({"ok": False, "error": "step must be 'prepare' or 'confirm'"}), 400


@perps_bp.route("/disarm", methods=["POST"])
def disarm():
    data = request.get_json() or {}
    reason = data.get("reason", "web_ui_disarm")
    actor = data.get("actor", "web_ui")

    ctrl = _get_live_control()
    if ctrl is None:
        return jsonify({"ok": False, "error": "LiveControlState not available"}), 500

    snapshot = ctrl.disarm(reason=reason, actor=actor)
    return jsonify({"ok": True, **snapshot})


@perps_bp.route("/limits", methods=["POST"])
def set_limits():
    data = request.get_json() or {}
    ctrl = _get_live_control()
    if ctrl is None:
        return jsonify({"ok": False, "error": "LiveControlState not available"}), 500

    snapshot = ctrl.set_limits(
        max_trades_per_day=data.get("max_trades_per_day"),
        daily_loss_limit_usd=data.get("daily_loss_limit_usd"),
    )
    return jsonify({"ok": True, **snapshot})


# ── Runner Start / Stop ──────────────────────────────────────────────────────

@perps_bp.route("/runner/start", methods=["POST"])
def runner_start():
    global _runner_proc

    # Check if already running
    pid = _read_pid(_RUNTIME_DIR / "runner.pid")
    if _pid_alive(pid):
        return jsonify({"ok": True, "message": "Runner already running", "pid": pid})

    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    try:
        cmd = [sys.executable, "-m", "core.jupiter_perps.runner"]
        _runner_proc = subprocess.Popen(
            cmd,
            cwd=str(_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=open(str(_RUNTIME_DIR / f"runner_stderr_{int(time.time())}.log"), "w"),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        # Write PID
        (_RUNTIME_DIR / "runner.pid").write_text(str(_runner_proc.pid))
        return jsonify({"ok": True, "pid": _runner_proc.pid, "message": "Runner started"})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@perps_bp.route("/runner/stop", methods=["POST"])
def runner_stop():
    global _runner_proc

    pid = _read_pid(_RUNTIME_DIR / "runner.pid")
    if not _pid_alive(pid):
        return jsonify({"ok": True, "message": "Runner not running"})

    try:
        if os.name == "nt":
            os.kill(pid, signal.CTRL_BREAK_EVENT)
        else:
            os.kill(pid, signal.SIGTERM)

        # Clean up PID file
        pid_file = _RUNTIME_DIR / "runner.pid"
        if pid_file.exists():
            pid_file.unlink()

        _runner_proc = None
        return jsonify({"ok": True, "message": f"Runner (PID {pid}) stopped"})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── Intent Queue ──────────────────────────────────────────────────────────────

def _queue_intent(intent: dict) -> dict[str, Any]:
    """Write intent to queue file consumed by canonical runner."""
    def _marker_path(key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return _RUNTIME_DIR / "intent_idempotency" / f"{digest}.seen"

    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    intent.setdefault("idempotency_key", str(uuid.uuid4()))
    intent["queued_at"] = time.time()
    idempotency_key = str(intent["idempotency_key"])
    marker = _marker_path(idempotency_key)
    marker.parent.mkdir(parents=True, exist_ok=True)

    try:
        with marker.open("x", encoding="utf-8") as marker_handle:
            marker_handle.write(str(intent["queued_at"]))
    except FileExistsError:
        _audit_intent(
            "intent_duplicate",
            idempotency_key=idempotency_key,
            endpoint=str(intent.get("source", "unknown")),
        )
        return {"ok": True, "duplicate": True, "idempotency_key": idempotency_key}

    try:
        with _INTENT_QUEUE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(intent) + "\n")
        _audit_intent(
            "intent_accepted",
            idempotency_key=idempotency_key,
            intent_type=intent.get("intent_type") or intent.get("type"),
            source=intent.get("source", "unknown"),
        )
        return {"ok": True, "idempotency_key": idempotency_key}
    except Exception as exc:
        try:
            marker.unlink(missing_ok=True)
        except Exception:
            pass
        _audit_intent(
            "intent_enqueue_failed",
            idempotency_key=idempotency_key,
            error=str(exc),
            intent_type=intent.get("intent_type") or intent.get("type"),
            source=intent.get("source", "unknown"),
        )
        return {"ok": False, "error": str(exc)}


@perps_bp.route("/open", methods=["POST"])
def open_position():
    data = request.get_json() or {}
    market = data.get("market", "").upper()
    side = data.get("side", "").lower()
    collateral_value = data.get("collateral_amount_usd", data.get("collateral_usd", 0))
    size_value = data.get("size_usd")
    collateral_mint = data.get("collateral_mint", _DEFAULT_COLLATERAL_MINT)
    max_slippage_bps = int(data.get("max_slippage_bps", data.get("slippage_bps", 50)))
    leverage = float(data.get("leverage", 1))
    try:
        collateral_amount_usd = float(collateral_value)
    except (TypeError, ValueError):
        _audit_intent(
            "ingress_rejected",
            endpoint="/api/perps/open",
            reason="invalid collateral amount",
            payload=_safe_payload_snapshot(data),
        )
        return jsonify({"ok": False, "error": "collateral_amount_usd must be numeric"}), 400

    if size_value is None:
        size_usd = collateral_amount_usd * leverage
    else:
        try:
            size_usd = float(size_value)
        except (TypeError, ValueError):
            _audit_intent(
                "ingress_rejected",
                endpoint="/api/perps/open",
                reason="invalid size_usd",
                payload=_safe_payload_snapshot(data),
            )
            return jsonify({"ok": False, "error": "size_usd must be numeric"}), 400

    tp_pct = float(data.get("tp_pct", 10))
    sl_pct = float(data.get("sl_pct", 5))

    if market not in _MARKETS:
        _audit_intent(
            "ingress_rejected",
            endpoint="/api/perps/open",
            reason=f"invalid market {market}",
            payload=_safe_payload_snapshot(data),
        )
        return jsonify({"ok": False, "error": f"market must be one of {_MARKETS}"}), 400
    if side not in ("long", "short"):
        _audit_intent(
            "ingress_rejected",
            endpoint="/api/perps/open",
            reason=f"invalid side {side}",
            payload=_safe_payload_snapshot(data),
        )
        return jsonify({"ok": False, "error": "side must be long or short"}), 400
    if collateral_amount_usd <= 0:
        _audit_intent(
            "ingress_rejected",
            endpoint="/api/perps/open",
            reason="collateral_amount_usd <= 0",
            payload=_safe_payload_snapshot(data),
        )
        return jsonify({"ok": False, "error": "collateral_amount_usd must be > 0"}), 400
    if leverage < 1 or leverage > 250:
        _audit_intent(
            "ingress_rejected",
            endpoint="/api/perps/open",
            reason=f"invalid leverage {leverage}",
            payload=_safe_payload_snapshot(data),
        )
        return jsonify({"ok": False, "error": "leverage must be 1-250"}), 400
    if size_usd <= 0:
        _audit_intent(
            "ingress_rejected",
            endpoint="/api/perps/open",
            reason="size_usd <= 0",
            payload=_safe_payload_snapshot(data),
        )
        return jsonify({"ok": False, "error": "size_usd must be > 0"}), 400

    intent = {
        "intent_type": "open_position",
        "idempotency_key": data.get("idempotency_key", str(uuid.uuid4())),
        "market": market,
        "side": side,
        "collateral_mint": collateral_mint,
        "collateral_amount_usd": collateral_amount_usd,
        "leverage": leverage,
        "size_usd": size_usd,
        "max_slippage_bps": max_slippage_bps,
        "take_profit_pct": tp_pct,
        "stop_loss_pct": sl_pct,
        "source": "web_ui",
    }
    result = _queue_intent(intent)
    return jsonify(result), (200 if result["ok"] else 500)


@perps_bp.route("/close", methods=["POST"])
def close_position():
    data = request.get_json() or {}
    position_pda = (
        data.get("position_pda")
        or data.get("original_position_pda")
        or data.get("original_idempotency_key")
        or ""
    )
    position_pda = str(position_pda).strip()
    if not position_pda:
        _audit_intent(
            "ingress_rejected",
            endpoint="/api/perps/close",
            reason="missing position_pda",
            payload=_safe_payload_snapshot(data),
        )
        return jsonify({"ok": False, "error": "position_pda required"}), 400

    idempotency_key = str(data.get("idempotency_key") or f"close-{uuid.uuid4()}").strip()

    intent = {
        "intent_type": "close_position",
        "idempotency_key": idempotency_key,
        "position_pda": position_pda,
        "original_idempotency_key": str(data.get("original_idempotency_key", "")),
        "max_slippage_bps": int(data.get("max_slippage_bps", data.get("slippage_bps", 300))),
        "source": "web_ui",
    }
    result = _queue_intent(intent)
    return jsonify(result), (200 if result["ok"] else 500)


# ── Audit Log ─────────────────────────────────────────────────────────────────

@perps_bp.route("/audit")
def audit():
    audit_file = _RUNTIME_DIR / "control_audit.log"
    sources = [audit_file, _INTENT_AUDIT]
    events: list[dict[str, Any]] = []
    try:
        for source in sources:
            if not source.exists():
                continue
            lines = source.read_text(errors="ignore").splitlines()[-100:]
            for line in lines:
                try:
                    event = json.loads(line)
                    if isinstance(event, dict):
                        events.append(event)
                except Exception:
                    continue
        events.sort(key=lambda item: int(item.get("timestamp", 0)), reverse=True)
        events = events[:50]
        return jsonify({"events": events})
    except Exception as exc:
        return jsonify({"events": [], "error": str(exc)})


# ── Performance (Self-Adjuster) ──────────────────────────────────────────────

@perps_bp.route("/performance")
def performance():
    """Read trade outcomes from self_adjuster SQLite DB."""
    db_path = _RUNTIME_DIR / "perps_journal.sqlite3"
    if not db_path.exists():
        # Check alternate location
        db_path = _RUNTIME_DIR / "event_journal.sqlite3"
    if not db_path.exists():
        return jsonify({
            "total_trades": 0, "win_rate": 0, "avg_pnl_pct": 0,
            "sources": {}, "error": "no_database",
        })

    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Total trades / win rate
        cur = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
                   AVG(pnl_pct) as avg_pnl,
                   SUM(pnl_usd) as total_pnl_usd
            FROM trade_outcomes
        """)
        row = cur.fetchone()
        total = row["total"] or 0
        wins = row["wins"] or 0
        avg_pnl = row["avg_pnl"] or 0
        total_pnl_usd = row["total_pnl_usd"] or 0

        # Per-source breakdown
        sources = {}
        try:
            cur2 = conn.execute("""
                SELECT signal_source,
                       COUNT(*) as trades,
                       SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
                       AVG(pnl_pct) as avg_pnl
                FROM trade_outcomes
                GROUP BY signal_source
            """)
            for r in cur2.fetchall():
                src = r["signal_source"] or "unknown"
                sources[src] = {
                    "trades": r["trades"],
                    "wins": r["wins"],
                    "win_rate": round(r["wins"] / r["trades"] * 100, 1) if r["trades"] else 0,
                    "avg_pnl_pct": round(r["avg_pnl"], 2) if r["avg_pnl"] else 0,
                }
        except Exception:
            pass  # table might not have signal_source column

        conn.close()

        return jsonify({
            "total_trades": total,
            "wins": wins,
            "win_rate": round(wins / total * 100, 1) if total else 0,
            "avg_pnl_pct": round(avg_pnl, 2),
            "total_pnl_usd": round(total_pnl_usd, 2),
            "sources": sources,
        })
    except Exception as exc:
        return jsonify({
            "total_trades": 0, "win_rate": 0, "avg_pnl_pct": 0,
            "sources": {}, "error": str(exc),
        })
