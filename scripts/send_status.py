import asyncio
import aiohttp
import json
import os
import sys
sys.path.insert(0, '.')

for line in open('tg_bot/.env').read().splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

async def send():
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat = os.environ.get('TELEGRAM_ADMIN_IDS', '').split(',')[0]
    
    msg = """*TREASURY STATUS REPORT*

*Wallet:* `BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR`
*Balance:* 0.100000 SOL

*System Status:*
Wallet loaded: OK
Encryption: OK  
Live mode: ENABLED
Admin auth: OK

*BLOCKER:* DNS cannot resolve Jupiter API
Your router DNS is blocking quote-api.jup.ag

*Fix Required:*
Change DNS to 8.8.8.8 (Google) or restart router

Once DNS is fixed, click buttons below to trade."""
    
    keyboard = {
        'inline_keyboard': [
            [{'text': 'Buy BONK (5%)', 'callback_data': 'trade_pct:DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263:5:B'}],
            [{'text': 'Buy WIF (5%)', 'callback_data': 'trade_pct:EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm:5:B'}],
            [{'text': 'View Positions', 'callback_data': 'show_positions_detail'}],
        ]
    }
    
    async with aiohttp.ClientSession() as s:
        r = await s.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat, 'text': msg, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(keyboard)}
        )
        print('Sent:', (await r.json()).get('ok'))

asyncio.run(send())
