"""
Raid Bot Command Handlers for Telegram.

Commands:
- /verify @handle - Link Telegram to Twitter account
- /startraid <tweet_url> - Admin: Start a raid (posts announcement)
- /endraid - Admin: End raid and post summary
- /cancelraid - Admin: Cancel raid without awarding points
- /leaderboard - View top 10 raiders
- /mypoints - Check your points and rank
- /setpoints - Admin: Configure point values
- /setreward - Admin: Set weekly reward amount
- /checkraid - Check your participation in active raid
- /raidstats - Admin: View raid statistics
"""

import logging
from datetime import time as dt_time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

from tg_bot.config import get_config
from tg_bot.handlers import error_handler, admin_only
from tg_bot.services.raid_service import get_raid_service

logger = logging.getLogger(__name__)


# =============================================================================
# User Commands
# =============================================================================

@error_handler
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /verify @handle - Link your Telegram account to your Twitter handle.

    Usage: /verify @YourTwitterHandle
    """
    if not context.args:
        await update.message.reply_text(
            "<b>Link your Twitter account</b>\n\n"
            "Usage: <code>/verify @YourTwitterHandle</code>\n\n"
            "Example: <code>/verify @elonmusk</code>\n\n"
            "This lets you earn points in Twitter raids!",
            parse_mode=ParseMode.HTML
        )
        return

    handle = context.args[0].lstrip("@")
    telegram_user = update.effective_user

    service = get_raid_service()

    # Check if already registered
    existing = service.get_user_by_telegram_id(telegram_user.id)
    if existing and existing.get("is_verified"):
        await update.message.reply_text(
            f"You're already verified as <b>@{existing['twitter_handle']}</b>!\n\n"
            f"To change your handle, contact an admin.",
            parse_mode=ParseMode.HTML
        )
        return

    # Send loading message
    loading_msg = await update.message.reply_text("Verifying your Twitter handle...")

    # Verify Twitter handle exists
    success, user_data = await service.verify_twitter_handle(handle)

    if not success:
        await loading_msg.edit_text(
            f"Could not verify <b>@{handle}</b>\n\n"
            f"Error: {user_data.get('error', 'Unknown error')}\n\n"
            f"Make sure the handle is correct and the account exists.",
            parse_mode=ParseMode.HTML
        )
        return

    # Register user
    service.register_user(
        telegram_id=telegram_user.id,
        telegram_username=telegram_user.username or "",
        twitter_handle=handle,
        twitter_id=user_data.get("twitter_id", ""),
        is_blue=user_data.get("is_blue", False)
    )

    blue_status = " (Blue Verified)" if user_data.get("is_blue") else ""
    await loading_msg.edit_text(
        f"Successfully linked!\n\n"
        f"Telegram: @{telegram_user.username or telegram_user.id}\n"
        f"Twitter: <b>@{handle}</b>{blue_status}\n"
        f"Followers: {user_data.get('followers', 0):,}\n\n"
        f"You can now participate in raids and earn points!",
        parse_mode=ParseMode.HTML
    )


@error_handler
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /leaderboard - View the top 10 raiders this week.
    """
    service = get_raid_service()
    leaders = service.get_leaderboard(limit=10, weekly=True)

    if not leaders:
        await update.message.reply_text(
            "<b>Weekly Raid Leaderboard</b>\n\n"
            "No raiders on the leaderboard yet!\n\n"
            "Be the first to participate in a raid.",
            parse_mode=ParseMode.HTML
        )
        return

    lines = ["<b>Weekly Raid Leaderboard</b>\n"]

    medals = ["1.", "2.", "3."]
    for i, user in enumerate(leaders):
        rank = i + 1
        medal = medals[i] if i < 3 else f"{rank}."
        blue = " " if user.get("is_blue") else ""

        lines.append(
            f"{medal} @{user['twitter_handle']}{blue} - <b>{user['weekly_points']}</b> pts"
        )

    # Get reward info
    reward_config = service.get_reward_config()
    if reward_config["amount"] > 0:
        lines.append(f"\n<b>Weekly Reward:</b> {reward_config['amount']:,.0f} {reward_config['token']}")
        lines.append("<i>Top 10 raiders win each week!</i>")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML
    )


@error_handler
async def mypoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /mypoints - Check your raid points and rank.
    """
    telegram_user = update.effective_user
    service = get_raid_service()

    user_data = service.get_user_points(telegram_user.id)

    if not user_data:
        await update.message.reply_text(
            "You haven't verified your Twitter account yet!\n\n"
            "Use <code>/verify @YourHandle</code> to get started.",
            parse_mode=ParseMode.HTML
        )
        return

    blue = " (Blue Verified)" if user_data.get("is_blue") else ""

    await update.message.reply_text(
        f"<b>Your Raid Stats</b>\n\n"
        f"Twitter: @{user_data['twitter_handle']}{blue}\n"
        f"Weekly Points: <b>{user_data['weekly_points']}</b>\n"
        f"Total Points: <b>{user_data['total_points']}</b>\n"
        f"Weekly Rank: <b>#{user_data['weekly_rank']}</b>\n"
        f"All-Time Rank: <b>#{user_data['total_rank']}</b>",
        parse_mode=ParseMode.HTML
    )


@error_handler
async def checkraid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /checkraid - Check your participation in the active raid.
    """
    telegram_user = update.effective_user
    service = get_raid_service()

    # Check if verified
    user = service.get_user_by_telegram_id(telegram_user.id)
    if not user:
        await update.message.reply_text(
            "You need to verify first!\n\n"
            "Use <code>/verify @YourHandle</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # Check active raid
    active = service.get_active_raid()
    if not active:
        await update.message.reply_text(
            "No active raid right now.\n\n"
            "Wait for an admin to start one!",
            parse_mode=ParseMode.HTML
        )
        return

    # Send loading message
    loading_msg = await update.message.reply_text("Checking your engagement on Twitter...")

    success, message, data = await service.check_participation(telegram_user.id)

    if not success:
        await loading_msg.edit_text(f"Error: {message}", parse_mode=ParseMode.HTML)
        return

    # Build response
    liked = "" if data.get("liked") else ""
    retweeted = "" if data.get("retweeted") else ""
    commented = "" if data.get("commented") else ""

    points = data.get("points_earned", 0)
    blue_bonus = data.get("blue_bonus", 0)
    already_checked = data.get("already_checked", False)

    status = "(already recorded)" if already_checked else "(just recorded!)"

    text = (
        f"<b>Raid Participation Check</b>\n\n"
        f"Tweet: {active['tweet_url']}\n\n"
        f"Like: {liked}\n"
        f"Retweet: {retweeted}\n"
        f"Comment: {commented}\n\n"
        f"<b>Points Earned: {points}</b> {status}"
    )

    if blue_bonus > 0:
        text += f"\n(includes +{blue_bonus} blue bonus)"

    if points == 0:
        text += "\n\n<i>Engage with the tweet and check again!</i>"

    await loading_msg.edit_text(text, parse_mode=ParseMode.HTML)


# =============================================================================
# Admin Commands
# =============================================================================

@error_handler
@admin_only
async def startraid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /startraid <tweet_url> - Start a new raid on a tweet.

    Admin only. Posts an announcement with a "Check Participation" button.
    """
    if not context.args:
        await update.message.reply_text(
            "<b>Start a Raid</b>\n\n"
            "Usage: <code>/startraid &lt;tweet_url&gt;</code>\n\n"
            "Example:\n"
            "<code>/startraid https://x.com/Jarvis_lifeos/status/123456789</code>",
            parse_mode=ParseMode.HTML
        )
        return

    tweet_url = context.args[0]
    service = get_raid_service()

    # Send loading message
    loading_msg = await update.message.reply_text("Starting raid...")

    success, message, raid = await service.start_raid(
        tweet_url=tweet_url,
        announcement_chat_id=update.effective_chat.id
    )

    if not success:
        await loading_msg.edit_text(f"Failed to start raid: {message}", parse_mode=ParseMode.HTML)
        return

    # Delete loading message
    await loading_msg.delete()

    # Post announcement
    point_values = service.get_point_values()

    announcement = (
        f"<b>RAID ACTIVE!</b>\n\n"
        f"Target: {raid['tweet_url']}\n"
    )

    if raid.get("tweet_author"):
        announcement += f"Author: @{raid['tweet_author']}\n"

    announcement += (
        f"\n<b>Earn Points:</b>\n"
        f" Like = {point_values['like']} pt\n"
        f" Retweet = {point_values['retweet']} pt\n"
        f" Comment = {point_values['comment']} pts\n"
        f" Blue Bonus = +{point_values['blue_bonus']} pt\n\n"
        f"<i>Click the button below after engaging to verify!</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(" Open Tweet", url=raid['tweet_url'])],
        [InlineKeyboardButton(" Check My Participation", callback_data="raid:check")],
    ])

    msg = await update.message.reply_text(
        announcement,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )

    # Update raid with announcement message ID
    service.update_raid_announcement(raid["id"], msg.message_id, update.effective_chat.id)


@error_handler
@admin_only
async def endraid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /endraid - End the current raid and post summary.
    """
    service = get_raid_service()

    loading_msg = await update.message.reply_text("Ending raid and calculating results...")

    success, message, summary = await service.end_raid()

    if not success:
        await loading_msg.edit_text(f"Error: {message}", parse_mode=ParseMode.HTML)
        return

    # Build summary message
    lines = [
        "<b>RAID ENDED!</b>\n",
        f"Tweet: {summary['tweet_url']}\n",
        f"Duration: {summary['duration_minutes']} minutes",
        f"Participants: {summary['total_participants']}",
        f"Total Points: {summary['total_points']}\n",
        f"Engagement:",
        f"  {summary['total_likes']} likes",
        f"  {summary['total_retweets']} retweets",
        f"  {summary['total_comments']} comments\n",
    ]

    if summary.get("top_participants"):
        lines.append("<b>Top Raiders:</b>")
        for i, p in enumerate(summary["top_participants"][:5], 1):
            blue = "" if p.get("is_blue") else ""
            lines.append(f"{i}. @{p['twitter_handle']}{blue} - {p['points_earned']} pts")

    await loading_msg.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)


@error_handler
@admin_only
async def cancelraid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cancelraid - Cancel the current raid without awarding points.
    """
    service = get_raid_service()

    success, message = service.cancel_raid()

    if not success:
        await update.message.reply_text(f"Error: {message}", parse_mode=ParseMode.HTML)
        return

    await update.message.reply_text(
        "<b>Raid Cancelled</b>\n\n"
        "No points were awarded.",
        parse_mode=ParseMode.HTML
    )


@error_handler
@admin_only
async def setpoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /setpoints like=N retweet=N comment=N blue_bonus=N

    Configure point values for raid actions.
    """
    service = get_raid_service()

    if not context.args:
        current = service.get_point_values()
        await update.message.reply_text(
            f"<b>Current Point Values:</b>\n"
            f"like = {current['like']}\n"
            f"retweet = {current['retweet']}\n"
            f"comment = {current['comment']}\n"
            f"blue_bonus = {current['blue_bonus']}\n\n"
            f"Usage: <code>/setpoints like=2 comment=3</code>",
            parse_mode=ParseMode.HTML
        )
        return

    updated = []

    for arg in context.args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            key = key.lower()
            if key in ("like", "retweet", "comment", "blue_bonus"):
                try:
                    int_value = int(value)
                    if service.set_point_value(key, int_value):
                        updated.append(f"{key}={int_value}")
                except ValueError:
                    pass

    if updated:
        await update.message.reply_text(
            f"<b>Updated point values:</b>\n" + "\n".join(updated),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "No valid values provided.\n\n"
            "Example: <code>/setpoints like=2 comment=3</code>",
            parse_mode=ParseMode.HTML
        )


@error_handler
@admin_only
async def setreward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /setreward <amount> [token] - Set weekly reward amount.

    Example: /setreward 100000 KR8TIV
    """
    service = get_raid_service()

    if not context.args:
        current = service.get_reward_config()
        await update.message.reply_text(
            f"<b>Current Weekly Reward:</b>\n"
            f"{current['amount']:,.0f} {current['token']}\n\n"
            f"Usage: <code>/setreward 100000 KR8TIV</code>",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        amount = float(context.args[0].replace(",", ""))
        token = context.args[1].upper() if len(context.args) > 1 else None

        service.set_reward_config(amount, token)

        reward = service.get_reward_config()
        await update.message.reply_text(
            f"Weekly reward set to <b>{reward['amount']:,.0f} {reward['token']}</b>",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text(
            "Invalid amount. Use a number.\n\n"
            "Example: <code>/setreward 100000 KR8TIV</code>",
            parse_mode=ParseMode.HTML
        )


@error_handler
@admin_only
async def raidstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /raidstats - View raid statistics.
    """
    service = get_raid_service()
    stats = service.get_raid_stats()
    reward = service.get_reward_config()
    points = service.get_point_values()

    lines = [
        "<b>Raid Bot Statistics</b>\n",
        f"Total Verified Users: {stats['total_verified_users']}",
        f"Total Raids Run: {stats['total_raids']}\n",
        "<b>Point Values:</b>",
        f"  Like: {points['like']}",
        f"  Retweet: {points['retweet']}",
        f"  Comment: {points['comment']}",
        f"  Blue Bonus: +{points['blue_bonus']}\n",
        f"<b>Weekly Reward:</b>",
        f"  {reward['amount']:,.0f} {reward['token']}",
    ]

    # Active raid status
    active = service.get_active_raid()
    if active:
        lines.append(f"\n<b>Active Raid:</b>")
        lines.append(f"  {active['tweet_url']}")
    else:
        lines.append(f"\n<i>No active raid</i>")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# =============================================================================
# Callback Handler
# =============================================================================

@error_handler
async def raid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle raid:* callback queries."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("raid:"):
        return

    action = data.split(":")[1]

    if action == "check":
        # Check participation inline
        telegram_user = update.effective_user
        service = get_raid_service()

        user = service.get_user_by_telegram_id(telegram_user.id)
        if not user:
            await query.answer(
                "You need to verify first! Send /verify @YourHandle",
                show_alert=True
            )
            return

        active = service.get_active_raid()
        if not active:
            await query.answer("Raid has ended!", show_alert=True)
            return

        await query.answer("Checking your engagement...")

        success, message, data = await service.check_participation(telegram_user.id)

        if not success:
            await query.answer(message, show_alert=True)
            return

        points = data.get("points_earned", 0)
        if points > 0:
            status = " (already recorded)" if data.get("already_checked") else " (recorded!)"
            await query.answer(
                f"You earned {points} points!{status}\n"
                f"Like: {'Yes' if data['liked'] else 'No'}, "
                f"RT: {'Yes' if data['retweeted'] else 'No'}, "
                f"Comment: {'Yes' if data['commented'] else 'No'}",
                show_alert=True
            )
        else:
            await query.answer(
                "No engagement detected yet.\n"
                "Like, RT, or comment on the tweet and try again!",
                show_alert=True
            )


# =============================================================================
# Weekly Reset Job
# =============================================================================

async def weekly_reset_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Weekly reset job - runs every Sunday at midnight UTC.
    Resets weekly points and announces winners.
    """
    service = get_raid_service()
    config = get_config()

    logger.info("Running weekly raid reset job...")

    result = await service.weekly_reset()
    winners = result.get("winners", [])
    reward = result.get("reward_amount", 0)
    token = result.get("reward_token", "SOL")

    if not winners:
        logger.info("No winners this week")
        return

    # Build announcement
    lines = [
        "<b>WEEKLY RAID RESET</b>\n",
        f"Week ending: {result['week_end'][:10]}\n",
        "<b>Top 10 Raiders:</b>"
    ]

    medals = ["1.", "2.", "3."]
    for i, winner in enumerate(winners[:10]):
        medal = medals[i] if i < 3 else f"{i+1}."
        blue = "" if winner.get("is_blue") else ""
        lines.append(
            f"{medal} @{winner['twitter_handle']}{blue} - <b>{winner['weekly_points']}</b> pts"
        )

    if reward > 0:
        lines.append(f"\n<b>Reward:</b> {reward:,.0f} {token} to be distributed!")

    lines.append("\n<i>Points have been reset. Good luck this week!</i>")

    message = "\n".join(lines)

    # Send to admin chat(s)
    for admin_id in config.admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send weekly reset to admin {admin_id}: {e}")

    logger.info(f"Weekly reset completed. {len(winners)} winners announced.")


# =============================================================================
# Registration Helper
# =============================================================================

def register_raid_handlers(app, job_queue=None):
    """Register all raid handlers with the app."""
    # User commands
    app.add_handler(CommandHandler("verify", verify))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("lb", leaderboard))  # Alias
    app.add_handler(CommandHandler("mypoints", mypoints))
    app.add_handler(CommandHandler("checkraid", checkraid))

    # Admin commands
    app.add_handler(CommandHandler("startraid", startraid))
    app.add_handler(CommandHandler("endraid", endraid))
    app.add_handler(CommandHandler("cancelraid", cancelraid))
    app.add_handler(CommandHandler("setpoints", setpoints))
    app.add_handler(CommandHandler("setreward", setreward))
    app.add_handler(CommandHandler("raidstats", raidstats))

    # Callback handler
    app.add_handler(CallbackQueryHandler(raid_callback, pattern=r"^raid:"))

    # Weekly reset job (Sunday midnight UTC)
    if job_queue:
        job_queue.run_daily(
            weekly_reset_job,
            time=dt_time(hour=0, minute=0, second=0),  # Midnight UTC
            days=(6,),  # Sunday (0=Monday, 6=Sunday)
            name="raid_weekly_reset"
        )
        logger.info("Raid weekly reset job scheduled for Sunday midnight UTC")

    logger.info("Raid handlers registered")
