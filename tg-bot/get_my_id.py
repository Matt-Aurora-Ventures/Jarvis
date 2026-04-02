"""
Quick script to get your Telegram user ID.
Just run this, then message your bot on Telegram.
"""
import os
from pathlib import Path

# Load .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if value:
                    os.environ[key] = value

import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def capture_id(update: Update, context):
    user = update.effective_user
    chat = update.effective_chat

    print("\n" + "=" * 50)
    print("GOT YOUR ID!")
    print("=" * 50)
    print(f"\nYour Telegram User ID: {user.id}")
    print(f"Your Username: @{user.username}" if user.username else "No username set")
    print(f"Your Name: {user.first_name} {user.last_name or ''}")
    print("\n" + "=" * 50)
    print(f"\nNow run this command to set yourself as admin:")
    print(f"\n  python cli.py setid {user.id}")
    print("\n" + "=" * 50)

    await update.message.reply_text(
        f"Got it! Your user ID is: {user.id}\n\n"
        f"Check your terminal for the next steps!"
    )

    # Stop the bot after capturing
    print("\nStopping bot... You can close this window.")
    os._exit(0)

def main():
    if not TOKEN:
        print("ERROR: No TELEGRAM_BOT_TOKEN in .env")
        return

    # Single-instance lock to avoid Telegram polling conflicts
    try:
        import sys
        from pathlib import Path as _Path
        sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
        from core.utils.instance_lock import acquire_instance_lock
        lock = acquire_instance_lock(TOKEN, name="telegram_polling", max_wait_seconds=0)
    except Exception as exc:
        print(f"WARNING: Polling lock helper unavailable ({exc})")
        lock = None

    if not lock:
        print("ERROR: Telegram polling lock is already held by another process.")
        print("Stop the other process or use a different token.")
        return

    print("=" * 50)
    print("TELEGRAM ID CAPTURE")
    print("=" * 50)
    print("\n1. Open Telegram")
    print("2. Search for your bot: @Jarviskr8tivbot")
    print("3. Send any message (like 'hi')")
    print("\nWaiting for your message...")
    print("=" * 50)

    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, capture_id))
    app.add_handler(CommandHandler("start", capture_id))

    try:
        app.run_polling()
    finally:
        try:
            lock.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
