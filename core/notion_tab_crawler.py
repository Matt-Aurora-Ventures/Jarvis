#!/usr/bin/env python3
"""
Enhanced Notion Tab Crawler with comprehensive state-crawl.

Handles:
- Database view tabs (Table / Board / Gallery or custom views)
- Toggle blocks (hidden content until expanded)
- Embedded widgets that implement tabs (in iframes)
- Linked database views with different filters
- Lazy loading via scroll
- "Load more" pagination
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from playwright.async_api import async_playwright, TimeoutError as PwTimeout, Page, Frame

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "lifeos" / "data" / "notion_scrapes"

# Tuning constants
MAX_TOGGLE_PASSES = 20
MAX_LOAD_MORE_CLICKS = 50
MAX_SCROLL_PASSES = 40
TAB_CLICK_DELAY_MS = 600
INITIAL_SETTLE_MS = 3000


def _hash(s: str) -> str:
    """Short hash for state deduplication."""
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _extract_youtube_urls(text: str) -> List[str]:
    """Extract YouTube URLs from text."""
    patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]+',
        r'https?://youtu\.be/[A-Za-z0-9_-]+',
        r'https?://(?:www\.)?youtube\.com/embed/[A-Za-z0-9_-]+',
    ]
    urls = set()
    for pattern in patterns:
        urls.update(re.findall(pattern, text))
    return sorted(urls)


def _extract_all_urls(text: str) -> List[str]:
    """Extract all HTTP(S) URLs from text."""
    return sorted(set(re.findall(r'https?://[^\s<>"\'`\)\]]+', text)))


class NotionTabCrawler:
    """Comprehensive Notion page crawler with tab/toggle state extraction."""

    def __init__(self, headless: bool = True, timeout_ms: int = 120000):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.browser = None
        self.page = None
        self.stats = {
            "tablists_found": 0,
            "tabs_clicked": 0,
            "toggles_expanded": 0,
            "load_more_clicked": 0,
            "scroll_passes": 0,
            "frames_crawled": 0,
            "states_extracted": 0,
        }

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self):
        """Initialize browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.timeout_ms)

    async def stop(self):
        """Clean up resources."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def expand_all_toggles(self, context) -> int:
        """
        Expand all toggle/accordion elements in context (page or frame).
        Returns count of toggles expanded.
        """
        total_expanded = 0
        for _ in range(MAX_TOGGLE_PASSES):
            toggles = context.locator('[aria-expanded="false"]')
            count = await toggles.count()
            if count == 0:
                break
            # Click in reverse to reduce DOM reflow issues
            for i in reversed(range(count)):
                try:
                    await toggles.nth(i).scroll_into_view_if_needed()
                    await toggles.nth(i).click(timeout=1500, force=True)
                    await context.wait_for_timeout(150)
                    total_expanded += 1
                except (PwTimeout, Exception):
                    pass
        self.stats["toggles_expanded"] += total_expanded
        return total_expanded

    async def click_all_load_more(self, context) -> int:
        """Click 'Load more' buttons until exhausted. Returns click count."""
        patterns = ["Load more", "Show more", "More", "Load"]
        clicks = 0
        while clicks < MAX_LOAD_MORE_CLICKS:
            found = False
            for p in patterns:
                btn = context.get_by_text(p, exact=False).first
                try:
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.scroll_into_view_if_needed()
                        await btn.click(timeout=1500, force=True)
                        await context.wait_for_timeout(300)
                        clicks += 1
                        found = True
                except (PwTimeout, Exception):
                    continue
            if not found:
                break
        self.stats["load_more_clicked"] += clicks
        return clicks

    async def scroll_to_stabilize(self, context) -> int:
        """Scroll to trigger lazy loading. Returns scroll pass count."""
        last_h = None
        stable = 0
        passes = 0
        for _ in range(MAX_SCROLL_PASSES):
            try:
                h = await context.evaluate("() => document.body.scrollHeight")
            except Exception:
                break
            if last_h is not None and h == last_h:
                stable += 1
            else:
                stable = 0
            if stable >= 3:
                break
            last_h = h
            passes += 1
            try:
                await context.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                pass
            await context.wait_for_timeout(250)
        # Scroll back to top
        try:
            await context.evaluate("() => window.scrollTo(0, 0)")
        except Exception:  # noqa: BLE001 - intentional catch-all
            pass
        self.stats["scroll_passes"] += passes
        return passes

    async def extract_visible_text(self, context) -> str:
        """Extract text from main content container."""
        for selector in ["main", "article", "div.notion-page-content", "div[role='main']", ".notion-scroller"]:
            loc = context.locator(selector).first
            try:
                if await loc.count() > 0:
                    txt = (await loc.inner_text()).strip()
                    if len(txt) > 200:
                        return txt
            except Exception:
                continue
        # Fallback: body innerText
        try:
            return (await context.evaluate("() => document.body.innerText")).strip()
        except Exception:
            return ""

    async def extract_links(self, context) -> Dict[str, List[Dict[str, str]]]:
        """Extract all links from context."""
        try:
            links_data = await context.evaluate(r"""
                () => {
                    const results = {
                        youtube: [],
                        notion: [],
                        external: [],
                        all: []
                    };

                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.href || '';
                        const title = (a.innerText || a.title || '').trim().slice(0, 200);

                        if (!href || href.startsWith('javascript:')) return;

                        const link = { url: href, title: title };
                        results.all.push(link);

                        if (href.includes('youtube.com') || href.includes('youtu.be')) {
                            results.youtube.push(link);
                        } else if (href.includes('notion.so') || href.includes('notion.site')) {
                            results.notion.push(link);
                        } else if (href.startsWith('http')) {
                            results.external.push(link);
                        }
                    });

                    return results;
                }
            """)
            return links_data
        except Exception:
            return {"youtube": [], "notion": [], "external": [], "all": []}

    async def tab_crawl(self, context, label_prefix: str = "page") -> Dict[str, Dict[str, Any]]:
        """
        Find all tablists and click each tab, extracting content per state.
        Returns dict keyed by state ID.
        """
        results = {}
        tablists = context.locator("[role='tablist']")
        n_lists = await tablists.count()
        self.stats["tablists_found"] += n_lists

        # If no explicit tablists, still do one extraction after expanding
        if n_lists == 0:
            await self.expand_all_toggles(context)
            await self.click_all_load_more(context)
            await self.scroll_to_stabilize(context)
            txt = await self.extract_visible_text(context)
            links = await self.extract_links(context)
            state_id = f"{label_prefix}:default:{_hash(txt)}"
            results[state_id] = {
                "tab": "default",
                "text": txt,
                "links": links,
                "youtube_count": len(links.get("youtube", [])),
            }
            self.stats["states_extracted"] += 1
            return results

        for li in range(n_lists):
            tablist = tablists.nth(li)
            tabs = tablist.locator("[role='tab']")
            n_tabs = await tabs.count()

            for ti in range(n_tabs):
                tab = tabs.nth(ti)
                try:
                    tab_name = (await tab.inner_text()).strip() or f"tab_{ti}"
                except Exception:
                    tab_name = f"tab_{ti}"

                # Click tab
                try:
                    await tab.scroll_into_view_if_needed()
                    await tab.click(timeout=3000, force=True)
                    await context.wait_for_timeout(TAB_CLICK_DELAY_MS)
                    self.stats["tabs_clicked"] += 1
                except PwTimeout:
                    try:
                        await context.evaluate("(el) => el.click()", await tab.element_handle())
                        await context.wait_for_timeout(TAB_CLICK_DELAY_MS)
                        self.stats["tabs_clicked"] += 1
                    except Exception:
                        pass

                # After tab click, force-load + expand
                await self.expand_all_toggles(context)
                await self.click_all_load_more(context)
                await self.scroll_to_stabilize(context)

                txt = await self.extract_visible_text(context)
                links = await self.extract_links(context)
                state_id = f"{label_prefix}:tablist{li}:{tab_name}:{_hash(txt)}"
                results[state_id] = {
                    "tab": tab_name,
                    "text": txt,
                    "links": links,
                    "youtube_count": len(links.get("youtube", [])),
                }
                self.stats["states_extracted"] += 1

        return results

    async def crawl_database_rows(self, context) -> List[Dict[str, Any]]:
        """Extract database row information (if present)."""
        rows = []
        try:
            row_data = await context.evaluate(r"""
                () => {
                    const rows = [];

                    // Find database rows
                    const rowElements = document.querySelectorAll('[data-block-id] .notion-collection-item, .notion-table-row, div[role="row"]');

                    rowElements.forEach((row, idx) => {
                        const links = row.querySelectorAll('a[href]');
                        const text = (row.innerText || '').trim().slice(0, 500);
                        const pageLinks = [];

                        links.forEach(a => {
                            if (a.href && (a.href.includes('notion.so') || a.href.includes('notion.site'))) {
                                pageLinks.push({ url: a.href, title: (a.innerText || '').trim() });
                            }
                        });

                        if (text || pageLinks.length > 0) {
                            rows.push({
                                index: idx,
                                text: text,
                                pageLinks: pageLinks
                            });
                        }
                    });

                    return rows;
                }
            """)
            rows = row_data
        except Exception:
            pass
        return rows

    async def scrape_page(self, url: str) -> Dict[str, Any]:
        """
        Full page scrape with tab-crawl, toggle expansion, and frame handling.
        """
        print(f"Navigating to: {url}")
        await self.page.goto(url, wait_until="domcontentloaded", timeout=120000)

        # Initial settle
        await self.page.wait_for_timeout(INITIAL_SETTLE_MS)

        # Wait for Notion content to load
        try:
            await self.page.wait_for_selector('[data-block-id]', timeout=15000)
        except PwTimeout:
            print("Warning: No Notion blocks detected, continuing anyway...")

        all_states = {}
        all_database_rows = []

        # Initial expansion
        print("Expanding main page content...")
        await self.expand_all_toggles(self.page)
        await self.click_all_load_more(self.page)
        await self.scroll_to_stabilize(self.page)

        # Crawl main page tabs
        print("Crawling main page tabs...")
        all_states.update(await self.tab_crawl(self.page, "page"))

        # Extract database rows
        db_rows = await self.crawl_database_rows(self.page)
        all_database_rows.extend(db_rows)

        # Crawl frames (tab widgets often live here)
        print("Checking frames...")
        for idx, frame in enumerate(self.page.frames):
            if frame == self.page.main_frame:
                continue
            self.stats["frames_crawled"] += 1
            try:
                await frame.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            try:
                await self.expand_all_toggles(frame)
                await self.click_all_load_more(frame)
                await self.scroll_to_stabilize(frame)
                frame_states = await self.tab_crawl(frame, f"frame{idx}")
                all_states.update(frame_states)

                frame_rows = await self.crawl_database_rows(frame)
                all_database_rows.extend(frame_rows)
            except Exception as e:
                print(f"Frame {idx} error: {e}")
                continue

        # Aggregate unique content
        all_text_parts = []
        all_youtube = {}
        all_notion_links = {}
        all_external_links = {}

        for state_id, state_data in all_states.items():
            all_text_parts.append(f"\n=== {state_id} ===\n{state_data['text']}")

            for yt in state_data.get("links", {}).get("youtube", []):
                all_youtube[yt["url"]] = yt
            for nl in state_data.get("links", {}).get("notion", []):
                all_notion_links[nl["url"]] = nl
            for el in state_data.get("links", {}).get("external", []):
                all_external_links[el["url"]] = el

        merged_text = "\n".join(all_text_parts)

        # Extract page title
        title = await self._get_title()

        return {
            "url": url,
            "title": title,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": self.stats,
            "states": all_states,
            "merged_text": merged_text,
            "youtube_links": list(all_youtube.values()),
            "notion_links": list(all_notion_links.values()),
            "external_links": list(all_external_links.values()),
            "database_rows": all_database_rows,
        }

    async def _get_title(self) -> str:
        """Extract page title."""
        try:
            for selector in ['.notion-page-title', 'h1', 'title']:
                loc = self.page.locator(selector).first
                if await loc.count() > 0:
                    txt = (await loc.inner_text()).strip()
                    if txt:
                        return txt
        except Exception:  # noqa: BLE001 - intentional catch-all
            pass
        return "Untitled"


async def scrape_notion_with_tabs(url: str, output_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Main entry point for comprehensive Notion scraping.
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    async with NotionTabCrawler(headless=True) as crawler:
        data = await crawler.scrape_page(url)

        # Save outputs
        timestamp = int(time.time())
        base_name = f"notion_tabcrawl_{timestamp}"

        # Save full JSON
        json_path = output_dir / f"{base_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        # Save merged text
        md_path = output_dir / f"{base_name}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {data['title']}\n\n")
            f.write(f"**Source:** {url}\n")
            f.write(f"**Scraped:** {data['timestamp']}\n\n")
            f.write("## Stats\n\n")
            for k, v in data['stats'].items():
                f.write(f"- {k}: {v}\n")
            f.write("\n## Content\n\n")
            f.write(data['merged_text'])

        # Save YouTube links
        if data['youtube_links']:
            yt_path = output_dir / f"{base_name}_youtube.json"
            with open(yt_path, "w", encoding="utf-8") as f:
                json.dump(data['youtube_links'], f, indent=2, ensure_ascii=False)
            data['youtube_file'] = str(yt_path)

        # Save external links
        if data['external_links']:
            links_path = output_dir / f"{base_name}_links.json"
            with open(links_path, "w", encoding="utf-8") as f:
                json.dump(data['external_links'], f, indent=2, ensure_ascii=False)
            data['links_file'] = str(links_path)

        data['saved_files'] = {
            'json': str(json_path),
            'markdown': str(md_path),
        }

        print(f"\n{'='*60}")
        print(f"Scrape Complete!")
        print(f"{'='*60}")
        print(f"Title: {data['title']}")
        print(f"States extracted: {data['stats']['states_extracted']}")
        print(f"Tabs clicked: {data['stats']['tabs_clicked']}")
        print(f"Toggles expanded: {data['stats']['toggles_expanded']}")
        print(f"Load more clicks: {data['stats']['load_more_clicked']}")
        print(f"YouTube links: {len(data['youtube_links'])}")
        print(f"External links: {len(data['external_links'])}")
        print(f"Notion links: {len(data['notion_links'])}")
        print(f"Database rows: {len(data['database_rows'])}")
        print(f"Files saved: {data['saved_files']}")

        return data


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "https://wonderful-kick-36b.notion.site/Free-Algo-Trading-Roadmap-Resources-Discord-7fa3d54e7a3046cc87bc787694fdeaf6"

    print(f"Starting enhanced tab-crawl scrape of: {url}")
    data = asyncio.run(scrape_notion_with_tabs(url))
