"""Trading position watchdog daemon with persistent state.

Enhanced to support:
- LUT Micro-Alpha exit intent enforcement
- Jupiter Perps position monitoring
- Redundant exit enforcement (works alongside lut_daemon.py)
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core import config, birdeye, dexscreener, geckoterminal
from core.risk_manager import get_risk_manager

# Import exit intents for LUT/Perps enforcement
try:
    from core import exit_intents
    HAS_EXIT_INTENTS = True
except ImportError:
    HAS_EXIT_INTENTS = False
    exit_intents = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path.home() / ".lifeos" / "trading"
DEFAULT_LOG_PATH = DEFAULT_DATA_DIR / "daemon.log"
DEFAULT_SYMBOL_MAP = DEFAULT_DATA_DIR / "symbol_map.json"
BASE58_ALPHABET = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
ERROR_LOG_THROTTLE_SECONDS = 300
_ERROR_LOG_TIMES: Dict[Tuple[str, str, str], float] = {}


def _resolve_path(value: Optional[str], fallback: Path) -> Path:
    if not value:
        return fallback
    expanded = os.path.expanduser(value)
    path = Path(expanded)
    if not path.is_absolute():
        return (ROOT / path).resolve()
    return path


def _load_config() -> Dict[str, Any]:
    cfg = config.load_config()
    daemon_cfg = cfg.get("trading_daemon", {})
    poll_seconds = int(daemon_cfg.get("poll_seconds", 60))
    price_sources = daemon_cfg.get("price_sources", ["birdeye", "geckoterminal", "dexscreener"])
    log_path = _resolve_path(daemon_cfg.get("log_path"), DEFAULT_LOG_PATH)
    symbol_map_path = _resolve_path(daemon_cfg.get("symbol_map_path"), DEFAULT_SYMBOL_MAP)
    reconcile_on_start = bool(daemon_cfg.get("reconcile_on_start", True))
    auto_create_intents = bool(daemon_cfg.get("auto_create_intents", False))
    json_logging = bool(daemon_cfg.get("json_logging", False))
    mirror_only = daemon_cfg.get("mirror_only_strategies", ["exit_intent_mirror"])
    if isinstance(mirror_only, str):
        mirror_only = [mirror_only]
    if not isinstance(mirror_only, list):
        mirror_only = ["exit_intent_mirror"]
    if os.getenv("LIFEOS_LOG_JSON", "").strip().lower() in {"1", "true", "yes", "on"}:
        json_logging = True
    return {
        "poll_seconds": max(poll_seconds, 5),
        "price_sources": price_sources,
        "log_path": log_path,
        "symbol_map_path": symbol_map_path,
        "reconcile_on_start": reconcile_on_start,
        "auto_create_intents": auto_create_intents,
        "json_logging": json_logging,
        "mirror_only_strategies": [str(item) for item in mirror_only if item],
    }


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _setup_logger(log_path: Path, *, json_logging: bool = False) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("lifeos.trading_daemon")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = _JsonFormatter() if json_logging else logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def _load_symbol_map(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        import json

        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def _looks_like_solana_address(value: str) -> bool:
    if not value:
        return False
    if not (32 <= len(value) <= 44):
        return False
    return all(char in BASE58_ALPHABET for char in value)


def _resolve_address(symbol: str, symbol_map: Dict[str, str]) -> Optional[str]:
    if _looks_like_solana_address(symbol):
        return symbol
    mapped = symbol_map.get(symbol)
    if mapped and _looks_like_solana_address(mapped):
        return mapped
    return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _should_log_error(intent_id: str, action: str, error: str, error_class: Optional[str]) -> bool:
    if error_class != "permanent":
        return True
    key = (intent_id, action, error)
    now = time.time()
    last = _ERROR_LOG_TIMES.get(key)
    if last and (now - last) < ERROR_LOG_THROTTLE_SECONDS:
        return False
    _ERROR_LOG_TIMES[key] = now
    return True


def _fetch_price_birdeye(address: str) -> Optional[float]:
    if not birdeye.has_api_key():
        return None
    payload = birdeye.fetch_token_price(address, cache_ttl_seconds=20)
    if not payload:
        return None
    value = payload.get("data", {}).get("value")
    return _to_float(value)


def _fetch_price_gecko(address: str) -> Optional[float]:
    payload = geckoterminal.fetch_token("solana", address, cache_ttl_seconds=20)
    if not payload:
        return None
    attrs = payload.get("data", {}).get("attributes", {}) or {}
    return _to_float(attrs.get("price_usd") or attrs.get("price_usd"))


def _fetch_price_dexscreener(address: str) -> Optional[float]:
    payload = dexscreener.fetch_token_pairs(address, cache_ttl_seconds=20)
    if not payload:
        return None
    pairs = payload.get("pairs", []) or []
    sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
    if not sol_pairs:
        return None

    def _score(pair: Dict[str, Any]) -> float:
        liquidity = _to_float((pair.get("liquidity") or {}).get("usd")) or 0.0
        volume = _to_float((pair.get("volume") or {}).get("h24")) or 0.0
        return liquidity + volume

    best = max(sol_pairs, key=_score)
    return _to_float(best.get("priceUsd") or best.get("priceNative"))


def _fetch_price(address: str, sources: Iterable[str]) -> Optional[float]:
    for source in sources:
        if source == "birdeye":
            price = _fetch_price_birdeye(address)
        elif source == "geckoterminal":
            price = _fetch_price_gecko(address)
        elif source == "dexscreener":
            price = _fetch_price_dexscreener(address)
        else:
            continue
        if price is not None:
            return price
    return None


def _check_lut_perps_intents(
    logger: logging.Logger,
    price_sources: List[str],
) -> List[Dict[str, Any]]:
    """
    Check and enforce LUT Micro-Alpha and Jupiter Perps exit intents.

    Returns list of actions taken.
    """
    if not HAS_EXIT_INTENTS or exit_intents is None:
        return []

    actions_taken = []

    try:
        intents = exit_intents.load_active_intents()

        for intent in intents:
            # Fetch current price
            if intent.position_type == "perps":
                # For perps, token_mint contains the asset symbol (SOL, BTC, ETH)
                from core import jupiter
                try:
                    price_data = jupiter.get_price([intent.token_mint])
                    if price_data and "data" in price_data:
                        asset_data = price_data["data"].get(intent.token_mint, {})
                        current_price = float(asset_data.get("price", 0))
                    else:
                        current_price = None
                except Exception:
                    current_price = None
            else:
                # For spot, token_mint is the Solana address
                current_price = _fetch_price(intent.token_mint, price_sources)

            if current_price is None:
                logger.debug(f"Could not fetch price for {intent.symbol}")
                intent.enforcement_failures += 1
                fallback_price = intent.last_check_price or intent.entry_price
                triggers = exit_intents.check_time_stop(intent, fallback_price)
                if not triggers:
                    exit_intents.update_intent(intent)
                    continue
            else:
                triggers = exit_intents.check_intent_triggers(
                    intent,
                    current_price,
                    sentiment_reversed=False,  # TODO: integrate xAI sentiment check
                )

            for action, params in triggers:
                # Execute the action
                result = exit_intents.execute_action(
                    intent,
                    action,
                    params,
                    paper_mode=intent.is_paper,
                )

                record_price = params.get("price", current_price)
                error = result.error if not result.success else None
                error_hint = None
                error_class = None
                if error:
                    try:
                        from core import solana_execution

                        error_hint = solana_execution.describe_simulation_error(error)
                        error_class = solana_execution.classify_simulation_error(error)
                    except Exception:
                        error_hint = None
                action_record = {
                    "intent_id": intent.id,
                    "symbol": intent.symbol,
                    "action": action.value,
                    "price": record_price,
                    "pnl_usd": result.pnl_usd,
                    "pnl_pct": result.pnl_pct,
                    "success": result.success,
                    "error": error,
                    "error_hint": error_hint,
                    "error_class": error_class,
                }
                actions_taken.append(action_record)

                logger.info(
                    "LUT/Perps: %s %s at %.6f PnL=%.2f (%.2f%%)",
                    action.value,
                    intent.symbol,
                    record_price or 0.0,
                    result.pnl_usd,
                    result.pnl_pct,
                )
                if error and _should_log_error(intent.id, action.value, error, error_class):
                    logger.warning(
                        "LUT/Perps action failed: %s %s error=%s hint=%s class=%s",
                        action.value,
                        intent.symbol,
                        error,
                        error_hint,
                        error_class,
                    )

            # Update intent with tracking
            exit_intents.update_intent(intent)

    except Exception as e:
        logger.error(f"Error checking LUT/Perps intents: {e}")

    return actions_taken


def run() -> None:
    cfg = _load_config()
    logger = _setup_logger(cfg["log_path"], json_logging=cfg["json_logging"])
    rm = get_risk_manager()
    symbol_map_path = cfg["symbol_map_path"]
    poll_seconds = cfg["poll_seconds"]
    price_sources = cfg["price_sources"]
    reconcile_on_start = cfg["reconcile_on_start"]
    auto_create_intents = cfg["auto_create_intents"]
    mirror_only_strategies = cfg["mirror_only_strategies"]

    logger.info("Trading daemon started. Poll=%ss sources=%s", poll_seconds, ",".join(price_sources))
    if mirror_only_strategies:
        logger.info("Mirror-only strategies: %s", ",".join(mirror_only_strategies))

    if reconcile_on_start:
        try:
            from core import position_reconciler

            report = position_reconciler.reconcile_positions(auto_create_intents=auto_create_intents)
            missing = report.get("missing_intents", [])
            if missing:
                logger.warning("Reconcile found %d holdings without intents.", len(missing))
            logger.info("Reconcile report written: %s", position_reconciler.RECONCILE_REPORT)
        except Exception as exc:
            logger.error("Reconcile failed: %s", str(exc)[:120])

    running = True

    def _handle_stop(_signum, _frame) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    last_open_count: Optional[int] = None
    while running:
        symbol_map = _load_symbol_map(symbol_map_path)
        open_trades = rm.get_open_trades()
        open_count = len(open_trades)
        if last_open_count != open_count:
            logger.info("Open positions: %d", open_count)
            last_open_count = open_count

        if not open_trades:
            time.sleep(poll_seconds)
            continue

        current_prices: Dict[str, float] = {}
        for trade in open_trades:
            symbol = trade.get("symbol")
            if not symbol:
                continue
            address = _resolve_address(symbol, symbol_map)
            if not address:
                logger.warning("Missing address for symbol %s (add to %s)", symbol, symbol_map_path)
                continue
            price = _fetch_price(address, price_sources)
            if price is None:
                logger.warning("Price not found for %s", symbol)
                continue
            current_prices[symbol] = price

        if current_prices:
            closed = rm.check_stops(current_prices, ignore_strategies=mirror_only_strategies)
            for trade in closed:
                logger.info(
                    "Closed %s (%s) at %.6f status=%s pnl=%.4f",
                    trade.symbol,
                    trade.id,
                    trade.exit_price or 0.0,
                    trade.status,
                    trade.pnl,
                )

        # Check LUT Micro-Alpha and Jupiter Perps exit intents
        lut_actions = _check_lut_perps_intents(logger, price_sources)
        if lut_actions:
            logger.info("LUT/Perps: Executed %d actions this cycle", len(lut_actions))

        time.sleep(poll_seconds)

    logger.info("Trading daemon stopped.")


if __name__ == "__main__":
    run()
