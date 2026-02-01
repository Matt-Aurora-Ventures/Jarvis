#!/usr/bin/env python3
"""
Bot Token Validation Script

Validates Telegram bot tokens by calling the getMe API endpoint.
This confirms tokens are valid and retrieves bot information.

Usage:
    python scripts/validate_bot_tokens.py

Output: JSON with validation results for each token.
"""

import os
import sys
import json
import asyncio
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import aiohttp
except ImportError:
    print("ERROR: aiohttp not installed. Run: pip install aiohttp")
    sys.exit(1)


# Token format: <numeric_id>:<alphanumeric_hash>
# Valid example: 7968869100:AAEanuTRjH4eHTOGvssn8BV71ChsuPrz6Hc
# Invalid example: 850H068106:AAHoS0GK... (H in numeric part)
TOKEN_PATTERN = re.compile(r'^(\d+):([A-Za-z0-9_-]{35,})$')


def validate_token_format(token: str) -> Tuple[bool, str]:
    """
    Validate token format before API call.

    Returns:
        (is_valid, error_message)
    """
    if not token:
        return False, "Token is empty"

    if ':' not in token:
        return False, "Token missing colon separator"

    parts = token.split(':', 1)
    if len(parts) != 2:
        return False, "Token malformed"

    bot_id, hash_part = parts

    # Check if bot_id is purely numeric
    if not bot_id.isdigit():
        # Find the invalid character(s)
        invalid_chars = [c for c in bot_id if not c.isdigit()]
        return False, f"Bot ID '{bot_id}' contains invalid characters: {invalid_chars}. Bot IDs must be numeric only."

    # Check hash length (typically 35+ alphanumeric chars)
    if len(hash_part) < 30:
        return False, f"Token hash too short ({len(hash_part)} chars, expected 35+)"

    return True, ""


async def validate_token_via_api(token: str) -> Dict[str, Any]:
    """
    Validate a Telegram bot token by calling getMe API.

    Returns:
        {
            "valid": bool,
            "bot_id": str,
            "username": str or None,
            "first_name": str or None,
            "error": str or None,
            "format_error": str or None
        }
    """
    result = {
        "token_preview": f"{token[:15]}...{token[-5:]}" if len(token) > 20 else token,
        "valid": False,
        "bot_id": None,
        "username": None,
        "first_name": None,
        "error": None,
        "format_error": None
    }

    # First check format
    format_valid, format_error = validate_token_format(token)
    if not format_valid:
        result["format_error"] = format_error
        result["error"] = format_error
        return result

    # Call Telegram API
    url = f"https://api.telegram.org/bot{token}/getMe"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()

                if resp.status == 200 and data.get("ok"):
                    bot_info = data.get("result", {})
                    result["valid"] = True
                    result["bot_id"] = bot_info.get("id")
                    result["username"] = bot_info.get("username")
                    result["first_name"] = bot_info.get("first_name")
                    result["can_join_groups"] = bot_info.get("can_join_groups")
                    result["can_read_all_group_messages"] = bot_info.get("can_read_all_group_messages")
                elif resp.status == 401:
                    result["error"] = "Unauthorized - invalid token"
                elif resp.status == 404:
                    result["error"] = "Bot not found"
                else:
                    result["error"] = f"API error {resp.status}: {data.get('description', 'Unknown')}"

    except asyncio.TimeoutError:
        result["error"] = "Request timeout"
    except aiohttp.ClientError as e:
        result["error"] = f"Network error: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"

    return result


def load_tokens_from_env() -> Dict[str, str]:
    """Load tokens from environment and .env files."""
    tokens = {}

    # Load from various .env files
    env_files = [
        project_root / "lifeos" / "config" / ".env",
        project_root / "bots" / "twitter" / ".env",
        project_root / "tg_bot" / ".env",
        project_root / ".env",
    ]

    for env_file in env_files:
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if 'BOT_TOKEN' in key.upper() or 'TOKEN' in key.upper():
                            if value and len(value) > 30:  # Basic token length check
                                tokens[key] = value

    # Load from secrets file if exists
    secrets_file = project_root / "secrets" / "bot_tokens_DEPLOY_ONLY.txt"
    if secrets_file.exists():
        with open(secrets_file, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if value and len(value) > 30:
                        tokens[f"[secrets] {key}"] = value

    return tokens


def load_tokens_from_secrets_file() -> Dict[str, str]:
    """Load tokens specifically from bot_tokens_DEPLOY_ONLY.txt"""
    tokens = {}
    secrets_file = project_root / "secrets" / "bot_tokens_DEPLOY_ONLY.txt"

    if secrets_file.exists():
        with open(secrets_file, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if value:
                        tokens[key] = value

    return tokens


async def main():
    """Main validation routine."""
    print("=" * 60)
    print("TELEGRAM BOT TOKEN VALIDATOR")
    print("=" * 60)
    print()

    # Load all tokens
    tokens = load_tokens_from_env()

    if not tokens:
        print("ERROR: No tokens found in environment or .env files")
        print("\nSearched locations:")
        print("  - lifeos/config/.env")
        print("  - bots/twitter/.env")
        print("  - tg_bot/.env")
        print("  - .env")
        print("  - secrets/bot_tokens_DEPLOY_ONLY.txt")
        return

    print(f"Found {len(tokens)} tokens to validate:\n")

    # Validate each token
    results = []
    for name, token in tokens.items():
        print(f"Validating: {name}...")
        result = await validate_token_via_api(token)
        result["name"] = name
        results.append(result)

        # Print immediate result
        if result["valid"]:
            print(f"  [OK] @{result['username']} (ID: {result['bot_id']})")
        elif result["format_error"]:
            print(f"  [FORMAT ERROR] {result['format_error']}")
        else:
            print(f"  [FAILED] {result['error']}")
        print()

    # Summary
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    valid_tokens = [r for r in results if r["valid"]]
    format_errors = [r for r in results if r["format_error"]]
    api_errors = [r for r in results if not r["valid"] and not r["format_error"]]

    print(f"\nTotal tokens: {len(results)}")
    print(f"Valid:        {len(valid_tokens)}")
    print(f"Format errors: {len(format_errors)}")
    print(f"API errors:   {len(api_errors)}")

    if format_errors:
        print("\n" + "-" * 40)
        print("TOKENS WITH FORMAT ERRORS (need regeneration):")
        print("-" * 40)
        for r in format_errors:
            print(f"\n  {r['name']}:")
            print(f"    Token preview: {r['token_preview']}")
            print(f"    Error: {r['format_error']}")
            print(f"    Action: Regenerate via @BotFather")

    if api_errors:
        print("\n" + "-" * 40)
        print("TOKENS THAT FAILED API VALIDATION:")
        print("-" * 40)
        for r in api_errors:
            print(f"\n  {r['name']}:")
            print(f"    Token preview: {r['token_preview']}")
            print(f"    Error: {r['error']}")

    if valid_tokens:
        print("\n" + "-" * 40)
        print("VALID TOKENS:")
        print("-" * 40)
        for r in valid_tokens:
            print(f"\n  {r['name']}:")
            print(f"    Bot: @{r['username']}")
            print(f"    ID: {r['bot_id']}")
            print(f"    Name: {r['first_name']}")

    # Output JSON for programmatic use
    output_file = project_root / ".claude" / "cache" / "token_validation_results.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
