"""Gather suggestions from Telegram chat history (last 24 hours)."""
import asyncio
import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

env_path = Path(__file__).resolve().parents[1] / "tg_bot" / ".env"
for line in env_path.read_text().splitlines():
    if line.strip() and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('\"'))

async def gather_suggestions():
    import aiohttp
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
    
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    
    # Keywords that might indicate suggestions/feedback
    suggestion_keywords = [
        'add', 'need', 'want', 'should', 'could', 'would be nice',
        'feature', 'suggestion', 'idea', 'request', 'improve',
        'fix', 'broken', 'bug', 'issue', 'problem', 'error',
        'please', 'can you', 'make it', 'wish', 'hope',
        '/price', '/gainers', '/losers', '/trending', 'command',
        'alert', 'notification', 'report', 'analysis'
    ]
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    
    async with aiohttp.ClientSession() as session:
        # Get updates
        async with session.get(url, params={"limit": 100, "offset": -100}) as resp:
            result = await resp.json()
        
        if not result.get("ok"):
            print("Failed to get updates:", result)
            return []
        
        suggestions = []
        messages = []
        
        for update in result.get("result", []):
            msg = update.get("message") or update.get("channel_post")
            if not msg:
                continue
            
            # Check if from our chat
            if str(msg.get("chat", {}).get("id")) != str(chat_id):
                continue
            
            text = msg.get("text", "")
            if not text:
                continue
            
            # Check timestamp
            msg_time = datetime.fromtimestamp(msg.get("date", 0), tz=timezone.utc)
            if msg_time < cutoff:
                continue
            
            # Get sender info
            sender = msg.get("from", {})
            username = sender.get("username", sender.get("first_name", "Unknown"))
            
            messages.append({
                "time": msg_time.isoformat(),
                "user": username,
                "text": text[:500],
                "msg_id": msg.get("message_id")
            })
            
            # Check if looks like a suggestion
            text_lower = text.lower()
            is_suggestion = any(kw in text_lower for kw in suggestion_keywords)
            
            # Skip bot messages and very short messages
            if sender.get("is_bot") or len(text) < 10:
                continue
            
            if is_suggestion:
                suggestions.append({
                    "time": msg_time.strftime("%Y-%m-%d %H:%M"),
                    "user": username,
                    "text": text[:300],
                    "msg_id": msg.get("message_id")
                })
        
        print(f"\n=== MESSAGES IN LAST 24H ({len(messages)} total) ===\n")
        for m in messages[-30:]:  # Last 30 messages
            print(f"[{m['time'][:16]}] @{m['user']}: {m['text'][:100]}...")
        
        print(f"\n\n=== POTENTIAL SUGGESTIONS ({len(suggestions)}) ===\n")
        for i, s in enumerate(suggestions, 1):
            print(f"{i}. [{s['time']}] @{s['user']}:")
            print(f"   \"{s['text']}\"")
            print()
        
        return suggestions

if __name__ == "__main__":
    asyncio.run(gather_suggestions())
