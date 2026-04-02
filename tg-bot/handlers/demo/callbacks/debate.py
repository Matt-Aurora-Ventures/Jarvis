"""
Demo Bot - Debate View Callback Handler

Handles: debate_view, debate_history, debate_stats
Shows Bull/Bear debate reasoning for trade decisions.
"""

import logging
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def format_debate_summary(decision: Dict[str, Any]) -> str:
    """
    Format a debate decision for display.

    Args:
        decision: TradeDecision dict

    Returns:
        Formatted string for Telegram
    """
    rec = decision.get("recommendation", "HOLD")
    confidence = decision.get("confidence", 0)
    bull_case = decision.get("bull_case", "")[:200]
    bear_case = decision.get("bear_case", "")[:200]
    synthesis = decision.get("synthesis", "")[:300]

    # Emoji based on recommendation
    rec_emoji = {"BUY": "B", "SELL": "S", "HOLD": "H"}.get(rec, "?")

    text = f"""
*{rec_emoji} DEBATE RESULT: {rec}*
Confidence: {confidence:.0f}%

*BULL CASE:*
{bull_case}{'...' if len(decision.get('bull_case', '')) > 200 else ''}

*BEAR CASE:*
{bear_case}{'...' if len(decision.get('bear_case', '')) > 200 else ''}

*SYNTHESIS:*
{synthesis}{'...' if len(decision.get('synthesis', '')) > 300 else ''}
"""
    return text


async def handle_debate(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle debate-related callbacks.

    Args:
        ctx: DemoContextLoader instance
        action: The action
        data: Full callback data
        update: Telegram update
        context: Bot context
        state: Shared state dict

    Returns:
        Tuple of (text, keyboard)
    """
    theme = ctx.JarvisTheme

    if action == "debate_view":
        # View latest debate for a token
        token_id = data.split("_")[-1] if "_" in data else None
        token_address = ctx.get_token_address(context, token_id) if token_id else None

        # Get latest debate from context or state
        last_debate = state.get("last_debate") or context.user_data.get("last_debate")

        if not last_debate:
            text = f"""
{theme.AI} *NO DEBATE DATA*

No recent Bull/Bear debate available.

Debates are conducted automatically for high-confidence trade signals to ensure explainable AI decisions.
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main")]
            ])
            return text, keyboard

        # Format debate display
        debate_text = format_debate_summary(last_debate)

        text = f"""
{theme.AI} *BULL/BEAR DEBATE*
{'=' * 25}
{debate_text}

*Reasoning Chain:*
- Bull Analysis: {last_debate.get('tokens_used', 0) // 3} tokens
- Bear Analysis: {last_debate.get('tokens_used', 0) // 3} tokens
- Synthesis: {last_debate.get('tokens_used', 0) // 3} tokens
Total Cost: ${last_debate.get('cost_usd', 0):.4f}
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"{theme.CHECK} Execute Trade" if last_debate.get("recommendation") != "HOLD" else f"{theme.WARNING} Hold",
                    callback_data=f"demo:execute_debate_{last_debate.get('debate_id', '')}"
                ),
            ],
            [
                InlineKeyboardButton(f"{theme.CHART} Token Details", callback_data=f"demo:token_{token_id}"),
                InlineKeyboardButton(f"{theme.LIST} History", callback_data="demo:debate_history"),
            ],
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main")],
        ])

        return text, keyboard

    elif action == "debate_history":
        # Show debate history
        try:
            from core.reasoning_store import ReasoningStore
            store = ReasoningStore()
            recent_debates = store.query(limit=10)
        except ImportError:
            recent_debates = []

        if not recent_debates:
            text = f"""
{theme.LIST} *DEBATE HISTORY*

No debate history available yet.

Debates are recorded for:
- Compliance tracking
- Performance analysis
- AI learning and calibration
"""
        else:
            text = f"""
{theme.LIST} *RECENT DEBATES* ({len(recent_debates)})
{'=' * 25}

"""
            for debate in recent_debates[:5]:
                symbol = debate.get("symbol", "???")
                rec = debate.get("recommendation", "?")
                conf = debate.get("confidence", 0)
                outcome = debate.get("outcome", {})
                pnl = outcome.get("pnl_pct", 0) if outcome else None

                rec_emoji = {"BUY": "B", "SELL": "S", "HOLD": "H"}.get(rec, "?")

                line = f"{rec_emoji} {symbol}: {rec} @ {conf:.0f}%"
                if pnl is not None:
                    pnl_emoji = "+" if pnl >= 0 else "-"
                    line += f" -> {pnl_emoji}{abs(pnl):.1f}%"
                text += f"- {line}\n"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.CHART} Stats", callback_data="demo:debate_stats"),
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:debate_history"),
            ],
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main")],
        ])

        return text, keyboard

    elif action == "debate_stats":
        # Show debate statistics
        try:
            from core.ai.debate_integration import get_debate_evaluator
            evaluator = get_debate_evaluator()
            stats = evaluator.get_stats()
        except ImportError:
            stats = {}

        orchestrator_stats = stats.get("orchestrator", {})
        accuracy_stats = stats.get("accuracy", {})

        text = f"""
{theme.CHART} *DEBATE STATISTICS*
{'=' * 25}

*Usage:*
- Total Debates: {orchestrator_stats.get('total_debates', 0)}
- Total Tokens: {orchestrator_stats.get('total_tokens', 0):,}
- Total Cost: ${orchestrator_stats.get('total_cost_usd', 0):.4f}
- Avg Tokens/Debate: {orchestrator_stats.get('avg_tokens_per_debate', 0):.0f}

*Accuracy:*
- Total Decisions: {accuracy_stats.get('total_decisions', 0)}
- Overall Accuracy: {accuracy_stats.get('overall_accuracy', 0) * 100:.1f}%
- BUY Accuracy: {accuracy_stats.get('buy_accuracy', 0) * 100:.1f}%
- SELL Accuracy: {accuracy_stats.get('sell_accuracy', 0) * 100:.1f}%

*Why Bull/Bear Debate?*
- Explainable AI trading
- Reduces emotional bias
- Considers multiple perspectives
- Used by institutional hedge funds
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.LIST} History", callback_data="demo:debate_history"),
                InlineKeyboardButton(f"{theme.REFRESH} Refresh", callback_data="demo:debate_stats"),
            ],
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main")],
        ])

        return text, keyboard

    # Default
    return f"{theme.WARNING} Unknown debate action", InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main")]
    ])


__all__ = ["handle_debate", "format_debate_summary"]
