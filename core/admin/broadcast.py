"""
Admin Broadcast Functionality.

Provides the ability to send admin messages to all bots or specific bots.
Includes confirmation requirement for safety.

Usage:
    from core.admin.broadcast import broadcast, broadcast_to_all

    # Send to specific bots (with confirmation)
    result = await broadcast(
        message="System maintenance in 10 minutes",
        bots=["telegram_bot", "treasury_bot"],
        confirmed=True
    )

    # Send to all running bots
    result = await broadcast_to_all(
        message="Emergency shutdown",
        confirmed=True
    )
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BroadcastRequiresConfirmation(Exception):
    """Raised when broadcast requires confirmation."""

    def __init__(self, message: str, bots: List[str]):
        self.message = message
        self.bots = bots
        super().__init__(f"Broadcast requires confirmation for {len(bots)} bots")


def _get_supervisor():
    """Get the bot supervisor if available."""
    try:
        from bots.supervisor import BotSupervisor
        return None  # Supervisor doesn't expose global instance yet
    except ImportError:
        return None


def _get_running_bots() -> List[str]:
    """
    Get list of currently running bots.

    Returns:
        List of bot names that are currently running
    """
    supervisor = _get_supervisor()

    if supervisor:
        status = supervisor.get_status()
        return [
            name for name, state in status.items()
            if state.get("status") == "running"
        ]

    # Fallback: return known bot names (assume running)
    return []


async def broadcast(
    message: str,
    bots: List[str],
    confirmed: bool = False
) -> Dict[str, Any]:
    """
    Broadcast a message to specified bots.

    Args:
        message: The message to broadcast
        bots: List of bot names to send to
        confirmed: Whether the broadcast has been confirmed

    Returns:
        Dict with broadcast results

    Note:
        If confirmed=False, returns a dict requesting confirmation
        instead of actually sending.
    """
    if not message:
        return {
            "success": False,
            "error": "Message cannot be empty",
        }

    if not bots:
        return {
            "success": False,
            "error": "No bots specified",
            "sent": 0,
        }

    # Require confirmation for broadcasts
    if not confirmed:
        return {
            "requires_confirmation": True,
            "pending_confirmation": True,
            "message": message,
            "bots": bots,
            "bot_count": len(bots),
            "prompt": f"Confirm broadcast to {len(bots)} bot(s)?",
        }

    # Execute broadcast
    results: Dict[str, Any] = {}
    success_count = 0
    fail_count = 0

    for bot_name in bots:
        try:
            result = await _send_to_bot(bot_name, message)
            results[bot_name] = result
            if result.get("success"):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            results[bot_name] = {"success": False, "error": str(e)}
            fail_count += 1

    return {
        "success": fail_count == 0,
        "sent": success_count,
        "failed": fail_count,
        "results": results,
    }


async def broadcast_to_all(
    message: str,
    confirmed: bool = False
) -> Dict[str, Any]:
    """
    Broadcast a message to all running bots.

    Args:
        message: The message to broadcast
        confirmed: Whether the broadcast has been confirmed

    Returns:
        Dict with broadcast results
    """
    running_bots = _get_running_bots()

    if not running_bots:
        # Fallback to known bots
        running_bots = [
            "telegram_bot",
            "treasury_bot",
        ]

    return await broadcast(message, running_bots, confirmed=confirmed)


async def _send_to_bot(bot_name: str, message: str) -> Dict[str, Any]:
    """
    Send a message to a specific bot.

    Currently supports Telegram bots by sending to admin chat.

    Args:
        bot_name: Name of the bot
        message: Message to send

    Returns:
        Dict with send result
    """
    # Get admin IDs for notification
    admin_ids_str = os.getenv("TELEGRAM_ADMIN_IDS", "")
    admin_ids = [
        int(x.strip())
        for x in admin_ids_str.split(",")
        if x.strip().isdigit()
    ]

    if not admin_ids:
        return {
            "success": False,
            "bot": bot_name,
            "error": "No admin IDs configured",
        }

    # Get the appropriate token for this bot
    if bot_name == "treasury_bot":
        token = os.getenv("TREASURY_BOT_TOKEN", "")
    elif bot_name == "public_trading_bot":
        token = os.getenv("PUBLIC_BOT_TELEGRAM_TOKEN", "")
    else:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")

    if not token:
        return {
            "success": False,
            "bot": bot_name,
            "error": f"No token configured for {bot_name}",
        }

    # Format message with bot identifier
    formatted_message = f"[{bot_name.upper()}] Admin Broadcast:\n\n{message}"

    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            # Send to first admin (primary)
            admin_id = admin_ids[0]
            url = f"https://api.telegram.org/bot{token}/sendMessage"

            async with session.post(
                url,
                json={
                    "chat_id": admin_id,
                    "text": formatted_message,
                    "parse_mode": "HTML",
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return {
                        "success": True,
                        "bot": bot_name,
                        "admin_id": admin_id,
                    }
                else:
                    error_text = await resp.text()
                    return {
                        "success": False,
                        "bot": bot_name,
                        "error": f"HTTP {resp.status}: {error_text[:100]}",
                    }

    except asyncio.TimeoutError:
        return {
            "success": False,
            "bot": bot_name,
            "error": "Request timeout",
        }
    except Exception as e:
        logger.error(f"Error sending to {bot_name}: {e}")
        return {
            "success": False,
            "bot": bot_name,
            "error": str(e),
        }


async def send_admin_notification(
    message: str,
    urgent: bool = False
) -> Dict[str, Any]:
    """
    Send a notification to all admin users.

    This is a convenience function that sends directly to admin
    Telegram IDs without going through bot channels.

    Args:
        message: The notification message
        urgent: If True, add urgent formatting

    Returns:
        Dict with send results
    """
    admin_ids_str = os.getenv("TELEGRAM_ADMIN_IDS", "")
    admin_ids = [
        int(x.strip())
        for x in admin_ids_str.split(",")
        if x.strip().isdigit()
    ]

    if not admin_ids:
        return {
            "success": False,
            "error": "No admin IDs configured",
        }

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return {
            "success": False,
            "error": "No Telegram token configured",
        }

    # Format message
    if urgent:
        formatted = f"!!! URGENT ALERT !!!\n\n{message}"
    else:
        formatted = f"Admin Notification:\n\n{message}"

    results = {}
    success_count = 0

    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            for admin_id in admin_ids:
                try:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"

                    async with session.post(
                        url,
                        json={
                            "chat_id": admin_id,
                            "text": formatted,
                            "parse_mode": "HTML",
                        },
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            results[admin_id] = "sent"
                            success_count += 1
                        else:
                            results[admin_id] = f"failed: HTTP {resp.status}"

                except Exception as e:
                    results[admin_id] = f"failed: {e}"

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

    return {
        "success": success_count > 0,
        "sent": success_count,
        "total": len(admin_ids),
        "results": results,
    }
