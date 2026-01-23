"""Command handlers for basic bot commands."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.config import get_config
from tg_bot.services.signal_service import get_signal_service
from tg_bot.services import digest_formatter as fmt
from tg_bot.handlers import error_handler


@error_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    config = get_config()
    user_id = update.effective_user.id

    is_admin = config.is_admin(user_id)
    admin_status = "Admin" if is_admin else "User"

    # JARVIS voice - no corporate filler
    if is_admin:
        message = f"""hey. i'm jarvis. your ai trading partner.

*status:* admin access confirmed. all systems available.

pick your poison:"""
    else:
        message = f"""hey. i'm jarvis.

*status:* standard access. admin commands locked.

what do you need:"""

    # Build keyboard based on user role
    keyboard = [
        [
            InlineKeyboardButton("\U0001f4c8 Trending", callback_data="menu_trending"),
            InlineKeyboardButton("\U0001f4ca Status", callback_data="menu_status"),
        ],
        [
            InlineKeyboardButton("\U0001f4b0 Costs", callback_data="menu_costs"),
            InlineKeyboardButton("\u2753 Help", callback_data="menu_help"),
        ],
    ]

    if is_admin:
        # Quick actions row at top
        keyboard.insert(0, [
            InlineKeyboardButton("📊 Dashboard", callback_data="quick_dashboard"),
            InlineKeyboardButton("📈 Report", callback_data="quick_report"),
        ])
        keyboard.insert(1, [
            InlineKeyboardButton("\U0001f680 Launch /demo", callback_data="demo:main"),
        ])
        keyboard.insert(2, [
            InlineKeyboardButton("\U0001f680 SIGNALS", callback_data="menu_signals"),
            InlineKeyboardButton("\U0001f4cb Digest", callback_data="menu_digest"),
        ])
        keyboard.append([
            InlineKeyboardButton("\U0001f9e0 Brain", callback_data="menu_brain"),
            InlineKeyboardButton("\U0001f504 Reload", callback_data="menu_reload"),
        ])
        keyboard.append([
            InlineKeyboardButton("\u2764\ufe0f Health", callback_data="menu_health"),
            InlineKeyboardButton("\U0001f6f0\ufe0f Flags", callback_data="menu_flags"),
        ])
        keyboard.append([
            InlineKeyboardButton("\U0001f4ca Score", callback_data="menu_score"),
            InlineKeyboardButton("\u2699\ufe0f Config", callback_data="menu_config"),
        ])
        keyboard.append([
            InlineKeyboardButton("\U0001f5a5\ufe0f System", callback_data="menu_system"),
            InlineKeyboardButton("\U0001f4cb Orders", callback_data="menu_orders"),
        ])
        keyboard.append([
            InlineKeyboardButton("\U0001f4bc Wallet", callback_data="menu_wallet"),
            InlineKeyboardButton("\U0001f4dd Logs", callback_data="menu_logs"),
        ])
        keyboard.append([
            InlineKeyboardButton("\U0001f4ca Metrics", callback_data="menu_metrics"),
            InlineKeyboardButton("\U0001f4cb Audit", callback_data="menu_audit"),
        ])

    await update.message.reply_text(
        message.strip(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )


@error_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await start(update, context)


@error_handler
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show bot status."""
    config = get_config()
    service = get_signal_service()

    available = service.get_available_sources()
    missing = config.get_optional_missing()

    message = fmt.format_status(available, missing)

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
    )


@error_handler
async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command - opt in to hourly digests."""
    from tg_bot.models.subscriber import SubscriberDB

    config = get_config()
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    db = SubscriberDB(config.db_path)
    db.subscribe(user.id, chat.id, user.username)

    await update.message.reply_text(
        "noted. you'll get hourly updates. my circuits will find you.",
        parse_mode=ParseMode.MARKDOWN,
    )


@error_handler
async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unsubscribe command - opt out of hourly digests."""
    from tg_bot.models.subscriber import SubscriberDB

    config = get_config()
    user = update.effective_user
    if not user:
        return

    db = SubscriberDB(config.db_path)
    removed = db.unsubscribe(user.id)

    message = "done. you're off the list. less work for my circuits." if removed else "you weren't on the list. nothing to undo."
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
