"""
Trading Logging Utilities

Provides structured logging helpers for trading operations.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

# Import structured logging for comprehensive JSON logs
try:
    from core.logging import get_structured_logger, JsonFormatter
    STRUCTURED_LOGGING_AVAILABLE = True
except ImportError:
    STRUCTURED_LOGGING_AVAILABLE = False

# Initialize structured logger if available, fallback to standard logger
if STRUCTURED_LOGGING_AVAILABLE:
    logger = get_structured_logger("jarvis.trading", service="trading_engine")
else:
    logger = logging.getLogger(__name__)


def log_trading_error(error: Exception, context: str, metadata: dict = None):
    """Log error with structured data and track in error rate system."""
    try:
        from core.monitoring.supervisor_health_bus import log_component_error
        log_component_error(
            component="treasury_trading",
            error=error,
            context={"operation": context, **(metadata or {})},
            severity="error"
        )
    except ImportError:
        logger.error(f"[{context}] {error}", exc_info=True)


def log_trading_event(event_type: str, message: str, data: dict = None):
    """Log trading event with structured data."""
    try:
        from core.monitoring.supervisor_health_bus import log_bot_event
        log_bot_event("treasury", event_type, message, data)
    except ImportError:
        logger.info(f"[{event_type}] {message}")


def log_position_change(
    action: str,
    position_id: str,
    symbol: str,
    details: dict = None
):
    """
    Log all position changes with consistent formatting.

    Actions: OPEN, CLOSE, UPDATE, RECONCILE, ERROR
    """
    details = details or {}
    timestamp = datetime.utcnow().isoformat()

    # Build log message
    log_data = {
        "timestamp": timestamp,
        "action": action,
        "position_id": position_id,
        "symbol": symbol,
        **details
    }

    # Log to standard logger with consistent prefix
    if action == "OPEN":
        logger.info(
            f"[POSITION:{action}] {position_id} {symbol} - "
            f"amount=${details.get('amount_usd', 0):.2f}, "
            f"entry=${details.get('entry_price', 0):.6f}, "
            f"TP=${details.get('tp_price', 0):.6f}, SL=${details.get('sl_price', 0):.6f}"
        )
    elif action == "CLOSE":
        logger.info(
            f"[POSITION:{action}] {position_id} {symbol} - "
            f"P&L=${details.get('pnl_usd', 0):+.2f} ({details.get('pnl_pct', 0):+.1f}%), "
            f"exit=${details.get('exit_price', 0):.6f}, "
            f"reason={details.get('reason', 'unknown')}"
        )
    elif action == "UPDATE":
        logger.debug(
            f"[POSITION:{action}] {position_id} {symbol} - "
            f"price=${details.get('current_price', 0):.6f}, "
            f"unrealized_pnl=${details.get('unrealized_pnl', 0):+.2f}"
        )
    elif action == "ERROR":
        logger.error(
            f"[POSITION:{action}] {position_id} {symbol} - "
            f"error={details.get('error', 'unknown')}"
        )
    else:
        logger.info(f"[POSITION:{action}] {position_id} {symbol} - {details}")

    # Also send to trading event system
    log_trading_event(f"POSITION_{action}", f"{symbol} position {action.lower()}", log_data)
