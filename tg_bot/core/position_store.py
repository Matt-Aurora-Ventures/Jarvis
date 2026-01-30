"""
Bulletproof Position Store - Redis-backed with execution locks

Features:
- Positions persist across bot restarts
- Execution locks prevent double-sells
- Atomic operations for consistency
- Compatible with existing demo_orders.py
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import redis

logger = logging.getLogger(__name__)

# Redis connection
_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    """Get or create Redis connection."""
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
    return _redis_client


# =============================================================================
# Position CRUD
# =============================================================================

def _position_key(user_id: int) -> str:
    return f"jarvis:positions:{user_id}"


def _trailing_stop_key(user_id: int) -> str:
    return f"jarvis:trailing_stops:{user_id}"


def _execution_lock_key(position_id: str) -> str:
    return f"jarvis:exec_lock:{position_id}"


def get_positions(user_id: int) -> List[Dict[str, Any]]:
    """Get all positions for a user."""
    try:
        r = _get_redis()
        data = r.get(_position_key(user_id))
        if data:
            return json.loads(data)
        return []
    except Exception as e:
        logger.error(f"Redis get_positions error: {e}")
        return []


def save_positions(user_id: int, positions: List[Dict[str, Any]]) -> bool:
    """Save positions for a user."""
    try:
        r = _get_redis()
        r.set(_position_key(user_id), json.dumps(positions))
        return True
    except Exception as e:
        logger.error(f"Redis save_positions error: {e}")
        return False


def add_position(user_id: int, position: Dict[str, Any]) -> bool:
    """Add a single position."""
    positions = get_positions(user_id)
    positions.append(position)
    return save_positions(user_id, positions)


def update_position(user_id: int, position_id: str, updates: Dict[str, Any]) -> bool:
    """Update a specific position."""
    positions = get_positions(user_id)
    for pos in positions:
        if pos.get("id") == position_id:
            pos.update(updates)
            break
    return save_positions(user_id, positions)


def remove_position(user_id: int, position_id: str) -> bool:
    """Remove a position."""
    positions = get_positions(user_id)
    positions = [p for p in positions if p.get("id") != position_id]
    return save_positions(user_id, positions)


# =============================================================================
# Trailing Stops
# =============================================================================

def get_trailing_stops(user_id: int) -> List[Dict[str, Any]]:
    """Get all trailing stops for a user."""
    try:
        r = _get_redis()
        data = r.get(_trailing_stop_key(user_id))
        if data:
            return json.loads(data)
        return []
    except Exception as e:
        logger.error(f"Redis get_trailing_stops error: {e}")
        return []


def save_trailing_stops(user_id: int, stops: List[Dict[str, Any]]) -> bool:
    """Save trailing stops for a user."""
    try:
        r = _get_redis()
        r.set(_trailing_stop_key(user_id), json.dumps(stops))
        return True
    except Exception as e:
        logger.error(f"Redis save_trailing_stops error: {e}")
        return False


# =============================================================================
# Execution Locks (prevent double-sells)
# =============================================================================

def acquire_execution_lock(position_id: str, source: str = "primary", ttl_seconds: int = 60) -> bool:
    """
    Try to acquire an execution lock for a position.
    
    Returns True if lock acquired, False if already locked.
    Uses Redis SET NX for atomic operation.
    """
    try:
        r = _get_redis()
        lock_data = json.dumps({
            "source": source,
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        })
        # NX = only set if not exists, EX = expire after ttl_seconds
        result = r.set(_execution_lock_key(position_id), lock_data, nx=True, ex=ttl_seconds)
        return result is True
    except Exception as e:
        logger.error(f"Redis acquire_lock error: {e}")
        return False


def release_execution_lock(position_id: str) -> bool:
    """Release an execution lock."""
    try:
        r = _get_redis()
        r.delete(_execution_lock_key(position_id))
        return True
    except Exception as e:
        logger.error(f"Redis release_lock error: {e}")
        return False


def is_locked(position_id: str) -> bool:
    """Check if a position is locked for execution."""
    try:
        r = _get_redis()
        return r.exists(_execution_lock_key(position_id)) > 0
    except Exception as e:
        logger.error(f"Redis is_locked error: {e}")
        return False


# =============================================================================
# All Users (for background monitor)
# =============================================================================

def get_all_user_ids_with_positions() -> List[int]:
    """Get all user IDs that have positions stored."""
    try:
        r = _get_redis()
        keys = r.keys("jarvis:positions:*")
        user_ids = []
        for key in keys:
            try:
                user_id = int(key.split(":")[-1])
                user_ids.append(user_id)
            except ValueError:
                continue
        return user_ids
    except Exception as e:
        logger.error(f"Redis get_all_users error: {e}")
        return []


# =============================================================================
# Monitor Heartbeat
# =============================================================================

def _heartbeat_key(monitor_name: str) -> str:
    return f"jarvis:monitor_heartbeat:{monitor_name}"


def update_monitor_heartbeat(monitor_name: str = "primary") -> bool:
    """Update the heartbeat for a monitor."""
    try:
        r = _get_redis()
        data = json.dumps({
            "last_check": datetime.now(timezone.utc).isoformat(),
            "timestamp": time.time(),
        })
        r.set(_heartbeat_key(monitor_name), data, ex=300)  # 5 min TTL
        return True
    except Exception as e:
        logger.error(f"Redis heartbeat error: {e}")
        return False


def get_monitor_status(monitor_name: str = "primary") -> Optional[Dict[str, Any]]:
    """Get the last heartbeat for a monitor."""
    try:
        r = _get_redis()
        data = r.get(_heartbeat_key(monitor_name))
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.error(f"Redis get_status error: {e}")
        return None


def is_monitor_alive(monitor_name: str = "primary", max_age_seconds: int = 120) -> bool:
    """Check if a monitor is alive (heartbeat within max_age)."""
    status = get_monitor_status(monitor_name)
    if not status:
        return False
    last_ts = status.get("timestamp", 0)
    return (time.time() - last_ts) < max_age_seconds


# =============================================================================
# Sync helpers (bridge between memory and Redis)
# =============================================================================

def sync_from_memory(user_id: int, positions: List[Dict], trailing_stops: List[Dict]) -> bool:
    """Sync positions from memory (PTB user_data) to Redis."""
    try:
        save_positions(user_id, positions)
        save_trailing_stops(user_id, trailing_stops)
        return True
    except Exception as e:
        logger.error(f"Sync to Redis failed: {e}")
        return False


def sync_to_memory(user_id: int) -> tuple:
    """Get positions and trailing stops from Redis (for restoring to memory)."""
    return get_positions(user_id), get_trailing_stops(user_id)
