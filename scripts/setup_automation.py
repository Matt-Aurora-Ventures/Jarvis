#!/usr/bin/env python3
"""
Setup LLM-native browser and computer automation for Jarvis.

Run this to install all required packages:
    python scripts/setup_automation.py

This installs:
1. browser-use - LLM-native browser automation (replaces clumsy CDP)
2. playwright - Browser engine
3. open-interpreter - Full computer control
4. langchain - LLM integrations
"""

import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list, desc: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f" {desc}")
    print(f"{'='*60}")

    try:
        subprocess.run(cmd, check=True)
        print(f" SUCCESS: {desc}")
        return True
    except subprocess.CalledProcessError as e:
        print(f" FAILED: {desc} - {e}")
        return False


def main():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║   Jarvis LLM Automation Setup                                 ║
    ║   Installing browser-use + open-interpreter                   ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    pip = [sys.executable, "-m", "pip"]

    # Core packages
    packages = [
        # Browser automation
        "browser-use",
        "playwright",

        # Full computer control
        "open-interpreter",

        # LLM integrations
        "langchain-anthropic",
        "langchain-openai",

        # Anti-detection (optional but recommended)
        "selenium-stealth",
        "undetected-chromedriver",
    ]

    # Install packages
    run_cmd(
        pip + ["install", "--upgrade"] + packages,
        "Installing LLM automation packages"
    )

    # Install Playwright browsers
    run_cmd(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        "Installing Playwright Chromium browser"
    )

    # Verify installations
    print("\n" + "="*60)
    print(" VERIFICATION")
    print("="*60)

    checks = [
        ("browser-use", "from browser_use import Agent, Browser"),
        ("playwright", "import playwright"),
        ("open-interpreter", "from interpreter import interpreter"),
        ("langchain-anthropic", "from langchain_anthropic import ChatAnthropic"),
    ]

    all_ok = True
    for name, import_stmt in checks:
        try:
            exec(import_stmt)
            print(f" ✓ {name}")
        except ImportError as e:
            print(f" ✗ {name}: {e}")
            all_ok = False

    # Summary
    print("\n" + "="*60)
    if all_ok:
        print(" ✅ ALL PACKAGES INSTALLED SUCCESSFULLY")
        print("""
    USAGE:

    # Browser automation (replaces CDP)
    from core.automation.browser_agent import BrowserAgent, browse
    result = await browse("Go to google.com and search for 'solana price'")

    # Full computer control
    from core.automation.computer_control import ask_computer
    result = await ask_computer("What files are on my desktop?")

    # Telegram Web
    from core.automation.browser_agent import TelegramWebAgent
    agent = TelegramWebAgent()
    await agent.send_message("Saved Messages", "Hello from Jarvis!")
        """)
    else:
        print(" ⚠️  SOME PACKAGES FAILED - check errors above")

    print("="*60)


if __name__ == "__main__":
    main()
