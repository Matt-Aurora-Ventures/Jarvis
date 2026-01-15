"""Fetch fresh sentiment data from Grok for X thread."""
import asyncio
import os
import sys
import json
import aiohttp
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Load env
for env_path in [Path(__file__).parent.parent.parent / 'tg_bot' / '.env', Path(__file__).parent / '.env']:
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


async def get_grok_analysis():
    xai_key = os.environ.get('XAI_API_KEY')

    async with aiohttp.ClientSession() as session:
        # 1. Get macro/geopolitics
        print('=== FETCHING MACRO ANALYSIS ===')
        macro_prompt = """Analyze current macro events and geopolitics affecting markets RIGHT NOW.

Provide analysis for:
1. SHORT TERM (Next 24-48 hours) - What's happening today/tomorrow?
2. MEDIUM TERM (This week) - Key events, data releases?
3. LONG TERM (Next month) - Major themes?

Also analyze:
- DXY (Dollar) direction and why
- US Stocks outlook and why
- How this affects risk assets

Be specific with dates, numbers, levels. No fluff.

Format:
SHORT|[analysis]
MEDIUM|[analysis]
LONG|[analysis]
DXY|[BULLISH/BEARISH/NEUTRAL]|[analysis]
STOCKS|[BULLISH/BEARISH/NEUTRAL]|[analysis]
CRYPTO_IMPACT|[how traditional markets affect crypto]"""

        async with session.post(
            'https://api.x.ai/v1/chat/completions',
            headers={'Authorization': f'Bearer {xai_key}', 'Content-Type': 'application/json'},
            json={'model': 'grok-3', 'messages': [{'role': 'user', 'content': macro_prompt}], 'max_tokens': 800, 'temperature': 0.6}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                macro = data['choices'][0]['message']['content'].strip()
                print(macro)
                print()
            else:
                macro = 'Macro analysis unavailable'
                print(f'Error: {resp.status}')

        # 2. Get stock picks (XStocks/PreStocks focus)
        print('=== FETCHING STOCK PICKS ===')
        stocks_prompt = """Give me your TOP 5 STOCK PICKS for the next week.

Focus on stocks that would be good for retail traders. Consider:
- Tech stocks (AAPL, NVDA, TSLA, META, GOOGL, MSFT, AMD, etc.)
- High-momentum names
- Stocks with clear catalysts

For each pick provide:
- Ticker
- BULLISH or BEARISH direction
- Detailed reasoning (30-50 words) - technicals, fundamentals, catalysts
- Specific price target
- Stop loss level

Format (one per line):
TICKER|DIRECTION|REASONING|TARGET|STOP_LOSS

Be specific and actionable."""

        async with session.post(
            'https://api.x.ai/v1/chat/completions',
            headers={'Authorization': f'Bearer {xai_key}', 'Content-Type': 'application/json'},
            json={'model': 'grok-3', 'messages': [{'role': 'user', 'content': stocks_prompt}], 'max_tokens': 600, 'temperature': 0.6}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                stocks = data['choices'][0]['message']['content'].strip()
                print(stocks)
                print()
            else:
                stocks = ''
                print(f'Error: {resp.status}')

        # 3. Get commodities
        print('=== FETCHING COMMODITIES ===')
        commodities_prompt = """Identify the TOP 5 COMMODITY MOVERS right now.

Consider: Oil, Natural Gas, Gold, Silver, Copper, Wheat, etc.

For each:
- Name
- Direction (UP/DOWN)
- Recent move
- Why it's moving (supply/demand, geopolitics, weather)
- Short-term outlook

Format:
COMMODITY|DIRECTION|CHANGE|REASON|OUTLOOK"""

        async with session.post(
            'https://api.x.ai/v1/chat/completions',
            headers={'Authorization': f'Bearer {xai_key}', 'Content-Type': 'application/json'},
            json={'model': 'grok-3', 'messages': [{'role': 'user', 'content': commodities_prompt}], 'max_tokens': 500, 'temperature': 0.6}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                commodities = data['choices'][0]['message']['content'].strip()
                print(commodities)
                print()
            else:
                commodities = ''

        # 4. Get precious metals
        print('=== FETCHING PRECIOUS METALS ===')
        metals_prompt = """Weekly outlook for Gold, Silver, and Platinum.

For each metal:
- Current trend direction
- Key price levels (support/resistance)
- Drivers (Fed, dollar, inflation, demand)
- Your call for the week

Format:
GOLD|DIRECTION|[detailed outlook with levels]
SILVER|DIRECTION|[detailed outlook with levels]
PLATINUM|DIRECTION|[detailed outlook with levels]"""

        async with session.post(
            'https://api.x.ai/v1/chat/completions',
            headers={'Authorization': f'Bearer {xai_key}', 'Content-Type': 'application/json'},
            json={'model': 'grok-3', 'messages': [{'role': 'user', 'content': metals_prompt}], 'max_tokens': 500, 'temperature': 0.6}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                metals = data['choices'][0]['message']['content'].strip()
                print(metals)
                print()
            else:
                metals = ''

        # 5. Get trending microcaps from multiple chains
        print('=== FETCHING TRENDING MICROCAPS (MULTI-CHAIN) ===')

        # Supported chains for trending tokens
        SUPPORTED_CHAINS = ['solana', 'ethereum', 'base', 'bsc', 'arbitrum']

        # First fetch trending tokens from DexScreener
        trending_tokens = []
        try:
            async with session.get('https://api.dexscreener.com/token-boosts/top/v1') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Get tokens from multiple chains (prioritize solana but include others)
                    multi_chain_tokens = [t for t in data if t.get('chainId') in SUPPORTED_CHAINS][:8]

                    for token in multi_chain_tokens:
                        addr = token.get('tokenAddress', '')
                        chain = token.get('chainId', 'unknown')
                        async with session.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}') as pair_resp:
                            if pair_resp.status == 200:
                                pair_data = await pair_resp.json()
                                pairs = pair_data.get('pairs', [])
                                if pairs:
                                    p = pairs[0]
                                    base = p.get('baseToken', {})
                                    txns = p.get('txns', {}).get('h24', {})
                                    trending_tokens.append({
                                        'symbol': base.get('symbol', '???'),
                                        'chain': chain.upper(),
                                        'price': float(p.get('priceUsd', 0) or 0),
                                        'change_24h': p.get('priceChange', {}).get('h24', 0) or 0,
                                        'volume': p.get('volume', {}).get('h24', 0) or 0,
                                        'mcap': p.get('marketCap', 0) or 0,
                                        'buys': txns.get('buys', 0),
                                        'sells': txns.get('sells', 0),
                                        'contract': base.get('address', addr),
                                    })
                        await asyncio.sleep(0.1)
        except Exception as e:
            print(f'DexScreener error: {e}')

        microcap_analysis = ''
        if trending_tokens:
            token_data = '\n'.join([
                f"{t['symbol']} ({t.get('chain', 'UNK')}): ${t['price']:.8f}, 24h: {t['change_24h']:+.1f}%, Vol: ${t['volume']:,.0f}, MCap: ${t['mcap']:,.0f}, B/S: {t['buys']}/{t['sells']}"
                for t in trending_tokens
            ])

            microcap_prompt = f"""Analyze these trending MICROCAP tokens from multiple chains. HIGH RISK lottery tickets.

{token_data}

For each token:
- Chain and sentiment: BULLISH/BEARISH/NEUTRAL
- Brief reasoning (why this sentiment based on metrics)
- If bullish: stop loss and targets (safe/medium/degen)

Format:
SYMBOL|CHAIN|SENTIMENT|REASONING|STOP_LOSS|TARGET_SAFE|TARGET_MED|TARGET_DEGEN

Be honest about the extreme risk. These can go to zero overnight."""

            async with session.post(
                'https://api.x.ai/v1/chat/completions',
                headers={'Authorization': f'Bearer {xai_key}', 'Content-Type': 'application/json'},
                json={'model': 'grok-3', 'messages': [{'role': 'user', 'content': microcap_prompt}], 'max_tokens': 600, 'temperature': 0.6}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    microcap_analysis = data['choices'][0]['message']['content'].strip()
                    print(microcap_analysis)
                else:
                    microcap_analysis = ''
        else:
            microcap_analysis = 'No trending tokens found'
            print(microcap_analysis)

        # Save all data for next step
        report_data = {
            'macro': macro,
            'stocks': stocks,
            'commodities': commodities,
            'metals': metals,
            'microcaps': microcap_analysis,  # Multi-chain microcaps (was solana-only)
            'tokens_raw': trending_tokens
        }

        output_path = Path(__file__).parent / 'sentiment_report_data.json'
        with open(output_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        print()
        print('=== DATA SAVED ===')
        print(f'Saved to: {output_path}')


if __name__ == '__main__':
    asyncio.run(get_grok_analysis())
