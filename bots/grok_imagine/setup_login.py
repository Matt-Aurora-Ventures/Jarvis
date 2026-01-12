"""
First-time setup - Opens browser for manual X login.
Run this once to save cookies, then automation can run headless.
"""

import asyncio
import logging
from grok_imagine import GrokImagine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


async def setup():
    print("=" * 60)
    print("GROK IMAGINE SETUP - @jarvis_lifeos")
    print("=" * 60)
    print()
    print("This will open a browser window.")
    print("Please log into X with the @jarvis_lifeos account.")
    print("After login, cookies will be saved for future use.")
    print()

    grok = GrokImagine(headless=False)

    try:
        await grok.start()

        # Check if already logged in
        if await grok.is_logged_in():
            print("\n[SUCCESS] Already logged in! Cookies are valid.")
            await grok.save_cookies()
        else:
            print("\nOpening X login page...")
            await grok.interactive_login()

    finally:
        await grok.stop()


if __name__ == "__main__":
    asyncio.run(setup())
