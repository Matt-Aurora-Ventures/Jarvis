"""
Grok Imagine Automation - Uses Playwright to access Grok Imagine via X Premium account.
Generates images and videos using your X Premium subscription.
"""

import asyncio
import os
import json
import logging
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

# Paths
COOKIES_PATH = Path(__file__).parent / "x_cookies.json"
OUTPUT_DIR = Path(__file__).parent / "generated"
OUTPUT_DIR.mkdir(exist_ok=True)


class GrokImagine:
    """Automates Grok Imagine via Playwright browser automation."""

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize Grok Imagine automation.

        Args:
            headless: Run browser in headless mode (default True for servers)
            timeout: Default timeout in milliseconds for operations
        """
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._playwright = None

    async def start(self):
        """Start the browser."""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )

        # Try to load saved cookies
        if COOKIES_PATH.exists():
            logger.info("Loading saved cookies...")
            self.context = await self.browser.new_context(
                storage_state=str(COOKIES_PATH),
                viewport={'width': 1280, 'height': 800}
            )
        else:
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 800}
            )

        self.page = await self.context.new_page()

        # Mask automation detection
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

    async def stop(self):
        """Stop the browser."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def save_cookies(self):
        """Save cookies for session persistence."""
        if self.context:
            await self.context.storage_state(path=str(COOKIES_PATH))
            logger.info(f"Cookies saved to {COOKIES_PATH}")

    async def login_x(self, username: str, password: str) -> bool:
        """
        Login to X (Twitter) account.

        Args:
            username: X username or email
            password: X password

        Returns:
            True if login successful
        """
        try:
            logger.info("Navigating to X login...")
            await self.page.goto("https://x.com/i/flow/login", wait_until="networkidle")
            await asyncio.sleep(2)

            # Enter username
            logger.info("Entering username...")
            username_input = await self.page.wait_for_selector(
                'input[autocomplete="username"]', timeout=10000
            )
            await username_input.fill(username)
            await self.page.click('text=Next')
            await asyncio.sleep(2)

            # Check for additional verification (phone/email)
            try:
                verify_input = await self.page.wait_for_selector(
                    'input[data-testid="ocfEnterTextTextInput"]', timeout=3000
                )
                if verify_input:
                    logger.warning("Additional verification required - please complete manually")
                    # Wait for manual input
                    await asyncio.sleep(30)
            except Exception:  # noqa: BLE001 - intentional catch-all
                pass

            # Enter password
            logger.info("Entering password...")
            password_input = await self.page.wait_for_selector(
                'input[type="password"]', timeout=10000
            )
            await password_input.fill(password)
            await self.page.click('text=Log in')
            await asyncio.sleep(3)

            # Check if login was successful
            try:
                await self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=15000)
                logger.info("Login successful!")
                await self.save_cookies()
                return True
            except Exception as e:
                logger.error("Login failed - could not verify success")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def is_logged_in(self) -> bool:
        """Check if we're logged into X."""
        try:
            await self.page.goto("https://x.com/home", wait_until="networkidle")
            await asyncio.sleep(2)

            # Check for login indicators
            try:
                await self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=5000)
                return True
            except Exception:
                return False
        except Exception:
            return False

    async def generate_image(
        self,
        prompt: str,
        mode: Literal["normal", "fun", "spicy"] = "normal",
        output_name: Optional[str] = None
    ) -> Optional[Path]:
        """
        Generate an image using Grok Imagine.

        Args:
            prompt: Text prompt for image generation
            mode: Generation mode (normal, fun, spicy)
            output_name: Optional custom filename

        Returns:
            Path to downloaded image, or None if failed
        """
        try:
            logger.info(f"Navigating to Grok Imagine...")
            await self.page.goto("https://grok.com/imagine", wait_until="networkidle")
            await asyncio.sleep(3)

            # Check if we need to login
            if "login" in self.page.url.lower():
                logger.error("Not logged in - please login first")
                return None

            # Find and fill the prompt input
            logger.info(f"Entering prompt: {prompt[:50]}...")

            # Look for textarea or input for prompt
            prompt_input = await self.page.wait_for_selector(
                'textarea, input[type="text"]', timeout=10000
            )
            await prompt_input.fill(prompt)

            # Select mode if available
            if mode != "normal":
                try:
                    mode_selector = await self.page.query_selector(f'text={mode.capitalize()}')
                    if mode_selector:
                        await mode_selector.click()
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Could not select mode: {mode}")

            # Click generate/submit button
            logger.info("Generating image...")
            submit_btn = await self.page.query_selector(
                'button[type="submit"], button:has-text("Generate"), button:has-text("Create")'
            )
            if submit_btn:
                await submit_btn.click()
            else:
                # Try pressing Enter
                await prompt_input.press("Enter")

            # Wait for generation (this can take a while)
            logger.info("Waiting for generation to complete...")
            await asyncio.sleep(10)

            # Look for generated image
            img_element = await self.page.wait_for_selector(
                'img[src*="pbs.twimg.com"], img[src*="generated"], img[src*="grok"]',
                timeout=60000
            )

            if img_element:
                img_src = await img_element.get_attribute("src")
                logger.info(f"Image generated: {img_src[:100]}...")

                # Download the image
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = output_name or f"grok_imagine_{timestamp}.png"
                output_path = OUTPUT_DIR / filename

                # Use page.screenshot of the image element or download via URL
                response = await self.page.request.get(img_src)
                if response.ok:
                    content = await response.body()
                    output_path.write_bytes(content)
                    logger.info(f"Image saved to: {output_path}")
                    return output_path
                else:
                    # Fallback: screenshot the image element
                    await img_element.screenshot(path=str(output_path))
                    logger.info(f"Image screenshot saved to: {output_path}")
                    return output_path

            logger.error("Could not find generated image")
            return None

        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return None

    async def generate_video(
        self,
        prompt: str,
        mode: Literal["normal", "fun", "spicy"] = "normal",
        output_name: Optional[str] = None
    ) -> Optional[Path]:
        """
        Generate a video using Grok Imagine.

        Args:
            prompt: Text prompt for video generation
            mode: Generation mode
            output_name: Optional custom filename

        Returns:
            Path to downloaded video, or None if failed
        """
        try:
            logger.info(f"Navigating to Grok Imagine for video...")
            await self.page.goto("https://grok.com/imagine", wait_until="networkidle")
            await asyncio.sleep(3)

            # Look for video mode toggle
            video_toggle = await self.page.query_selector(
                'text=Video, button:has-text("Video"), [data-testid*="video"]'
            )
            if video_toggle:
                await video_toggle.click()
                await asyncio.sleep(1)

            # Fill prompt
            prompt_input = await self.page.wait_for_selector(
                'textarea, input[type="text"]', timeout=10000
            )
            await prompt_input.fill(prompt)

            # Submit
            submit_btn = await self.page.query_selector(
                'button[type="submit"], button:has-text("Generate"), button:has-text("Create")'
            )
            if submit_btn:
                await submit_btn.click()
            else:
                await prompt_input.press("Enter")

            # Wait for video generation (longer than images)
            logger.info("Waiting for video generation (this may take a while)...")
            await asyncio.sleep(30)

            # Look for video element
            video_element = await self.page.wait_for_selector(
                'video[src], video source[src]',
                timeout=120000
            )

            if video_element:
                video_src = await video_element.get_attribute("src")
                if not video_src:
                    source = await video_element.query_selector("source")
                    if source:
                        video_src = await source.get_attribute("src")

                if video_src:
                    logger.info(f"Video generated: {video_src[:100]}...")

                    # Download video
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = output_name or f"grok_video_{timestamp}.mp4"
                    output_path = OUTPUT_DIR / filename

                    response = await self.page.request.get(video_src)
                    if response.ok:
                        content = await response.body()
                        output_path.write_bytes(content)
                        logger.info(f"Video saved to: {output_path}")
                        return output_path

            logger.error("Could not find generated video")
            return None

        except Exception as e:
            logger.error(f"Video generation error: {e}")
            return None

    async def interactive_login(self, timeout: int = 300):
        """
        Open browser for manual login - useful for first-time setup.
        User logs in manually, then cookies are saved.

        Args:
            timeout: Max seconds to wait for login (default 5 minutes)
        """
        logger.info("Opening browser for manual login...")
        logger.info("Please log into X with your @jarvis_lifeos account")
        logger.info(f"Waiting up to {timeout} seconds for login...")

        await self.page.goto("https://x.com/login")

        # Poll for login success
        for i in range(timeout // 5):
            await asyncio.sleep(5)

            # Check if we've navigated away from login
            current_url = self.page.url
            if "home" in current_url or ("x.com" in current_url and "login" not in current_url and "flow" not in current_url):
                # Verify actual login
                try:
                    await self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=5000)
                    await self.save_cookies()
                    logger.info("Login successful! Cookies saved for future use.")
                    return True
                except Exception:  # noqa: BLE001 - intentional catch-all
                    pass

            if i % 6 == 0:  # Every 30 seconds
                logger.info(f"Still waiting for login... ({i * 5}s elapsed)")

        logger.error(f"Login timeout after {timeout} seconds")
        return False


async def main():
    """Test the Grok Imagine automation."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    grok = GrokImagine(headless=False)  # Set to True for headless operation

    try:
        await grok.start()

        # Check if we have saved cookies and are logged in
        if await grok.is_logged_in():
            logger.info("Already logged in!")
        else:
            # Interactive login for first time
            logger.info("Not logged in - starting interactive login...")
            await grok.interactive_login()

        # Test image generation
        prompt = """Ethereal chrome silver AI face in 3/4 profile view against pure black background.
Thick flowing translucent glass ribbons emanating from the head like liquid mercury.
Luminescent cyan and white particles suspended inside the translucent glass strands.
Circuit board patterns visible through the translucent head structure.
Cinematic 3D render quality."""

        result = await grok.generate_image(prompt)
        if result:
            logger.info(f"Generated image: {result}")

    finally:
        await grok.stop()


if __name__ == "__main__":
    asyncio.run(main())
