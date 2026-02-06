"""
Telegram User Authorization Middleware for ClawdBots

Provides role-based access control for bot command handlers.

File locations (on VPS):
- Allowlist: /root/clawdbots/allowlist.json
"""

import functools
import json
import logging
import os
from datetime import datetime
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

logger = logging.getLogger(__name__)

# Default allowlist file path (VPS)
DEFAULT_ALLOWLIST_FILE = "/root/clawdbots/allowlist.json"


# === New API (AuthorizationLevel-based) ===

class AuthorizationLevel(IntEnum):
    """Authorization levels, higher value = more privilege."""
    OBSERVER = 10
    OPERATOR = 20
    ADMIN = 30
    OWNER = 40


def load_allowlist(filepath: Optional[str] = None) -> Dict[str, AuthorizationLevel]:
    """
    Load authorized users from env var or JSON file.

    Env var format: CLAWDBOT_AUTHORIZED_USERS=123:OWNER,456:ADMIN
    JSON format: {"users": {"123": {"role": "founder"}}} or {"users": {"123": "OWNER"}}

    Returns empty dict if no allowlist found (development fallback = allow all).
    """
    # Check env var first
    env_val = os.environ.get("CLAWDBOT_AUTHORIZED_USERS", "")
    if env_val.strip():
        result = {}
        for entry in env_val.split(","):
            entry = entry.strip()
            if ":" in entry:
                uid, level = entry.split(":", 1)
                try:
                    result[uid.strip()] = AuthorizationLevel[level.strip().upper()]
                except KeyError:
                    logger.warning(f"Unknown auth level: {level}")
        return result

    # Fall back to file
    filepath = filepath or DEFAULT_ALLOWLIST_FILE
    try:
        path = Path(filepath)
        if path.exists():
            data = json.loads(path.read_text())
            users = data.get("users", {})
            result = {}
            for uid, val in users.items():
                try:
                    # Support both {"123": "OWNER"} and {"123": {"role": "founder"}}
                    if isinstance(val, str):
                        result[str(uid)] = AuthorizationLevel[val.upper()]
                    elif isinstance(val, dict):
                        role_str = val.get("role", "").upper()
                        # Map legacy Role names to AuthorizationLevel
                        mapped = _ROLE_TO_LEVEL.get(role_str)
                        if mapped:
                            result[str(uid)] = mapped
                        else:
                            result[str(uid)] = AuthorizationLevel[role_str]
                except KeyError:
                    logger.warning(f"Unknown auth level for user {uid}: {val}")
            return result
    except Exception as e:
        logger.warning(f"Error loading allowlist from {filepath}: {e}")

    # No file found = empty (development mode)
    return {}


def check_authorization(
    user_id: Union[int, str],
    required_level: AuthorizationLevel,
    allowlist: Dict[str, AuthorizationLevel],
) -> bool:
    """
    Check if a user has the required authorization level.

    If allowlist is empty, allows all (development fallback).
    """
    if not allowlist:
        return True  # Development mode - no restrictions

    uid = str(user_id)
    user_level = allowlist.get(uid)
    if user_level is None:
        return False
    return user_level >= required_level


def require_auth(
    level: AuthorizationLevel,
    allowlist: Optional[Dict[str, AuthorizationLevel]] = None,
    deny_message: str = "Unauthorized. You do not have permission for this command.",
):
    """
    Decorator for bot handlers that requires authorization.

    Usage:
        @require_auth(AuthorizationLevel.ADMIN)
        async def admin_handler(message):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(message: Any, *args, **kwargs):
            al = allowlist if allowlist is not None else _get_global_allowlist()
            user_id = message.from_user.id
            if not check_authorization(user_id, level, al):
                username = getattr(message.from_user, "username", "unknown")
                logger.warning(
                    f"Authorization denied: user {user_id} ({username}) "
                    f"requires {level.name}, command: {getattr(message, 'text', '')[:50]}"
                )
                return None
            return await func(message, *args, **kwargs)
        return wrapper
    return decorator


# Global allowlist cache
_global_allowlist: Optional[Dict[str, AuthorizationLevel]] = None


def _get_global_allowlist() -> Dict[str, AuthorizationLevel]:
    """Get or load the global allowlist."""
    global _global_allowlist
    if _global_allowlist is None:
        _global_allowlist = load_allowlist()
    return _global_allowlist


# === Legacy API (Role-based, backward compatibility) ===

class Role(Enum):
    FOUNDER = 'founder'
    ADMIN = 'admin'
    OPERATOR = 'operator'
    VIEWER = 'viewer'


# Map legacy Role values to AuthorizationLevel
_ROLE_TO_LEVEL = {
    'FOUNDER': AuthorizationLevel.OWNER,
    'ADMIN': AuthorizationLevel.ADMIN,
    'OPERATOR': AuthorizationLevel.OPERATOR,
    'VIEWER': AuthorizationLevel.OBSERVER,
}

ROLE_PERMISSIONS = {
    Role.FOUNDER: ['*'],
    Role.ADMIN: [
        'view', 'trade', 'deploy', 'configure', 'handoff',
        'approve', 'brief', 'status', 'logs', 'restart'
    ],
    Role.OPERATOR: [
        'view', 'trade', 'status', 'brief', 'handoff'
    ],
    Role.VIEWER: [
        'view', 'status', 'brief'
    ]
}


def _load_allowlist_legacy() -> dict:
    """Load raw allowlist JSON (legacy format)."""
    if Path(DEFAULT_ALLOWLIST_FILE).exists():
        try:
            return json.loads(Path(DEFAULT_ALLOWLIST_FILE).read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {'users': {}, 'ip_allowlist': []}


def save_allowlist(data: dict):
    Path(DEFAULT_ALLOWLIST_FILE).write_text(json.dumps(data, indent=2))


def initialize_allowlist(founder_telegram_id: str, founder_name: str = 'Founder'):
    data = _load_allowlist_legacy()
    data['users'][str(founder_telegram_id)] = {
        'name': founder_name,
        'role': Role.FOUNDER.value,
        'added_at': datetime.now().isoformat()
    }
    # Load IP allowlist from env or use defaults
    ip_env = os.environ.get("CLAWDBOT_IP_ALLOWLIST", "")
    if ip_env:
        data['ip_allowlist'] = [ip.strip() for ip in ip_env.split(",") if ip.strip()]
    else:
        data['ip_allowlist'] = ['100.102.41.120', '100.72.121.115', '76.13.106.100']
    save_allowlist(data)
    return data


def check_permission(telegram_user_id: str, action: str) -> bool:
    data = _load_allowlist_legacy()
    user_id = str(telegram_user_id)

    if user_id not in data.get('users', {}):
        return False

    user = data['users'][user_id]
    role = Role(user['role'])
    permissions = ROLE_PERMISSIONS.get(role, [])

    if '*' in permissions:
        return True

    return action in permissions


def get_user_role(telegram_user_id: str) -> Optional[Role]:
    data = _load_allowlist_legacy()
    user_id = str(telegram_user_id)
    if user_id in data.get('users', {}):
        return Role(data['users'][user_id]['role'])
    return None


def add_user(telegram_user_id: str, name: str, role: Role):
    data = _load_allowlist_legacy()
    data['users'][str(telegram_user_id)] = {
        'name': name,
        'role': role.value,
        'added_at': datetime.now().isoformat()
    }
    save_allowlist(data)


def remove_user(telegram_user_id: str):
    data = _load_allowlist_legacy()
    data['users'].pop(str(telegram_user_id), None)
    save_allowlist(data)
