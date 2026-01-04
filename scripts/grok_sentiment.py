#!/usr/bin/env python3
"""Grok sentiment analysis for trading candidates."""

import json
import requests
from pathlib import Path

# Load XAI key
secrets_path = Path(__file__).parent.parent / "secrets" / "keys.json"
secrets = json.loads(secrets_path.read_text())
api_key = secrets.get("xai", {}).get("api_key")

if not api_key:
    print("No XAI API key found")
    exit(1)

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

prompt = """You are a crypto trading sentiment analyst with access to X/Twitter.

Search X for real-time sentiment on these Solana tokens RIGHT NOW:
1. FARTCOIN - meme coin
2. TRUMP - Official Trump token  
3. pippin - AI agent token
4. FAFO - Trending token (+1000% today)
5. WIF - dogwifhat

For each token, search X and report:
- Current sentiment (bullish/bearish/neutral) with confidence 0-100
- Volume of mentions in last 1 hour (high/medium/low)
- Key influencers talking about it (if any)
- Any catalysts or news driving momentum
- Risk flags (potential rug, dump incoming, etc.)

Also identify:
- Which token has the strongest POSITIVE momentum RIGHT NOW
- Which token is the best SHORT TERM scalp opportunity (next 1-4 hours)
- Any tokens I should AVOID

Be extremely current - I need real-time data, not historical. This is for a live trading decision."""

payload = {
    "model": "grok-4-1-fast-non-reasoning",
    "input": prompt,
    "tools": [{"type": "x_search"}],
    "tool_choice": "auto",
    "temperature": 0.2,
    "max_tokens": 3000,
}

print("Querying Grok for real-time X sentiment...")
resp = requests.post("https://api.x.ai/v1/responses", headers=headers, json=payload, timeout=120)

if resp.status_code == 200:
    data = resp.json()
    # Get the text response
    for item in data.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    print(content.get("text", ""))
else:
    print(f"Error: {resp.status_code}")
    print(resp.text)
