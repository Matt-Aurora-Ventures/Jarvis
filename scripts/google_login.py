"""
Google Login Setup - Opens browser for one-time login.
Run this, log into Google, then close the browser.
"""

import asyncio
import os
import sys
from pathlib import Path

async def main():
    profile_dir = Path.home() / '.jarvis' / 'browser_profile'
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nProfile: {profile_dir}")
    print("Opening browser... Log into Google, then close when done.\n")

    try:
        from browser_use import Browser, BrowserConfig
        from browser_use.browser.context import BrowserContextConfig
    except ImportError:
        print("Installing browser-use...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "browser-use", "playwright"], check=False)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
        from browser_use import Browser, BrowserConfig
        from browser_use.browser.context import BrowserContextConfig

    config = BrowserConfig(headless=False, disable_security=True)
    context_config = BrowserContextConfig(
        user_data_dir=str(profile_dir),
        browser_window_size={'width': 1280, 'height': 900},
    )

    browser = Browser(config=config, context_config=context_config)
    context = await browser.new_context()
    page = await context.get_current_page()

    # Visit Google services to establish cookies
    services = [
        "https://accounts.google.com",
        "https://mail.google.com",
        "https://calendar.google.com",
        "https://drive.google.com",
        "https://console.cloud.google.com",
    ]

    for url in services:
        print(f"Opening {url}...")
        await page.goto(url)
        await asyncio.sleep(3)

    print("\n" + "="*50)
    print("Browser is open. Log into Google if not already.")
    print("When done, just close the browser window.")
    print("="*50 + "\n")

    # Keep browser open until user closes it
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

    await browser.close()
    print("Done! Session saved.")

if __name__ == "__main__":
    asyncio.run(main())
