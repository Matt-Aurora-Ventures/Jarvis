"""Jarvis Trading Web Interface - Matches /demo UI functionality."""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for API access


# =============================================================================
# Helper Functions
# =============================================================================

def _get_demo_engine():
    """Get demo trading engine instance."""
    import asyncio
    from tg_bot.handlers.demo.demo_trading import _get_demo_engine as get_engine
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(get_engine())


def _serialize(value: Any) -> Any:
    """Serialize dataclass/complex objects for JSON."""
    from dataclasses import is_dataclass, asdict
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


# =============================================================================
# Routes
# =============================================================================

@app.route("/")
def index():
    """Main trading interface page."""
    return render_template("trading.html")


@app.route("/api/status", methods=["GET"])
def api_status():
    """Get trading system status (wallet, balance, positions)."""
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from tg_bot.handlers.demo.demo_trading import _get_demo_engine
        from tg_bot.handlers.demo.demo_sentiment import get_market_regime

        engine = loop.run_until_complete(_get_demo_engine())

        # Get wallet info
        treasury = engine.wallet.get_treasury()
        wallet_address = treasury.address if treasury else "Not configured"

        # Get balances
        sol_balance, usd_value = loop.run_until_complete(engine.get_portfolio_value())

        # Get positions
        loop.run_until_complete(engine.update_positions())
        positions = engine.get_open_positions()

        total_pnl = sum(p.unrealized_pnl for p in positions)

        # Get market regime
        try:
            market_regime = loop.run_until_complete(get_market_regime())
        except Exception:
            market_regime = {}

        return jsonify({
            "success": True,
            "wallet_address": wallet_address,
            "sol_balance": sol_balance,
            "usd_value": usd_value,
            "is_live": not engine.dry_run,
            "open_positions": len(positions),
            "total_pnl": total_pnl,
            "market_regime": market_regime,
        })
    except Exception as exc:
        logger.error(f"Failed to get status: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        loop.close()


@app.route("/api/positions", methods=["GET"])
def api_positions():
    """Get all open trading positions."""
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from tg_bot.handlers.demo.demo_trading import _get_demo_engine

        engine = loop.run_until_complete(_get_demo_engine())
        loop.run_until_complete(engine.update_positions())
        positions = engine.get_open_positions()

        position_data = [
            {
                "id": p.id,
                "symbol": p.token_symbol,
                "address": p.token_mint,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "amount": p.amount,
                "cost_basis_sol": p.cost_basis,
                "current_value_sol": p.current_value,
                "unrealized_pnl": p.unrealized_pnl,
                "unrealized_pnl_pct": p.unrealized_pnl_pct,
                "timestamp": p.timestamp.isoformat() if hasattr(p.timestamp, 'isoformat') else str(p.timestamp),
            }
            for p in positions
        ]

        return jsonify({
            "success": True,
            "positions": position_data,
        })
    except Exception as exc:
        logger.error(f"Failed to get positions: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        loop.close()


@app.route("/api/token/sentiment", methods=["POST"])
def api_token_sentiment():
    """Get AI sentiment analysis for a token."""
    import asyncio

    data = request.get_json() or {}
    token_address = data.get("token_address", "").strip()

    if not token_address:
        return jsonify({"success": False, "error": "token_address required"}), 400

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from tg_bot.handlers.demo.demo_sentiment import get_ai_sentiment_for_token

        sentiment = loop.run_until_complete(get_ai_sentiment_for_token(token_address))

        return jsonify({
            "success": True,
            "sentiment": sentiment,
        })
    except Exception as exc:
        logger.error(f"Failed to get sentiment: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        loop.close()


@app.route("/api/trade/buy", methods=["POST"])
def api_trade_buy():
    """Execute a buy order with TP/SL."""
    import asyncio

    data = request.get_json() or {}
    token_address = data.get("token_address", "").strip()
    amount_sol = float(data.get("amount_sol", 0))
    tp_percent = float(data.get("tp_percent", 0))
    sl_percent = float(data.get("sl_percent", 0))
    slippage_bps = data.get("slippage_bps", 100)  # 1% default

    if not token_address:
        return jsonify({"success": False, "error": "token_address required"}), 400
    if amount_sol <= 0:
        return jsonify({"success": False, "error": "amount_sol must be > 0"}), 400
    if tp_percent <= 0:
        return jsonify({"success": False, "error": "tp_percent must be > 0"}), 400
    if sl_percent <= 0:
        return jsonify({"success": False, "error": "sl_percent must be > 0"}), 400

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from tg_bot.handlers.demo.demo_trading import (
            _get_demo_engine,
            execute_buy_with_tpsl,
        )

        # Get wallet address
        engine = loop.run_until_complete(_get_demo_engine())
        treasury = engine.wallet.get_treasury()
        wallet_address = treasury.address if treasury else None

        if not wallet_address:
            return jsonify({"success": False, "error": "Wallet not configured"}), 500

        # Execute buy
        result = loop.run_until_complete(
            execute_buy_with_tpsl(
                token_address=token_address,
                amount_sol=amount_sol,
                wallet_address=wallet_address,
                tp_percent=tp_percent,
                sl_percent=sl_percent,
                slippage_bps=slippage_bps,
            )
        )

        return jsonify(result)
    except Exception as exc:
        logger.error(f"Buy failed: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        loop.close()


@app.route("/api/trade/sell", methods=["POST"])
def api_trade_sell():
    """Execute a sell order for a position."""
    import asyncio

    data = request.get_json() or {}
    position_id = data.get("position_id", "").strip()
    percentage = float(data.get("percentage", 100))  # Default sell all

    if not position_id:
        return jsonify({"success": False, "error": "position_id required"}), 400
    if percentage <= 0 or percentage > 100:
        return jsonify({"success": False, "error": "percentage must be 1-100"}), 400

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from tg_bot.handlers.demo.demo_trading import _get_demo_engine

        engine = loop.run_until_complete(_get_demo_engine())
        loop.run_until_complete(engine.update_positions())

        # Find position
        position = None
        for p in engine.get_open_positions():
            if p.id == position_id:
                position = p
                break

        if not position:
            return jsonify({"success": False, "error": f"Position {position_id} not found"}), 404

        # Execute sell
        treasury = engine.wallet.get_treasury()
        wallet_address = treasury.address if treasury else None

        if not wallet_address:
            return jsonify({"success": False, "error": "Wallet not configured"}), 500

        from tg_bot.handlers.demo.demo_trading import _execute_swap_with_fallback

        # Calculate amount to sell
        amount_to_sell = position.amount * (percentage / 100)

        result = loop.run_until_complete(
            _execute_swap_with_fallback(
                from_token=position.token_mint,
                to_token="So11111111111111111111111111111111111111112",  # SOL
                amount=amount_to_sell,
                wallet_address=wallet_address,
                slippage_bps=100,
            )
        )

        if result.get("success"):
            # Close position if 100% sold
            if percentage >= 100:
                loop.run_until_complete(engine.close_position(position_id))

        return jsonify(result)
    except Exception as exc:
        logger.error(f"Sell failed: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        loop.close()


@app.route("/api/market/regime", methods=["GET"])
def api_market_regime():
    """Get current market regime analysis."""
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from tg_bot.handlers.demo.demo_sentiment import get_market_regime

        regime = loop.run_until_complete(get_market_regime())

        return jsonify({
            "success": True,
            "regime": regime,
        })
    except Exception as exc:
        logger.error(f"Failed to get market regime: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        loop.close()


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    from core.logging_utils import configure_component_logger
    configure_component_logger("web.trading", prefix="TRADE_WEB", level=logging.INFO)

    templates_dir = ROOT / "web" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)

    print(" Jarvis Trading Web Interface starting on http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=True)
