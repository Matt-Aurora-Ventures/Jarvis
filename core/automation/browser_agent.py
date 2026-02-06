"""
LLM-Native Browser Automation using Browser-Use with Real Chrome.

This connects to your actual Chrome browser via CDP (Chrome DevTools Protocol)
so Google and other sites don't block automated access.

Setup:
1. Chrome must be running with: --remote-debugging-port=9222
2. Or use the launch_chrome() helper to start it

Usage:
    from core.automation.browser_agent import BrowserAgent

    agent = BrowserAgent()
    result = await agent.run("Go to Gmail and check my email")
"""

import asyncio
import logging
import subprocess
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Chrome paths by platform
CHROME_PATHS = {
    "win32": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ],
    "linux": [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
    ],
}

# Profile directory for persistent sessions
CHROME_PROFILE_DIR = Path.home() / ".jarvis" / "chrome_profile"
CDP_PORT = 9222


def find_chrome() -> Optional[str]:
    """Find Chrome executable on this system."""
    paths = CHROME_PATHS.get(sys.platform, CHROME_PATHS["linux"])
    for path in paths:
        if os.path.exists(path):
            return path
    return None


def is_chrome_running_with_debugging() -> bool:
    """Check if Chrome is running with remote debugging."""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', CDP_PORT))
        sock.close()
        return result == 0
    except:
        return False


def launch_chrome(url: str = "about:blank") -> subprocess.Popen:
    """
    Launch Chrome with remote debugging enabled.
    Uses a separate profile for Jarvis to keep sessions isolated.
    """
    chrome_path = find_chrome()
    if not chrome_path:
        raise RuntimeError("Chrome not found. Please install Google Chrome.")

    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    args = [
        chrome_path,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={CHROME_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]

    if sys.platform == "win32":
        # On Windows, use CREATE_NEW_PROCESS_GROUP to detach
        return subprocess.Popen(
            args,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        return subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


async def ensure_chrome_running():
    """Ensure Chrome is running with debugging enabled."""
    if is_chrome_running_with_debugging():
        return True

    logger.info("Starting Chrome with remote debugging...")
    launch_chrome()

    # Wait for Chrome to start
    for _ in range(30):
        await asyncio.sleep(0.5)
        if is_chrome_running_with_debugging():
            logger.info("Chrome started successfully")
            return True

    raise RuntimeError("Failed to start Chrome with debugging")


# Check for browser-use
try:
    from browser_use import Agent, Browser, BrowserConfig
    HAS_BROWSER_USE = True
except ImportError:
    HAS_BROWSER_USE = False
    logger.warning("browser-use not installed. Run: pip install browser-use")

# Check for langchain
try:
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    logger.warning("langchain not installed")


class BrowserAgent:
    """
    LLM-native browser automation that connects to real Chrome.

    Uses CDP to connect to Chrome running with --remote-debugging-port,
    which means Google trusts it as a real browser (no automation detection).
    """

    def __init__(
        self,
        llm_provider: str = "anthropic",
        model: str = None,
        headless: bool = False,  # Ignored - we use real Chrome
        auto_launch_chrome: bool = True,
    ):
        """
        Initialize the browser agent.

        Args:
            llm_provider: "anthropic" or "openai"
            model: Model name (defaults to claude-sonnet-4-20250514 or gpt-4o)
            headless: Ignored (real Chrome is always visible)
            auto_launch_chrome: Auto-start Chrome if not running
        """
        if not HAS_BROWSER_USE:
            raise ImportError("browser-use required: pip install browser-use")
        if not HAS_LANGCHAIN:
            raise ImportError("langchain required: pip install langchain-anthropic")

        self.llm_provider = llm_provider
        self.model = model
        self.auto_launch_chrome = auto_launch_chrome
        self._browser: Optional[Browser] = None
        self._llm = None

    def _get_llm(self):
        """Get the LLM instance."""
        if self._llm:
            return self._llm

        if self.llm_provider == "anthropic":
            self._llm = ChatAnthropic(
                model=self.model or "claude-sonnet-4-20250514",
                timeout=120,
                stop=None,
            )
        elif self.llm_provider == "openai":
            self._llm = ChatOpenAI(
                model=self.model or "gpt-4o",
                timeout=120,
            )
        else:
            raise ValueError(f"Unknown LLM provider: {self.llm_provider}")

        return self._llm

    async def _get_browser(self) -> Browser:
        """Get browser connected to real Chrome via CDP."""
        if self._browser:
            return self._browser

        # Ensure Chrome is running
        if self.auto_launch_chrome:
            await ensure_chrome_running()

        if not is_chrome_running_with_debugging():
            raise RuntimeError(
                f"Chrome not running with debugging. Start it with:\n"
                f'chrome --remote-debugging-port={CDP_PORT} --user-data-dir="{CHROME_PROFILE_DIR}"'
            )

        # Connect via CDP
        config = BrowserConfig(
            headless=False,
            cdp_url=f"http://127.0.0.1:{CDP_PORT}",
        )

        self._browser = Browser(config=config)
        logger.info(f"Connected to Chrome via CDP on port {CDP_PORT}")
        return self._browser

    async def run(
        self,
        task: str,
        max_steps: int = 25,
        additional_context: str = None,
    ) -> Dict[str, Any]:
        """
        Execute a browser task using natural language.

        Args:
            task: What to do, in plain English
                  e.g. "Go to Gmail and check my recent emails"
            max_steps: Maximum navigation steps
            additional_context: Extra context for the agent

        Returns:
            Dict with 'success', 'result'
        """
        try:
            browser = await self._get_browser()
        except Exception as e:
            return {
                'success': False,
                'error': f"Browser not available: {e}",
                'task': task,
            }

        llm = self._get_llm()

        full_task = task
        if additional_context:
            full_task = f"{task}\n\nContext: {additional_context}"

        agent = Agent(
            task=full_task,
            llm=llm,
            browser=browser,
            max_actions_per_step=4,
        )

        try:
            result = await agent.run(max_steps=max_steps)
            return {
                'success': True,
                'result': str(result),
                'task': task,
            }
        except Exception as e:
            logger.error(f"Browser agent error: {e}")
            return {
                'success': False,
                'error': str(e),
                'task': task,
            }

    async def close(self):
        """Close browser connection (not Chrome itself)."""
        if self._browser:
            try:
                await self._browser.close()
            except:
                pass
            self._browser = None


class TelegramWebAgent(BrowserAgent):
    """Specialized agent for Telegram Web automation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.telegram_url = "https://web.telegram.org/k/"

    async def send_message(self, chat_name: str, message: str) -> Dict:
        """Send a message to a specific chat."""
        return await self.run(
            task=f"Go to {self.telegram_url}. "
                 f"Search for and open the chat '{chat_name}'. "
                 f"Send this message: {message}",
            max_steps=15,
        )

    async def read_recent_messages(self, chat_name: str, count: int = 10) -> Dict:
        """Read recent messages from a chat."""
        return await self.run(
            task=f"Go to {self.telegram_url}. "
                 f"Open the chat '{chat_name}'. "
                 f"Read and list the last {count} messages.",
            max_steps=10,
        )


# Convenience functions
async def browse(task: str) -> Dict:
    """Quick browser automation."""
    agent = BrowserAgent()
    try:
        return await agent.run(task)
    finally:
        await agent.close()


async def telegram_send(chat: str, message: str) -> Dict:
    """Send a Telegram message via web."""
    agent = TelegramWebAgent()
    try:
        return await agent.send_message(chat, message)
    finally:
        await agent.close()


if __name__ == "__main__":
    async def test():
        print("Testing browser agent with real Chrome...")
        agent = BrowserAgent()
        result = await agent.run("Go to google.com and tell me what you see")
        print(f"Result: {result}")
        await agent.close()

    asyncio.run(test())
