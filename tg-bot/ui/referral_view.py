"""
Referral View for Telegram Bot.

Shows:
- User's referral code and unique link
- Referral clicks and signups
- Commission earned
- Conversion rate analytics
"""

import logging
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger("jarvis.tg.referral")


class ReferralView:
    """
    Handles referral-related Telegram UI.

    Usage:
        view = ReferralView()

        # Show referral dashboard
        await view.show_referral_dashboard(update, context, user_id)

        # Handle referral code generation
        await view.generate_referral_code(update, context, user_id)
    """

    def __init__(self):
        """Initialize referral view."""
        self._leaderboard = None
        self._ambassador = None

    def _get_leaderboard(self):
        """Lazy load leaderboard manager."""
        if self._leaderboard is None:
            try:
                from core.community.leaderboard import Leaderboard
                self._leaderboard = Leaderboard()
            except Exception as e:
                logger.error(f"Failed to load leaderboard: {e}")
        return self._leaderboard

    def _get_ambassador(self):
        """Lazy load ambassador manager."""
        if self._ambassador is None:
            try:
                from core.community.ambassador import AmbassadorManager
                self._ambassador = AmbassadorManager()
            except Exception as e:
                logger.error(f"Failed to load ambassador manager: {e}")
        return self._ambassador

    # =========================================================================
    # Main Dashboard
    # =========================================================================

    async def show_referral_dashboard(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: str,
    ) -> None:
        """
        Show the main referral dashboard.

        Args:
            update: Telegram update
            context: Bot context
            user_id: User's Jarvis ID
        """
        lb = self._get_leaderboard()
        ambassador = self._get_ambassador()

        if not lb:
            await update.effective_message.reply_text(
                "Referral system is currently unavailable."
            )
            return

        # Get referral stats
        stats = lb.get_referral_stats(user_id)

        # Check if ambassador
        is_ambassador = ambassador.is_ambassador(user_id) if ambassador else False
        commission_rate = 0.15 if is_ambassador else 0.10

        # Generate code if doesn't exist
        referral_code = stats.get("referral_code")
        if not referral_code:
            referral_code = lb.generate_referral_code(user_id)
            stats["referral_code"] = referral_code

        # Build message
        referral_link = f"https://jarvis.lifeos.com/ref/{referral_code}"

        message = f"""
<b>Your Referral Dashboard</b>

<b>Your Referral Code:</b> <code>{referral_code}</code>
<b>Your Link:</b> <code>{referral_link}</code>

<b>Statistics:</b>
- Referrals: {stats.get('referral_count', 0)}
- Total Commission: ${stats.get('total_commission', 0):,.2f}
- Commission Rate: {commission_rate*100:.0f}%

{"<b>Ambassador Status:</b> Active" if is_ambassador else ""}

<i>Share your link to earn {commission_rate*100:.0f}% of your referrals' trading profits!</i>
"""

        # Build keyboard
        keyboard = [
            [
                InlineKeyboardButton("Copy Code", callback_data=f"ref:copy:{referral_code}"),
                InlineKeyboardButton("Share Link", switch_inline_query=f"Join Jarvis with my referral: {referral_link}"),
            ],
            [
                InlineKeyboardButton("View Referrals", callback_data="ref:list"),
                InlineKeyboardButton("Commission History", callback_data="ref:history"),
            ],
        ]

        if not is_ambassador:
            keyboard.append([
                InlineKeyboardButton("Apply for Ambassador", callback_data="ref:ambassador"),
            ])

        keyboard.append([
            InlineKeyboardButton("Back", callback_data="menu:main"),
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.effective_message.reply_text(
            message,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    # =========================================================================
    # Referral List
    # =========================================================================

    async def show_referral_list(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: str,
    ) -> None:
        """Show list of user's referrals."""
        lb = self._get_leaderboard()

        if not lb:
            await update.effective_message.reply_text("Referral system unavailable.")
            return

        # Get referral count (detailed list would need DB query)
        count = lb.get_referral_count(user_id)

        message = f"""
<b>Your Referrals</b>

Total Referrals: {count}

<i>Referral details are kept private for user protection.</i>
"""

        keyboard = [[
            InlineKeyboardButton("Back to Referrals", callback_data="ref:dashboard"),
        ]]

        await update.effective_message.reply_text(
            message,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # =========================================================================
    # Commission History
    # =========================================================================

    async def show_commission_history(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: str,
    ) -> None:
        """Show commission earning history."""
        lb = self._get_leaderboard()

        if not lb:
            await update.effective_message.reply_text("Commission history unavailable.")
            return

        stats = lb.get_referral_stats(user_id)

        message = f"""
<b>Commission History</b>

Total Earned: ${stats.get('total_commission', 0):,.2f}

<i>Commissions are calculated based on your referrals' profitable trades.</i>

<b>How it works:</b>
- Standard rate: 10% of referral profits
- Ambassador rate: 15% of referral profits
- Paid monthly to your account
"""

        keyboard = [[
            InlineKeyboardButton("Back to Referrals", callback_data="ref:dashboard"),
        ]]

        await update.effective_message.reply_text(
            message,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # =========================================================================
    # Ambassador Application
    # =========================================================================

    async def show_ambassador_info(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: str,
    ) -> None:
        """Show ambassador program info and eligibility."""
        ambassador = self._get_ambassador()

        if not ambassador:
            await update.effective_message.reply_text("Ambassador program unavailable.")
            return

        # Check if already ambassador
        if ambassador.is_ambassador(user_id):
            benefits = ambassador.get_ambassador_benefits(user_id)
            message = f"""
<b>Ambassador Status: Active</b>

<b>Your Benefits:</b>
- Commission Rate: {benefits['referral_commission_rate']*100:.0f}%
- Featured Profile: {"Yes" if benefits['featured_profile'] else "No"}
- Early Access: {"Yes" if benefits['early_access'] else "No"}
- Direct Channel: {"Yes" if benefits['direct_channel'] else "No"}

<i>Thank you for being a Jarvis Ambassador!</i>
"""
        else:
            # Show requirements and eligibility
            # Note: Would need to get actual user stats
            message = """
<b>Ambassador Program</b>

<b>Requirements:</b>
- Account age: 3+ months
- Total profit: $500+
- Community involvement

<b>Benefits:</b>
- 15% referral commission (vs 10%)
- Featured on community page
- Early access to new features
- Direct communication channel

<i>Apply below if you meet the requirements!</i>
"""

        keyboard = []

        if not ambassador.is_ambassador(user_id):
            keyboard.append([
                InlineKeyboardButton("Apply Now", callback_data="ref:ambassador:apply"),
            ])

        keyboard.append([
            InlineKeyboardButton("Back to Referrals", callback_data="ref:dashboard"),
        ])

        await update.effective_message.reply_text(
            message,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def process_ambassador_application(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: str,
    ) -> None:
        """Process ambassador application."""
        ambassador = self._get_ambassador()

        if not ambassador:
            await update.effective_message.reply_text("Application system unavailable.")
            return

        # In production, would get actual user stats from leaderboard
        # For now, use placeholder values
        result = ambassador.apply_for_ambassador(
            user_id=user_id,
            account_age_months=4,  # Would get from user registration date
            total_pnl=600.0,       # Would get from trading history
            community_score=50,    # Would calculate from activity
        )

        if result["status"] == "pending":
            message = """
<b>Application Submitted!</b>

Your ambassador application has been received and is pending review.

We'll notify you once it's been reviewed (usually within 2-3 business days).

Thank you for your interest in the Jarvis Ambassador Program!
"""
        elif result["status"] == "rejected":
            missing = result.get("missing", [])
            message = f"""
<b>Application Not Eligible</b>

You don't yet meet all requirements:
{chr(10).join(f'- {m}' for m in missing)}

Keep trading and engaging with the community!
"""
        else:
            message = f"Application status: {result['status']}"

        keyboard = [[
            InlineKeyboardButton("Back to Referrals", callback_data="ref:dashboard"),
        ]]

        await update.effective_message.reply_text(
            message,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # =========================================================================
    # Callback Handler
    # =========================================================================

    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: str,
        action: str,
        data: str = None,
    ) -> None:
        """
        Handle referral-related callbacks.

        Args:
            update: Telegram update
            context: Bot context
            user_id: User's Jarvis ID
            action: Callback action (dashboard, list, history, ambassador, etc.)
            data: Additional callback data
        """
        if action == "dashboard":
            await self.show_referral_dashboard(update, context, user_id)

        elif action == "list":
            await self.show_referral_list(update, context, user_id)

        elif action == "history":
            await self.show_commission_history(update, context, user_id)

        elif action == "ambassador":
            await self.show_ambassador_info(update, context, user_id)

        elif action == "ambassador:apply":
            await self.process_ambassador_application(update, context, user_id)

        elif action == "copy":
            # Just acknowledge the copy request (copying handled client-side)
            await update.callback_query.answer(f"Code: {data}")

        else:
            await update.callback_query.answer("Unknown action")


# Global instance for import
_referral_view: Optional[ReferralView] = None


def get_referral_view() -> ReferralView:
    """Get or create referral view instance."""
    global _referral_view
    if _referral_view is None:
        _referral_view = ReferralView()
    return _referral_view
