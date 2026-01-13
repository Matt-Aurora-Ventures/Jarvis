"""
Treasury Trade Test Script
Executes a small test trade and reports to Telegram.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aiohttp

# Load env from tg_bot/.env
env_path = ROOT / "tg_bot" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_IDS", "").split(",")[0].strip()
TREASURY_ADDRESS = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"

# Popular liquid tokens for test trading
TEST_TOKENS = [
    {"symbol": "BONK", "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "name": "Bonk"},
    {"symbol": "WIF", "mint": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "name": "dogwifhat"},
    {"symbol": "JUP", "mint": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", "name": "Jupiter"},
]


async def get_sol_balance():
    """Get SOL balance of treasury."""
    async with aiohttp.ClientSession() as session:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [TREASURY_ADDRESS]
        }
        async with session.post("https://api.mainnet-beta.solana.com", json=payload) as resp:
            data = await resp.json()
            lamports = data.get("result", {}).get("value", 0)
            return lamports / 1e9


async def get_sol_price():
    """Get current SOL price in USD."""
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd") as resp:
            data = await resp.json()
            return data.get("solana", {}).get("usd", 0)


async def send_telegram_message(text: str, reply_markup: dict = None):
    """Send a message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_ID:
        print("ERROR: Telegram not configured")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_ADMIN_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            result = await resp.json()
            if result.get("ok"):
                print(f"Message sent to Telegram")
                return True
            else:
                print(f"Telegram error: {result}")
                return False


async def send_treasury_report():
    """Send a treasury report with buy buttons."""
    sol_balance = await get_sol_balance()
    sol_price = await get_sol_price()
    usd_value = sol_balance * sol_price
    
    # Build report
    report = f"""📊 *TREASURY REPORT*

💰 *Balance:* `{sol_balance:.6f}` SOL
💵 *Value:* ~${usd_value:.2f} USD
📍 *Address:* `{TREASURY_ADDRESS[:8]}...{TREASURY_ADDRESS[-6:]}`

🔄 *Available Trades:*
Select a token to trade with the treasury wallet.

⚠️ *Risk Controls Active:*
• Max trade: $100 / 5% portfolio
• Daily limit: $500
• TP/SL required for all trades
"""
    
    # Build inline keyboard with buy buttons
    keyboard = {
        "inline_keyboard": [
            [
                {"text": f"🐕 Buy BONK (5%)", "callback_data": f"trade_pct:DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263:5:B"},
            ],
            [
                {"text": f"🐶 Buy WIF (5%)", "callback_data": f"trade_pct:EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm:5:B"},
            ],
            [
                {"text": f"🪐 Buy JUP (5%)", "callback_data": f"trade_pct:JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN:5:B"},
            ],
            [
                {"text": "📋 View Positions", "callback_data": "show_positions_detail"},
                {"text": "📊 Full Report", "callback_data": "refresh_report"},
            ],
        ]
    }
    
    success = await send_telegram_message(report, keyboard)
    return success


async def main():
    print("=" * 50)
    print("TREASURY TRADE TEST")
    print("=" * 50)
    
    # Step 1: Check balance
    balance = await get_sol_balance()
    print(f"\n[OK] Treasury Balance: {balance:.6f} SOL")
    
    if balance < 0.01:
        print("ERROR: Insufficient balance for test trade")
        return
    
    # Step 2: Send report to Telegram
    print("\n-> Sending treasury report to Telegram...")
    await send_treasury_report()
    
    print("\n" + "=" * 50)
    print("REPORT SENT - Check Telegram for buy buttons")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
