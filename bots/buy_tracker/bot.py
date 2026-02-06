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
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from bots.buy_tracker.config import BuyBotConfig, load_config
from bots.buy_tracker.monitor import BuyTransaction, TransactionMonitor
from core.utils.instance_lock import acquire_instance_lock
from bots.buy_tracker.ape_buttons import (
    parse_ape_callback,
    create_trade_setup,
    execute_ape_trade,
    RISK_PROFILE_CONFIG,
    get_risk_config,
)
from core.logging.error_tracker import error_tracker

# Import self-correcting AI system
try:
    from core.self_correcting import (
        get_shared_memory,
        get_message_bus,
        get_ollama_router,
        LearningType,
        MessageType,
        MessagePriority,
        TaskType,
    )
    SELF_CORRECTING_AVAILABLE = True
except ImportError:
    SELF_CORRECTING_AVAILABLE = False
    get_shared_memory = None
    get_message_bus = None
    get_ollama_router = None

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

🌐 <a href="https://jarvislife.io">jarvislife.io</a>
🐦 <a href="https://x.com/Jarvis_lifeos">x.com/Jarvis_lifeos</a>
💻 <a href="https://github.com/Matt-Aurora-Ventures/Jarvis">github.com/Matt-Aurora-Ventures/Jarvis</a>
📱 <a href="https://t.me/kr8tivai">@kr8tivai</a>

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


def _parse_admin_ids(value: str) -> set[int]:
    ids = set()
    for item in value.split(","):
        item = item.strip()
        if item.isdigit():
            ids.add(int(item))
    return ids


def _get_admin_ids() -> set[int]:
    ids_str = os.environ.get("TREASURY_ADMIN_IDS") or os.environ.get("TELEGRAM_ADMIN_IDS", "")
    return _parse_admin_ids(ids_str) if ids_str else set()


def _is_admin(user_id: int) -> bool:
    admin_ids = _get_admin_ids()
    return user_id in admin_ids if admin_ids else False


class JarvisBuyBot:
    """
    Telegram bot that posts token buy notifications with video.

    Features:
    - Real-time buy tracking via Helius
    - MP4 video with each notification
    - Customizable minimum buy threshold
    - Position percentage display

    Guardrail (2026-01-31): In group chats, only respond when @mentioned AND sender is admin.
    """

    def __init__(self, config: Optional[BuyBotConfig] = None):
        self.config = config or load_config()
        self.bot: Optional[Bot] = None
        self.app: Optional[Application] = None
        self.monitor: Optional[TransactionMonitor] = None
        self._running = False
        self._polling_lock = None
        self._bot_username: str = ""
        # Store original messages for FAQ expand/collapse {message_id: original_text}
        self._message_cache: dict[int, str] = {}
        # Counter for emoji credit attribution
        self._buy_counter = 0
        # KR8TIV sticker file_id cache (fetched on first use)
        self._kr8tiv_sticker_id: Optional[str] = None

        # Initialize self-correcting AI system
        self.memory = None
        self.bus = None
        self.router = None
        if SELF_CORRECTING_AVAILABLE:
            try:
                self.memory = get_shared_memory()
                self.bus = get_message_bus()
                self.router = get_ollama_router()

                # Load past learnings about token buys
                past_learnings = self.memory.search_learnings(
                    component="buy_tracker",
                    learning_type=LearningType.SUCCESS_PATTERN,
                    min_confidence=0.6
                )
                logger.info(f"Loaded {len(past_learnings)} past buy patterns from memory")

            except Exception as e:
                logger.warning(f"Failed to initialize self-correcting AI: {e}")
                self.memory = None
                self.bus = None
                self.router = None

    async def start(self):
        """Start the buy bot."""
        logger.info("Starting Jarvis Buy Bot Tracker...")

        # Validate config
        missing = []
        if not self.config.bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.config.chat_id:
            missing.append("TELEGRAM_BUY_BOT_CHAT_ID")
        if not self.config.token_address:
            missing.append("BUY_BOT_TOKEN_ADDRESS")
        if not self.config.helius_api_key:
            missing.append("HELIUS_API_KEY")

        if missing:
            logger.error(
                "Jarvis Buy Bot disabled: missing configuration (%s)",
                ", ".join(missing),
            )
            return

        # Log non-sensitive config summary for diagnostics (no secrets)
        token_addr = self.config.token_address
        pair_addr = self.config.pair_address
        logger.info(
            "Buy bot config: token=%s pair=%s min_usd=%.2f extra_pairs=%d",
            f"{token_addr[:6]}...{token_addr[-4:]}" if token_addr else "unset",
            f"{pair_addr[:6]}...{pair_addr[-4:]}" if pair_addr else "unset",
            self.config.min_buy_usd,
            len(self.config.additional_pairs),
        )
        if token_addr and not pair_addr:
            logger.warning(
                "BUY_BOT_PAIR_ADDRESS not set/resolved; monitoring token address only (may miss swaps)."
            )

        # Initialize Telegram Application for callback handling
        self.app = Application.builder().token(self.config.bot_token).build()
        self.bot = self.app.bot

        # Add callback handlers
        # Ape button handler (pattern: starts with "ape:")
        self.app.add_handler(CallbackQueryHandler(self._handle_ape_callback, pattern="^ape:"))

        # Mention handler (admin-only): respond when Matt @mentions this bot in group
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_mentions)
        )
        # Confirm/cancel trade handler
        self.app.add_handler(CallbackQueryHandler(self._handle_confirm_callback, pattern="^confirm:"))
        self.app.add_handler(CallbackQueryHandler(self._handle_confirm_callback, pattern="^cancel_trade$"))
        # Info button handler (pattern: starts with "info:")
        self.app.add_handler(CallbackQueryHandler(self._handle_info_callback, pattern="^info:"))
        # Expand section handler (pattern: starts with "expand:")
        self.app.add_handler(CallbackQueryHandler(self._handle_expand_callback, pattern="^expand:"))
        # FAQ handler for all other callbacks
        self.app.add_handler(CallbackQueryHandler(self._handle_faq_callback))

        # Test bot connection
        try:
            me = await self.bot.get_me()
            self._bot_username = (me.username or "").lower()
            logger.info(f"Bot connected: @{me.username}")
        except Exception as e:
            raise RuntimeError(f"Failed to connect bot: {e}")

        # Start Application (polling optional)
        await self.app.initialize()
        await self.app.start()
        enable_polling = os.environ.get("BUY_BOT_ENABLE_POLLING", "auto").lower()
        main_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        should_poll = False
        if enable_polling in ("1", "true", "yes", "on"):
            should_poll = True
        elif enable_polling == "auto" and self.config.bot_token and self.config.bot_token != main_token:
            should_poll = True

        # Hard safety: never poll if using the same token as the main Telegram bot
        token_match = bool(self.config.bot_token and main_token and self.config.bot_token == main_token)
        if token_match and should_poll:
            logger.warning("Buy bot polling disabled: token matches main Telegram bot")
            should_poll = False

        logger.info(
            "Buy bot polling decision: mode=%s should_poll=%s token_match=%s",
            enable_polling,
            should_poll,
            token_match,
        )

        if self.app.updater and should_poll:
            self._polling_lock = acquire_instance_lock(
                self.config.bot_token,
                name="telegram_polling",
                max_wait_seconds=5,
            )
            if not self._polling_lock:
                logger.warning("Buy bot polling disabled: lock held for token")
            else:
                # Need message updates too so admin @mentions work in group
                await self.app.updater.start_polling(allowed_updates=["message", "callback_query"])
                logger.info("Buy bot started (polling enabled)")
        elif self.app.updater:
            logger.info("Buy bot started (polling disabled to avoid token conflicts)")
        else:
            logger.info("Buy bot started (no updater available; callbacks inactive)")

        # Send startup message
        await self._send_startup_message()

        # Initialize transaction monitor with additional LP pairs
        self.monitor = TransactionMonitor(
            token_address=self.config.token_address,
            helius_api_key=self.config.helius_api_key,
            min_buy_usd=self.config.min_buy_usd,
            on_buy=self._on_buy_detected,
            pair_address=self.config.pair_address,
            additional_pairs=self.config.additional_pairs,
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
        pair_info = ""
        if self.config.pair_address:
            pair_info = f"🔗 Main Pair: <code>{self.config.pair_address[:8]}...{self.config.pair_address[-4:]}</code>\n"

        # Show additional LP pairs count
        additional_pairs_info = ""
        if self.config.additional_pairs:
            count = len(self.config.additional_pairs)
            additional_pairs_info = f"📊 Tracking: {count} additional LP pairs\n"

        message = (
            f"🤖 <b>{self.config.bot_name}</b>\n\n"
            f"✅ Bot started successfully!\n\n"
            f"📊 Tracking: <b>${self.config.token_symbol}</b>\n"
            f"{pair_info}"
            f"{additional_pairs_info}"
            f"💰 Min buy: <b>${self.config.min_buy_usd:.2f}</b>\n\n"
            f"<i>Watching for buys on LP pairs...</i>"
        )

        # Optional validation + fallback routing:
        # If the buy bot is not a member of the target chat, Telegram returns
        # `BadRequest: Chat not found`. In that case, route a concise alert to
        # the admin chat (if configured) so the failure is visible.
        fallback_chat = (os.getenv("TELEGRAM_ADMIN_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        if fallback_chat and fallback_chat.lstrip("-").isdigit():
            fallback_chat = int(fallback_chat)
        validate_chat = os.getenv("BUY_BOT_VALIDATE_CHAT", "1").strip().lower() not in ("0", "false", "no", "off")

        try:
            if validate_chat:
                # Proactively verify access to the chat (will raise on "chat not found").
                await self.bot.get_chat(chat_id=self.config.chat_id)
            await self.bot.send_message(
                chat_id=self.config.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error(f"Failed to send startup message: {e}")
            if fallback_chat and fallback_chat != self.config.chat_id:
                try:
                    await self.bot.send_message(
                        chat_id=fallback_chat,
                        text=(
                            "⚠️ Buy bot startup notification failed.\n\n"
                            f"Target chat: `{self.config.chat_id}`\n"
                            f"Error: `{str(e)[:180]}`\n\n"
                            "Fix: add the buy bot to the target group/channel, or update `TELEGRAM_BUY_BOT_CHAT_ID`."
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True,
                    )
                except Exception as e2:
                    logger.error(f"Failed to send fallback startup alert: {e2}")

    async def _send_kr8tiv_sticker(self):
        """Send KR8TIV robot sticker as decoration before buy notification.

        Fetches sticker file_id from KR8TIV sticker set on first use and caches it.
        Fails gracefully - if sticker can't be sent, buy notification still goes through.
        """
        KR8TIV_STICKER_SET = "KR8TIV"  # t.me/addemoji/KR8TIV

        try:
            # Fetch sticker file_id on first use
            if not self._kr8tiv_sticker_id:
                try:
                    sticker_set = await self.bot.get_sticker_set(KR8TIV_STICKER_SET)
                    if sticker_set.stickers:
                        # Use the first sticker (the robot emoji)
                        self._kr8tiv_sticker_id = sticker_set.stickers[0].file_id
                        logger.info(f"Cached KR8TIV sticker file_id: {self._kr8tiv_sticker_id[:20]}...")
                    else:
                        logger.warning("KR8TIV sticker set is empty")
                        return
                except Exception as e:
                    logger.warning(f"Could not fetch KR8TIV sticker set: {e}")
                    return

            # Send the sticker
            await self.bot.send_sticker(
                chat_id=self.config.chat_id,
                sticker=self._kr8tiv_sticker_id,
            )
        except Exception as e:
            # Don't fail the whole notification if sticker fails
            logger.warning(f"Could not send KR8TIV sticker: {e}")

    async def _on_buy_detected(self, buy: BuyTransaction):
        """Handle detected buy transaction."""
        logger.info(f"Processing buy: ${buy.usd_amount:.2f} from {buy.buyer_short}")

        # Store purchase event in memory (fire-and-forget)
        try:
            from bots.buy_tracker.memory_hooks import store_purchase_event
            from core.async_utils import fire_and_forget

            fire_and_forget(
                store_purchase_event(
                    token_symbol=self.config.token_symbol,
                    token_mint=self.config.token_address,
                    buyer_wallet=buy.buyer_wallet,
                    purchase_amount_sol=buy.sol_amount,
                    token_amount=buy.token_amount,
                    price_at_purchase=buy.price_per_token,
                    source="kr8tiv",
                    metadata={
                        "market_cap": buy.market_cap,
                        "buyer_position_pct": buy.buyer_position_pct,
                        "sol_price_usd": buy.usd_amount / buy.sol_amount if buy.sol_amount > 0 else 0,
                    },
                ),
                name=f"store_purchase_{buy.signature[:8]}",
            )
        except Exception as e:
            logger.debug(f"Memory hook skipped: {e}")

        # Format the message
        message = self._format_buy_message(buy)
        keyboard = get_faq_keyboard(show_faq=False)

        # Retry logic with exponential backoff for network issues
        max_retries = 3
        retry_delay = 2.0

        for attempt in range(max_retries):
            try:
                # Send KR8TIV sticker first as decoration (if available)
                await self._send_kr8tiv_sticker()

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
                            read_timeout=30,
                            write_timeout=30,
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

                # Self-correcting AI: Record learning and broadcast signal
                if SELF_CORRECTING_AVAILABLE and self.memory and self.bus:
                    try:
                        # Record learning about this buy
                        await self._record_buy_learning(buy)

                        # Broadcast buy signal to other bots
                        await self.bus.publish(
                            sender="buy_tracker",
                            message_type=MessageType.BUY_SIGNAL,
                            data={
                                "token": buy.token_symbol,
                                "contract": buy.token_mint,
                                "usd_amount": buy.usd_amount,
                                "buyer": buy.buyer_short,
                                "timestamp": buy.timestamp,
                                "tx_signature": buy.tx_signature,
                            },
                            priority=MessagePriority.HIGH
                        )
                        logger.info(f"Broadcasted buy signal to other bots")
                    except Exception as e:
                        logger.error(f"Failed to record learning or broadcast: {e}")

                return  # Success, exit retry loop

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Buy notification attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Failed to send buy notification after {max_retries} attempts: {e}")

    async def _handle_mentions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin-only: respond to @mentions in group chats so Matt can confirm it's alive."""
        try:
            if not update.message or not update.message.text:
                return
            if not update.effective_user or update.effective_user.is_bot:
                return

            user_id = update.effective_user.id
            if not _is_admin(user_id):
                return

            text = update.message.text.strip()
            text_lower = text.lower()

            # Only respond if explicitly @mentioned
            if not self._bot_username:
                # Best-effort fetch (should already be set in start())
                me = await context.bot.get_me()
                self._bot_username = (me.username or "").lower()

            if self._bot_username and f"@{self._bot_username}" not in text_lower:
                return

            await update.message.reply_text(
                "✅ I’m here.\n\nUse /demo on @jarvistrades_bot for the trading UI.",
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.warning(f"Mention handler error: {exc}")


    async def _handle_faq_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle FAQ expand/collapse button clicks."""
        query = update.callback_query
        action = query.data  # "show_faq" or "hide_faq"
        message_id = query.message.message_id if query.message else None
        chat_id = query.message.chat_id if query.message else None
        user_id = query.from_user.id if query.from_user else 0

        # ENTRY LOGGING
        logger.info(f"[FAQ_CALLBACK] action='{action}' user={user_id} msg_id={message_id}")

        # CRITICAL: Always answer callback first
        try:
            await query.answer()
        except Exception as e:
            logger.warning(f"[FAQ_CALLBACK] Could not answer callback: {e}")
            error_tracker.track_error(
                e,
                context=f"faq_callback.answer:{action}",
                component="buy_tracker_bot",
                metadata={"user_id": user_id, "action": action}
            )

        if not message_id or not chat_id:
            logger.warning(f"[FAQ_CALLBACK] Missing message context: msg_id={message_id} chat_id={chat_id}")
            return

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
                    logger.info(f"[FAQ_CALLBACK] FAQ expanded for msg_id={message_id}")
                else:
                    # No cached message, just send FAQ as new message
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=FAQ_CONTENT,
                        parse_mode=ParseMode.HTML,
                    )
                    logger.info(f"[FAQ_CALLBACK] FAQ sent as new message (no cache) chat_id={chat_id}")

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
                    logger.info(f"[FAQ_CALLBACK] FAQ collapsed for msg_id={message_id}")

        except Exception as e:
            logger.error(f"[FAQ_CALLBACK] Failed to handle FAQ callback: {e}", exc_info=True)
            error_tracker.track_error(
                e,
                context=f"faq_callback.handle:{action}",
                component="buy_tracker_bot",
                metadata={"user_id": user_id, "action": action, "message_id": message_id}
            )

    async def _handle_ape_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle ape button clicks for treasury trading with TP/SL."""
        query = update.callback_query
        callback_data = query.data
        chat_id = query.message.chat_id if query.message else None
        user_id = query.from_user.id if query.from_user else 0
        message_id = query.message.message_id if query.message else None

        # ENTRY LOGGING
        logger.info(f"[APE_CALLBACK] data='{callback_data}' user={user_id} msg_id={message_id}")

        # CRITICAL: Always answer callback first to stop loading spinner
        try:
            await query.answer("Processing...", show_alert=False)
        except Exception as e:
            logger.warning(f"[APE_CALLBACK] Could not answer callback: {e}")
            error_tracker.track_error(
                e,
                context=f"ape_callback.answer:{callback_data}",
                component="buy_tracker_bot",
                metadata={"user_id": user_id, "callback_data": callback_data}
            )

        if not chat_id:
            logger.warning(f"[APE_CALLBACK] Missing chat_id for callback: {callback_data}")
            return

        if not _is_admin(user_id):
            await self.bot.send_message(
                chat_id=chat_id,
                text="Admin only. Trade request blocked.",
                parse_mode=ParseMode.HTML,
            )
            logger.warning(f"[APE_CALLBACK] Unauthorized ape trade attempt by user {user_id}")
            return

        logger.info(f"[APE_CALLBACK] Processing trade: {callback_data}")

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
            logger.error(f"[APE_CALLBACK] Error: {e}", exc_info=True)
            error_tracker.track_error(
                e,
                context=f"ape_callback.handle:{callback_data}",
                component="buy_tracker_bot",
                metadata={"user_id": user_id, "callback_data": callback_data, "chat_id": chat_id}
            )
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=f"Error processing trade: {str(e)[:100]}",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass  # Ignore errors when sending error notification

    async def _handle_confirm_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle trade confirmation button clicks."""
        query = update.callback_query
        callback_data = query.data
        chat_id = query.message.chat_id if query.message else None
        user_id = query.from_user.id if query.from_user else 0
        message_id = query.message.message_id if query.message else None

        # ENTRY LOGGING
        logger.info(f"[CONFIRM_CALLBACK] data='{callback_data}' user={user_id} msg_id={message_id}")

        # CRITICAL: Always answer callback first to stop loading spinner
        try:
            await query.answer("Executing...", show_alert=False)
        except Exception as e:
            logger.warning(f"[CONFIRM_CALLBACK] Could not answer callback: {e}")
            error_tracker.track_error(
                e,
                context=f"confirm_callback.answer:{callback_data}",
                component="buy_tracker_bot",
                metadata={"user_id": user_id, "callback_data": callback_data}
            )

        if not chat_id:
            logger.warning(f"[CONFIRM_CALLBACK] Missing chat_id for callback: {callback_data}")
            return

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
                if not _is_admin(user_id):
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text="Admin only. Trade request blocked.",
                        parse_mode=ParseMode.HTML,
                    )
                    logger.warning(f"Unauthorized trade confirm by user {user_id}")
                    return

                from bots.treasury.trading import TreasuryTrader

                trader = TreasuryTrader()
                balance_sol, _ = await trader.get_balance()
                if balance_sol <= 0:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text="❌ Treasury balance unavailable or zero.",
                        parse_mode=ParseMode.HTML,
                    )
                    return

                result = await execute_ape_trade(
                    callback_data=original_callback,
                    entry_price=0.0,
                    treasury_balance_sol=balance_sol,
                    user_id=user_id,
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
                logger.error(f"[CONFIRM_CALLBACK] Trade execution error: {trade_error}", exc_info=True)
                error_tracker.track_error(
                    trade_error,
                    context=f"confirm_callback.execute:{callback_data}",
                    component="buy_tracker_bot",
                    metadata={"user_id": user_id, "callback_data": callback_data, "chat_id": chat_id}
                )
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=f"Trade in simulation mode\n\nSymbol: {parsed['symbol']}\nAllocation: {parsed['allocation_percent']}%\n\n<i>Live trading coming soon!</i>",
                    parse_mode=ParseMode.HTML,
                )

    async def _handle_info_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle info button clicks."""
        query = update.callback_query
        callback_data = query.data
        user_id = query.from_user.id if query.from_user else 0
        message_id = query.message.message_id if query.message else None

        # ENTRY LOGGING
        logger.info(f"[INFO_CALLBACK] data='{callback_data}' user={user_id} msg_id={message_id}")

        # CRITICAL: Always answer callback first (will be overwritten by info popup)
        # Note: For info callbacks, the answer with info text IS the response

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
            logger.error(f"[INFO_CALLBACK] Error: {e}", exc_info=True)
            error_tracker.track_error(
                e,
                context=f"info_callback.handle:{callback_data}",
                component="buy_tracker_bot",
                metadata={"user_id": user_id, "callback_data": callback_data}
            )
            try:
                await query.answer("Info unavailable", show_alert=True)
            except Exception:
                pass  # Ignore if answer fails

    async def _handle_expand_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle expand section button clicks - show trading options for a section."""
        query = update.callback_query
        callback_data = query.data
        chat_id = query.message.chat_id if query.message else None
        user_id = query.from_user.id if query.from_user else 0
        message_id = query.message.message_id if query.message else None

        # ENTRY LOGGING
        logger.info(f"[EXPAND_CALLBACK] data='{callback_data}' user={user_id} msg_id={message_id}")

        # CRITICAL: Answer callback first to stop loading spinner
        # Note: We answer with loading message, then do the actual work
        try:
            # Parse: expand:{section_type}
            # section_type: trending, stocks, indexes, top_picks
            parts = callback_data.split(":")
            if len(parts) < 2:
                await query.answer("Invalid section", show_alert=True)
                return

            section_type = parts[1]
            await query.answer(f"Loading {section_type}...")

            if not chat_id:
                logger.warning(f"[EXPAND_CALLBACK] Missing chat_id for section: {section_type}")
                return

            # Import here to avoid circular deps
            from core.enhanced_market_data import (
                fetch_trending_solana_tokens,
                BACKED_XSTOCKS,
            )

            # Dynamically load data based on section type
            if section_type == "trending":
                # Fetch trending tokens and post buy buttons
                tokens, _ = await fetch_trending_solana_tokens(10)
                if tokens:
                    for token in tokens[:10]:
                        keyboard = create_ape_buttons_with_tp_sl(
                            symbol=token.symbol,
                            asset_type="token",
                            contract_address=token.contract or "",
                            entry_price=token.price_usd,
                            grade="",
                        )
                        price_str = f"${token.price_usd:.8f}" if token.price_usd < 0.01 else f"${token.price_usd:.4f}"
                        msg = f"🔥 <b>{token.symbol}</b> - {price_str}"
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=msg,
                            parse_mode=ParseMode.HTML,
                            reply_markup=keyboard,
                        )
                        await asyncio.sleep(0.2)

            elif section_type == "stocks":
                # Get stocks from registry
                stocks = [(k, v) for k, v in BACKED_XSTOCKS.items() if v["type"] == "stock"][:15]
                for symbol, info in stocks:
                    keyboard = create_ape_buttons_with_tp_sl(
                        symbol=symbol,
                        asset_type="stock",
                        contract_address=info["mint"],
                        entry_price=0.0,
                        grade="",
                    )
                    msg = f"📈 <b>{symbol}</b> ({info['underlying']}) - {info['name']}"
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=msg,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                    )
                    await asyncio.sleep(0.2)

            elif section_type == "indexes":
                # Get indexes from registry
                indexes = [(k, v) for k, v in BACKED_XSTOCKS.items() if v["type"] in ("index", "bond", "commodity")]
                for symbol, info in indexes:
                    keyboard = create_ape_buttons_with_tp_sl(
                        symbol=symbol,
                        asset_type="stock",
                        contract_address=info["mint"],
                        entry_price=0.0,
                        grade="",
                    )
                    type_emoji = "📊" if info["type"] == "index" else "🥇" if info["type"] == "commodity" else "📄"
                    msg = f"{type_emoji} <b>{symbol}</b> ({info['underlying']}) - {info['name']}"
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=msg,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                    )
                    await asyncio.sleep(0.2)

            elif section_type == "bluechip":
                # Load blue-chip tokens from temp file
                import tempfile
                import json
                from core.enhanced_market_data import HIGH_LIQUIDITY_SOLANA_TOKENS

                bluechip_file = Path(tempfile.gettempdir()) / "jarvis_bluechip_tokens.json"

                if bluechip_file.exists():
                    with open(bluechip_file) as f:
                        bluechips = json.load(f)

                    # Group by category for better UX
                    by_category = {}
                    for token in bluechips:
                        cat = token.get("category", "Other")
                        if cat not in by_category:
                            by_category[cat] = []
                        by_category[cat].append(token)

                    # Category emojis
                    category_emojis = {
                        "L1": "⚡",
                        "DeFi": "💱",
                        "Infrastructure": "🛠️",
                        "Meme": "🐕",
                        "Wrapped": "🔗",
                        "LST": "💧",
                        "Stablecoin": "💵",
                        "Other": "📊"
                    }

                    # Send each category
                    for cat in ["L1", "DeFi", "Infrastructure", "Meme", "Wrapped", "LST", "Stablecoin"]:
                        if cat in by_category:
                            category_emoji = category_emojis.get(cat, "📊")
                            await self.bot.send_message(
                                chat_id=chat_id,
                                text=f"\n{category_emoji} <b>{cat}</b> Blue Chips",
                                parse_mode=ParseMode.HTML,
                            )

                            for token in by_category[cat]:
                                keyboard = create_ape_buttons_with_tp_sl(
                                    symbol=token["symbol"],
                                    asset_type="token",
                                    contract_address=token.get("contract", ""),
                                    entry_price=token.get("price_usd", 0.0),
                                    grade="",
                                )

                                price_str = f"${token.get('price_usd', 0):.8f}" if token.get('price_usd', 0) < 0.01 else f"${token.get('price_usd', 0):.4f}"
                                change_emoji = "🟢" if token.get("change_24h", 0) > 0 else "🔴"
                                msg = f"💎 <b>{token['symbol']}</b> - {price_str} {change_emoji} {token.get('change_24h', 0):+.1f}%"
                                await self.bot.send_message(
                                    chat_id=chat_id,
                                    text=msg,
                                    parse_mode=ParseMode.HTML,
                                    reply_markup=keyboard,
                                )
                                await asyncio.sleep(0.15)
                else:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text="⚠️ Blue-chip data not available. Wait for next report.",
                        parse_mode=ParseMode.HTML,
                    )

            elif section_type == "top_picks":
                # Load picks from temp file
                import tempfile
                import json
                picks_file = Path(tempfile.gettempdir()) / "jarvis_top_picks.json"

                if picks_file.exists():
                    with open(picks_file) as f:
                        picks = json.load(f)

                    for i, pick in enumerate(picks[:10]):
                        asset_type = "token" if pick["asset_class"] == "token" else "stock"
                        keyboard = create_ape_buttons_with_tp_sl(
                            symbol=pick["symbol"],
                            asset_type=asset_type,
                            contract_address=pick.get("contract", ""),
                            entry_price=pick.get("entry_price", 0.0),
                            grade=str(pick["conviction"]),
                        )

                        # Conviction color
                        conv = pick["conviction"]
                        conv_emoji = "🟢" if conv >= 80 else "🟡" if conv >= 60 else "🟠"

                        # Medal for top 3
                        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else ""

                        msg = f"{medal} <b>{pick['symbol']}</b> ({pick['asset_class'].upper()}) {conv_emoji} {conv}/100"
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=msg,
                            parse_mode=ParseMode.HTML,
                            reply_markup=keyboard,
                        )
                        await asyncio.sleep(0.2)
                else:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text="⚠️ Top picks data not available. Wait for next report.",
                        parse_mode=ParseMode.HTML,
                    )

            # Update original message to show "Expanded"
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass  # Message may not be editable

        except Exception as e:
            logger.error(f"[EXPAND_CALLBACK] Error: {e}", exc_info=True)
            error_tracker.track_error(
                e,
                context=f"expand_callback.handle:{callback_data}",
                component="buy_tracker_bot",
                metadata={"user_id": user_id, "callback_data": callback_data, "chat_id": chat_id}
            )
            try:
                await query.answer(f"Error loading section: {str(e)[:50]}", show_alert=True)
            except Exception:
                pass  # Ignore if answer fails

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

        # Show LP pair at bottom if not the main pair
        if buy.lp_pair_name and buy.lp_pair_name != "main":
            message += f"\n🔗 <i>LP: {buy.lp_pair_name}</i>\n"

        # Add @FrankkkNL credit every 10th buy
        if self._buy_counter % 10 == 0:
            message += f"\n<i>🤖 KR8TIV sticker by @FrankkkNL</i>\n"

        return message

    def _get_buy_circles(self, usd_amount: float) -> str:
        """Get green circle emojis based on buy amount.

        Note: Custom emoji in text requires premium/Fragment username ($4000+).
        Using standard emojis here, with KR8TIV sticker sent separately.
        """
        emoji = "🟢"  # Standard green circle

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

    async def _record_buy_learning(self, buy: BuyTransaction):
        """Record buy detection as a learning for self-correcting AI system.

        Stores patterns about significant buys to help other bots make better decisions.
        Only records buys >= $100 to focus on meaningful signals.
        """
        if not SELF_CORRECTING_AVAILABLE or not self.memory:
            return

        try:
            # Only record significant buys (>= $100)
            if buy.usd_amount < 100:
                return

            # Determine learning type based on buy size
            if buy.usd_amount >= 1000:
                learning_type = LearningType.SUCCESS_PATTERN
                confidence = 0.8
                content = f"Large buy detected on {buy.token_symbol}: ${buy.usd_amount:,.2f} - significant market interest"
            elif buy.usd_amount >= 500:
                learning_type = LearningType.SUCCESS_PATTERN
                confidence = 0.7
                content = f"Notable buy on {buy.token_symbol}: ${buy.usd_amount:,.2f} - growing interest"
            else:  # >= 100
                learning_type = LearningType.MARKET_INSIGHT
                confidence = 0.6
                content = f"Buy activity on {buy.token_symbol}: ${buy.usd_amount:,.2f}"

            # Store learning with context
            learning_id = self.memory.add_learning(
                component="buy_tracker",
                learning_type=learning_type,
                content=content,
                context={
                    "token": buy.token_symbol,
                    "contract": buy.token_mint,
                    "usd_amount": buy.usd_amount,
                    "buyer": buy.buyer_short,
                    "timestamp": buy.timestamp,
                    "tx_signature": buy.signature,
                },
                confidence=confidence
            )

            logger.info(f"Recorded buy learning: {learning_id} (${buy.usd_amount:,.2f})")

            # Broadcast learning to other bots
            if self.bus:
                await self.bus.publish(
                    sender="buy_tracker",
                    message_type=MessageType.NEW_LEARNING,
                    data={
                        "learning_id": learning_id,
                        "component": "buy_tracker",
                        "type": learning_type.value,
                        "content": content,
                    },
                    priority=MessagePriority.NORMAL
                )

        except Exception as e:
            logger.error(f"Failed to record buy learning: {e}")


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

    # SECURITY: prevent HTTP client libraries from logging full request URLs (can include bot tokens)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)

    # Start metrics server (best-effort)
    try:
        from core.monitoring.metrics import start_metrics_server
        start_metrics_server()
    except Exception as exc:
        logger.warning(f"Metrics server unavailable: {exc}")

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
