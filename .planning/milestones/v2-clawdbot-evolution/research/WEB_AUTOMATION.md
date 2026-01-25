# Web Automation Research: Playwright for Jarvis

**Created:** 2026-01-25
**Status:** Research Complete
**Priority:** High

## Executive Summary

Playwright is the recommended web automation solution for Jarvis. It offers:
- Native async Python support (matches Jarvis architecture)
- Built-in anti-detection features
- Firefox Developer Edition support
- Excellent reliability for Gmail/Drive automation
- Superior to Selenium in virtually all metrics

---

## 1. Playwright Architecture

### 1.1 Overview

Playwright is a browser automation library developed by Microsoft that:
- Controls Chromium, Firefox, and WebKit via native protocols
- Uses WebSocket connections (not HTTP like Selenium)
- Has first-class async Python support
- Provides auto-waiting and retry mechanisms

### 1.2 Python Installation

```bash
# Install playwright package (already in requirements.txt)
pip install playwright>=1.42.0

# Install browser binaries (REQUIRED - run once)
playwright install

# Install just Firefox (if you prefer)
playwright install firefox

# Install with dependencies (Linux)
playwright install-deps firefox
```

### 1.3 Core Concepts

| Concept | Description |
|---------|-------------|
| **Browser** | Browser instance (Chromium/Firefox/WebKit) |
| **BrowserContext** | Isolated session (cookies, localStorage) |
| **Page** | Single tab/window |
| **Frame** | iframe within a page |
| **Locator** | Element selector with auto-wait |

### 1.4 Async vs Sync APIs

Playwright provides both APIs. **Use async for Jarvis** (matches existing aiohttp architecture):

```python
# RECOMMENDED: Async API (matches Jarvis patterns)
from playwright.async_api import async_playwright

async def automate():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://example.com")
        await browser.close()

# Sync API (for scripts/testing only)
from playwright.sync_api import sync_playwright

def automate_sync():
    with sync_playwright() as p:
        browser = p.firefox.launch()
        page = browser.new_page()
        page.goto("https://example.com")
        browser.close()
```

---

## 2. Firefox Developer Edition Setup

### 2.1 Why Firefox Developer Edition?

- Enhanced privacy controls
- Better anti-fingerprinting
- Developer tools for debugging
- Separate profile from main Firefox

### 2.2 Custom Firefox Executable

```python
from playwright.async_api import async_playwright

async def launch_firefox_dev():
    async with async_playwright() as p:
        browser = await p.firefox.launch(
            headless=False,
            executable_path=r"C:\Program Files\Firefox Developer Edition\firefox.exe",
            # Or on Mac: "/Applications/Firefox Developer Edition.app/Contents/MacOS/firefox"
            args=[
                "--devtools",  # Open DevTools automatically
            ]
        )
        return browser
```

### 2.3 Persistent Profile (Keeps Login State)

```python
async def launch_with_profile():
    async with async_playwright() as p:
        # Use persistent context to maintain session
        context = await p.firefox.launch_persistent_context(
            user_data_dir="~/.jarvis/browser_profiles/gmail",
            headless=False,
            executable_path=r"C:\Program Files\Firefox Developer Edition\firefox.exe",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = context.pages[0] if context.pages else await context.new_page()
        return context, page
```

---

## 3. Use Cases for Jarvis

### 3.1 Gmail/Google Drive Login

```python
class GmailAutomation:
    def __init__(self, profile_dir: str = "~/.jarvis/browser_profiles/google"):
        self.profile_dir = os.path.expanduser(profile_dir)
    
    async def login(self, email: str, password: str):
        async with async_playwright() as p:
            context = await p.firefox.launch_persistent_context(
                self.profile_dir,
                headless=False,  # Google requires visible browser for login
                viewport={"width": 1280, "height": 800},
            )
            page = context.pages[0] if context.pages else await context.new_page()
            
            await page.goto("https://accounts.google.com")
            
            # Email input
            await page.fill('input[type="email"]', email)
            await page.click('button:has-text("Next")')
            await page.wait_for_timeout(2000)
            
            # Password input
            await page.fill('input[type="password"]', password)
            await page.click('button:has-text("Next")')
            
            # Wait for login completion
            await page.wait_for_url("**/myaccount.google.com/**", timeout=30000)
            await context.close()
    
    async def check_inbox(self):
        """Check Gmail inbox (assumes already logged in)"""
        async with async_playwright() as p:
            context = await p.firefox.launch_persistent_context(
                self.profile_dir,
                headless=True,  # Can run headless after initial login
            )
            page = context.pages[0] if context.pages else await context.new_page()
            
            await page.goto("https://mail.google.com")
            await page.wait_for_selector('[role="main"]')
            
            unread = await page.locator('.aim [data-tooltip*="unread"]').count()
            await context.close()
            return {"unread_count": unread}
```

### 3.2 Web Scraping for Market Data

```python
class MarketDataScraper:
    async def scrape_dexscreener(self, token_address: str):
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            page = await browser.new_page()
            
            # Block unnecessary resources for speed
            await page.route("**/*.{png,jpg,jpeg,gif,webp}", lambda r: r.abort())
            await page.route("**/analytics/**", lambda r: r.abort())
            
            url = f"https://dexscreener.com/solana/{token_address}"
            await page.goto(url, wait_until="networkidle")
            
            price = await page.locator('[class*="price"]').first.text_content()
            volume = await page.locator('[class*="volume"]').first.text_content()
            
            await browser.close()
            return {"price": price, "volume": volume}
```

### 3.3 Twitter/X Automation

```python
class TwitterAutomation:
    def __init__(self, profile_dir: str = "~/.jarvis/browser_profiles/twitter"):
        self.profile_dir = os.path.expanduser(profile_dir)
    
    async def post_tweet(self, content: str, media_path: str = None):
        """Post a tweet (assumes logged in via persistent profile)"""
        async with async_playwright() as p:
            context = await p.firefox.launch_persistent_context(
                self.profile_dir,
                headless=False,  # X has strong bot detection
            )
            page = context.pages[0] if context.pages else await context.new_page()
            
            await page.goto("https://twitter.com/compose/tweet")
            await page.wait_for_selector('[data-testid="tweetTextarea_0"]')
            
            # Type tweet with human-like delays
            await page.locator('[data-testid="tweetTextarea_0"]').click()
            await page.keyboard.type(content, delay=50)
            
            if media_path:
                file_input = page.locator('input[type="file"]')
                await file_input.set_input_files(media_path)
                await page.wait_for_selector('[data-testid="attachments"]')
            
            await page.click('[data-testid="tweetButton"]')
            await page.wait_for_timeout(3000)
            await context.close()
```

---

## 4. Anti-Detection & Stealth

### 4.1 Built-in Playwright Features

```python
async def stealth_browser():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"latitude": 40.7128, "longitude": -74.0060},
            permissions=["geolocation"],
            color_scheme="light",
        )
        
        # Add stealth scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)
        
        return context
```

### 4.2 Human-Like Behavior

```python
import random
import asyncio

class HumanBehavior:
    @staticmethod
    async def random_delay(min_ms: int = 100, max_ms: int = 500):
        await asyncio.sleep(random.randint(min_ms, max_ms) / 1000)
    
    @staticmethod
    async def human_type(page, selector: str, text: str):
        await page.click(selector)
        for char in text:
            if random.random() < 0.05:  # 5% typo chance
                wrong_char = random.choice('abcdefghijklmnop')
                await page.keyboard.type(wrong_char)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await page.keyboard.press("Backspace")
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))
    
    @staticmethod
    async def human_scroll(page):
        for _ in range(random.randint(2, 5)):
            await page.mouse.wheel(0, random.randint(100, 500))
            await asyncio.sleep(random.uniform(0.5, 1.5))
```

---

## 5. Session Management

### 5.1 Persistent Sessions

```python
class SessionManager:
    def __init__(self, base_dir: str = "~/.jarvis/browser_sessions"):
        self.base_dir = os.path.expanduser(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)
    
    def get_session_path(self, name: str) -> str:
        return os.path.join(self.base_dir, name)
    
    async def create_session(self, name: str):
        async with async_playwright() as p:
            context = await p.firefox.launch_persistent_context(
                self.get_session_path(name),
                headless=False,
            )
            return context
    
    async def save_cookies(self, context, name: str):
        cookies = await context.cookies()
        cookie_path = os.path.join(self.base_dir, f"{name}_cookies.json")
        with open(cookie_path, "w") as f:
            json.dump(cookies, f)
    
    async def clear_session(self, name: str):
        session_path = self.get_session_path(name)
        if os.path.exists(session_path):
            shutil.rmtree(session_path)
```

### 5.2 Storage State (Alternative)

```python
async def save_storage_state(page, path: str):
    await page.context.storage_state(path=path)

async def load_storage_state(playwright, state_path: str):
    browser = await playwright.firefox.launch()
    context = await browser.new_context(storage_state=state_path)
    return context
```

---

## 6. Error Handling & Reliability

### 6.1 Robust Page Operations

```python
class RobustPage:
    def __init__(self, page):
        self.page = page
    
    async def safe_click(self, selector: str, timeout: int = 10000):
        try:
            await self.page.locator(selector).click(timeout=timeout)
            return True
        except Exception:
            try:
                await self.page.evaluate(f'document.querySelector("{selector}").click()')
                return True
            except:
                return False
    
    async def retry_operation(self, operation, retries: int = 3, delay: float = 1.0):
        last_error = None
        for attempt in range(retries):
            try:
                return await operation()
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    await asyncio.sleep(delay * (attempt + 1))
        raise last_error
```

### 6.2 Screenshot on Failure

```python
async def with_screenshot_on_failure(page, operation, screenshot_dir="~/.jarvis/screenshots"):
    screenshot_dir = os.path.expanduser(screenshot_dir)
    os.makedirs(screenshot_dir, exist_ok=True)
    
    try:
        return await operation()
    except Exception as e:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(screenshot_dir, f"error_{timestamp}.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        raise Exception(f"{e}\nScreenshot saved to: {screenshot_path}")
```

---

## 7. Integration with Jarvis

### 7.1 Proposed Architecture

```
core/
  web/
    __init__.py
    browser.py          # Browser lifecycle management
    session.py          # Session/cookie management
    stealth.py          # Anti-detection utilities
    automations/
        gmail.py        # Gmail automation
        drive.py        # Google Drive automation
        twitter.py      # X/Twitter automation
        scraper.py      # Generic web scraping
```

### 7.2 Browser Service Class

```python
# core/web/browser.py

import os
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

class BrowserService:
    """Singleton browser service for Jarvis"""
    
    _instance: Optional['BrowserService'] = None
    
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._contexts: dict[str, BrowserContext] = {}
        self.profile_base = os.path.expanduser("~/.jarvis/browser_profiles")
        os.makedirs(self.profile_base, exist_ok=True)
    
    @classmethod
    async def get_instance(cls) -> 'BrowserService':
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance._initialize()
        return cls._instance
    
    async def _initialize(self):
        self._playwright = await async_playwright().start()
    
    async def get_context(self, name: str, persistent: bool = True) -> BrowserContext:
        if name in self._contexts:
            return self._contexts[name]
        
        if persistent:
            profile_path = os.path.join(self.profile_base, name)
            context = await self._playwright.firefox.launch_persistent_context(
                profile_path,
                headless=False,
                viewport={"width": 1920, "height": 1080},
            )
        else:
            if not self._browser:
                self._browser = await self._playwright.firefox.launch(headless=False)
            context = await self._browser.new_context()
        
        self._contexts[name] = context
        return context
    
    async def get_page(self, context_name: str) -> Page:
        context = await self.get_context(context_name)
        if context.pages:
            return context.pages[0]
        return await context.new_page()
    
    async def shutdown(self):
        for context in self._contexts.values():
            await context.close()
        self._contexts.clear()
        
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        
        BrowserService._instance = None
```

### 7.3 Telegram Integration

```python
# In tg_bot/handlers or services
from core.web.browser import BrowserService

async def handle_web_command(update, context):
    """Handle web automation commands from Telegram"""
    command = update.message.text
    
    if command.startswith("/gmail"):
        browser = await BrowserService.get_instance()
        page = await browser.get_page("google")
        await page.goto("https://mail.google.com")
        await page.wait_for_selector('[role="main"]')
        unread = await page.locator('.aim [data-tooltip*="unread"]').count()
        await update.message.reply_text(f"You have {unread} unread emails")
    
    elif command.startswith("/screenshot"):
        url = command.split(" ", 1)[1] if " " in command else "https://google.com"
        browser = await BrowserService.get_instance()
        page = await browser.get_page("scraper")
        await page.goto(url)
        screenshot = await page.screenshot()
        await update.message.reply_photo(screenshot)
```

---

## 8. Performance Considerations

### 8.1 Resource Usage

| Mode | RAM per Browser | CPU | Best For |
|------|-----------------|-----|----------|
| Headless | ~100-200 MB | Low | Scraping, APIs |
| Headed | ~300-500 MB | Medium | Login, CAPTCHA |
| Multiple Contexts | ~50 MB each | Low | Parallel sessions |

### 8.2 Optimization Tips

```python
# 1. Block unnecessary resources
await page.route("**/*.{png,jpg,jpeg,gif,webp,svg}", lambda r: r.abort())
await page.route("**/analytics/**", lambda r: r.abort())

# 2. Use single browser with multiple contexts
browser = await playwright.firefox.launch()
context1 = await browser.new_context()  # Session 1
context2 = await browser.new_context()  # Session 2 (isolated)

# 3. Reuse persistent contexts (see BrowserService)

# 4. Use domcontentloaded when possible (faster than networkidle)
await page.goto(url, wait_until="domcontentloaded")

# 5. Close pages when done
await page.close()
```

---

## 9. Security Best Practices

### 9.1 Credential Management

```python
# NEVER hardcode credentials - use environment variables or secure storage
import os
from cryptography.fernet import Fernet

class SecureCredentials:
    def __init__(self, key_path: str = "~/.jarvis/secrets/browser.key"):
        self.key_path = os.path.expanduser(key_path)
        self._load_or_create_key()
    
    def _load_or_create_key(self):
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key()
            os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
            with open(self.key_path, "wb") as f:
                f.write(self.key)
        self.cipher = Fernet(self.key)
    
    def encrypt(self, value: str) -> bytes:
        return self.cipher.encrypt(value.encode())
    
    def decrypt(self, token: bytes) -> str:
        return self.cipher.decrypt(token).decode()
```

### 9.2 Rate Limiting

```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
    
    async def wait_if_needed(self, domain: str, requests_per_minute: int = 30):
        now = time.time()
        minute_ago = now - 60
        self.requests[domain] = [t for t in self.requests[domain] if t > minute_ago]
        
        if len(self.requests[domain]) >= requests_per_minute:
            wait_time = self.requests[domain][0] - minute_ago
            await asyncio.sleep(wait_time)
        
        self.requests[domain].append(now)
```

### 9.3 Legal Considerations

| Activity | Risk Level | Recommendation |
|----------|------------|----------------|
| Scraping public data | Low | Check robots.txt |
| Logging into own accounts | Low | Safe for personal use |
| Automating social media | Medium | Respect ToS, rate limit |
| Scraping behind login | High | Ensure compliance |
| Mass automation | High | May violate ToS |

---

## 10. Comparison: Playwright vs Alternatives

### 10.1 Playwright vs Selenium

| Feature | Playwright | Selenium |
|---------|------------|----------|
| Speed | Fast (WebSocket) | Slower (HTTP) |
| Auto-wait | Built-in | Manual |
| Async Support | Native | Via wrapper |
| Browser Coverage | Chromium, FF, WebKit | More browsers |
| Anti-detection | Better | Worse |
| Setup | Simple | Complex drivers |
| API Design | Modern | Legacy |
| Maintenance | Active | Stable |

**Verdict: Playwright wins for Jarvis use case**

### 10.2 Playwright vs Puppeteer

| Feature | Playwright | Puppeteer |
|---------|------------|-----------|
| Language | Python, JS, etc. | JS/TS only |
| Browsers | All three | Chromium focus |
| Firefox | Native support | Experimental |
| Jarvis Fit | Perfect | Would need Node.js |

**Verdict: Playwright (Python native)**

### 10.3 Raw CDP (Chrome DevTools Protocol)

- Pro: Maximum control, lowest overhead
- Con: Chromium only, complex, no auto-wait
- Use when: Need specific CDP features

---

## 11. Implementation Roadmap

### Phase 1: Foundation (Week 1)
- [ ] Create `core/web/` module structure
- [ ] Implement `BrowserService` singleton
- [ ] Add session management
- [ ] Basic stealth configuration

### Phase 2: Automations (Week 2)
- [ ] Gmail integration
- [ ] Google Drive integration
- [ ] Screenshot service
- [ ] Generic scraper

### Phase 3: Telegram Commands (Week 3)
- [ ] `/web screenshot <url>`
- [ ] `/gmail check`
- [ ] `/drive list`
- [ ] `/scrape <url> <selector>`

### Phase 4: Advanced (Week 4)
- [ ] Anti-detection improvements
- [ ] CAPTCHA handling (2captcha integration?)
- [ ] Scheduled automations
- [ ] Error recovery

---

## 12. Quick Start Code

```python
# Quick test to verify Playwright works
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # Launch Firefox Developer Edition (if installed)
        try:
            browser = await p.firefox.launch(
                headless=False,
                executable_path=r"C:\Program Files\Firefox Developer Edition\firefox.exe"
            )
        except:
            # Fallback to bundled Firefox
            browser = await p.firefox.launch(headless=False)
        
        page = await browser.new_page()
        await page.goto("https://example.com")
        
        print(f"Title: {await page.title()}")
        await page.screenshot(path="test_screenshot.png")
        
        await browser.close()
        print("Playwright is working!")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Sources

- Playwright Documentation: https://playwright.dev/python/
- Playwright GitHub: https://github.com/microsoft/playwright-python
- Firefox Developer Edition: https://www.mozilla.org/en-US/firefox/developer/

---

## Open Questions

1. **CAPTCHA Handling**: Should Jarvis integrate with 2captcha/anti-captcha services, or rely on human intervention?
2. **Proxy Support**: Will Jarvis need rotating proxies for heavy scraping?
3. **Multi-machine**: Should browser sessions be shareable across Jarvis instances?
4. **Browser Choice**: Should we default to Firefox (privacy) or Chromium (compatibility)?
