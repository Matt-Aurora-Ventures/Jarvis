#!/usr/bin/env python3
"""
VPS Deployment Script Generator with Key Injection
Generates a custom deployment script with your API keys baked in.
Run this on your local machine to create a custom deployment script.
"""

import os
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 40)
    print(text)
    print("=" * 40 + "\n")

def safe_print(text):
    """Print text with encoding safety"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback for Windows console
        safe_text = text.replace("✓", "[OK]").replace("✗", "[FAIL]")
        print(safe_text)

def read_key(prompt, default="REPLACEME"):
    """Read API key with optional default"""
    if default == "REPLACEME":
        user_input = input(f"{prompt}: ").strip()
    else:
        user_input = input(f"{prompt} [{default}]: ").strip()

    return user_input if user_input else default

def main():
    print_header("JARVIS VPS DEPLOYMENT SCRIPT GENERATOR")

    print("This will create a custom deployment script with your API keys.")
    print("Keep this script private - never commit it to Git!\n")

    # Check if template exists
    template_path = Path("vps-deploy-with-keys.sh")
    if not template_path.exists():
        print("ERROR: vps-deploy-with-keys.sh not found.")
        print("Run this script from the Jarvis root directory.")
        return False

    print_header("GATHERING API KEYS")
    safe_print("Leave blank to use REPLACEME (you'll update on VPS later)\n")

    # Read API keys
    anthropic = read_key("Anthropic API Key (sk-ant-...)", "sk-ant-REPLACEME")
    xai = read_key("XAI/Grok API Key", "REPLACEME")
    groq = read_key("Groq API Key", "REPLACEME")
    minimax = read_key("MiniMax API Key", "REPLACEME")
    birdeye = read_key("BirdEye API Key", "REPLACEME")
    helius = read_key("Helius API Key", "REPLACEME")

    print("\nTwitter/X API Credentials (4 keys required):\n")
    twitter_api = read_key("  API Key (Consumer Key)", "REPLACEME")
    twitter_secret = read_key("  API Secret (Consumer Secret)", "REPLACEME")
    twitter_token = read_key("  Access Token (OAuth Token)", "REPLACEME")
    twitter_token_secret = read_key("  Access Secret (OAuth Token Secret)", "REPLACEME")

    print()
    telegram = read_key("Telegram Bot Token", "REPLACEME")

    # Summary
    print_header("SUMMARY")
    print("API Keys being configured:")
    safe_print(f"  [OK] Anthropic: {'PROVIDED' if anthropic != 'sk-ant-REPLACEME' else 'PLACEHOLDER'}")
    safe_print(f"  [OK] XAI: {'PROVIDED' if xai != 'REPLACEME' else 'PLACEHOLDER'}")
    safe_print(f"  [OK] Groq: {'PROVIDED' if groq != 'REPLACEME' else 'PLACEHOLDER'}")
    safe_print(f"  [OK] MiniMax: {'PROVIDED' if minimax != 'REPLACEME' else 'PLACEHOLDER'}")
    safe_print(f"  [OK] BirdEye: {'PROVIDED' if birdeye != 'REPLACEME' else 'PLACEHOLDER'}")
    safe_print(f"  [OK] Helius: {'PROVIDED' if helius != 'REPLACEME' else 'PLACEHOLDER'}")
    safe_print(f"  [OK] Twitter API: {'PROVIDED' if twitter_api != 'REPLACEME' else 'PLACEHOLDER'}")
    safe_print(f"  [OK] Telegram: {'PROVIDED' if telegram != 'REPLACEME' else 'PLACEHOLDER'}")
    print()

    confirm = input("Ready to generate deployment script? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Aborted.")
        return False

    # Create custom deployment script
    timestamp = int(datetime.now().timestamp())
    output_file = f"vps-deploy-custom-{timestamp}.sh"

    print(f"\nGenerating {output_file}...")

    # Read template
    with open(template_path, 'r') as f:
        content = f.read()

    # Replace placeholders
    replacements = {
        '"anthropic_api_key": "sk-ant-REPLACEME"': f'"anthropic_api_key": "{anthropic}"',
        '"api_key": "REPLACEME"': f'"api_key": "{xai}"',
        '"groq_api_key": "REPLACEME"': f'"groq_api_key": "{groq}"',
        '"minimax_api_key": "REPLACEME"': f'"minimax_api_key": "{minimax}"',
        '"birdeye_api_key": "REPLACEME"': f'"birdeye_api_key": "{birdeye}"',
        '"helius": {"api_key": "REPLACEME"}': f'"helius": {{"api_key": "{helius}"}}',
    }

    for old, new in replacements.items():
        content = content.replace(old, new)

    # Handle Twitter keys (multiple REPLACEME values)
    lines = content.split('\n')
    new_lines = []
    twitter_api_done = False
    twitter_secret_done = False
    twitter_token_done = False
    twitter_token_secret_done = False

    for line in lines:
        if '"api_key": "REPLACEME",' in line and not twitter_api_done:
            line = line.replace('"REPLACEME"', f'"{twitter_api}"')
            twitter_api_done = True
        elif '"api_secret": "REPLACEME"' in line and not twitter_secret_done:
            line = line.replace('"REPLACEME"', f'"{twitter_secret}"')
            twitter_secret_done = True
        elif '"access_token": "REPLACEME"' in line and not twitter_token_done:
            line = line.replace('"REPLACEME"', f'"{twitter_token}"')
            twitter_token_done = True
        elif '"access_secret": "REPLACEME"' in line and not twitter_token_secret_done:
            line = line.replace('"REPLACEME"', f'"{twitter_token_secret}"')
            twitter_token_secret_done = True
        elif '"bot_token": "REPLACEME"' in line:
            line = line.replace('"REPLACEME"', f'"{telegram}"')

        new_lines.append(line)

    content = '\n'.join(new_lines)

    # Write custom script
    with open(output_file, 'w') as f:
        f.write(content)

    # Make executable (on Unix-like systems)
    try:
        os.chmod(output_file, 0o755)
    except OSError:
        pass  # Windows doesn't use chmod

    print_header("[OK] DEPLOYMENT SCRIPT GENERATED")
    print(f"Custom script: {output_file}\n")
    print("NEXT STEPS:\n")
    print("1. Copy this script to your VPS:")
    print(f"   scp {output_file} root@72.61.7.126:~/\n")
    print("2. SSH into VPS and run it:")
    print("   ssh root@72.61.7.126")
    print(f"   bash {output_file}\n")
    print("3. Keep this script private - DO NOT commit to Git\n")
    print("=" * 40)

    return True

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        exit(1)
