#!/usr/bin/env python3
"""
Unfreeze chat and send sentiment report (no buy buttons).
"""

import os
import asyncio
from pathlib import Path

# Manual .env loading
def load_env_manual():
    possible_paths = [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent / "tg_bot" / ".env",
    ]
    for env_path in possible_paths:
        if not env_path.exists():
            continue
        try:
            content = env_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = env_path.read_text(encoding='utf-16')
            except:
                content = env_path.read_text(encoding='latin-1')
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value
        print(f"Loaded env from: {env_path}")
        return

load_env_manual()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_BROADCAST_CHAT_ID") or os.getenv("TELEGRAM_BUY_BOT_CHAT_ID")


async def main():
    from telegram import Bot
    import aiohttp

    bot = Bot(token=TOKEN)

    # 1. Unfreeze the chat
    print(f"Unfreezing chat {CHAT_ID}...")
    try:
        await bot.set_chat_permissions(
            chat_id=CHAT_ID,
            permissions={
                "can_send_messages": True,
                "can_send_media_messages": True,
                "can_send_polls": True,
                "can_send_other_messages": True,
                "can_add_web_page_previews": True,
                "can_change_info": False,
                "can_invite_users": True,
                "can_pin_messages": False,
            }
        )
        print("[OK] Chat unfrozen!")
    except Exception as e:
        print(f"[WARN] Could not unfreeze chat: {e}")

    # 2. Generate sentiment report (no buy buttons)
    print("\nGenerating sentiment report...")

    try:
        # Fetch trending tokens from DexScreener
        async with aiohttp.ClientSession() as session:
            url = "https://api.dexscreener.com/token-boosts/top/v1"
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tokens = data[:10] if isinstance(data, list) else []
                else:
                    tokens = []

        if not tokens:
            # Fallback to Solana trending
            async with aiohttp.ClientSession() as session:
                url = "https://api.dexscreener.com/latest/dex/tokens/solana"
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tokens = data.get("pairs", [])[:10]

        # Build report message
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        message = f"""
*JARVIS Sentiment Report*
{now.strftime('%B %d, %Y')} | {now.strftime('%H:%M')} UTC

*Top Trending Tokens:*
"""

        for i, token in enumerate(tokens[:10], 1):
            if isinstance(token, dict):
                # Handle different API response formats
                symbol = token.get("tokenSymbol") or token.get("baseToken", {}).get("symbol", "???")
                name = token.get("tokenName") or token.get("baseToken", {}).get("name", "")
                price_change = token.get("priceChange24h") or token.get("priceChange", {}).get("h24", 0)

                try:
                    change_val = float(price_change) if price_change else 0
                    change_str = f"+{change_val:.1f}%" if change_val >= 0 else f"{change_val:.1f}%"
                except:
                    change_str = "N/A"

                message += f"{i}. *{symbol}* {change_str}\n"

        message += """
_Live trading starts today!_
_Use /sentiment <token> for detailed analysis._

*Status:* Bot operational
*Mode:* Ready for live trading
"""

        # Send the report
        print("Sending sentiment report...")
        msg = await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="Markdown"
        )
        print(f"[OK] Report sent! Message ID: {msg.message_id}")

    except Exception as e:
        print(f"[ERROR] Failed to generate report: {e}")
        import traceback
        traceback.print_exc()

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
