"""
One-time Google login setup.

This opens a browser window for you to log into Google.
Once logged in, the session is saved and all future automation
will have access to your full Google account.
"""

import asyncio
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pathlib import Path

async def setup_google_login():
    """Open browser for Google login."""

    # Ensure profile directory exists
    profile_dir = Path.home() / '.jarvis' / 'browser_profile'
    profile_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*60)
    print("GOOGLE ACCOUNT LOGIN SETUP")
    print("="*60)
    print(f"\nBrowser profile: {profile_dir}")
    print("\nA browser window will open.")
    print("Please log into your Google account.")
    print("This gives Jarvis access to:")
    print("  - Gmail")
    print("  - Calendar")
    print("  - Drive/Docs/Sheets")
    print("  - Google Cloud Console")
    print("  - Firebase")
    print("  - All Google services")
    print("\nPress Enter to continue...")
    input()

    try:
        from browser_use import Browser, BrowserConfig
        from browser_use.browser.context import BrowserContextConfig
    except ImportError:
        print("\nInstalling browser-use...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "browser-use", "playwright"], check=False)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
        from browser_use import Browser, BrowserConfig
        from browser_use.browser.context import BrowserContextConfig

    # Configure browser with persistent profile
    config = BrowserConfig(
        headless=False,  # Visible so you can log in
        disable_security=True,
    )

    context_config = BrowserContextConfig(
        user_data_dir=str(profile_dir),
        no_viewport=False,
        browser_window_size={'width': 1280, 'height': 900},
    )

    browser = Browser(config=config, context_config=context_config)

    print("\nOpening Google login page...")

    # Get browser context and navigate to Google
    context = await browser.new_context()
    page = await context.get_current_page()

    await page.goto("https://accounts.google.com")

    print("\n" + "-"*60)
    print("Browser is open. Please:")
    print("1. Log into your Google account")
    print("2. Make sure you stay logged in")
    print("3. Press Enter here when done")
    print("-"*60)
    input()

    # Check if logged in by going to Gmail
    await page.goto("https://mail.google.com")
    await asyncio.sleep(2)

    # Also visit other services to establish cookies
    print("\nEstablishing sessions for all Google services...")

    services = [
        ("Gmail", "https://mail.google.com"),
        ("Calendar", "https://calendar.google.com"),
        ("Drive", "https://drive.google.com"),
        ("Cloud Console", "https://console.cloud.google.com"),
        ("Firebase", "https://console.firebase.google.com"),
    ]

    for name, url in services:
        print(f"  - {name}...")
        try:
            await page.goto(url)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"    Warning: {e}")

    await browser.close()

    print("\n" + "="*60)
    print("SETUP COMPLETE!")
    print("="*60)
    print("\nYour Google session is now saved.")
    print("Jarvis can now access all your Google services.")
    print("\nTest it by sending a message to @ClawdJarvisBot:")
    print('  "Check my email"')
    print('  "What\'s on my calendar today?"')
    print('  "Create a new doc called Meeting Notes"')
    print()


if __name__ == "__main__":
    asyncio.run(setup_google_login())
