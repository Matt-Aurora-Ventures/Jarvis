"""
Generate VIDEO from existing JARVIS base image using Grok Imagine img2video.

PROCESS:
1. Load base image (original_jarvis.jpg - our consistent JARVIS style)
2. Upload to Grok Imagine
3. Add video prompt describing the motion/animation
4. Download generated video

This maintains visual consistency across all JARVIS content.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# Paths
GROK_COOKIES_PATH = Path(__file__).parent / "grok_cookies.json"
OUTPUT_DIR = Path(__file__).parent / "generated"
BASE_IMAGE = OUTPUT_DIR / "original_jarvis.jpg"  # Our consistent JARVIS style

# Video prompt - describes the MOTION, not the image (image is already provided)
VIDEO_PROMPT = """Subtle neural network particles flowing through the translucent glass strands,
gentle pulsing glow on the circuit patterns,
slight camera drift to the right,
cinematic lighting shift,
smooth 4 second loop"""


async def generate_video_from_base():
    """Generate video from base JARVIS image."""
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    print("\n" + "="*60)
    print("GROK IMAGINE - VIDEO FROM BASE IMAGE")
    print("="*60)

    if not BASE_IMAGE.exists():
        print(f"ERROR: Base image not found: {BASE_IMAGE}")
        return None

    print(f"Base image: {BASE_IMAGE}")
    print(f"Video prompt: {VIDEO_PROMPT[:80]}...")

    if not GROK_COOKIES_PATH.exists():
        print("ERROR: Grok cookies not found. Run grok_login.py first.")
        return None

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=False,  # Show browser to see the process
        args=['--disable-blink-features=AutomationControlled']
    )

    context = await browser.new_context(
        storage_state=str(GROK_COOKIES_PATH),
        viewport={'width': 1400, 'height': 900}
    )

    page = await context.new_page()
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    try:
        print("\nNavigating to Grok Imagine...")
        await page.goto("https://grok.com/imagine", timeout=60000)
        await asyncio.sleep(5)

        # Look for image upload button/area
        print("Looking for image upload option...")

        # Try to find upload input
        upload_input = await page.query_selector('input[type="file"]')

        if upload_input:
            print("Found upload input, uploading base image...")
            await upload_input.set_input_files(str(BASE_IMAGE))
            await asyncio.sleep(3)
        else:
            # Look for upload button/icon to click first
            print("Looking for upload button...")
            upload_btn = await page.query_selector('[aria-label*="upload"], button:has-text("Upload"), [data-testid*="upload"]')
            if upload_btn:
                await upload_btn.click()
                await asyncio.sleep(2)
                # Now find the file input
                upload_input = await page.query_selector('input[type="file"]')
                if upload_input:
                    await upload_input.set_input_files(str(BASE_IMAGE))
                    await asyncio.sleep(3)

        # Find video mode toggle
        print("Looking for video mode...")
        video_btn = await page.query_selector('button:has-text("Video"), [aria-label*="video"], input[value="video"]')
        if video_btn:
            await video_btn.click()
            await asyncio.sleep(2)

        # Enter video description/prompt
        print("Entering video prompt...")
        prompt_input = await page.query_selector('textarea, [contenteditable="true"], input[type="text"]')
        if prompt_input:
            await prompt_input.click()
            await asyncio.sleep(0.5)
            await page.keyboard.type(VIDEO_PROMPT, delay=10)
            await asyncio.sleep(2)

            # Submit by pressing Enter
            print("Pressing Enter to generate...")
            await page.keyboard.press("Enter")
            await asyncio.sleep(5)

            # Also try clicking Redo button if visible
            redo_btn = await page.query_selector('button:has-text("Redo"), [aria-label*="redo"]')
            if redo_btn:
                print("Found Redo button, clicking...")
                await redo_btn.click()

            print("Generating video (this may take 1-2 minutes)...")

            # Wait for video generation
            await asyncio.sleep(60)  # Videos take longer

            # Wait for generation and look for download button
            for attempt in range(15):
                print(f"Looking for video/download (attempt {attempt + 1}/15)...")

                # Look for download button - the arrow down icon in the right panel
                # Try multiple selectors for the download button
                download_selectors = [
                    'button[aria-label*="ownload"]',
                    'button[aria-label*="save"]',
                    '[role="button"][aria-label*="ownload"]',
                    'button svg[stroke="currentColor"]',  # Icon button
                    'button:has(svg)',  # Any button with an SVG icon
                    'a[download]',
                    '[data-testid*="download"]',
                ]

                for sel in download_selectors:
                    try:
                        btns = await page.query_selector_all(sel)
                        for btn in btns:
                            # Check if this looks like a download button (has arrow/download icon)
                            aria = await btn.get_attribute("aria-label") or ""
                            if "download" in aria.lower() or "save" in aria.lower():
                                print(f"Found download button with aria: {aria}")

                                # Set up download handler
                                async with page.expect_download(timeout=30000) as download_info:
                                    await btn.click()

                                download = await download_info.value
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"jarvis_btc_video_{timestamp}.mp4"
                                output_path = OUTPUT_DIR / filename

                                await download.save_as(str(output_path))
                                print(f"\n*** SUCCESS! ***")
                                print(f"Video saved to: {output_path}")
                                return str(output_path)
                    except Exception as e:
                        continue

                # Try clicking any button in the right panel area (buttons near the video)
                try:
                    # Get all buttons and filter by position (right side of viewport)
                    all_btns = await page.query_selector_all('button')
                    for btn in all_btns:
                        box = await btn.bounding_box()
                        if box and box['x'] > 800:  # Right side of screen
                            inner = await btn.inner_html()
                            if 'svg' in inner.lower() or 'path' in inner.lower():
                                print(f"Trying right-side button at x={box['x']}")
                                try:
                                    async with page.expect_download(timeout=10000) as download_info:
                                        await btn.click()
                                    download = await download_info.value
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    filename = f"jarvis_btc_video_{timestamp}.mp4"
                                    output_path = OUTPUT_DIR / filename
                                    await download.save_as(str(output_path))
                                    print(f"\n*** SUCCESS! ***")
                                    print(f"Video saved to: {output_path}")
                                    return str(output_path)
                                except:
                                    continue
                except Exception as e:
                    print(f"Button scan error: {e}")

                # Also try finding video element directly
                video = await page.query_selector('video')
                if video:
                    src = await video.get_attribute("src")
                    if src and 'blob:' not in src:
                        print(f"Found video src: {src[:60]}...")

                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"jarvis_btc_video_{timestamp}.mp4"
                        output_path = OUTPUT_DIR / filename

                        try:
                            response = await page.request.get(src)
                            if response.ok:
                                content = await response.body()
                                if len(content) > 100000:  # Real video
                                    output_path.write_bytes(content)
                                    print(f"\n*** SUCCESS! ***")
                                    print(f"Video saved to: {output_path}")
                                    return str(output_path)
                        except Exception as e:
                            print(f"Direct download failed: {e}")

                await asyncio.sleep(8)

        # Take debug screenshot
        screenshot_path = OUTPUT_DIR / f"debug_video_{datetime.now().strftime('%H%M%S')}.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"\nDebug screenshot saved: {screenshot_path}")

        print("\n*** Video generation incomplete - check browser ***")
        print("Keeping browser open for 30 seconds...")
        await asyncio.sleep(30)

        return None

    finally:
        await context.close()
        await browser.close()
        await playwright.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(generate_video_from_base())

    if result:
        print(f"\nVideo ready for approval: {result}")
    else:
        print("\nVideo generation failed")
