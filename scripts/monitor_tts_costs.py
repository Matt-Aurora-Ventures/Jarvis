#!/usr/bin/env python3
"""
OpenAI TTS Cost Monitor
Tracks API usage and estimated costs for voice synthesis.
"""

import json
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COST_LOG = ROOT / "data" / "openai_tts_costs.jsonl"

# Pricing per 1M characters
TTS_1_COST = 0.015
TTS_1_HD_COST = 0.030


def log_tts_usage(text: str, voice: str, model: str):
    """Log TTS API usage."""
    char_count = len(text)
    cost = (char_count / 1_000_000) * (TTS_1_HD_COST if model == "tts-1-hd" else TTS_1_COST)
    
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "characters": char_count,
        "voice": voice,
        "model": model,
        "estimated_cost_usd": round(cost, 6),
    }
    
    with open(COST_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_hourly_stats() -> dict:
    """Get TTS usage stats for the last hour."""
    if not COST_LOG.exists():
        return {
            "total_requests": 0,
            "total_characters": 0,
            "total_cost_usd": 0.0,
            "average_response_length": 0,
        }
    
    one_hour_ago = time.time() - 3600
    
    total_chars = 0
    total_cost = 0.0
    count = 0
    
    with open(COST_LOG, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry["timestamp"]).timestamp()
                if ts >= one_hour_ago:
                    total_chars += entry["characters"]
                    total_cost += entry["estimated_cost_usd"]
                    count += 1
            except:
                continue
    
    return {
        "total_requests": count,
        "total_characters": total_chars,
        "total_cost_usd": round(total_cost, 6),
        "average_response_length": round(total_chars / count) if count > 0 else 0,
    }


def get_daily_stats() -> dict:
    """Get TTS usage stats for today."""
    if not COST_LOG.exists():
        return {
            "total_requests": 0,
            "total_characters": 0,
            "total_cost_usd": 0.0,
        }
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    
    total_chars = 0
    total_cost = 0.0
    count = 0
    
    with open(COST_LOG, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry["timestamp"]).timestamp()
                if ts >= today_start:
                    total_chars += entry["characters"]
                    total_cost += entry["estimated_cost_usd"]
                    count += 1
            except:
                continue
    
    return {
        "total_requests": count,
        "total_characters": total_chars,
        "total_cost_usd": round(total_cost, 6),
    }


if __name__ == "__main__":
    print("=== OpenAI TTS Cost Monitor ===\n")
    
    hourly = get_hourly_stats()
    daily = get_daily_stats()
    
    print("Last Hour:")
    print(f"  Requests: {hourly['total_requests']}")
    print(f"  Characters: {hourly['total_characters']:,}")
    print(f"  Cost: ${hourly['total_cost_usd']:.6f}")
    print(f"  Avg Response: {hourly['average_response_length']} chars\n")
    
    print("Today:")
    print(f"  Requests: {daily['total_requests']}")
    print(f"  Characters: {daily['total_characters']:,}")
    print(f"  Cost: ${daily['total_cost_usd']:.6f}\n")
    
    # Projections
    if hourly['total_requests'] > 0:
        hourly_rate = hourly['total_cost_usd']
        print("Projections (if this rate continues):")
        print(f"  Per day: ${hourly_rate * 24:.4f}")
        print(f"  Per month: ${hourly_rate * 24 * 30:.2f}")
