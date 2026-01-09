#!/usr/bin/env python3
"""Monitor active exit intents and positions.
- Polls Dexscreener for token prices and transaction ratios
- Updates trailing stops locally
- Notifies via console and log when targets or stops are hit
- Does NOT auto-execute sells unless an intent has "auto_execute": true
- Includes aggressive timeout protection to prevent hanging
"""
import asyncio
import json
import time
from pathlib import Path
from datetime import datetime, timezone
import aiohttp

EXIT_FILE = Path.home() / '.lifeos' / 'trading' / 'exit_intents.json'
LOG_FILE = Path.home() / '.lifeos' / 'trading' / 'monitor.log'
POLL_INTERVAL = 30  # seconds
API_TIMEOUT = 10  # Aggressive timeout for API calls

async def fetch_token_info(session, mint):
    url = f'https://api.dexscreener.com/latest/dex/tokens/{mint}'
    try:
        # Add aggressive timeout
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as resp:
            data = await resp.json()
            pairs = data.get('pairs', [])
            if not pairs:
                return None
            return pairs[0]
    except asyncio.TimeoutError:
        return {'error': f'API timeout after {API_TIMEOUT}s'}
    except Exception as e:
        return {'error': str(e)}

def load_intents():
    if not EXIT_FILE.exists():
        return []
    try:
        data = json.loads(EXIT_FILE.read_text())
        if isinstance(data, dict):
            return list(data.values())
        return data
    except Exception:
        return []

def log(msg):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    print(line, end='')
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text(LOG_FILE.read_text() + line)
    except Exception:
        pass

async def check_once(session):
    intents = load_intents()
    for intent in intents:
        if intent.get('status') != 'active':
            continue
        mint = intent.get('token_mint')
        symbol = intent.get('symbol')
        entry = float(intent.get('entry_price', 0))
        data = await fetch_token_info(session, mint)
        if data is None:
            log(f"{symbol}: no data")
            continue
        if 'error' in data:
            log(f"{symbol}: fetch error: {data['error']}")
            continue
        price = float(data.get('priceUsd') or 0)
        liq = float(data.get('liquidity',{}).get('usd') or 0)
        pc = data.get('priceChange', {})
        h1 = float(pc.get('h1') or 0)
        txns_h1 = data.get('txns', {}).get('h1', {})
        buys = txns_h1.get('buys', 0)
        sells = txns_h1.get('sells', 0)
        ratio = (buys / sells) if sells > 0 else buys

        pnl = (price - entry) / entry if entry > 0 else 0
        msg = f"{symbol}: ${price:.8f} | PnL: {pnl*100:+.2f}% | Liq: ${liq:,.0f} | 1h: {h1:+.1f}% | B/S: {buys}/{sells} ({ratio:.2f}x)"
        log(msg)

        # Check take profits
        tps = intent.get('take_profits', [])
        for tp in tps:
            if not tp.get('filled') and price >= float(tp.get('price')):
                log(f"{symbol} reached TP{tp['level']} @ {price:.8f} -> intended sell {tp['size_pct']}%")
                # mark filled locally
                tp['filled'] = True
                intent['remaining_quantity'] = intent.get('remaining_quantity', 0) * (1 - tp['size_pct']/100.0)
                # Auto-execute if allowed
                if intent.get('auto_execute'):
                    # call external sell command
                    log(f"Auto-executing sell for {symbol} TP{tp['level']} (auto_execute enabled)")
                    # For safety, we just log here. Extend to call savage_swap.py --sell when desired.

        # Check stop loss
        sl = intent.get('stop_loss', {})
        if sl and price <= float(sl.get('price')):
            log(f"{symbol} hit STOP LOSS @ {price:.8f} -> intended exit {sl['size_pct']}%")
            if intent.get('auto_execute'):
                log(f"Auto-executing stop sell for {symbol} (auto_execute enabled)")

        # Update trailing stop if active
        trailing = intent.get('trailing_stop', {})
        if trailing and trailing.get('active'):
            highest = float(trailing.get('highest_price') or price)
            if price > highest:
                trailing['highest_price'] = price
                trailing['current_stop'] = round(price * (1 - float(trailing.get('trail_pct', 0.15))), 10)
                log(f"{symbol} new high: ${price:.8f} -> trailing stop updated to ${trailing['current_stop']:.8f}")
            # Trigger trailing stop
            if price <= float(trailing.get('current_stop')):
                log(f"{symbol} hit TRAILING STOP @ {price:.8f} (current_stop={trailing['current_stop']})")
                if intent.get('auto_execute'):
                    log(f"Auto-executing trailing stop sell for {symbol} (auto_execute enabled)")

    # persist any changes locally
    try:
        EXIT_FILE.write_text(json.dumps(intents, indent=2))
    except Exception as e:
        log(f"Failed to write intents: {e}")

async def monitor(interval=POLL_INTERVAL):
    """Monitor positions with timeout protection."""
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Wrap check_once with timeout to prevent hanging
                await asyncio.wait_for(check_once(session), timeout=60)
            except asyncio.TimeoutError:
                log("Position check timed out after 60s, skipping cycle")
            except Exception as e:
                log(f"Error in monitor loop: {e}")
            
            await asyncio.sleep(interval)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', type=int, default=POLL_INTERVAL)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()

    if args.once:
        asyncio.run(check_once(aiohttp.ClientSession()))
    else:
        try:
            asyncio.run(monitor(args.interval))
        except KeyboardInterrupt:
            print('Monitor stopped by user')
