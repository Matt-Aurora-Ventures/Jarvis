#!/usr/bin/env python3
"""
Claude Code ↔ Telegram Relay Monitor.

Monitors the relay inbox for messages from Telegram and processes them
using the Claude Code console. Responses are sent back via the relay.

This script runs alongside Claude Code and enables controlling it from Telegram.
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from core.telegram_relay import get_relay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("claude_relay_monitor")


def process_claude_request(user_message: str, user_id: int, username: str) -> str:
    """
    Process a request from Telegram using Claude Code logic.

    This is where you integrate with your existing Jarvis/Claude Code infrastructure.
    For now, this is a placeholder that demonstrates the concept.

    Args:
        user_message: The message from Telegram user
        user_id: Telegram user ID
        username: Telegram username

    Returns:
        Claude Code's response
    """
    # Example: Check for specific commands/patterns
    message_lower = user_message.lower()

    if "treasury balance" in message_lower or "balance" in message_lower:
        # Call treasury balance checker
        try:
            from bots.treasury.run_treasury import TreasuryTrader
            # This would need proper async handling
            return "Treasury balance check initiated. See treasury bot for details."
        except Exception as e:
            return f"Error checking treasury balance: {str(e)}"

    elif "positions" in message_lower:
        return "Position check requested. Use /dashboard in Telegram for full details."

    elif "sentiment" in message_lower or "market" in message_lower:
        # Call sentiment analyzer
        try:
            from core.dexter_sentiment import get_latest_sentiment_summary
            sentiment = get_latest_sentiment_summary()
            return f"Latest market sentiment:\n\n{sentiment}"
        except Exception as e:
            return f"Error retrieving sentiment: {str(e)}"

    else:
        # Generic AI response
        return (
            f"📨 Message received from @{username} (ID: {user_id})\n\n"
            f"Request: {user_message}\n\n"
            "I'm processing your request. For now, this is a direct relay.\n"
            "Future updates will integrate full Claude Code command processing."
        )


async def monitor_loop():
    """Main monitoring loop that checks for Telegram messages."""
    relay = get_relay()

    logger.info("🚀 Claude Relay Monitor started")
    logger.info(f"Inbox: {relay.inbox}")
    logger.info(f"Outbox: {relay.outbox}")

    check_interval = 5  # Check every 5 seconds

    while True:
        try:
            # Check for pending messages from Telegram
            messages = relay.get_pending_messages()

            for message in messages:
                logger.info(
                    f"📬 New message from @{message.username} (ID: {message.user_id}): "
                    f"{message.content[:50]}..."
                )

                # Process the message
                try:
                    response = process_claude_request(
                        user_message=message.content,
                        user_id=message.user_id,
                        username=message.username or "Unknown"
                    )

                    # Send response back to Telegram
                    relay.send_response_to_telegram(
                        content=response,
                        request_id=message.id,
                        user_id=message.user_id,
                        username=message.username
                    )

                    # Mark as processed
                    relay.mark_processed(message.id)

                    logger.info(f"✅ Response sent for message {message.id}")

                except Exception as e:
                    logger.exception(f"Error processing message {message.id}: {e}")

                    # Send error response
                    try:
                        relay.send_response_to_telegram(
                            content=f"Error processing your request: {str(e)}",
                            request_id=message.id,
                            user_id=message.user_id,
                            username=message.username
                        )
                        relay.mark_processed(message.id)
                    except Exception:
                        pass

            # Cleanup old messages (every hour)
            current_time = time.time()
            if not hasattr(monitor_loop, '_last_cleanup'):
                monitor_loop._last_cleanup = current_time

            if current_time - monitor_loop._last_cleanup > 3600:
                relay.cleanup_old_messages(days=7)
                monitor_loop._last_cleanup = current_time
                logger.info("🧹 Cleaned up old messages")

            # Sleep before next check
            await asyncio.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("⏹️ Monitor stopped by user")
            break
        except Exception as e:
            logger.exception(f"Error in monitor loop: {e}")
            await asyncio.sleep(check_interval)


def main():
    """Entry point for Claude Relay Monitor."""
    print("=" * 60)
    print("  CLAUDE CODE ↔ TELEGRAM RELAY MONITOR")
    print("  Control Claude Code from Telegram via /vibe")
    print("=" * 60)
    print()

    # Run the monitor
    try:
        asyncio.run(monitor_loop())
    except KeyboardInterrupt:
        print("\n👋 Monitor stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
