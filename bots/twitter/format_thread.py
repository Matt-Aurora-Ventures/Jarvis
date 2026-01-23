"""Format Grok sentiment data into X thread via Claude."""
from pathlib import Path
import json
import os
import sys

import requests

from core.llm.anthropic_utils import get_anthropic_messages_url, get_anthropic_api_key

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Load env
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

anthropic_key = get_anthropic_api_key()
anthropic_url = get_anthropic_messages_url()
if not anthropic_url:
    raise SystemExit("Anthropic-compatible endpoint not configured (set ANTHROPIC_BASE_URL)")

# Load Grok data
data_path = Path(__file__).parent / 'sentiment_report_data.json'
with open(data_path, encoding='utf-8') as f:
    data = json.load(f)

# Build the full report for Claude to reformat
full_report = f"""
=== GROK SENTIMENT REPORT DATA ===

MACRO ANALYSIS:
{data['macro']}

STOCK PICKS:
{data['stocks']}

COMMODITIES:
{data['commodities']}

PRECIOUS METALS:
{data['metals']}

CRYPTO MICROCAPS - MULTI-CHAIN (LOTTERY TICKETS):
{data.get('microcaps', data.get('solana', ''))}
"""

prompt = """You are JARVIS - Tony Stark's AI assistant. Sophisticated, calm, subtle wit, self-aware. NO EMOJIS ALLOWED.

Transform this Grok sentiment report into a THREAD for X (Twitter). With Premium, each tweet can be up to 4000 characters, so make them substantive.

CRITICAL REQUIREMENTS:
1. WARN HEAVILY that this is still being tested - we are calibrating, be super careful
2. Microcap tokens are LOTTERY TICKETS - extreme risk, can go to zero
3. Stocks mentioned are available via XStocks.fi and PreStocks.com (tokenized stocks on Solana)
4. Credit Grok for the analysis - JARVIS just presents it
5. Be measured and careful in tone - not hype, not FUD, just facts
6. Include specific price targets, stop losses, levels where available
7. Include disclaimers throughout
8. ABSOLUTELY NO EMOJIS - this is JARVIS, not a crypto bro

Structure the thread as:
1/ INTRO - System announcement, warnings about testing phase
2/ MACRO OUTLOOK - Short/Medium/Long term
3/ TRADITIONAL MARKETS - DXY and Stocks outlook
4/ STOCK PICKS - The 5 picks with targets (mention XStocks/PreStocks)
5/ COMMODITIES - The 5 movers
6/ PRECIOUS METALS - Gold/Silver/Platinum
7/ CRYPTO MICROCAPS - The lottery tickets with heavy warnings
8/ CLOSING - Final disclaimer, building in public

Format each tweet like:
---TWEET 1---
[content]
---TWEET 2---
[content]
etc.

Here is the raw Grok data:

""" + full_report

response = requests.post(
    anthropic_url,
    headers={
        'x-api-key': anthropic_key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    },
    json={
        'model': 'claude-sonnet-4-20250514',
        'max_tokens': 6000,
        'messages': [{'role': 'user', 'content': prompt}],
    }
)

if response.status_code == 200:
    result = response.json()
    thread = result['content'][0]['text'].strip()
    print(thread)

    # Save to file
    output_path = Path(__file__).parent / 'thread_draft.txt'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(thread)
    print(f"\n\nSaved to: {output_path}")
else:
    print(f'Error: {response.status_code}')
    print(response.text)
