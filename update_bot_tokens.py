#!/usr/bin/env python3
"""
Interactive Bot Token Updater

This script helps you update the .env file with new bot tokens after creating them via @BotFather.
It validates tokens before updating to ensure they work.
"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv, set_key

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def validate_token(token):
    """Validate a Telegram bot token by calling getMe API."""
    if not token or ':' not in token:
        return False, "Invalid token format (should be like: 123456:ABC-DEF1234)"

    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get('ok'):
            bot_info = data.get('result', {})
            username = bot_info.get('username', 'Unknown')
            first_name = bot_info.get('first_name', 'Unknown')
            return True, f"Valid! Bot: @{username} ({first_name})"
        else:
            error_desc = data.get('description', 'Unknown error')
            return False, f"API Error: {error_desc}"
    except requests.RequestException as e:
        return False, f"Network error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}! {text}{Colors.END}")

def main():
    project_root = Path(__file__).parent
    env_file = project_root / ".env"

    if not env_file.exists():
        print_error(f".env file not found at {env_file}")
        sys.exit(1)

    print_header("TELEGRAM BOT TOKEN UPDATER")

    print("This script will help you update bot tokens in your .env file.")
    print("Make sure you've created new tokens via @BotFather first!")
    print()

    # Load current environment
    load_dotenv(env_file)

    # Tokens to update
    tokens_to_update = [
        ("TREASURY_BOT_TOKEN", "Treasury Trading Bot", "Current token is shared - needs NEW token"),
        ("TELEGRAM_BUY_BOT_TOKEN", "Buy Tracker Bot", "Current token is shared - needs NEW token"),
    ]

    print("Current token status:")
    for var_name, description, note in tokens_to_update:
        current = os.getenv(var_name, "NOT SET")
        token_id = current.split(':')[0] if ':' in current else current
        print(f"  {var_name}: {token_id[:15]}... ({note})")
    print()

    # Collect new tokens
    new_tokens = {}

    for var_name, description, note in tokens_to_update:
        print_header(f"UPDATE: {description}")
        print(f"Environment variable: {var_name}")
        print(f"Current value: {os.getenv(var_name, 'NOT SET')[:30]}...")
        print()

        while True:
            token = input(f"Enter NEW token for {description} (or 'skip' to keep current): ").strip()

            if token.lower() == 'skip':
                print_warning(f"Skipping {var_name}")
                break

            if not token:
                print_error("Token cannot be empty. Try again or type 'skip'.")
                continue

            # Validate token
            print("Validating token...", end=' ', flush=True)
            is_valid, message = validate_token(token)

            if is_valid:
                print_success(message)
                new_tokens[var_name] = token
                break
            else:
                print_error(message)
                retry = input("Try again? (y/n): ").strip().lower()
                if retry != 'y':
                    print_warning(f"Skipping {var_name}")
                    break

    # Update .env file
    if not new_tokens:
        print()
        print_warning("No tokens were updated.")
        sys.exit(0)

    print_header("UPDATING .ENV FILE")

    # Create backup
    backup_file = env_file.with_suffix('.env.backup')
    import shutil
    shutil.copy2(env_file, backup_file)
    print_success(f"Created backup: {backup_file}")

    # Update tokens
    for var_name, token in new_tokens.items():
        set_key(env_file, var_name, token)
        print_success(f"Updated {var_name}")

    print()
    print_header("UPDATE COMPLETE")

    print("Summary of changes:")
    for var_name, token in new_tokens.items():
        token_id = token.split(':')[0]
        print(f"  {var_name}: {token_id} (NEW)")

    print()
    print_success("Tokens updated successfully!")
    print()
    print("Next steps:")
    print("  1. Verify tokens with: python fix_telegram_polling_conflict.py")
    print("  2. Restart supervisor: python bots/supervisor.py")
    print("  3. Monitor logs for polling errors (should be gone!)")
    print()
    print(f"Backup saved to: {backup_file}")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_warning("Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
