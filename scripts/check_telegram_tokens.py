#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check Telegram Token Configuration

Diagnoses polling lock conflicts by analyzing token usage.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List
import hashlib

# Fix Windows encoding
if sys.platform == "win32":
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


def load_env_files() -> Dict[str, str]:
    """Load all .env files and extract token configurations."""
    env_files = [
        project_root / ".env",
        project_root / "tg_bot" / ".env",
        project_root / "bots" / "twitter" / ".env",
    ]

    env_vars = {}
    for env_path in env_files:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key not in env_vars:  # First occurrence wins
                            env_vars[key] = value

    # Also check environment variables (they override .env)
    for key in ["TELEGRAM_BOT_TOKEN", "PUBLIC_BOT_TELEGRAM_TOKEN", "TREASURY_BOT_TOKEN"]:
        if key in os.environ:
            env_vars[key] = os.environ[key]

    return env_vars


def hash_token(token: str) -> str:
    """Create a short hash of token for comparison."""
    if not token:
        return "MISSING"
    return hashlib.sha256(token.encode()).hexdigest()[:12]


def main():
    print("=" * 70)
    print("TELEGRAM TOKEN CONFIGURATION DIAGNOSTICS")
    print("=" * 70)
    print()

    env_vars = load_env_files()

    # Extract tokens
    tokens = {
        "Main Bot (TELEGRAM_BOT_TOKEN)": env_vars.get("TELEGRAM_BOT_TOKEN", ""),
        "Public Bot (PUBLIC_BOT_TELEGRAM_TOKEN)": env_vars.get("PUBLIC_BOT_TELEGRAM_TOKEN", ""),
        "Treasury Bot (TREASURY_BOT_TOKEN)": env_vars.get("TREASURY_BOT_TOKEN", ""),
    }

    # Analyze tokens
    token_hashes = {}
    for name, token in tokens.items():
        token_hash = hash_token(token)
        if token:
            prefix = token[:10] + "..." if len(token) > 10 else token
        else:
            prefix = "NOT SET"

        print(f"{name:40s}: {prefix:20s} (hash: {token_hash})")

        # Track duplicates
        if token and token_hash != "MISSING":
            if token_hash not in token_hashes:
                token_hashes[token_hash] = []
            token_hashes[token_hash].append(name)

    print()
    print("-" * 70)
    print("CONFLICT ANALYSIS")
    print("-" * 70)

    conflicts_found = False
    for token_hash, bots in token_hashes.items():
        if len(bots) > 1:
            conflicts_found = True
            print(f"⚠️  CONFLICT: Same token used by {len(bots)} bots:")
            for bot in bots:
                print(f"   - {bot}")
            print()

    if not conflicts_found:
        all_set = all(tokens.values())
        if all_set:
            print("✅ No conflicts detected - each bot has unique token")
        else:
            missing = [name for name, token in tokens.items() if not token]
            print("⚠️  No conflicts, but some tokens missing:")
            for name in missing:
                print(f"   - {name}")
            print()
            print("Missing bots will skip startup automatically.")

    print()
    print("-" * 70)
    print("RECOMMENDATIONS")
    print("-" * 70)

    if conflicts_found:
        print("❌ CONFLICTS DETECTED")
        print()
        print("Each bot needs its own unique token from @BotFather.")
        print()
        print("Steps to fix:")
        print("1. Go to @BotFather on Telegram")
        print("2. Create separate bots for each service:")
        print("   - /newbot → Create new bot")
        print("   - Copy the token it gives you")
        print("3. Update .env file with unique tokens:")
        print()
        print("Example .env:")
        print("   TELEGRAM_BOT_TOKEN=123456:ABCdef...")
        print("   PUBLIC_BOT_TELEGRAM_TOKEN=789012:XYZabc...")
        print("   TREASURY_BOT_TOKEN=345678:QRStuv...")
        print()
    else:
        print("✅ Configuration looks good")
        print()
        print("Each bot will poll independently with no conflicts.")

    print()
    print("=" * 70)

    # Return exit code
    sys.exit(1 if conflicts_found else 0)


if __name__ == "__main__":
    main()
