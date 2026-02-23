"""
Web API Adapter
==============
Provides the same interface as demo_trading/demo_sentiment but bypasses the
tg_bot → bot_core → telegram import chain that breaks the Flask server.

All I/O uses stdlib urllib — zero external dependencies beyond Flask itself.

Reads state from:
  - bots/treasury/.positions.json  (open positions)
  - Solana RPC                     (SOL balance)
  - DexScreener                    (market regime)
  - XAI / Grok                     (sentiment)
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
POSITIONS_FILE = ROOT / "bots" / "treasury" / ".positions.json"
RPC_URL = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
WALLET_ADDRESS = os.environ.get("TREASURY_WALLET_ADDRESS", "")

_RUNTIME_DIR = Path(
    os.environ.get(
        "JARVIS_RALPH_RUNTIME_DIR",
        str(Path(os.environ.get("LOCALAPPDATA", ".")) / "Jarvis" / "vanguard-standalone"),
    )
)
_INTENT_QUEUE = _RUNTIME_DIR / "intent_queue.jsonl"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _http_get(url: str, timeout: int = 8) -> dict:
    """Synchronous HTTP GET returning parsed JSON."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("HTTP GET failed %s: %s", url, exc)
        return {}


def _http_post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 10) -> dict:
    """Synchronous HTTP POST with JSON body, returning parsed JSON."""
    try:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if headers:
            h.update(headers)
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("HTTP POST failed %s: %s", url, exc)
        return {}


# ── Portfolio ─────────────────────────────────────────────────────────────────

def _get_sol_balance(address: str) -> tuple[float, float]:
    """Return (sol_balance, usd_value). USD price from DexScreener."""
    if not address:
        return 0.0, 0.0
    try:
        balance_res = _http_post_json(RPC_URL, {
            "jsonrpc": "2.0", "id": 1,
            "method": "getBalance",
            "params": [address],
        })
        lamports = balance_res.get("result", {}).get("value", 0) or 0
        sol = lamports / 1e9

        # SOL price from DexScreener
        data = _http_get(
            "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112"
        )
        pairs = data.get("pairs") or []
        sol_price = 0.0
        for p in pairs:
            try:
                sol_price = float(p.get("priceUsd", 0))
                if sol_price > 0:
                    break
            except Exception:
                pass
        return sol, sol * sol_price
    except Exception as exc:
        logger.warning("Could not fetch SOL balance: %s", exc)
        return 0.0, 0.0


def _load_positions() -> list[dict]:
    """Load open positions from .positions.json."""
    try:
        if POSITIONS_FILE.exists():
            data = json.loads(POSITIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return list(data.values())
    except Exception as exc:
        logger.warning("Could not load positions: %s", exc)
    return []


def get_portfolio() -> dict[str, Any]:
    """Return portfolio summary for /api/status."""
    wallet_address = WALLET_ADDRESS
    sol_balance, usd_value = _get_sol_balance(wallet_address)
    positions = _load_positions()
    total_pnl = sum(float(p.get("unrealized_pnl", 0)) for p in positions)
    return {
        "success": True,
        "wallet_address": wallet_address or "Not configured",
        "sol_balance": sol_balance,
        "usd_value": usd_value,
        "is_live": os.environ.get("TREASURY_LIVE_MODE", "false").lower() in {"1", "true", "yes"},
        "open_positions": len(positions),
        "total_pnl": total_pnl,
    }


def get_positions() -> list[dict]:
    """Return serialised position list for /api/positions."""
    raw = _load_positions()
    result = []
    for p in raw:
        entry = float(p.get("entry_price", 0))
        current = float(p.get("current_price", entry))
        amount = float(p.get("amount", 0))
        cost = float(p.get("cost_basis", 0))
        value = float(p.get("current_value", current * amount))
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost else 0.0
        result.append({
            "id": p.get("id", ""),
            "symbol": p.get("token_symbol", p.get("symbol", "???")),
            "address": p.get("token_mint", p.get("address", "")),
            "entry_price": entry,
            "current_price": current,
            "amount": amount,
            "cost_basis_sol": cost,
            "current_value_sol": value,
            "unrealized_pnl": pnl,
            "unrealized_pnl_pct": pnl_pct,
            "timestamp": p.get("timestamp", ""),
        })
    return result


# ── Market Regime ─────────────────────────────────────────────────────────────

def get_market_regime() -> dict[str, Any]:
    try:
        data = _http_get(
            "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112"
        )
        pairs = data.get("pairs") or []
        if pairs:
            sol_change = float(pairs[0].get("priceChange", {}).get("h24", 0))
            if sol_change > 5:
                regime, risk = "BULL", "LOW"
            elif sol_change > -5:
                regime, risk = "NEUTRAL", "NORMAL"
            else:
                regime, risk = "BEAR", "HIGH"
            return {
                "sol_change_24h": sol_change,
                "btc_change_24h": round(sol_change * 0.7, 2),
                "regime": regime,
                "risk_level": risk,
            }
    except Exception as exc:
        logger.warning("Market regime fetch failed: %s", exc)
    return {"regime": "UNKNOWN", "risk_level": "UNKNOWN"}


# ── Sentiment ─────────────────────────────────────────────────────────────────

def get_ai_sentiment_for_token(token_address: str) -> dict[str, Any]:
    if not XAI_API_KEY:
        return {"analysis": "XAI_API_KEY not set.", "score": 0}
    symbol = token_address[:8] + "..."
    price = 0.0
    market_cap = 0
    try:
        data = _http_get(f"https://api.dexscreener.com/latest/dex/tokens/{token_address}")
        pairs = data.get("pairs") or []
        if pairs:
            p = pairs[0]
            symbol = p.get("baseToken", {}).get("symbol", symbol)
            price = float(p.get("priceUsd", 0) or 0)
            market_cap = int(p.get("marketCap", 0) or 0)

        # Grok sentiment
        prompt = (
            f"Analyze {symbol} ({token_address}) on Solana. "
            f"Price: ${price:.6f}, Market cap: ${market_cap:,}. "
            "Give a 2-sentence trading sentiment analysis. Be direct, no fluff."
        )
        resp = _http_post_json(
            "https://api.x.ai/v1/chat/completions",
            payload={
                "model": "grok-4-1-fast-non-reasoning",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 120,
            },
            headers={"Authorization": f"Bearer {XAI_API_KEY}"},
        )
        analysis = resp.get("choices", [{}])[0].get("message", {}).get("content", "No analysis.")
    except Exception as exc:
        logger.warning("Sentiment fetch failed: %s", exc)
        analysis = f"Analysis unavailable: {exc}"

    return {"symbol": symbol, "price": price, "market_cap": market_cap, "analysis": analysis}


# ── Trade Execution ───────────────────────────────────────────────────────────

def execute_buy(token_address: str, amount_sol: float, tp_percent: float,
                sl_percent: float, slippage_bps: int) -> dict[str, Any]:
    """Queue a spot buy intent. Routes through the perps intent queue."""
    import uuid
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    intent = {
        "type": "SpotBuy",
        "token_address": token_address,
        "amount_sol": amount_sol,
        "take_profit_pct": tp_percent,
        "stop_loss_pct": sl_percent,
        "slippage_bps": slippage_bps,
        "source": "web_ui_spot",
        "idempotency_key": str(uuid.uuid4()),
        "queued_at": time.time(),
    }
    try:
        with _INTENT_QUEUE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(intent) + "\n")
        return {"success": True, "message": f"Buy intent queued for {token_address}", "idempotency_key": intent["idempotency_key"]}
    except Exception as exc:
        logger.error("Buy queue failed: %s", exc)
        return {"success": False, "error": str(exc)}


def execute_sell(position_id: str, percentage: float) -> dict[str, Any]:
    """Queue a spot sell intent."""
    import uuid
    positions = _load_positions()
    position = next((p for p in positions if p.get("id") == position_id), None)
    if not position:
        return {"success": False, "error": f"Position {position_id} not found"}
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    intent = {
        "type": "SpotSell",
        "position_id": position_id,
        "token_address": position.get("token_mint", position.get("address", "")),
        "percentage": percentage,
        "source": "web_ui_spot",
        "idempotency_key": str(uuid.uuid4()),
        "queued_at": time.time(),
    }
    try:
        with _INTENT_QUEUE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(intent) + "\n")
        return {"success": True, "message": f"Sell intent queued ({percentage}%) for {position_id}", "idempotency_key": intent["idempotency_key"]}
    except Exception as exc:
        logger.error("Sell queue failed: %s", exc)
        return {"success": False, "error": str(exc)}
