"""
Jarvis Buy Bot Tracker - Telegram bot for token buy notifications.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from bots.buy_tracker.config import BuyBotConfig, load_config
from bots.buy_tracker.monitor import BuyTransaction, TransactionMonitor
from bots.buy_tracker.ape_buttons import (
    parse_ape_callback,
    create_trade_setup,
    execute_ape_trade,
    RISK_PROFILE_CONFIG,
    get_risk_config,
)

logger = logging.getLogger(__name__)

# FAQ content for expandable section
FAQ_CONTENT = """
━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <b>WHAT IS JARVIS?</b>
━━━━━━━━━━━━━━━━━━━━━━━━

your iron man AI. one brain across every device.
trades while you sleep. manages your life. open source forever.

━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>WHAT IS $KR8TIV?</b>
━━━━━━━━━━━━━━━━━━━━━━━━

the token powering the jarvis ecosystem.
launched on bags.fm. solana native.

━━━━━━━━━━━━━━━━━━━━━━━━
🔗 <b>LINKS</b>
━━━━━━━━━━━━━━━━━━━━━━━━

🌐 jarvislife.io
🐦 x.com/Jarvis_lifeos
💻 github.com/Matt-Aurora-Ventures/Jarvis
📱 @kr8tivai

━━━━━━━━━━━━━━━━━━━━━━━━
❓ <b>FAQ</b>
━━━━━━━━━━━━━━━━━━━━━━━━

<b>Q:</b> is this financial advice?
<b>A:</b> no. im literally a bot. NFA.

<b>Q:</b> who built this?
<b>A:</b> kr8tiv AI (@kr8tivai)

<b>Q:</b> is jarvis open source?
<b>A:</b> yes. github link above. fork it.

━━━━━━━━━━━━━━━━━━━━━━━━
"""


def get_faq_keyboard(show_faq: bool = False) -> InlineKeyboardMarkup:
    """Get inline keyboard with FAQ button."""
    if show_faq:
        button = InlineKeyboardButton("🔼 Hide Info", callback_data="hide_faq")
    else:
        button = InlineKeyboardButton("ℹ️ What is Jarvis?", callback_data="show_faq")
    return InlineKeyboardMarkup([[button]])


class JarvisBuyBot:
    """
    Telegram bot that posts token buy notifications with video.

    Features:
    - Real-time buy tracking via Helius
    - MP4 video with each notification
    - Customizable minimum buy threshold
    - Position percentage display
    """

    def __init__(self, config: Optional[BuyBotConfig] = None):
        self.config = config or load_config()
        self.bot: Optional[Bot] = None
        self.app: Optional[Application] = None
        self.monitor: Optional[TransactionMonitor] = None
        self._running = False
        # Store original messages for FAQ expand/collapse {message_id: original_text}
        self._message_cache: dict[int, str] = {}
        # Counter for emoji credit attribution
        self._buy_counter = 0

    async def start(self):
        """Start the buy bot."""
        logger.info("Starting Jarvis Buy Bot Tracker...")

        # Validate config
        if not self.config.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")
        if not self.config.chat_id:
            raise ValueError("TELEGRAM_BUY_BOT_CHAT_ID not set")
        if not self.config.token_address:
            raise ValueError("BUY_BOT_TOKEN_ADDRESS not set")
        if not self.config.helius_api_key:
            raise ValueError("HELIUS_API_KEY not set")

        # Initialize Telegram Application for callback handling
        self.app = Application.builder().token(self.config.bot_token).build()
        self.bot = self.app.bot

        # Add callback handlers
        # Ape button handler (pattern: starts with "ape:")
        self.app.add_handler(CallbackQueryHandler(self._handle_ape_callback, pattern="^ape:"))
        # Confirm/cancel trade handler
        self.app.add_handler(CallbackQueryHandler(self._handle_confirm_callback, pattern="^confirm:"))
        self.app.add_handler(CallbackQueryHandler(self._handle_confirm_callback, pattern="^cancel_trade$"))
        # Info button handler (pattern: starts with "info:")
        self.app.add_handler(CallbackQueryHandler(self._handle_info_callback, pattern="^info:"))
        # FAQ handler for all other callbacks
        self.app.add_handler(CallbackQueryHandler(self._handle_faq_callback))

        # Test bot connection
        try:
            me = await self.bot.get_me()
            logger.info(f"Bot connected: @{me.username}")
        except Exception as e:
            raise RuntimeError(f"Failed to connect bot: {e}")

        # Start Application for callback handling FIRST (before any messages)
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(allowed_updates=["callback_query"])
        logger.info("Callback handler ready")

        # Send startup message
        await self._send_startup_message()

        # Initialize transaction monitor
        self.monitor = TransactionMonitor(
            token_address=self.config.token_address,
            helius_api_key=self.config.helius_api_key,
            min_buy_usd=self.config.min_buy_usd,
            on_buy=self._on_buy_detected,
        )

        self._running = True
        await self.monitor.start()

        logger.info(f"Buy bot running - tracking {self.config.token_symbol}")

        # Keep running
        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        """Stop the buy bot."""
        self._running = False
        if self.monitor:
            await self.monitor.stop()
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        logger.info("Buy bot stopped")

    async def _send_startup_message(self):
        """Send startup notification to the chat."""
        message = (
            f"🤖 <b>{self.config.bot_name}</b>\n\n"
            f"✅ Bot started successfully!\n\n"
            f"📊 Tracking: <b>${self.config.token_symbol}</b>\n"
            f"💰 Min buy: <b>${self.config.min_buy_usd:.2f}</b>\n\n"
            f"<i>Watching for buys...</i>"
        )

        try:
            await self.bot.send_message(
                chat_id=self.config.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error(f"Failed to send startup message: {e}")

    async def _on_buy_detected(self, buy: BuyTransaction):
        """Handle detected buy transaction."""
        logger.info(f"Processing buy: ${buy.usd_amount:.2f} from {buy.buyer_short}")

        # Format the message
        message = self._format_buy_message(buy)
        keyboard = get_faq_keyboard(show_faq=False)

        try:
            # Check if we have a video to send
            video_path = Path(self.config.video_path) if self.config.video_path else None

            if video_path and video_path.exists():
                # Send video with caption and FAQ button
                with open(video_path, 'rb') as video_file:
                    sent_msg = await self.bot.send_video(
                        chat_id=self.config.chat_id,
                        video=video_file,
                        caption=message,
                        parse_mode=ParseMode.HTML,
                        supports_streaming=True,
                        reply_markup=keyboard,
                    )
            else:
                # Send text message with FAQ button
                sent_msg = await self.bot.send_message(
                    chat_id=self.config.chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard,
                )

            # Cache original message for expand/collapse
            self._message_cache[sent_msg.message_id] = message
            # Limit cache size to last 100 messages
            if len(self._message_cache) > 100:
                oldest = list(self._message_cache.keys())[0]
                del self._message_cache[oldest]

            logger.info(f"Buy notification sent: ${buy.usd_amount:.2f}")

        except Exception as e:
            logger.error(f"Failed to send buy notification: {e}")

    async def _handle_faq_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle FAQ expand/collapse button clicks."""
        query = update.callback_query
        await query.answer()  # Acknowledge the callback

        message_id = query.message.message_id
        chat_id = query.message.chat_id
        action = query.data  # "show_faq" or "hide_faq"

        try:
            if action == "show_faq":
                # Expand: show FAQ content
                original_text = self._message_cache.get(message_id)
                if original_text:
                    expanded_text = original_text + FAQ_CONTENT
                    keyboard = get_faq_keyboard(show_faq=True)

                    # Check if it's a video message (caption) or text message
                    if query.message.video or query.message.animation:
                        await query.message.edit_caption(
                            caption=expanded_text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=keyboard,
                        )
                    else:
                        await query.message.edit_text(
                            text=expanded_text,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=keyboard,
                        )
                else:
                    # No cached message, just send FAQ as new message
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=FAQ_CONTENT,
                        parse_mode=ParseMode.HTML,
                    )

            elif action == "hide_faq":
                # Collapse: restore original message
                original_text = self._message_cache.get(message_id)
                if original_text:
                    keyboard = get_faq_keyboard(show_faq=False)

                    if query.message.video or query.message.animation:
                        await query.message.edit_caption(
                            caption=original_text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=keyboard,
                        )
                    else:
                        await query.message.edit_text(
                            text=original_text,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=keyboard,
                        )

        except Exception as e:
            logger.error(f"Failed to handle FAQ callback: {e}")

    async def _handle_ape_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle ape button clicks for treasury trading with TP/SL."""
        query = update.callback_query
        callback_data = query.data
        chat_id = query.message.chat_id

        logger.info(f"APE CALLBACK RECEIVED: {callback_data}")

        # Try to acknowledge callback (may fail if old)
        try:
            await query.answer("🦍 Processing...", show_alert=False)
        except Exception:
            logger.debug("Callback acknowledgment failed (may be stale)")

        try:
            # Parse the callback
            parsed = parse_ape_callback(callback_data)
            logger.info(f"Parsed callback: {parsed}")

            if not parsed:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Invalid button data",
                    parse_mode=ParseMode.HTML,
                )
                return

            # Get risk profile config
            profile_config = get_risk_config(parsed["asset_type"], parsed["risk_profile"])

            # Send confirmation request with CONFIRM/CANCEL buttons
            confirm_msg = (
                f"🦍 <b>CONFIRM APE TRADE?</b>\n\n"
                f"🪙 Asset: <code>{parsed['symbol']}</code>\n"
                f"📊 Type: {parsed['asset_type'].upper()}\n"
                f"💰 Allocation: {parsed['allocation_percent']}% of treasury\n"
                f"📈 Profile: {profile_config['emoji']} {profile_config['label']}\n\n"
                f"🎯 Take Profit: +{profile_config['tp_pct']}%\n"
                f"🛑 Stop Loss: -{profile_config['sl_pct']}%\n"
                f"⚖️ Risk/Reward: {profile_config['tp_pct']/profile_config['sl_pct']:.1f}:1\n\n"
                f"<i>Click CONFIRM to execute or CANCEL to abort</i>"
            )

            # Create confirm/cancel buttons
            confirm_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ CONFIRM", callback_data=f"confirm:{callback_data}"[:64]),
                    InlineKeyboardButton("❌ CANCEL", callback_data="cancel_trade"),
                ]
            ])

            await self.bot.send_message(
                chat_id=chat_id,
                text=confirm_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=confirm_keyboard,
            )

        except Exception as e:
            logger.error(f"Ape callback error: {e}", exc_info=True)
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Error processing trade: {str(e)[:100]}",
                    parse_mode=ParseMode.HTML,
                )
            except:
                pass

    async def _handle_confirm_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle trade confirmation button clicks."""
        query = update.callback_query
        callback_data = query.data
        chat_id = query.message.chat_id

        logger.info(f"CONFIRM CALLBACK: {callback_data}")

        # Try to acknowledge
        try:
            await query.answer("🚀 Executing...", show_alert=False)
        except Exception:
            pass

        if callback_data == "cancel_trade":
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ <b>Trade cancelled.</b>",
                parse_mode=ParseMode.HTML,
            )
            return

        # Extract original ape callback from confirm:ape:...
        if callback_data.startswith("confirm:"):
            original_callback = callback_data[8:]  # Remove "confirm:"
            parsed = parse_ape_callback(original_callback)

            if not parsed:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Invalid trade data",
                    parse_mode=ParseMode.HTML,
                )
                return

            profile_config = get_risk_config(parsed["asset_type"], parsed["risk_profile"])

            # INSTANT FEEDBACK - Send "executing" message immediately
            executing_msg = await self.bot.send_message(
                chat_id=chat_id,
                text=f"⏳ <b>EXECUTING TRADE...</b>\n\n🪙 {parsed['symbol']}\n💰 {parsed['allocation_percent']}% allocation\n\n<i>Fetching live price from DexScreener...</i>",
                parse_mode=ParseMode.HTML,
            )

            # Execute the trade
            try:
                result = await execute_ape_trade(
                    callback_data=original_callback,
                    entry_price=0.0,
                    treasury_balance_sol=0.1,
                )

                if result.success:
                    setup = result.trade_setup
                    result_msg = (
                        f"✅ <b>TRADE EXECUTED!</b>\n\n"
                        f"🪙 {setup.symbol}\n"
                        f"💰 Amount: {setup.amount_sol:.4f} SOL\n"
                        f"📍 Entry: ${setup.entry_price:.8f}\n"
                        f"🎯 TP: ${setup.take_profit_price:.8f}\n"
                        f"🛑 SL: ${setup.stop_loss_price:.8f}\n\n"
                        f"<i>TX: {result.tx_signature[:20]}...</i>"
                    )
                else:
                    result_msg = (
                        f"⚠️ <b>TRADE SIMULATION</b>\n\n"
                        f"Symbol: {parsed['symbol']}\n"
                        f"Allocation: {parsed['allocation_percent']}%\n"
                        f"Profile: {profile_config['label']}\n\n"
                        f"<i>Status: {result.error}</i>\n\n"
                        f"<i>Live execution coming soon!</i>"
                    )

                await self.bot.send_message(
                    chat_id=chat_id,
                    text=result_msg,
                    parse_mode=ParseMode.HTML,
                )

            except Exception as trade_error:
                logger.error(f"Trade execution error: {trade_error}")
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Trade in simulation mode\n\nSymbol: {parsed['symbol']}\nAllocation: {parsed['allocation_percent']}%\n\n<i>Live trading coming soon!</i>",
                    parse_mode=ParseMode.HTML,
                )

    async def _handle_info_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle info button clicks."""
        query = update.callback_query
        callback_data = query.data

        try:
            # Parse info callback (format: info:{profile} or info:{type}:{symbol}:{contract})
            parts = callback_data.split(":")

            if len(parts) == 2:
                # Risk profile info
                profile = parts[1]
                profile_info = {
                    "safe": "🛡️ SAFE Profile\n\n+15% Take Profit\n-5% Stop Loss\n3:1 Risk/Reward\n\nBest for: Stable coins, blue chips",
                    "med": "⚖️ MEDIUM Profile\n\n+30% Take Profit\n-10% Stop Loss\n3:1 Risk/Reward\n\nBest for: Mid-cap tokens",
                    "degen": "🔥 DEGEN Profile\n\n+50% Take Profit\n-15% Stop Loss\n3.3:1 Risk/Reward\n\nBest for: High-risk plays",
                }
                info_text = profile_info.get(profile, "Unknown profile")
                await query.answer(info_text, show_alert=True)
            else:
                # Asset info
                asset_type = parts[1] if len(parts) > 1 else "t"
                symbol = parts[2] if len(parts) > 2 else "?"
                info_text = f"ℹ️ {symbol}\nType: {'Token' if asset_type == 't' else 'Stock'}"
                await query.answer(info_text, show_alert=True)

        except Exception as e:
            logger.error(f"Info callback error: {e}")
            await query.answer("Info unavailable", show_alert=True)

    def _format_buy_message(self, buy: BuyTransaction) -> str:
        """Format buy notification message like BobbyBuyBot style."""
        # Increment buy counter
        self._buy_counter += 1

        # Green circles based on buy size
        circles = self._get_buy_circles(buy.usd_amount)

        # Format numbers
        token_amount_str = self._format_number(buy.token_amount)
        usd_str = f"${buy.usd_amount:,.2f}"
        sol_str = f"{buy.sol_amount:.4f}"
        price_str = f"${buy.price_per_token:.10f}".rstrip('0').rstrip('.')
        mcap_str = self._format_mcap(buy.market_cap)
        position_str = f"{buy.buyer_position_pct:.2f}%" if buy.buyer_position_pct > 0 else "< 0.01%"

        message = (
            f"<b>{self.config.bot_name}</b>\n"
            f"<b>{self.config.token_name} Buy!</b>\n"
            f"{circles}\n"
            f"<b>Spent:</b> {sol_str} SOL ({usd_str})\n"
            f"<b>Got:</b> {token_amount_str} {self.config.token_symbol}\n"
            f"<b>Buyer Position:</b> 🔋{position_str}\n"
            f"<b>Price:</b> {price_str}\n"
            f"<b>MCap:</b> {mcap_str}\n\n"
            f"<a href=\"{buy.tx_url}\">TX</a> | <a href=\"{buy.dex_url}\">Dex</a>\n"
        )

        # Add @FrankkkNL credit every 10th buy
        if self._buy_counter % 10 == 0:
            message += f"\n<i>🎨 Custom emojis by @FrankkkNL</i>\n"

        return message

    def _get_buy_circles(self, usd_amount: float) -> str:
        """Get KR8TIV custom emoji circles based on buy amount."""
        # Custom KR8TIV robot emoji (ID from t.me/addemoji/KR8TIV)
        KR8TIV_ROBOT_ID = "5990286304724655084"
        emoji = f'<tg-emoji emoji-id="{KR8TIV_ROBOT_ID}">🤖</tg-emoji>'

        if usd_amount >= 10000:
            return emoji * 10
        elif usd_amount >= 5000:
            return emoji * 8
        elif usd_amount >= 1000:
            return emoji * 6
        elif usd_amount >= 500:
            return emoji * 5
        elif usd_amount >= 100:
            return emoji * 4
        elif usd_amount >= 50:
            return emoji * 3
        elif usd_amount >= 20:
            return emoji * 2
        else:
            return emoji

    def _format_number(self, num: float) -> str:
        """Format large numbers with commas and abbreviations."""
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:,.2f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:,.2f}M"
        elif num >= 1_000:
            return f"{num:,.0f}"
        else:
            return f"{num:,.2f}"

    def _format_mcap(self, mcap: float) -> str:
        """Format market cap."""
        if mcap >= 1_000_000:
            return f"${mcap / 1_000_000:,.2f}M"
        elif mcap >= 1_000:
            return f"${mcap / 1_000:,.2f}K"
        else:
            return f"${mcap:,.2f}"


async def run_buy_bot():
    """Main entry point to run the buy bot."""
    # Load environment from tg_bot/.env if it exists
    env_path = Path(__file__).resolve().parents[2] / "tg_bot" / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    bot = JarvisBuyBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        await bot.stop()
    except Exception as e:
        logger.error(f"Bot error: {e}")
        await bot.stop()
        raise


if __name__ == "__main__":
    asyncio.run(run_buy_bot())
