#!/usr/bin/env python3
"""Diagnose Telegram UI handler wiring and send a test inline keyboard."""

import argparse
import asyncio
import os
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application


def _format_handler(handler) -> str:
    name = type(handler).__name__
    commands = getattr(handler, "commands", None)
    if commands:
        return f"{name}: {sorted(list(commands))}"
    return name


def _print_handlers(app: Application) -> None:
    for group, handlers in sorted(app.handlers.items()):
        print(f"group {group}: {len(handlers)}")
        for handler in handlers:
            print(f"  - {_format_handler(handler)}")


async def _build_app(mode: str, token: str) -> Application:
    app = Application.builder().token(token).build()
    if mode == "main":
        import tg_bot.bot as main_bot

        config = main_bot.get_config()
        main_bot.register_handlers(app, config)
    elif mode == "public":
        from tg_bot.public_bot_handler import PublicBotHandler
        from tg_bot.public_trading_bot_integration import register_public_handlers

        handler = PublicBotHandler(trading_engine=None)
        register_public_handlers(app, handler)
    else:
        raise ValueError(f"Unknown mode: {mode}")
    return app


async def _run(mode: str, token: str, chat_id: Optional[str]) -> int:
    app = await _build_app(mode, token)
    await app.initialize()
    try:
        me = await app.bot.get_me()
        print(f"token ok: @{me.username} ({me.id})")
        _print_handlers(app)

        if chat_id:
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Ping", callback_data="ui_test_ping")]]
            )
            await app.bot.send_message(
                chat_id=chat_id,
                text="Jarvis UI test",
                reply_markup=keyboard,
            )
            print(f"sent test message to chat_id={chat_id}")
    finally:
        await app.shutdown()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose Telegram bot UI wiring.")
    parser.add_argument("--mode", choices=["main", "public"], default="main")
    parser.add_argument("--token", default=os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    parser.add_argument("--chat-id", default=os.environ.get("TG_DIAG_CHAT_ID", ""))
    args = parser.parse_args()

    if not args.token:
        print("Missing token. Set TELEGRAM_BOT_TOKEN or pass --token.")
        return 1

    chat_id = args.chat_id.strip() or None
    return asyncio.run(_run(args.mode, args.token, chat_id))


if __name__ == "__main__":
    raise SystemExit(main())
