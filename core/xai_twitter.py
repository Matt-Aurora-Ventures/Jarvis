"""XAI/Grok API client for X/Twitter trading sentiment analysis."""

from __future__ import annotations

import json
import os
import time
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from core import config

ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / "secrets" / "keys.json"
CACHE_DIR = ROOT / "data" / "trader" / "xai_cache"
CACHE_PATH = CACHE_DIR / "xai_twitter_cache.json"
USAGE_PATH = ROOT / "data" / "trader" / "grok_usage.json"


def load_api_key() -> Optional[str]:
    """Load XAI API key from secrets file."""
    if not SECRETS_PATH.exists():
        return None
    try:
        data = json.loads(SECRETS_PATH.read_text())
        return data.get("xai", {}).get("api_key")
    except (json.JSONDecodeError, KeyError):
        return None


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _budget_config() -> Dict[str, Any]:
    cfg = config.load_config()
    policy = cfg.get("sentiment_spend_policy", {})
    return {
        "enabled": bool(policy.get("enabled", True)),
        "daily_budget_usd": float(policy.get("daily_budget_usd", 3.0)),
        "warn_at_usd": float(policy.get("warn_at_usd", 3.0)),
        "per_request_cost_usd": float(policy.get("per_request_cost_usd", 0.05)),
        "ttl_seconds": int(policy.get("ttl_seconds", 3600)),
    }


def _usage_key() -> str:
    return time.strftime("%Y-%m-%d")


def _check_budget(requests_needed: int = 1) -> bool:
    policy = _budget_config()
    if not policy["enabled"]:
        return True
    usage = _load_json(USAGE_PATH)
    day_key = _usage_key()
    daily = usage.get(day_key, {"requests": 0, "cost_usd": 0.0})
    projected_cost = daily["cost_usd"] + (requests_needed * policy["per_request_cost_usd"])
    return projected_cost <= policy["daily_budget_usd"]


def _record_usage(requests_used: int) -> None:
    policy = _budget_config()
    if not policy["enabled"]:
        return
    usage = _load_json(USAGE_PATH)
    day_key = _usage_key()
    daily = usage.get(day_key, {"requests": 0, "cost_usd": 0.0})
    daily["requests"] = int(daily.get("requests", 0)) + requests_used
    daily["cost_usd"] = float(daily.get("cost_usd", 0.0)) + (requests_used * policy["per_request_cost_usd"])
    usage[day_key] = daily
    _write_json(USAGE_PATH, usage)


def _cache_key(*parts: str) -> str:
    payload = "::".join(parts).encode("utf-8")
    return sha256(payload).hexdigest()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    policy = _budget_config()
    cache = _load_json(CACHE_PATH)
    entry = cache.get(key)
    if not entry:
        return None
    if time.time() - float(entry.get("timestamp", 0)) > policy["ttl_seconds"]:
        return None
    return entry.get("payload")


def _cache_set(key: str, payload: Dict[str, Any]) -> None:
    cache = _load_json(CACHE_PATH)
    cache[key] = {
        "timestamp": time.time(),
        "payload": payload,
    }
    _write_json(CACHE_PATH, cache)


def analyze_trader_tweets(
    handle: str,
    *,
    max_results: int = 50,
    focus: str = "crypto trading calls, token mentions, buy/sell signals",
) -> Dict[str, Any]:
    """
    Use Grok with X search to analyze a trader's tweet history.
    
    Returns analysis of win/loss ratio based on historical calls.
    """
    cache_key = _cache_key("analysis", handle.lower(), str(max_results), focus)
    cached = _cache_get(cache_key)
    if cached:
        cached["cached"] = True
        return cached

    if not _check_budget(1):
        return {"error": "XAI budget exceeded", "cached": False}

    api_key = load_api_key()
    if not api_key:
        return {"error": "XAI API key not found in secrets/keys.json"}
    
    # Use Grok with live search to analyze the trader's history
    prompt = f"""Analyze the X/Twitter account @{handle} for crypto trading performance.

Search their recent tweets (last 30-60 days) and identify:
1. All token/coin calls they made (buy signals, mentions of specific tokens with bullish sentiment)
2. For each call, note:
   - The token mentioned (symbol and contract if available)
   - The date/time of the call
   - Their apparent conviction level (strong call vs casual mention)
   - Whether they mentioned a target price or exit strategy

3. Try to determine outcomes by:
   - Looking for follow-up tweets about the same tokens
   - Checking if they mentioned wins/losses
   - Any "told you so" or regret posts

4. Calculate:
   - Estimated win rate (% of calls that appeared profitable)
   - Average conviction score on their calls
   - Their trading style (scalper, swing trader, long-term holder)
   - Red flags (if any) - e.g., paid promotions, rug history

Be honest about data limitations - if you can't verify outcomes, say so.
Focus on: {focus}

Return a structured analysis with concrete numbers where possible."""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # Use the Responses API with x_search tool
    system_prompt = "You are a crypto trading analyst. Search X to find and analyze trading calls. Be precise with numbers and honest about uncertainty."
    payload = {
        "model": "grok-4-1-fast-non-reasoning",
        "input": f"{system_prompt}\n\n{prompt}",
        "tools": [
            {
                "type": "x_search",
                "allowed_x_handles": [handle],
            }
        ],
        "tool_choice": "auto",
        "temperature": 0.3,
        "max_tokens": 4000,
    }

    try:
        resp = requests.post(
            "https://api.x.ai/v1/responses",
            headers=headers,
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        result = resp.json()

        # Extract the analysis from the response
        # The responses API returns output with tool calls and message
        content = ""
        if isinstance(result, dict):
            output = result.get("output", [])
            if isinstance(output, list):
                for item in output:
                    item_type = item.get("type", "")
                    # Handle message type (contains the actual response)
                    if item_type == "message":
                        msg_content = item.get("content", [])
                        for c in msg_content:
                            if c.get("type") == "output_text":
                                content += c.get("text", "")
                    # Handle direct text type
                    elif item_type == "text":
                        content += item.get("text", "")
        
        payload = {
            "handle": handle,
            "analysis": content,
            "model": payload["model"],
            "raw_response": result,
        }
        _cache_set(cache_key, payload)
        _record_usage(1)
        return payload
        
    except requests.HTTPError as e:
        error_body = ""
        try:
            error_body = e.response.text
        except Exception:
            pass
        return {"error": f"API request failed: {str(e)}", "details": error_body}
    except requests.RequestException as e:
        return {"error": f"API request failed: {str(e)}"}


def quick_sentiment_check(handle: str) -> Dict[str, Any]:
    """Quick check of a trader's recent sentiment (uses fewer API credits)."""
    cache_key = _cache_key("quick", handle.lower())
    cached = _cache_get(cache_key)
    if cached:
        cached["cached"] = True
        return cached

    if not _check_budget(1):
        return {"error": "XAI budget exceeded", "cached": False}

    api_key = load_api_key()
    if not api_key:
        return {"error": "XAI API key not found"}
    
    prompt = f"""Check @{handle}'s last 10-20 tweets. 
What tokens are they currently bullish on? 
Any specific calls with contract addresses?
Rate their current sentiment: very bullish / bullish / neutral / bearish / very bearish.
Keep response brief and actionable."""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "grok-4-1-fast-non-reasoning",
        "input": prompt,
        "tools": [
            {
                "type": "x_search",
                "allowed_x_handles": [handle],
            }
        ],
        "tool_choice": "auto",
        "temperature": 0.2,
        "max_tokens": 1000,
    }

    try:
        resp = requests.post(
            "https://api.x.ai/v1/responses",
            headers=headers,
            json=payload,
            timeout=90,
        )
        resp.raise_for_status()
        result = resp.json()
        content = ""
        if isinstance(result, dict):
            output = result.get("output", [])
            if isinstance(output, list):
                for item in output:
                    item_type = item.get("type", "")
                    if item_type == "message":
                        msg_content = item.get("content", [])
                        for c in msg_content:
                            if c.get("type") == "output_text":
                                content += c.get("text", "")
                    elif item_type == "text":
                        content += item.get("text", "")
        payload = {"handle": handle, "sentiment": content}
        _cache_set(cache_key, payload)
        _record_usage(1)
        return payload
    except requests.RequestException as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import sys
    handle = sys.argv[1] if len(sys.argv) > 1 else "xinsanity"
    print(f"Analyzing @{handle}...")
    result = analyze_trader_tweets(handle)
    if "error" in result:
        print(f"Error: {result['error']}")
        if result.get("details"):
            print(f"Details: {result['details']}")
    else:
        print(result.get("analysis", "No analysis returned"))
