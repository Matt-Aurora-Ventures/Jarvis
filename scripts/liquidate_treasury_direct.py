#!/usr/bin/env python3
"""
Liquidate entire treasury to SOL - Direct engine access.
Closes all open positions bypassing auth checks.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.trading.engine import TradingEngine
from telegram import Bot
from telegram.constants import ParseMode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def liquidate_treasury():
    """Close all positions using direct engine access."""

    logger.info("🔴 Starting treasury liquidation (direct engine access)...")

    try:
        # Initialize trading engine directly
        from core.solana.client import SolanaClient
        from core.security.key_manager import KeyManager

        key_mgr = KeyManager()
        wallet_keypair = key_mgr.get_treasury_keypair()

        solana_client = SolanaClient()

        engine = TradingEngine(
            wallet_keypair=wallet_keypair,
            solana_client=solana_client,
            max_positions=50,
            admin_user_ids=[]  # Empty since we're bypassing auth
        )

        # Get all open positions
        positions = engine.get_open_positions()

        if not positions:
            logger.info("No open positions to close")
            message = """
🔴 *TREASURY LIQUIDATION COMPLETE*
━━━━━━━━━━━━━━━━━━━━━

*Result:* No positions to close
*Status:* ✅ Already 100% SOL

━━━━━━━━━━━━━━━━━━━━━
"""
            await send_telegram_notification(message)
            return

        logger.info(f"Found {len(positions)} open positions to close")

        # Track results
        closed_count = 0
        failed_count = 0
        total_pnl = 0.0
        results = []

        # Close each position directly
        for position in positions:
            logger.info(f"Closing position: {position.token_symbol} (ID: {position.id[:8]}...)")

            try:
                # Get PnL before closing
                pnl = position.unrealized_pnl_usd

                # Close position using internal method (bypass auth)
                result = await engine._force_close_position(
                    position_id=position.id,
                    reason="System liquidation to SOL"
                )

                if result.get("success", False):
                    closed_count += 1
                    total_pnl += pnl
                    results.append(f"✅ {position.token_symbol}: {pnl:+.2f} USD")
                    logger.info(f"✅ Closed {position.token_symbol}: {pnl:+.2f} USD")
                else:
                    failed_count += 1
                    error = result.get("error", "Unknown error")
                    results.append(f"❌ {position.token_symbol}: {error}")
                    logger.error(f"❌ Failed to close {position.token_symbol}: {error}")

            except Exception as e:
                failed_count += 1
                results.append(f"❌ {position.token_symbol}: {str(e)}")
                logger.error(f"Error closing {position.token_symbol}: {e}", exc_info=True)

        # Prepare summary message
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        pnl_sign = "+" if total_pnl >= 0 else ""

        result_lines = "\n".join(results[:15])  # Limit to 15
        if len(results) > 15:
            result_lines += f"\n_...and {len(results) - 15} more positions_"

        message = f"""
🔴 *TREASURY LIQUIDATION COMPLETE*
━━━━━━━━━━━━━━━━━━━━━

*Total Positions:* {len(positions)}
*Successfully Closed:* {closed_count} ✅
*Failed:* {failed_count} ❌

{pnl_emoji} *Total P&L:* {pnl_sign}${abs(total_pnl):.2f}

*Results:*
{result_lines}

━━━━━━━━━━━━━━━━━━━━━
*Treasury Status:* 100% SOL
"""

        logger.info(f"Liquidation complete: {closed_count} closed, {failed_count} failed")
        await send_telegram_notification(message)

    except Exception as e:
        logger.error(f"Fatal error during liquidation: {e}", exc_info=True)

        error_message = f"""
🔴 *TREASURY LIQUIDATION ERROR*
━━━━━━━━━━━━━━━━━━━━━

*Error:* {str(e)}

Please check logs for details.
"""
        await send_telegram_notification(error_message)
        raise


async def send_telegram_notification(message: str):
    """Send notification to Telegram group."""

    try:
        # Get credentials from environment
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_BROADCAST_CHAT_ID") or os.getenv("TELEGRAM_BUY_BOT_CHAT_ID")

        if not bot_token:
            logger.error("TELEGRAM_BOT_TOKEN not found in environment")
            return

        if not chat_id:
            logger.error("Chat ID not found in environment - using fallback")
            # Use a fallback chat ID if needed - you can get this from any message in the group
            return

        # Send message
        bot = Bot(token=bot_token)
        await bot.send_message(
            chat_id=int(chat_id),
            text=message,
            parse_mode=ParseMode.MARKDOWN
        )

        logger.info("✅ Telegram notification sent")

    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(liquidate_treasury())
