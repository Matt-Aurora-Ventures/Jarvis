#!/usr/bin/env python3
"""Test single post to Twitter using Claude + Grok sentiment data."""
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
for env_path in [
    Path(__file__).parent / ".env",
    Path(__file__).parent.parent.parent / "tg_bot" / ".env",
]:
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

from bots.twitter.twitter_client import TwitterClient, TwitterCredentials
from bots.twitter.claude_content import ClaudeContentGenerator


async def test_post():
    print("=" * 50)
    print("  TEST POST: Claude + Grok -> Twitter")
    print("=" * 50)
    print()

    # Setup Twitter
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
    claude = ClaudeContentGenerator(api_key=os.environ.get('ANTHROPIC_API_KEY'))

    # Connect Twitter
    connected = twitter.connect()
    print(f"Twitter connected: {connected}")
    if not connected:
        print("Failed to connect to Twitter")
        return

    # Load latest predictions
    predictions_file = Path(__file__).parent.parent / "buy_tracker" / "predictions_history.json"
    with open(predictions_file, encoding="utf-8") as f:
        history = json.load(f)

    latest = history[-1]
    token_data = latest.get('token_predictions', {})

    # Count sentiments
    bullish = [s for s, d in token_data.items() if d.get('verdict') == 'BULLISH']
    bearish = [s for s, d in token_data.items() if d.get('verdict') == 'BEARISH']
    neutral = [s for s, d in token_data.items() if d.get('verdict') == 'NEUTRAL']

    # Get top bullish picks with contracts
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

    print(f"\nGrok Data:")
    print(f"  Bullish: {len(bullish)}")
    print(f"  Bearish: {len(bearish)}")
    print(f"  Neutral: {len(neutral)}")
    print(f"  Top picks: {[t['symbol'] for t in top_tokens[:3]]}")
    print()

    # Build sentiment summary for Claude
    sentiment_summary = f"""
Grok's Solana Microcap Scan:

Stats: {len(bullish)} bullish | {len(bearish)} bearish | {len(neutral)} neutral

TOP BULLISH PICKS:
"""
    for i, t in enumerate(top_tokens[:3], 1):
        contract = t['contract']
        short_ca = f"{contract[:6]}...{contract[-4:]}" if len(contract) > 10 else contract
        sentiment_summary += f"""
{i}. ${t['symbol'].upper()}
   Why: {t['reasoning']}
   CA: {short_ca}
   Targets: {t['targets']}
"""

    if bearish:
        sentiment_summary += f"\nBEARISH (avoid): {', '.join(bearish[:3])}"

    # Generate tweets with Claude - simple single tweet first
    t1 = top_tokens[0] if top_tokens else None
    t2 = top_tokens[1] if len(top_tokens) > 1 else None

    prompt = f"""Write ONE tweet about grok's solana microcap scan.

Data: {len(bullish)} bullish, {len(bearish)} bearish
Top pick: ${t1['symbol'] if t1 else 'none'} with contract {t1['contract'][:6]}...{t1['contract'][-4:] if t1 else ''}

Include: mention "big bro grok", the stats, casual lowercase energy, NFA
Under 280 chars. Just the tweet text, no JSON or formatting."""

    print("Generating tweets with Claude (Voice Bible)...")
    response = await claude.generate_tweet(prompt, temperature=0.85)

    if not response.success:
        print(f"Claude failed: {response.error}")
        return

    print(f"\nClaude response:\n{response.content}\n")

    # Use the single tweet directly
    tweets = [response.content.strip()]

    print(f"Tweets to post: {len(tweets)}")
    for i, tweet in enumerate(tweets, 1):
        print(f"\n--- Tweet {i} ({len(tweet)} chars) ---")
        print(tweet)

    print("\n" + "=" * 50)
    print("Posting to @Jarvis_lifeos...")

    # Post thread
    reply_to = None
    for i, tweet in enumerate(tweets):
        if len(tweet) > 280:
            tweet = tweet[:277] + '...'
        print(f'\nPosting tweet {i+1}...')
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
    asyncio.run(test_post())
