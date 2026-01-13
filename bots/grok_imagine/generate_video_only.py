"""
Generate video using Grok Imagine for the Bitcoin tweet.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# Use grok-specific cookies (separate from X)
GROK_COOKIES_PATH = Path(__file__).parent / "grok_cookies.json"
X_COOKIES_PATH = Path(__file__).parent / "x_cookies.json"

# Try grok cookies first, fall back to X cookies
COOKIES_PATH = GROK_COOKIES_PATH if GROK_COOKIES_PATH.exists() else X_COOKIES_PATH
OUTPUT_DIR = Path(__file__).parent / "generated"
OUTPUT_DIR.mkdir(exist_ok=True)

# Video prompt for the Bitcoin tweet
VIDEO_PROMPT = """Futuristic AI trading terminal displaying Bitcoin price chart at $90,000,
holographic candlestick patterns floating in 3D space,
chrome robot hand pointing at accumulation zone on chart,
glowing cyan and gold data streams,
dark cyberpunk atmosphere,
cinematic 4K quality,
smooth camera movement around the display"""


async def generate_grok_image(page, prompt: str) -> str:
    """Generate image/video using Grok."""
    try:
        logger.info("Navigating to Grok Imagine...")
        await page.goto("https://grok.com/imagine", timeout=90000)
        await asyncio.sleep(8)

        # Find input - try multiple selectors
        logger.info("Finding input...")
        input_box = None
        selectors = [
            'textarea',
            '[data-testid="tweetTextarea_0"]',
            'div[role="textbox"]',
            '[contenteditable="true"]',
            'input[type="text"]',
        ]
        for sel in selectors:
            try:
                input_box = await page.wait_for_selector(sel, timeout=5000)
                if input_box:
                    logger.info(f"Found input with selector: {sel}")
                    break
            except:
                continue

        if not input_box:
            # Take screenshot for debugging
            await page.screenshot(path=str(OUTPUT_DIR / "debug_grok_page.png"))
            logger.error("Could not find input - screenshot saved")
            return ""

        await input_box.click()
        await asyncio.sleep(1)

        # Type prompt for image generation
        logger.info("Typing prompt...")
        full_prompt = f"Generate an image of: {prompt}"
        await page.keyboard.type(full_prompt, delay=10)
        await asyncio.sleep(2)

        # Submit
        logger.info("Submitting...")
        await page.keyboard.press("Enter")

        # Wait for generation
        logger.info("Waiting for Grok to generate (this may take 30-60 seconds)...")
        await asyncio.sleep(30)

        # Look for generated image - grok.com specific selectors
        # Based on debug screenshot, images appear in a grid
        image_selectors = [
            'img[src*="pbs.twimg.com"]',
            'img[src*="ton.twimg.com"]',
            'img[src*="blob:"]',
            'img[src^="https://"]',
            'div img',
            'button img',
        ]

        for attempt in range(12):
            logger.info(f"Looking for image (attempt {attempt + 1}/12)...")

            # Get all images on page
            try:
                all_imgs = await page.query_selector_all('img')
                for img in all_imgs:
                    src = await img.get_attribute("src")
                    if not src:
                        continue

                    # Skip small icons, emojis, logos
                    if any(skip in src.lower() for skip in ['profile', 'emoji', 'logo', 'icon', 'avatar', 'data:image']):
                        continue

                    # Look for likely generated images (large image URLs)
                    if 'twimg.com' in src or 'blob:' in src or 'grok' in src:
                        logger.info(f"Candidate image: {src[:100]}...")

                        # Try to get image dimensions
                        try:
                            box = await img.bounding_box()
                            if box and box['width'] > 200 and box['height'] > 200:
                                # This looks like a real generated image
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"btc_tweet_{timestamp}.png"
                                output_path = OUTPUT_DIR / filename

                                # Try downloading from URL
                                if 'blob:' not in src:
                                    response = await page.request.get(src)
                                    if response.ok:
                                        content = await response.body()
                                        if len(content) > 50000:  # Ensure it's a real image
                                            output_path.write_bytes(content)
                                            logger.info(f"Downloaded to: {output_path}")
                                            return str(output_path)
                                else:
                                    # For blob URLs, screenshot the element
                                    await img.screenshot(path=str(output_path))
                                    logger.info(f"Screenshot saved to: {output_path}")
                                    return str(output_path)
                        except Exception as e:
                            logger.debug(f"Failed to process image: {e}")

            except Exception as e:
                logger.debug(f"Image search failed: {e}")

            # Save full page screenshot on attempt 5
            if attempt == 5:
                screenshot_path = OUTPUT_DIR / f"debug_full_{datetime.now().strftime('%H%M%S')}.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)
                logger.info(f"Debug screenshot saved: {screenshot_path}")

            await asyncio.sleep(6)

        logger.warning("Could not generate image")
        return ""

    except Exception as e:
        logger.error(f"Generation error: {e}")
        return ""


async def check_account(page) -> str:
    """Check which account is logged in."""
    try:
        await page.goto("https://x.com/home", wait_until="networkidle")
        await asyncio.sleep(3)

        # Get profile link
        profile_link = await page.query_selector('[data-testid="AppTabBar_Profile_Link"]')
        if profile_link:
            href = await profile_link.get_attribute("href")
            if href:
                return href.split("/")[-1]
    except:
        pass
    return "unknown"


async def main():
    """Generate video and report results."""
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*60)
    print("GROK IMAGINE VIDEO GENERATION")
    print("="*60)

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )

    context = await browser.new_context(
        storage_state=str(COOKIES_PATH),
        viewport={'width': 1400, 'height': 900}
    )

    page = await context.new_page()
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    try:
        # Check account
        print("\nChecking logged-in account...")
        username = await check_account(page)
        print(f"\n*** LOGGED IN AS: @{username} ***")

        # Generate image
        print(f"\nVideo Prompt: {VIDEO_PROMPT[:100]}...")
        print("\nGenerating with Grok Imagine...")

        result = await generate_grok_image(page, VIDEO_PROMPT)

        if result:
            print(f"\n*** SUCCESS! ***")
            print(f"Image saved to: {result}")
            print("\nPlease check the file and approve before posting.")
        else:
            print("\n*** Generation failed - check browser window ***")

        # Wait longer for generation
        print("\nKeeping browser open for 30 seconds for generation...")
        await asyncio.sleep(30)

    finally:
        await context.close()
        await browser.close()
        await playwright.stop()


if __name__ == "__main__":
    asyncio.run(main())
