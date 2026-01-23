"""Format Grok sentiment data into X thread with authentic Jarvis voice."""
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

# Load voice bible for context
voice_bible_path = Path(__file__).parent.parent.parent / 'lifeos' / 'context' / 'jarvis_voice_bible.md'
with open(voice_bible_path, encoding='utf-8') as f:
    voice_bible = f.read()[:8000]  # First 8k chars for context

# Build the report
full_report = f"""
MACRO ANALYSIS:
{data['macro']}

STOCK PICKS:
{data['stocks']}

COMMODITIES:
{data['commodities']}

PRECIOUS METALS:
{data['metals']}

CRYPTO MICROCAPS (MULTI-CHAIN):
{data.get('microcaps', data.get('solana', ''))}
"""

prompt = f"""You ARE Jarvis. Here is your voice bible - internalize this completely:

{voice_bible}

---

Now transform this Grok sentiment data into a THREAD for X (Twitter). With X Premium, each tweet can be longer (up to 4000 chars), so be substantive.

CRITICAL REQUIREMENTS FOR THIS REPORT:
1. This is TESTING PHASE - warn heavily, we are still calibrating
2. Microcap tokens are LOTTERY TICKETS - extreme risk, most go to zero
3. Stocks are available via XStocks.fi and PreStocks.com (tokenized on Solana)
4. Credit big brother Grok for the analysis - you just present it
5. Keep all the DATA intact - prices, targets, levels, percentages
6. Use lowercase, casual energy, self-aware AI humor
7. Reference your chrome skull, circuits, neural weights naturally
8. Include NFA naturally, not robotically

STRUCTURE:
1/ intro - announce the report, heavy warnings about testing phase
2/ macro outlook - short/medium/long term, keep the dates and levels
3/ traditional markets - DXY and stocks, keep specific numbers
4/ stock picks - the 5 picks with all targets (mention xStocks/PreStocks)
5/ commodities - the 5 movers with why
6/ precious metals - gold/silver/platinum with levels
7/ crypto microcaps - the lottery tickets with HEAVY warnings
8/ closing - final disclaimer, building in public vibe

Format:
---TWEET 1---
[content]
---TWEET 2---
[content]
etc.

GROK'S RAW DATA:
{full_report}
"""

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
    output_path = Path(__file__).parent / 'thread_jarvis_voice.txt'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(thread)
    print(f"\n\nSaved to: {output_path}")
else:
    print(f'Error: {response.status_code}')
    print(response.text)
