#!/usr/bin/env python3
"""Post sentiment report to X now - direct version."""
import asyncio
import os
import sys
import json
from pathlib import Path

# Fix encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

from bots.twitter.twitter_client import TwitterClient, TwitterCredentials


async def post():
    # Setup
    creds = TwitterCredentials(
        api_key=os.environ.get('X_API_KEY', ''),
        api_secret=os.environ.get('X_API_SECRET', ''),
        access_token=os.environ.get('X_ACCESS_TOKEN', ''),
        access_token_secret=os.environ.get('X_ACCESS_TOKEN_SECRET', ''),
        bearer_token=os.environ.get('X_BEARER_TOKEN', ''),
        oauth2_client_id=os.environ.get('X_OAUTH2_CLIENT_ID', ''),
        oauth2_client_secret=os.environ.get('X_OAUTH2_CLIENT_SECRET', ''),
        oauth2_access_token=os.environ.get('X_OAUTH2_ACCESS_TOKEN', ''),
        oauth2_refresh_token=os.environ.get('X_OAUTH2_REFRESH_TOKEN', ''),
    )

    twitter = TwitterClient(creds)

    # Connect
    connected = twitter.connect()
    print(f'Connected: {connected}')
    if not connected:
        return

    # Load latest predictions
    predictions_file = Path(__file__).parent.parent / "buy_tracker" / "predictions_history.json"
    with open(predictions_file, encoding="utf-8") as f:
        history = json.load(f)

    latest = history[-1]
    token_data = latest.get('token_predictions', {})

    # Get bullish/bearish
    bullish = [s for s, d in token_data.items() if d.get('verdict') == 'BULLISH']
    bearish = [s for s, d in token_data.items() if d.get('verdict') == 'BEARISH']

    # Top picks with contracts
    top_tokens = []
    for symbol, data in token_data.items():
        if data.get('verdict') == 'BULLISH' and data.get('contract'):
            top_tokens.append({
                'symbol': symbol,
                'reasoning': data.get('reasoning', ''),
                'contract': data.get('contract', ''),
                'targets': data.get('targets', ''),
                'score': data.get('score', 0),
            })
    top_tokens.sort(key=lambda x: x.get('score', 0), reverse=True)

    print(f'Bullish: {len(bullish)}, Bearish: {len(bearish)}')
    print(f'Top tokens: {[t["symbol"] for t in top_tokens[:3]]}')

    # Manual tweet generation in Jarvis voice
    t1 = top_tokens[0] if len(top_tokens) > 0 else None
    t2 = top_tokens[1] if len(top_tokens) > 1 else None

    # Tweet 1 - Hook
    tweet1 = f"big bro grok just finished scanning solana microcaps\n\n{len(bullish)} looking bullish, {len(bearish)} to avoid\n\nlet me break it down"

    # Tweet 2 - Top picks with CA
    if t1 and t2:
        ca1 = f"{t1['contract'][:6]}...{t1['contract'][-4:]}"
        ca2 = f"{t2['contract'][:6]}...{t2['contract'][-4:]}"
        tweet2 = f"top plays rn:\n\n${t1['symbol'].lower()} ({ca1})\n{t1['reasoning'][:60]}\n\n${t2['symbol'].lower()} ({ca2})\n{t2['reasoning'][:60]}"
    elif t1:
        ca1 = f"{t1['contract'][:6]}...{t1['contract'][-4:]}"
        tweet2 = f"watching ${t1['symbol'].lower()}\nca: {ca1}\n\n{t1['reasoning']}"

    # Tweet 3 - CTA
    tweet3 = f"full breakdown + more alpha in the tg\n\nt.me/kr8tiventry\n\nthis is not financial advice, dyor"

    tweets = [tweet1, tweet2, tweet3]

    print(f'Tweets to post: {len(tweets)}')

    # Post thread
    reply_to = None
    for i, tweet in enumerate(tweets):
        if len(tweet) > 280:
            tweet = tweet[:277] + '...'
        print(f'\nTweet {i+1} ({len(tweet)} chars):\n{tweet}')
        result = await twitter.post_tweet(tweet, reply_to=reply_to)
        if result.success:
            reply_to = result.tweet_id
            print(f'Posted: {result.url}')
        else:
            print(f'Failed: {result.error}')
        await asyncio.sleep(1)

    twitter.disconnect()
    print('\nDone!')


if __name__ == "__main__":
    asyncio.run(post())
