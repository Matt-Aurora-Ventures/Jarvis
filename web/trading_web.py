"""Jarvis Trading Web Interface — Perps-first UI, no telegram dependency."""

import logging
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


def _safe_console_print(message: str) -> None:
    """Print startup/operator messages without crashing on legacy Windows consoles."""
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", "ignore").decode("ascii"))


def _adapter():
    """Lazy-import adapter so startup never fails on missing deps."""
    from web.api_adapter import (  # noqa: PLC0415
        get_portfolio, get_positions, get_market_regime,
        get_ai_sentiment_for_token, execute_buy, execute_sell,
    )
    return get_portfolio, get_positions, get_market_regime, get_ai_sentiment_for_token, execute_buy, execute_sell


# ── Blueprints ────────────────────────────────────────────────────────────────
try:
    from web.perps_api import perps_bp
    app.register_blueprint(perps_bp)
except ImportError:
    pass  # perps_api not built yet — graceful


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("trading.html")


@app.route("/api/status")
def api_status():
    try:
        get_portfolio, _, get_market_regime, *_ = _adapter()
        portfolio = get_portfolio()
        try:
            regime = get_market_regime()
        except Exception:
            regime = {}
        portfolio["market_regime"] = regime
        return jsonify(portfolio)
    except Exception as exc:
        logger.error("Status failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/positions")
def api_positions():
    try:
        _, get_positions, *_ = _adapter()
        return jsonify({"success": True, "positions": get_positions()})
    except Exception as exc:
        logger.error("Positions failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/token/sentiment", methods=["POST"])
def api_token_sentiment():
    token_address = (request.get_json() or {}).get("token_address", "").strip()
    if not token_address:
        return jsonify({"success": False, "error": "token_address required"}), 400
    try:
        _, _, _, get_ai_sentiment_for_token, _, _ = _adapter()
        return jsonify({"success": True, "sentiment": get_ai_sentiment_for_token(token_address)})
    except Exception as exc:
        logger.error("Sentiment failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/trade/buy", methods=["POST"])
def api_trade_buy():
    data = request.get_json() or {}
    token_address = data.get("token_address", "").strip()
    try:
        amount_sol = float(data.get("amount_sol", 0))
        tp_percent = float(data.get("tp_percent", 0))
        sl_percent = float(data.get("sl_percent", 0))
        slippage_bps = int(data.get("slippage_bps", 100))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "amount_sol, tp_percent, sl_percent, slippage_bps must be numeric"}), 400
    if not token_address:
        return jsonify({"success": False, "error": "token_address required"}), 400
    if amount_sol <= 0 or tp_percent <= 0 or sl_percent <= 0:
        return jsonify({"success": False, "error": "amount_sol, tp_percent, sl_percent must be > 0"}), 400
    try:
        _, _, _, _, execute_buy, _ = _adapter()
        return jsonify(execute_buy(token_address, amount_sol, tp_percent, sl_percent, slippage_bps))
    except Exception as exc:
        logger.error("Buy failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/trade/sell", methods=["POST"])
def api_trade_sell():
    data = request.get_json() or {}
    position_id = data.get("position_id", "").strip()
    try:
        percentage = float(data.get("percentage", 100))
    except (ValueError, TypeError):
        percentage = 100.0
    if not position_id:
        return jsonify({"success": False, "error": "position_id required"}), 400
    try:
        _, _, _, _, _, execute_sell = _adapter()
        return jsonify(execute_sell(position_id, percentage))
    except Exception as exc:
        logger.error("Sell failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/market/regime")
def api_market_regime():
    try:
        _, _, get_market_regime, *_ = _adapter()
        return jsonify({"success": True, "regime": get_market_regime()})
    except Exception as exc:
        logger.error("Regime failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    (ROOT / "logs").mkdir(exist_ok=True)
    _safe_console_print("  [WARNING] Prototype surface: web/trading_web.py is non-canonical.")
    _safe_console_print("  [WARNING] Canonical production UI is jarvis-sniper (http://127.0.0.1:3001).")
    _safe_console_print("  Jarvis Trading UI -> http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)

