#!/usr/bin/env python3
"""
Playwright-based Notion scraper for full content extraction.
Expands toggles, captures inline databases, and extracts YouTube links.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

ROOT = Path(__file__).resolve().parents[1]


class NotionScraper:
    """Headless browser scraper for Notion pages with full content expansion."""

    def __init__(self, headless: bool = True, timeout_ms: int = 30000):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self, timeout_ms: int = 60000) -> None:
        """Start the browser and create a new page."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(timeout_ms)

    async def stop(self) -> None:
        """Clean up browser resources."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def scrape_page(self, url: str, timeout_ms: int = 60000) -> Dict[str, Any]:
        """
        Scrape a Notion page with full content expansion.
        
        Args:
            url: Notion page URL
            
        Returns:
            Dict containing scraped content, metadata, and extracted resources
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() or use async context manager.")

        # Navigate to the page
        await self.page.goto(url, wait_until="domcontentloaded")
        
        # Wait a bit for any dynamic content
        await asyncio.sleep(3)
        
        # Try to find main content - don't fail if not found immediately
        try:
            await self.page.wait_for_selector('[data-block-id]', timeout=10000)
        except:
            # If no data-block-id found, try other selectors
            try:
                await self.page.wait_for_selector('.notion-page-content', timeout=5000)
            except:
                # Continue anyway - page might still load content
                pass
        
        # Expand all toggles and lazy-loaded content
        await self._expand_all_content()
        
        # Extract content
        content = await self._extract_content()
        
        # Extract YouTube links and other resources
        resources = await self._extract_resources()
        
        # Get page metadata
        metadata = await self._get_page_metadata()
        
        return {
            "url": url,
            "timestamp": time.time(),
            "metadata": metadata,
            "content": content,
            "resources": resources,
            "raw_html": await self.page.content()
        }

    async def _expand_all_content(self) -> None:
        """Expand all toggles, lazy-loaded content, and dynamic elements."""
        if not self.page:
            return
        
        print("Expanding all content...")
        
        # First, try to expand all toggle blocks by clicking on them
        # Notion toggles have specific structure
        try:
            # Find all toggle elements (they have chevron icons)
            toggles = await self.page.query_selector_all('div[role="button"][aria-expanded="false"]')
            print(f"Found {len(toggles)} collapsed toggles")
            
            for i, toggle in enumerate(toggles):
                try:
                    # Get the parent block that contains the toggle
                    parent_block = await toggle.evaluate('el => el.closest("[data-block-id]")')
                    if parent_block:
                        # Click the toggle to expand
                        await toggle.click()
                        await asyncio.sleep(0.5)  # Wait for animation
                        print(f"Expanded toggle {i+1}/{len(toggles)}")
                except Exception as e:
                    print(f"Failed to expand toggle {i+1}: {e}")
                    continue
        except Exception as e:
            print(f"Error finding toggles: {e}")
        
        # Also try other selectors for toggles
        toggle_selectors = [
            '.notion-toggle > div',
            '[data-block-id] > div > div[role="button"]',
            '.notion-selectable[style*="padding-left"]:has([role="button"])',
        ]
        
        for selector in toggle_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                for element in elements:
                    try:
                        # Check if it has a toggle/collapse button
                        button = await element.query_selector('[role="button"], .notion-toggle')
                        if button:
                            aria_expanded = await button.get_attribute('aria-expanded')
                            if aria_expanded == "false":
                                await button.click()
                                await asyncio.sleep(0.3)
                    except:
                        pass
            except:
                pass
        
        # Wait for content to load
        await asyncio.sleep(2)
        
        # Scroll to trigger lazy loading
        print("Triggering lazy loading...")
        for _ in range(3):
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(1)
            await self.page.evaluate('window.scrollTo(0, 0)')
            await asyncio.sleep(1)
        
        # Look for "Load more" buttons and click them
        load_more_selectors = [
            'button:has-text("Load more")',
            'button:has-text("Show more")',
            'a:has-text("Load more")',
            'a:has-text("Show more")',
            '.notion-load-more',
            '.notion-collection-view-more',
        ]
        
        for selector in load_more_selectors:
            try:
                buttons = await self.page.query_selector_all(selector)
                for button in buttons:
                    try:
                        await button.click()
                        await asyncio.sleep(1)
                        print(f"Clicked load more button")
                    except:
                        pass
            except:
                pass
        
        # Final wait for any remaining content
        await asyncio.sleep(2)
        print("Content expansion complete")

    async def _expand_inline_databases(self) -> None:
        """Expand inline databases and load more content."""
        if not self.page:
            return
        
        # Look for inline database "Load more" buttons
        db_selectors = [
            '.notion-collection-view-more',
            'button[aria-label="Load more"]',
            '.notion-simple-table-button-more',
        ]
        
        for selector in db_selectors:
            try:
                buttons = await self.page.query_selector_all(selector)
                for button in buttons:
                    try:
                        await button.click()
                        await asyncio.sleep(1)
                    except:
                        pass
            except:
                pass
        """Scroll down to trigger lazy loading of images and content."""
        if not self.page:
            return

        # Get page height
        body = await self.page.query_selector('body')
        if not body:
            return
            
        # Scroll down in steps
        last_height = 0
        for _ in range(10):  # Max 10 scrolls
            # Scroll to bottom
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            
            # Wait for content to load
            await asyncio.sleep(1)
            
            # Check if we've reached the bottom
            current_height = await self.page.evaluate('document.body.scrollHeight')
            if current_height == last_height:
                break
            last_height = current_height
        
        # Scroll back to top
        await self.page.evaluate('window.scrollTo(0, 0)')
        await asyncio.sleep(0.5)

    async def _extract_content(self) -> Dict[str, Any]:
        """Extract structured content from the page."""
        if not self.page:
            return {}

        # Extract all blocks with their content
        blocks = await self.page.evaluate(r"""
            () => {
                const blocks = [];
                const elements = document.querySelectorAll('[data-block-id]');
                
                elements.forEach(el => {
                    const blockId = el.getAttribute('data-block-id');
                    const text = el.innerText || el.textContent || '';
                    const tagName = el.tagName.toLowerCase();
                    
                    // Get block type from class or data attributes
                    const blockType = el.getAttribute('data-block-type') || 
                                    Array.from(el.classList).find(c => c.startsWith('notion-')) ||
                                    tagName;
                    
                    blocks.push({
                        id: blockId,
                        type: blockType,
                        text: text.trim(),
                        html: el.outerHTML
                    });
                });
                
                return blocks;
            }
        """)
        
        # Extract page title
        title = await self.page.evaluate("""
            () => {
                const titleSelectors = [
                    '.notion-page-title',
                    'h1[data-content-editable-void="true"]',
                    'h1',
                    'title'
                ];
                
                for (const selector of titleSelectors) {
                    const el = document.querySelector(selector);
                    if (el && el.innerText) {
                        return el.innerText.trim();
                    }
                }
                return '';
            }
        """)
        
        return {
            "title": title,
            "blocks": blocks,
            "full_text": "\n\n".join(block["text"] for block in blocks if block["text"])
        }

    async def _extract_resources(self) -> Dict[str, List[str]]:
        """Extract YouTube links, PDFs, and other resources."""
        if not self.page:
            return {"youtube": [], "pdfs": [], "links": []}

        resources = await self.page.evaluate(r"""
            () => {
                const resources = {
                    youtube: [],
                    pdfs: [],
                    links: []
                };
                
                // Extract YouTube links
                const youtubeRegex = /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]+)/;
                const links = document.querySelectorAll('a[href]');
                
                links.forEach(link => {
                    const href = link.href;
                    if (!href) return;
                    
                    // YouTube links
                    const youtubeMatch = href.match(youtubeRegex);
                    if (youtubeMatch) {
                        resources.youtube.push({
                            url: href,
                            id: youtubeMatch[1],
                            title: link.innerText || ''
                        });
                    }
                    // PDF links
                    else if (href.includes('.pdf') || href.includes('pdf')) {
                        resources.pdfs.push({
                            url: href,
                            title: link.innerText || ''
                        });
                    }
                    // Other external links
                    else if (href.startsWith('http')) {
                        resources.links.push({
                            url: href,
                            title: link.innerText || ''
                        });
                    }
                });
                
                return resources;
            }
        """)
        
        return resources

    async def _get_page_metadata(self) -> Dict[str, Any]:
        """Extract page metadata."""
        if not self.page:
            return {}

        metadata = await self.page.evaluate("""
            () => {
                const meta = {};
                
                // Page icon
                const icon = document.querySelector('.notion-page-icon img, .notion-page-icon span');
                if (icon) {
                    meta.icon = icon.innerText || icon.src || '';
                }
                
                // Page properties
                const properties = document.querySelectorAll('.notion-property');
                meta.properties = {};
                
                properties.forEach(prop => {
                    const key = prop.querySelector('.notion-property-key')?.innerText;
                    const value = prop.querySelector('.notion-property-value')?.innerText;
                    if (key && value) {
                        meta.properties[key.trim()] = value.trim();
                    }
                });
                
                // Breadcrumbs
                const breadcrumbs = document.querySelectorAll('.notion-breadcrumb a');
                meta.breadcrumbs = Array.from(breadcrumbs).map(b => b.innerText);
                
                return meta;
            }
        """)
        
        return metadata


async def scrape_notion_page(url: str, output_dir: Optional[Path] = None, timeout_ms: int = 60000) -> Dict[str, Any]:
    """
    Scrape a Notion page and save results.
    
    Args:
        url: Notion page URL to scrape
        output_dir: Directory to save results (defaults to lifeos/data/notion_scrapes)
        
    Returns:
        Dict containing scraped data
    """
    if output_dir is None:
        output_dir = ROOT / "lifeos" / "data" / "notion_scrapes"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    async with NotionScraper() as scraper:
        # Scrape the page
        data = await scraper.scrape_page(url, timeout_ms=timeout_ms)
        
        # Save to files
        timestamp = int(time.time())
        base_name = f"notion_scrape_{timestamp}"
        
        # Save full JSON
        json_path = output_dir / f"{base_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Save markdown
        md_path = output_dir / f"{base_name}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {data['content'].get('title', 'Untitled')}\n\n")
            f.write(f"**Source:** {url}\n")
            f.write(f"**Scraped:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Write content blocks
            for block in data["content"]["blocks"]:
                if block["text"]:
                    # Simple markdown conversion
                    text = block["text"]
                    if block["type"] in ["h1", "heading_1"]:
                        text = f"# {text}"
                    elif block["type"] in ["h2", "heading_2"]:
                        text = f"## {text}"
                    elif block["type"] in ["h3", "heading_3"]:
                        text = f"### {text}"
                    elif block["type"] in ["code", "code_block"]:
                        text = f"```\n{text}\n```"
                    elif block["type"] in ["bulleted_list", "numbered_list"]:
                        text = f"- {text}"
                    
                    f.write(f"{text}\n\n")
        
        # Save resources list
        if data["resources"]["youtube"] or data["resources"]["pdfs"]:
            resources_path = output_dir / f"{base_name}_resources.json"
            with open(resources_path, "w", encoding="utf-8") as f:
                json.dump(data["resources"], f, indent=2, ensure_ascii=False)
        
        data["saved_files"] = {
            "json": str(json_path),
            "markdown": str(md_path),
            "resources": str(resources_path) if data["resources"]["youtube"] or data["resources"]["pdfs"] else None
        }
        
        return data


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python notion_scraper.py <notion_url>")
        sys.exit(1)
    
    url = sys.argv[1]
    if not url.startswith("https://www.notion.so/"):
        print("Error: Please provide a valid Notion URL")
        sys.exit(1)
    
    print(f"Scraping Notion page: {url}")
    
    try:
        data = asyncio.run(scrape_notion_page(url))
        print(f"Scraping completed!")
        print(f"Title: {data['content'].get('title', 'Untitled')}")
        print(f"Blocks extracted: {len(data['content']['blocks'])}")
        print(f"YouTube videos found: {len(data['resources']['youtube'])}")
        print(f"PDFs found: {len(data['resources']['pdfs'])}")
        print(f"Files saved to: {data['saved_files']}")
        
    except Exception as e:
        print(f"Error during scraping: {e}")
        sys.exit(1)
