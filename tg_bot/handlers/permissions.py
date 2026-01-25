"""
Telegram handlers for permission management.

Provides /approve, /deny, /allowlist, and /permissions commands.
"""

import logging
from datetime import datetime
from typing import Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler, admin_only

logger = logging.getLogger(__name__)


def build_approval_message(
    request: "ExecRequest",
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Build approval request message with inline buttons.

    Args:
        request: The ExecRequest to display

    Returns:
        Tuple of (message_text, inline_keyboard)
    """
    from core.permissions.manager import ExecRequest

    # Calculate time remaining
    now = datetime.now()
    remaining = request.expires_at - now
    remaining_mins = int(remaining.total_seconds() / 60)
    remaining_secs = int(remaining.total_seconds() % 60)

    if remaining_mins > 0:
        expires_text = f"{remaining_mins}m {remaining_secs}s"
    else:
        expires_text = f"{remaining_secs}s"

    # Risk emoji
    risk_emoji = {
        "safe": "",
        "moderate": "",
        "high": "",
        "critical": "",
    }.get(request.risk_level, "")

    text = f"""<b>{risk_emoji} Approval Required</b>

<b>Command:</b>
<code>{request.command}</code>

<b>Risk:</b> {request.risk_level.upper()}
<b>Description:</b> {request.description or 'No description'}

<b>Request ID:</b> <code>{request.id}</code>
<b>Expires in:</b> {expires_text}"""

    # Build inline keyboard
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Approve", callback_data=f"approve:{request.id}"
                ),
                InlineKeyboardButton(
                    "Deny", callback_data=f"deny:{request.id}"
                ),
            ]
        ]
    )

    return text, keyboard


@error_handler
@admin_only
async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /approve command - approve pending exec requests.

    Usage:
        /approve - List pending requests
        /approve <request_id> - Approve specific request
    """
    from core.permissions.manager import get_permission_manager

    user_id = update.effective_user.id
    manager = get_permission_manager()

    # If no args, list pending requests
    if not context.args:
        pending = manager.list_pending_requests(user_id)

        if not pending:
            await update.message.reply_text(
                "no pending approval requests.",
                parse_mode=ParseMode.HTML,
            )
            return

        lines = ["<b>pending approval requests</b>", ""]
        for req in pending:
            remaining = req.expires_at - datetime.now()
            remaining_mins = int(remaining.total_seconds() / 60)
            lines.append(
                f"<code>{req.id}</code> - {req.risk_level.upper()}"
            )
            lines.append(f"  <code>{req.command[:50]}{'...' if len(req.command) > 50 else ''}</code>")
            lines.append(f"  expires: {remaining_mins}m")
            lines.append("")

        lines.append("<i>/approve &lt;request_id&gt; to approve</i>")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    # Approve specific request
    request_id = context.args[0]
    request = manager.get_request(request_id)

    if not request:
        await update.message.reply_text(
            f"request <code>{request_id}</code> not found.",
            parse_mode=ParseMode.HTML,
        )
        return

    result = manager.approve_request(request_id)

    if result:
        await update.message.reply_text(
            f"<b>approved</b> request <code>{request_id}</code>\n\n"
            f"command: <code>{request.command}</code>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"failed to approve <code>{request_id}</code>. "
            "may already be processed or expired.",
            parse_mode=ParseMode.HTML,
        )


@error_handler
@admin_only
async def deny_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /deny command - deny pending exec requests.

    Usage:
        /deny <request_id> - Deny specific request
    """
    from core.permissions.manager import get_permission_manager

    manager = get_permission_manager()

    if not context.args:
        await update.message.reply_text(
            "<b>usage:</b> /deny &lt;request_id&gt;",
            parse_mode=ParseMode.HTML,
        )
        return

    request_id = context.args[0]
    request = manager.get_request(request_id)

    if not request:
        await update.message.reply_text(
            f"request <code>{request_id}</code> not found.",
            parse_mode=ParseMode.HTML,
        )
        return

    result = manager.deny_request(request_id)

    if result:
        await update.message.reply_text(
            f"<b>denied</b> request <code>{request_id}</code>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"failed to deny <code>{request_id}</code>. "
            "may already be processed or expired.",
            parse_mode=ParseMode.HTML,
        )


@error_handler
@admin_only
async def allowlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /allowlist command - manage command allowlist.

    Usage:
        /allowlist - Show current allowlist
        /allowlist add <pattern> - Add pattern to allowlist
        /allowlist remove <pattern> - Remove pattern from allowlist
    """
    from core.permissions.manager import get_permission_manager

    user_id = update.effective_user.id
    manager = get_permission_manager()

    # No args - show allowlist
    if not context.args:
        allowlist = manager.get_allowlist(user_id)

        if not allowlist:
            await update.message.reply_text(
                "<b>allowlist</b>\n\n"
                "no patterns configured.\n\n"
                "<i>/allowlist add &lt;pattern&gt; to add</i>",
                parse_mode=ParseMode.HTML,
            )
            return

        lines = ["<b>allowlist</b>", ""]
        for pattern in allowlist:
            lines.append(f"  <code>{pattern}</code>")

        lines.append("")
        lines.append("<i>/allowlist remove &lt;pattern&gt; to remove</i>")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    # Parse subcommand
    subcommand = context.args[0].lower()

    if subcommand == "add" and len(context.args) > 1:
        pattern = " ".join(context.args[1:])
        result = manager.add_to_allowlist(user_id, pattern)

        if result:
            await update.message.reply_text(
                f"<b>added</b> <code>{pattern}</code> to allowlist",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(
                f"pattern <code>{pattern}</code> already exists",
                parse_mode=ParseMode.HTML,
            )

    elif subcommand == "remove" and len(context.args) > 1:
        pattern = " ".join(context.args[1:])
        result = manager.remove_from_allowlist(user_id, pattern)

        if result:
            await update.message.reply_text(
                f"<b>removed</b> <code>{pattern}</code> from allowlist",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(
                f"pattern <code>{pattern}</code> not found",
                parse_mode=ParseMode.HTML,
            )

    else:
        await update.message.reply_text(
            "<b>usage:</b>\n"
            "  /allowlist - show current\n"
            "  /allowlist add &lt;pattern&gt;\n"
            "  /allowlist remove &lt;pattern&gt;",
            parse_mode=ParseMode.HTML,
        )


@error_handler
async def permissions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /permissions command - show or set permission level.

    Usage:
        /permissions - Show current level
        /permissions <level> - Set level (admin only)
    """
    from core.permissions.manager import get_permission_manager, PermissionLevel

    user_id = update.effective_user.id
    manager = get_permission_manager()

    current_level = manager.get_user_level(user_id)

    # No args - show current level
    if not context.args:
        level_descriptions = {
            PermissionLevel.NONE: "read-only, no execution",
            PermissionLevel.BASIC: "safe operations only",
            PermissionLevel.ELEVATED: "most operations allowed",
            PermissionLevel.ADMIN: "full access, no approval needed",
        }

        await update.message.reply_text(
            f"<b>permission level:</b> {current_level.name.lower()}\n\n"
            f"<i>{level_descriptions.get(current_level, '')}</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Setting level requires admin
    if current_level != PermissionLevel.ADMIN:
        await update.message.reply_text(
            "only admins can change permission levels.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Set new level
    new_level_str = context.args[0].lower()
    new_level = PermissionLevel.from_string(new_level_str)

    if new_level_str not in ["none", "basic", "elevated", "admin"]:
        await update.message.reply_text(
            "<b>valid levels:</b> none, basic, elevated, admin",
            parse_mode=ParseMode.HTML,
        )
        return

    manager.set_user_level(user_id, new_level)
    await update.message.reply_text(
        f"<b>updated</b> permission level to: {new_level.name.lower()}",
        parse_mode=ParseMode.HTML,
    )


async def approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approval/denial callback from inline buttons."""
    from core.permissions.manager import get_permission_manager

    query = update.callback_query
    await query.answer()

    data = query.data
    if not data or ":" not in data:
        return

    action, request_id = data.split(":", 1)
    manager = get_permission_manager()

    if action == "approve":
        result = manager.approve_request(request_id)
        if result:
            await query.edit_message_text(
                f"<b>APPROVED</b>\n\n"
                f"Request <code>{request_id}</code> has been approved.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await query.edit_message_text(
                f"Failed to approve request. May be expired or already processed.",
                parse_mode=ParseMode.HTML,
            )

    elif action == "deny":
        result = manager.deny_request(request_id)
        if result:
            await query.edit_message_text(
                f"<b>DENIED</b>\n\n"
                f"Request <code>{request_id}</code> has been denied.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await query.edit_message_text(
                f"Failed to deny request. May be expired or already processed.",
                parse_mode=ParseMode.HTML,
            )


async def send_approval_request(
    bot,
    chat_id: int,
    request: "ExecRequest",
) -> None:
    """
    Send approval request message to user.

    Args:
        bot: Telegram Bot instance
        chat_id: Chat ID to send to
        request: The ExecRequest requiring approval
    """
    text, keyboard = build_approval_message(request)
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )
