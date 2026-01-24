"""
Observation Collector - US-003 AI Learning System

Logs every user action and outcome for AI learning.

What Gets Logged:
- Every buy/sell action with entry/exit prices
- User decisions (bought vs skipped)
- Grok recommendations vs actual outcomes
- TP/SL triggers and PnL results
- Token performance after user actions

Storage: ~/.lifeos/trading/demo_observations.jsonl (append-only)

Architecture:
- JSONL format (one JSON object per line)
- Append-only for reliability
- Event-driven logging (called from trade execution points)
- learning_compressor.py processes these into insights hourly

Event Types:
- buy_executed: User bought a token
- sell_executed: User sold a token
- tp_hit: Take-profit triggered
- sl_hit: Stop-loss triggered
- pick_shown: Grok showed a pick to user
- pick_ignored: User saw pick but didn't buy
- token_outcome: Final outcome tracked
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import traceback

logger = logging.getLogger(__name__)

# Observations file
OBSERVATIONS_FILE = Path.home() / ".lifeos" / "trading" / "demo_observations.jsonl"


# =============================================================================
# Observation Logger
# =============================================================================

def log_observation(
    event_type: str,
    data: Dict[str, Any],
    user_id: Optional[int] = None
):
    """
    Log an observation event.

    Args:
        event_type: Type of event (buy_executed, sell_executed, etc.)
        data: Event data (token, price, amount, etc.)
        user_id: Telegram user ID (optional)
    """
    try:
        # Ensure directory exists
        OBSERVATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Build observation entry
        observation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "data": data,
        }

        # Append to JSONL file
        with open(OBSERVATIONS_FILE, 'a') as f:
            f.write(json.dumps(observation) + '\n')

        logger.debug(f"Logged observation: {event_type}")

    except Exception as e:
        logger.error(f"Failed to log observation: {e}")
        logger.error(traceback.format_exc())


# =============================================================================
# Specific Event Loggers
# =============================================================================

def log_buy_executed(
    user_id: int,
    token_symbol: str,
    token_address: str,
    amount_sol: float,
    entry_price: float,
    tp_percent: Optional[float] = None,
    sl_percent: Optional[float] = None,
    source: str = "manual",  # manual, grok_pick, ai_auto
    grok_grade: Optional[str] = None,
    grok_reasoning: Optional[str] = None
):
    """
    Log a buy execution.

    Args:
        user_id: Telegram user ID
        token_symbol: Token symbol (e.g., "PONKE")
        token_address: Token mint address
        amount_sol: Amount in SOL
        entry_price: Entry price in USD
        tp_percent: Take-profit percentage (if set)
        sl_percent: Stop-loss percentage (if set)
        source: Where buy came from (manual, grok_pick, ai_auto)
        grok_grade: Grok's grade (if from Grok pick)
        grok_reasoning: Grok's reasoning (if from Grok pick)
    """
    data = {
        "token_symbol": token_symbol,
        "token_address": token_address,
        "amount_sol": amount_sol,
        "entry_price": entry_price,
        "tp_percent": tp_percent,
        "sl_percent": sl_percent,
        "source": source,
        "grok_grade": grok_grade,
        "grok_reasoning": grok_reasoning,
    }

    log_observation("buy_executed", data, user_id)


def log_sell_executed(
    user_id: int,
    token_symbol: str,
    token_address: str,
    amount_tokens: float,
    entry_price: float,
    exit_price: float,
    pnl_usd: float,
    pnl_pct: float,
    exit_reason: str,  # tp_hit, sl_hit, manual, trailing_stop_hit
    hold_duration_minutes: Optional[int] = None
):
    """
    Log a sell execution.

    Args:
        user_id: Telegram user ID
        token_symbol: Token symbol
        token_address: Token mint address
        amount_tokens: Amount sold
        entry_price: Entry price
        exit_price: Exit price
        pnl_usd: PnL in USD
        pnl_pct: PnL percentage
        exit_reason: Why sold (tp_hit, sl_hit, manual, etc.)
        hold_duration_minutes: How long held
    """
    data = {
        "token_symbol": token_symbol,
        "token_address": token_address,
        "amount_tokens": amount_tokens,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl_usd": pnl_usd,
        "pnl_pct": pnl_pct,
        "exit_reason": exit_reason,
        "hold_duration_minutes": hold_duration_minutes,
        "success": pnl_usd > 0,  # Did we make money?
    }

    log_observation("sell_executed", data, user_id)


def log_grok_pick_shown(
    user_id: int,
    token_symbol: str,
    token_address: str,
    grade: str,
    sentiment_label: str,
    reasoning: str,
    current_price: float
):
    """
    Log when a Grok pick is shown to user.

    This helps track: Did user buy what Grok recommended?

    Args:
        user_id: Telegram user ID
        token_symbol: Token symbol
        token_address: Token mint address
        grade: Grok grade (A+, A, B+, etc.)
        sentiment_label: BULLISH, NEUTRAL, etc.
        reasoning: Grok's reasoning
        current_price: Price when shown
    """
    data = {
        "token_symbol": token_symbol,
        "token_address": token_address,
        "grade": grade,
        "sentiment_label": sentiment_label,
        "reasoning": reasoning,
        "current_price": current_price,
    }

    log_observation("grok_pick_shown", data, user_id)


def log_pick_ignored(
    user_id: int,
    token_symbol: str,
    token_address: str,
    grade: str,
    reason: Optional[str] = None
):
    """
    Log when user saw a pick but didn't buy.

    Args:
        user_id: Telegram user ID
        token_symbol: Token symbol
        token_address: Token mint address
        grade: Grok grade
        reason: Why ignored (optional, e.g., "too risky", "no funds")
    """
    data = {
        "token_symbol": token_symbol,
        "token_address": token_address,
        "grade": grade,
        "reason": reason,
    }

    log_observation("pick_ignored", data, user_id)


def log_token_outcome(
    token_symbol: str,
    token_address: str,
    shown_at_price: float,
    current_price: float,
    hours_elapsed: int,
    grok_grade: Optional[str] = None,
    user_bought: bool = False,
    user_pnl_pct: Optional[float] = None
):
    """
    Log final outcome for a token that was shown.

    This helps AI learn: Was Grok right? Should user have bought?

    Args:
        token_symbol: Token symbol
        token_address: Token mint address
        shown_at_price: Price when shown to user
        current_price: Current price
        hours_elapsed: Hours since shown
        grok_grade: Grok's original grade
        user_bought: Did user buy?
        user_pnl_pct: User's PnL if they bought
    """
    price_change_pct = ((current_price - shown_at_price) / shown_at_price) * 100

    data = {
        "token_symbol": token_symbol,
        "token_address": token_address,
        "shown_at_price": shown_at_price,
        "current_price": current_price,
        "price_change_pct": price_change_pct,
        "hours_elapsed": hours_elapsed,
        "grok_grade": grok_grade,
        "user_bought": user_bought,
        "user_pnl_pct": user_pnl_pct,
        "outcome": "good_call" if price_change_pct > 10 else "bad_call" if price_change_pct < -10 else "neutral",
    }

    log_observation("token_outcome", data, user_id=None)


# =============================================================================
# Observation Reader (for learning_compressor.py)
# =============================================================================

def load_observations(
    since_timestamp: Optional[str] = None,
    event_types: Optional[list] = None
) -> list:
    """
    Load observations from file.

    Args:
        since_timestamp: Only load observations after this timestamp
        event_types: Only load these event types (e.g., ["buy_executed", "sell_executed"])

    Returns:
        List of observation dicts
    """
    if not OBSERVATIONS_FILE.exists():
        return []

    try:
        observations = []

        with open(OBSERVATIONS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    obs = json.loads(line)

                    # Filter by timestamp
                    if since_timestamp and obs.get("timestamp", "") < since_timestamp:
                        continue

                    # Filter by event type
                    if event_types and obs.get("event_type") not in event_types:
                        continue

                    observations.append(obs)

                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in observations file: {e}")

        return observations

    except Exception as e:
        logger.error(f"Failed to load observations: {e}")
        return []


def get_observation_stats() -> Dict[str, Any]:
    """
    Get statistics about logged observations.

    Returns:
        {
            "total_count": 150,
            "by_type": {"buy_executed": 50, "sell_executed": 48, ...},
            "oldest": "2026-01-24T10:00:00Z",
            "newest": "2026-01-24T15:00:00Z",
        }
    """
    observations = load_observations()

    if not observations:
        return {
            "total_count": 0,
            "by_type": {},
            "oldest": None,
            "newest": None,
        }

    # Count by type
    by_type = {}
    for obs in observations:
        event_type = obs.get("event_type", "unknown")
        by_type[event_type] = by_type.get(event_type, 0) + 1

    # Get timestamps
    timestamps = [obs.get("timestamp") for obs in observations if obs.get("timestamp")]
    timestamps.sort()

    return {
        "total_count": len(observations),
        "by_type": by_type,
        "oldest": timestamps[0] if timestamps else None,
        "newest": timestamps[-1] if timestamps else None,
    }


# =============================================================================
# Integration Points (call from demo.py)
# =============================================================================

def on_buy_executed(**kwargs):
    """
    Call this from demo.py after executing a buy.

    Example:
        from tg_bot.services.observation_collector import on_buy_executed
        on_buy_executed(
            user_id=update.effective_user.id,
            token_symbol=symbol,
            token_address=address,
            amount_sol=0.5,
            entry_price=0.00042,
            tp_percent=50.0,
            sl_percent=20.0,
            source="grok_pick",
            grok_grade="A",
            grok_reasoning="Strong buy/sell ratio...",
        )
    """
    log_buy_executed(**kwargs)


def on_sell_executed(**kwargs):
    """
    Call this from demo.py or order_monitor.py after executing a sell.

    Example:
        from tg_bot.services.observation_collector import on_sell_executed
        on_sell_executed(
            user_id=user_id,
            token_symbol=symbol,
            token_address=address,
            amount_tokens=1000,
            entry_price=0.00042,
            exit_price=0.00063,
            pnl_usd=21.0,
            pnl_pct=50.0,
            exit_reason="tp_hit",
            hold_duration_minutes=120,
        )
    """
    log_sell_executed(**kwargs)


def on_grok_pick_shown(**kwargs):
    """
    Call this from demo_sentiment.py when showing Grok picks.

    Example:
        from tg_bot.services.observation_collector import on_grok_pick_shown
        on_grok_pick_shown(
            user_id=update.effective_user.id,
            token_symbol="PONKE",
            token_address="...",
            grade="A",
            sentiment_label="BULLISH",
            reasoning="Strong momentum...",
            current_price=0.00042,
        )
    """
    log_grok_pick_shown(**kwargs)


# =============================================================================
# Manual Testing
# =============================================================================

if __name__ == "__main__":
    # Test observation logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("Testing observation collector...\n")

    # Test buy
    log_buy_executed(
        user_id=123456,
        token_symbol="PONKE",
        token_address="test_address_123",
        amount_sol=0.5,
        entry_price=0.00042,
        tp_percent=50.0,
        sl_percent=20.0,
        source="grok_pick",
        grok_grade="A",
        grok_reasoning="Strong buy/sell ratio and momentum",
    )

    # Test sell
    log_sell_executed(
        user_id=123456,
        token_symbol="PONKE",
        token_address="test_address_123",
        amount_tokens=1190.48,
        entry_price=0.00042,
        exit_price=0.00063,
        pnl_usd=25.0,
        pnl_pct=50.0,
        exit_reason="tp_hit",
        hold_duration_minutes=120,
    )

    # Get stats
    stats = get_observation_stats()
    print(f"\nObservation Stats:")
    print(json.dumps(stats, indent=2))

    print(f"\nObservations file: {OBSERVATIONS_FILE}")
