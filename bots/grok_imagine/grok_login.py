"""
Grok.com Interactive Login via Playwright.

Opens browser for manual login, saves cookies for future automation.
Run this once to authenticate, then use generate_video.py for automation.

CURRENT PROCESS (Manual):
1. Run this script
2. Browser opens to grok.com
3. Login manually with X/Google account
4. Script detects login and saves cookies
5. Future runs of generate_video.py will use saved cookies

TODO - IMPROVEMENTS NEEDED:
1. [ ] Integrate with X OAuth flow programmatically (no manual login)
2. [ ] Add cookie refresh/expiration detection
3. [ ] Implement headless login with stored credentials
4. [ ] Add Grok API integration when available (bypass browser)
5. [ ] Create unified auth system for X + Grok
"""

import asyncio
import logging
from pathlib import Path
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# Separate cookie file for grok.com (different from x.com)
GROK_COOKIES_PATH = Path(__file__).parent / "grok_cookies.json"
OUTPUT_DIR = Path(__file__).parent / "generated"
OUTPUT_DIR.mkdir(exist_ok=True)


async def interactive_grok_login(timeout: int = 300):
    """
    Open browser for manual Grok login.

    Args:
        timeout: Max seconds to wait for login (default 5 minutes)

    Returns:
        True if login successful and cookies saved
    """
    print("\n" + "="*60)
    print("GROK.COM INTERACTIVE LOGIN")
    print("="*60)
    print("\nThis will open a browser window.")
    print("Please login to grok.com using your X or Google account.")
    print(f"Waiting up to {timeout} seconds for login...\n")

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=False,  # Must be visible for manual login
        args=['--disable-blink-features=AutomationControlled']
    )

    # Check for existing cookies
    if GROK_COOKIES_PATH.exists():
        print("Found existing cookies, loading...")
        context = await browser.new_context(
            storage_state=str(GROK_COOKIES_PATH),
            viewport={'width': 1400, 'height': 900}
        )
    else:
        context = await browser.new_context(
            viewport={'width': 1400, 'height': 900}
        )

    page = await context.new_page()

    # Mask automation
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    try:
        # Navigate to Grok Imagine
        await page.goto("https://grok.com/imagine", timeout=60000)
        await asyncio.sleep(3)

        # Check if already logged in
        if await _is_logged_in(page):
            print("\n*** ALREADY LOGGED IN! ***")
            await _save_cookies(context)
            return True

        # Wait for manual login
        print("\nPlease login in the browser window...")
        print("The script will detect when you're logged in.\n")

        for i in range(timeout // 5):
            await asyncio.sleep(5)

            if await _is_logged_in(page):
                print("\n*** LOGIN DETECTED! ***")
                await _save_cookies(context)
                print(f"Cookies saved to: {GROK_COOKIES_PATH}")
                return True

            if i % 6 == 0 and i > 0:
                print(f"Still waiting for login... ({i * 5}s elapsed)")

        print(f"\n*** LOGIN TIMEOUT after {timeout} seconds ***")
        return False

    finally:
        await context.close()
        await browser.close()
        await playwright.stop()


async def _is_logged_in(page) -> bool:
    """Check if user is logged into Grok."""
    try:
        # Look for signs of being logged in
        # 1. No "Sign in" button visible
        # 2. Prompt input is accessible
        # 3. User avatar/menu visible

        current_url = page.url

        # If we're on imagine page with input available, we're logged in
        if "imagine" in current_url:
            try:
                # Look for the prompt input
                input_el = await page.query_selector('textarea, input[type="text"], div[contenteditable="true"]')
                if input_el:
                    # Check it's not behind a login wall
                    sign_in = await page.query_selector('button:has-text("Sign in"), a:has-text("Sign in")')
                    if not sign_in:
                        return True
            except Exception:  # noqa: BLE001 - intentional catch-all
                pass

        return False
    except Exception:
        return False


async def _save_cookies(context):
    """Save browser cookies for future sessions."""
    await context.storage_state(path=str(GROK_COOKIES_PATH))
    print("Cookies saved successfully!")


async def test_grok_access():
    """Test if saved cookies work for Grok access."""
    if not GROK_COOKIES_PATH.exists():
        print("No saved cookies found. Run interactive login first.")
        return False

    print("\nTesting Grok access with saved cookies...")

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        storage_state=str(GROK_COOKIES_PATH),
        viewport={'width': 1400, 'height': 900}
    )
    page = await context.new_page()

    try:
        await page.goto("https://grok.com/imagine", timeout=30000)
        await asyncio.sleep(5)

        if await _is_logged_in(page):
            print("*** Cookies valid - Grok access confirmed! ***")
            return True
        else:
            print("*** Cookies expired or invalid - need to login again ***")
            return False
    finally:
        await context.close()
        await browser.close()
        await playwright.stop()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    logging.basicConfig(level=logging.INFO)

    print("\nGrok.com Login Utility")
    print("-" * 40)
    print("1. Interactive Login (opens browser)")
    print("2. Test existing cookies")
    print("-" * 40)

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        result = asyncio.run(interactive_grok_login())
        if result:
            print("\nLogin successful! You can now use generate_video.py")
        else:
            print("\nLogin failed. Please try again.")
    elif choice == "2":
        asyncio.run(test_grok_access())
    else:
        print("Invalid choice")
