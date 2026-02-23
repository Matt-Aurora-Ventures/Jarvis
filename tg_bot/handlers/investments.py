"""Telegram handlers for investment service control.

Commands:
  /kill_investments   — Activate kill switch (admin only)
  /resume_investments — Deactivate kill switch (admin only)
  /invest_status      — Quick status summary
"""

from __future__ import annotations

import logging
import os

import httpx
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler, admin_only

logger = logging.getLogger(__name__)

# Investment service base URL (same host, different port)
_BASE_URL = os.getenv("INVESTMENTS_SERVICE_URL", "http://127.0.0.1:8770")


async def _api_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_BASE_URL}{path}")
        resp.raise_for_status()
        return resp.json()


async def _api_post(path: str, admin_key: str | None = None) -> dict:
    headers = {}
    if admin_key:
        headers["Authorization"] = f"Bearer {admin_key}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{_BASE_URL}{path}", headers=headers)
        resp.raise_for_status()
        return resp.json()


@error_handler
async def invest_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /invest_status — show current investment service status."""
    try:
        health = await _api_get("/health")
        kill = await _api_get("/api/investments/kill-switch")
        basket = await _api_get("/api/investments/basket")

        nav = basket.get("nav_usd", 0)
        tokens = basket.get("tokens", {})
        token_count = len(tokens)
        dry_run = health.get("dry_run", True)
        killed = kill.get("active", False)

        status_icon = "🔴" if killed else ("🟡" if dry_run else "🟢")
        mode = "KILLED" if killed else ("DRY RUN" if dry_run else "LIVE")

        lines = [
            f"<b>{status_icon} Investment Service — {mode}</b>",
            "",
            f"<b>NAV:</b> ${nav:,.2f}",
            f"<b>Tokens:</b> {token_count}",
        ]

        if tokens:
            lines.append("")
            for symbol, data in sorted(tokens.items(), key=lambda x: x[1].get("weight", 0), reverse=True):
                weight = data.get("weight", 0) * 100
                lines.append(f"  {symbol}: {weight:.1f}%")

        text = "\n".join(lines)

    except httpx.ConnectError:
        text = "⚠️ Investment service not running (port 8770 unreachable)"
    except Exception as exc:
        text = f"⚠️ Error fetching status: {exc}"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


@error_handler
@admin_only
async def kill_investments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kill_investments — activate kill switch (admin only)."""
    try:
        admin_key = os.environ.get("INVESTMENT_ADMIN_KEY", "")
        result = await _api_post("/api/investments/kill-switch/activate", admin_key or None)
        await update.message.reply_text(
            f"🔴 <b>Kill switch ACTIVATED</b>\nStatus: {result.get('status')}",
            parse_mode=ParseMode.HTML,
        )
    except httpx.ConnectError:
        await update.message.reply_text("⚠️ Investment service not running")
    except httpx.HTTPStatusError as exc:
        await update.message.reply_text(f"⚠️ Auth failed ({exc.response.status_code})")


@error_handler
@admin_only
async def resume_investments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /resume_investments — deactivate kill switch (admin only)."""
    try:
        admin_key = os.environ.get("INVESTMENT_ADMIN_KEY", "")
        result = await _api_post("/api/investments/kill-switch/deactivate", admin_key or None)
        await update.message.reply_text(
            f"🟢 <b>Kill switch DEACTIVATED</b>\nStatus: {result.get('status')}",
            parse_mode=ParseMode.HTML,
        )
    except httpx.ConnectError:
        await update.message.reply_text("⚠️ Investment service not running")
    except httpx.HTTPStatusError as exc:
        await update.message.reply_text(f"⚠️ Auth failed ({exc.response.status_code})")
