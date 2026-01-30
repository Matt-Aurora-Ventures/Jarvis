"""tg_bot.handlers.commands.news_command

/news [token]

Dexter news: pulls recent market headlines/events and formats them in Jarvis voice.

Design goals:
- Works even if external APIs (CryptoPanic/LunarCrush) are not configured
- Telegram-safe formatting (Markdown)
- Short, punchy, lowercase (Jarvis voice)

If a token/symbol is provided, filters to events mentioning it.
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler

logger = logging.getLogger(__name__)


def _clean_symbol(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("$"):
        s = s[1:]
    # keep it simple: alnum only
    s = "".join(ch for ch in s if ch.isalnum())
    return s.upper()


def _jarvis_news_format(title: str, sentiment: str, priority: str, url: Optional[str] = None) -> str:
    # jarvis voice: lowercase, short. keep emoji minimal.
    sent = sentiment.lower() if sentiment else "neutral"
    pri = priority.lower() if priority else "low"

    tag = ""
    if pri in ("critical", "high"):
        tag = "⚠️ "

    # Avoid markdown injection
    safe_title = title.replace("*", "").replace("_", "")

    line = f"{tag}{safe_title}\n"
    line += f"   {sent} • {pri}"
    if url:
        line += f"\n   {url}"
    return line


@error_handler
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /news [token]."""
    try:
        from core.autonomy.news_detector import get_news_detector
    except Exception as e:
        logger.error(f"news detector import failed: {e}")
        await update.message.reply_text(
            "news module isn't wired on this box yet. give me a minute.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    symbol = _clean_symbol(context.args[0]) if getattr(context, "args", None) else ""

    detector = get_news_detector()

    # Always scan fresh for /news (fast feedback)
    try:
        await update.message.chat.send_action("typing")
        await detector.scan_news()
    except Exception as e:
        # If APIs missing, scan_news may return empty; we still respond
        logger.warning(f"news scan failed: {e}")

    events = detector.events or []
    if symbol:
        events = detector.get_events_for_token(symbol)

    if not events:
        if symbol:
            msg = f"no clean headlines for ${symbol} right now. either it's quiet or my feeds are."  # jarvis tone
        else:
            msg = "news feeds are quiet (or not configured). ask again later."  # jarvis tone
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        return

    # Sort by priority then confidence
    events_sorted = sorted(
        events,
        key=lambda e: (getattr(e.priority, "value", 0), getattr(e, "confidence", 0.0)),
        reverse=True,
    )

    header = "📰 *dexter news*\n"
    if symbol:
        header += f"for *${symbol}*\n"
    header += "\n"

    lines = []
    for e in events_sorted[:6]:
        url = getattr(e, "url", None)
        lines.append(
            _jarvis_news_format(
                title=getattr(e, "title", ""),
                sentiment=getattr(e, "sentiment", "neutral"),
                priority=getattr(getattr(e, "priority", None), "name", "low"),
                url=url,
            )
        )

    footer = "\n" + "nfa. headlines move fast. so does liquidity."  # jarvis tone

    await update.message.reply_text(
        header + "\n\n".join(lines) + footer,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )
