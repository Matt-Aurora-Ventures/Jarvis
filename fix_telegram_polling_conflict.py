#!/usr/bin/env python3
"""
Telegram Bot Token Conflict Analyzer and Fixer

This script identifies which bots are sharing the same tokens (causing polling conflicts)
and helps you generate new tokens to fix the issue.

Root Cause: TREASURY_BOT_TOKEN and TELEGRAM_BUY_BOT_TOKEN are using the same token,
causing Telegram's "Conflict: terminated by other getUpdates request" error.
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv

# Load environment
project_root = Path(__file__).parent
env_file = project_root / ".env"

if not env_file.exists():
    print(f"ERROR: .env file not found at {env_file}")
    sys.exit(1)

load_dotenv(env_file)

# Token mapping
token_vars = {
    "TELEGRAM_BOT_TOKEN": "Main Jarvis Trading Bot",
    "PUBLIC_BOT_TELEGRAM_TOKEN": "Public Bot",
    "TREASURY_BOT_TOKEN": "Treasury Trading Bot",
    "TREASURY_BOT_TELEGRAM_TOKEN": "Treasury Bot (alt name)",
    "TELEGRAM_BUY_BOT_TOKEN": "Buy Tracker Bot",
}

print("=" * 80)
print("TELEGRAM BOT TOKEN CONFLICT ANALYSIS")
print("=" * 80)
print()

# Collect tokens
tokens_found = {}
for var_name, description in token_vars.items():
    token = os.getenv(var_name)
    if token:
        tokens_found[var_name] = {
            "token": token,
            "description": description,
            "token_id": token.split(":")[0] if ":" in token else token,
        }

# Find conflicts
conflicts = defaultdict(list)
for var_name, info in tokens_found.items():
    token_id = info["token_id"]
    conflicts[token_id].append((var_name, info["description"]))

# Report findings
print("CURRENT TOKEN ASSIGNMENTS:")
print("-" * 80)
for var_name, info in tokens_found.items():
    print(f"{var_name:35} = {info['token_id']} ({info['description']})")
print()

print("CONFLICT DETECTION:")
print("-" * 80)
has_conflicts = False
for token_id, usages in conflicts.items():
    if len(usages) > 1:
        has_conflicts = True
        print(f"\nWARNING: CONFLICT DETECTED - Token {token_id} is shared by:")
        for var_name, description in usages:
            print(f"   - {var_name} ({description})")
        print(f"   -> This causes Telegram polling errors!")
print()

if not has_conflicts:
    print("[OK] No conflicts detected - all bots have unique tokens")
else:
    print("\n" + "=" * 80)
    print("RECOMMENDED FIX:")
    print("=" * 80)
    print()
    print("You need to create SEPARATE bot tokens for each component.")
    print()
    print("MANUAL STEPS (via @BotFather on Telegram):")
    print()
    print("1. Open Telegram Web: https://web.telegram.org/a/")
    print("2. Search for '@BotFather'")
    print("3. For each conflicting bot:")
    print()

    # Identify which bots need new tokens
    for token_id, usages in conflicts.items():
        if len(usages) > 1:
            print(f"   Token {token_id} is shared by:")
            for var_name, description in usages:
                # Skip aliases
                if "alt name" not in description:
                    print(f"   -> Create NEW bot for: {description}")
                    print(f"      /newbot")
                    print(f"      Name: {description}")
                    print(f"      Username: {description.lower().replace(' ', '_')}_bot")
                    print(f"      Save token to: {var_name}")
                    print()

    print("4. Update .env file with new tokens")
    print("5. Restart supervisor: python bots/supervisor.py")
    print()

    print("ALTERNATIVE: Use the included manual guide:")
    print(f"   {project_root / 'TELEGRAM_BOT_TOKEN_GENERATION_GUIDE.md'}")
    print()

print("=" * 80)
print("TOKEN VERIFICATION COMMANDS:")
print("=" * 80)
print()
print("After creating new tokens, verify each one works:")
print()
for var_name, info in tokens_found.items():
    if "alt name" not in info["description"]:
        print(f"# Test {info['description']}")
        print(f'curl "https://api.telegram.org/bot{info["token"]}/getMe"')
        print()

print("=" * 80)
print("CURRENT ENVIRONMENT FILE:")
print("=" * 80)
print(f"Location: {env_file}")
print()
print("Tokens in .env (obfuscated):")
for var_name, info in tokens_found.items():
    token_masked = info["token"][:15] + "..." + info["token"][-10:] if len(info["token"]) > 25 else info["token"]
    print(f"{var_name} = {token_masked}")
print()

# Additional diagnostics
print("=" * 80)
print("ADDITIONAL DIAGNOSTICS:")
print("=" * 80)
print()

# Check if .env is in .gitignore
gitignore = project_root / ".gitignore"
if gitignore.exists():
    with open(gitignore, "r") as f:
        if ".env" in f.read():
            print("[OK] .env is in .gitignore (good - tokens won't be committed)")
        else:
            print("[WARNING] .env is NOT in .gitignore - add it to prevent leaking tokens!")
else:
    print("[WARNING] No .gitignore found - create one and add .env")

print()
print("=" * 80)

if has_conflicts:
    sys.exit(1)  # Exit with error code if conflicts found
else:
    sys.exit(0)  # Exit successfully if no conflicts
