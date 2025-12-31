"""Notion ingestion for public pages.

Fetches the Notion record map, extracts all text, links, code blocks, and
resource URLs, then compiles a digest plus structured execution artifacts.
Supports both API-based fetching and Playwright-based headless scraping
for full content expansion including toggles and inline databases.
"""

from __future__ import annotations

import json
import re
import time
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import requests

from core import context_manager, notes_manager


ROOT = Path(__file__).resolve().parents[1]
NOTION_DIR = ROOT / "data" / "notion"
EXEC_DIR = ROOT / "data" / "trader" / "notion"
ASSET_DIR = NOTION_DIR / "assets"


@dataclass
class NotionExtract:
    title: str
    url: str
    text_lines: List[str]
    sections: Dict[str, List[str]]
    links: List[str]
    youtube_links: List[str]
    code_blocks: List[Dict[str, Any]]
    action_items: List[str]


@dataclass
class ResourceExtract:
    url: str
    status_code: int
    content_type: str
    title: str
    text_excerpt: str
    raw_path: Optional[str]
    file_path: Optional[str]
    links: List[str]
    youtube_links: List[str]
    depth: int = 0
    error: Optional[str] = None


def ingest_notion_page(
    url: str,
    *,
    crawl_links: bool = True,
    max_links: int = 200,
    crawl_depth: int = 1,
    max_pages: int = 20,
    max_chunks: int = 40,
    use_headless: bool = False,
    notebooklm_summary: bool = False,
) -> Dict[str, Any]:
    """
    Ingest a Notion page with optional headless scraping and NotebookLM summarization.
    
    Args:
        url: Notion page URL
        crawl_links: Whether to crawl linked resources
        max_links: Maximum number of links to crawl
        crawl_depth: Maximum depth for link crawling
        max_pages: Maximum pages to fetch (API mode only)
        max_chunks: Maximum chunks per page (API mode only)
        use_headless: Use Playwright headless scraper for full content
        notebooklm_summary: Use NotebookLM MCP to summarize YouTube videos
    """
    if use_headless:
        return _ingest_with_headless(
            url,
            crawl_links=crawl_links,
            max_links=max_links,
            crawl_depth=crawl_depth,
            notebooklm_summary=notebooklm_summary,
        )
    else:
        return _ingest_with_api(
            url,
            crawl_links=crawl_links,
            max_links=max_links,
            crawl_depth=crawl_depth,
            max_pages=max_pages,
            max_chunks=max_chunks,
        )
def _ingest_with_api(
    url: str,
    *,
    crawl_links: bool = True,
    max_links: int = 200,
    crawl_depth: int = 1,
    max_pages: int = 20,
    max_chunks: int = 40,
) -> Dict[str, Any]:
    """Original API-based ingestion method."""
    page_id = _extract_page_id(url)
    if not page_id:
        return {"error": "Could not extract page id", "url": url}

    record_map = _fetch_record_map_recursive(
        page_id,
        max_pages=max_pages,
        max_chunks=max_chunks,
    )
    if not record_map:
        return {"error": "No record map returned", "url": url}

    extract = _extract_from_record_map(url, record_map)
    digest = _render_digest(extract)

    NOTION_DIR.mkdir(parents=True, exist_ok=True)
    EXEC_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = NOTION_DIR / f"{page_id}.json"
    raw_path.write_text(json.dumps(record_map, indent=2), encoding="utf-8")

    note_path, summary_path, _ = notes_manager.save_note(
        topic="notion_trading_roadmap",
        content=digest,
        fmt="md",
        tags=["notion", "trading", "resources"],
        source="notion_ingest",
        metadata={"url": url, "page_id": page_id},
    )

    resources: List[ResourceExtract] = []
    if crawl_links and extract.links:
        resources = _crawl_links_recursive(
            extract.links,
            max_links=max_links,
            max_depth=crawl_depth,
        )

    exec_payload = {
        "source": url,
        "title": extract.title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "links": extract.links,
        "youtube_links": extract.youtube_links,
        "code_blocks": extract.code_blocks,
        "action_items": extract.action_items,
        "sections": extract.sections,
        "resources": [resource.__dict__ for resource in resources],
    }
    exec_path = EXEC_DIR / "notion_execution_base.json"
    exec_path.write_text(json.dumps(exec_payload, indent=2), encoding="utf-8")

    summary_text = "\n".join(extract.text_lines[:12]) if extract.text_lines else "Notion resources ingested."
    context_manager.add_context_document(
        title=f"Notion Trading Roadmap ({extract.title or 'Resources'})",
        source="Notion",
        category="trading",
        summary=summary_text,
        content=digest,
        tags=["notion", "trading", "resources"],
        monetization_angle="Translate curated resources into backtest-ready strategies.",
        metadata={"url": url, "page_id": page_id},
    )

    return {
        "url": url,
        "page_id": page_id,
        "title": extract.title,
        "note_path": str(note_path),
        "summary_path": str(summary_path),
        "raw_path": str(raw_path),
        "exec_path": str(exec_path),
        "links": len(extract.links),
        "youtube_links": len(extract.youtube_links),
        "code_blocks": len(extract.code_blocks),
        "action_items": len(extract.action_items),
        "resources": len(resources),
    }


def _fetch_record_map(page_id: str, limit: int = 100, max_chunks: int = 40) -> Dict[str, Any]:
    """Fetch all chunks for a Notion page id."""
    url = "https://www.notion.so/api/v3/loadPageChunk"
    merged: Dict[str, Any] = {}
    prev_count = 0

    for chunk_number in range(max_chunks):
        payload = {
            "pageId": page_id,
            "limit": limit,
            "cursor": {"stack": []},
            "chunkNumber": chunk_number,
            "verticalColumns": False,
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        record_map = data.get("recordMap", {})
        if not record_map:
            break
        _merge_record_map(merged, record_map)

        block_count = len(merged.get("block", {}))
        if block_count == prev_count:
            break
        prev_count = block_count

        chunk_blocks = record_map.get("block", {})
        if chunk_number > 0 and len(chunk_blocks) < limit:
            # If the chunk is smaller than the limit, it's likely the last one.
            break
        time.sleep(0.15)

    return merged


def _fetch_record_map_recursive(
    page_id: str,
    *,
    max_pages: int = 20,
    max_chunks: int = 40,
) -> Dict[str, Any]:
    """Fetch record maps for the page and any nested sub-pages."""
    merged: Dict[str, Any] = {}
    queue: List[str] = [page_id]
    seen: Set[str] = set()

    while queue and len(seen) < max_pages:
        current_id = queue.pop(0)
        if current_id in seen:
            continue
        seen.add(current_id)
        record_map = _fetch_record_map(current_id, max_chunks=max_chunks)
        if not record_map:
            continue
        _merge_record_map(merged, record_map)

        for nested_id in _extract_nested_page_ids(record_map, root_id=page_id):
            if nested_id not in seen:
                queue.append(nested_id)

    return merged


def _extract_from_record_map(url: str, record_map: Dict[str, Any]) -> NotionExtract:
    blocks = record_map.get("block", {})
    page_title = _extract_page_title(blocks)

    root_id = _extract_page_id(url)
    text_lines: List[str] = []
    sections: Dict[str, List[str]] = {}
    links: Set[str] = set()
    code_blocks: List[Dict[str, Any]] = []
    action_items: List[str] = []

    current_section = "Overview"
    sections[current_section] = []

    def _walk(block_id: str, depth: int = 0) -> None:
        nonlocal current_section
        block = blocks.get(block_id, {}).get("value", {})
        if not block:
            return

        block_type = block.get("type", "")
        text, text_links = _extract_block_text(block)
        line_prefix = "  " * max(depth - 1, 0)
        line = text.strip() if text else ""

        if block_type in {"header", "sub_header", "sub_sub_header"} and line:
            current_section = line
            if current_section not in sections:
                sections[current_section] = []
        if block_type == "toggle" and line:
            current_section = f"Toggle: {line}"
            if current_section not in sections:
                sections[current_section] = []

        if line:
            text_lines.append(line)
            sections.setdefault(current_section, []).append(f"{line_prefix}{line}")
            if _looks_like_action(line):
                action_items.append(line)

        urls = _extract_urls(block)
        for url_item in urls:
            links.add(url_item)
        for url_item in text_links:
            links.add(url_item)

        if block_type == "code":
            lang = _extract_code_language(block)
            if line:
                code_blocks.append({"language": lang, "code": line})
        if block_type == "to_do" and line:
            action_items.append(line)

        for child_id in block.get("content", []) or []:
            _walk(child_id, depth + 1)

    if root_id and root_id in blocks:
        _walk(root_id, 0)
        for block_id, block in blocks.items():
            if block_id == root_id:
                continue
            value = block.get("value", {})
            if value.get("type") in {"page", "collection_view_page"}:
                _walk(block_id, 0)
    else:
        for block_id in list(blocks.keys()):
            _walk(block_id, 0)

    youtube_links = sorted({link for link in links if _is_youtube(link)})

    return NotionExtract(
        title=page_title,
        url=url,
        text_lines=text_lines,
        sections=sections,
        links=sorted(links),
        youtube_links=youtube_links,
        code_blocks=code_blocks,
        action_items=action_items,
    )


def _extract_page_id(url: str) -> Optional[str]:
    match = re.search(r"([a-f0-9]{32})", url)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


def _merge_record_map(target: Dict[str, Any], incoming: Dict[str, Any]) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict):
            target.setdefault(key, {})
            target[key].update(value)
        else:
            target[key] = value


def _extract_nested_page_ids(record_map: Dict[str, Any], root_id: Optional[str] = None) -> List[str]:
    blocks = record_map.get("block", {})
    nested: List[str] = []
    for block_id, block in blocks.items():
        value = block.get("value", {})
        block_type = value.get("type")
        if block_type in {"page", "collection_view_page"}:
            if block_id != root_id:
                nested.append(block_id)
        if block_type == "alias":
            alias = value.get("format", {}).get("alias_pointer", {})
            alias_id = alias.get("id")
            if alias_id and alias_id != root_id:
                nested.append(alias_id)
    return nested


def _extract_page_title(blocks: Dict[str, Any]) -> str:
    for block in blocks.values():
        value = block.get("value", {})
        if value.get("type") == "page":
            title_prop = value.get("properties", {}).get("title")
            if title_prop:
                text, _ = _parse_rich_text(title_prop)
                return text
    return "Notion Page"


def _extract_block_text(block: Dict[str, Any]) -> Tuple[str, List[str]]:
    props = block.get("properties", {})
    title_prop = props.get("title")
    if title_prop:
        return _parse_rich_text(title_prop)
    return "", []


def _parse_rich_text(prop: Iterable[Any]) -> Tuple[str, List[str]]:
    chunks: List[str] = []
    links: List[str] = []
    for segment in prop:
        if not segment:
            continue
        if isinstance(segment, list):
            text = segment[0]
            chunks.append(text)
            if len(segment) > 1:
                for fmt in segment[1]:
                    if isinstance(fmt, list) and fmt and fmt[0] == "a":
                        links.append(fmt[1])
        else:
            chunks.append(str(segment))
    return "".join(chunks).strip(), links


def _extract_code_language(block: Dict[str, Any]) -> str:
    props = block.get("properties", {})
    lang_prop = props.get("language")
    if lang_prop and isinstance(lang_prop, list) and lang_prop[0]:
        return str(lang_prop[0][0])
    return ""


def _extract_urls(obj: Any) -> List[str]:
    raw = json.dumps(obj, ensure_ascii=True)
    return re.findall(r"https?://[^\"\\\s]+", raw)


def _is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def _looks_like_action(text: str) -> bool:
    keywords = [
        "build",
        "test",
        "backtest",
        "paper",
        "deploy",
        "implement",
        "automate",
        "create",
        "optimize",
        "ship",
        "launch",
        "setup",
        "set up",
        "run",
    ]
    lower = text.lower()
    return any(word in lower for word in keywords)


def _render_digest(extract: NotionExtract) -> str:
    lines = [
        "# Notion Trading Roadmap Digest",
        f"Source: {extract.url}",
        f"Title: {extract.title}",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Sections",
    ]
    for section, items in extract.sections.items():
        if not items:
            continue
        lines.append(f"### {section}")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")

    if extract.links:
        lines.append("## Links")
        for link in extract.links:
            lines.append(f"- {link}")
        lines.append("")

    if extract.youtube_links:
        lines.append("## YouTube")
        for link in extract.youtube_links:
            lines.append(f"- {link}")
        lines.append("")

    if extract.code_blocks:
        lines.append("## Code Snippets")
        for block in extract.code_blocks:
            lang = block.get("language", "")
            code = block.get("code", "")
            if not code:
                continue
            lines.append(f"```{lang}")
            lines.append(code)
            lines.append("```")
        lines.append("")

    if extract.action_items:
        lines.append("## Action Items")
        for item in extract.action_items:
            lines.append(f"- {item}")

    return "\n".join(lines).strip() + "\n"


def ingest_resource_list(
    title: str,
    urls: List[str],
    *,
    category: str = "research",
    tags: Optional[List[str]] = None,
    crawl_depth: int = 1,
    max_links: int = 200,
) -> Dict[str, Any]:
    """Ingest and crawl a list of resource URLs."""
    resources = _crawl_links_recursive(
        urls,
        max_links=max_links,
        max_depth=crawl_depth,
    )

    NOTION_DIR.mkdir(parents=True, exist_ok=True)
    EXEC_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "title": title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed_urls": urls,
        "resources": [resource.__dict__ for resource in resources],
    }
    safe_title = _safe_label(title)
    exec_path = EXEC_DIR / f"{safe_title}_resources.json"
    exec_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    digest_lines = [f"# {title}", "", f"Generated: {payload['generated_at']}", "", "## Resources"]
    for resource in resources:
        digest_lines.append(f"- {resource.url} ({resource.content_type or 'unknown'})")
        if resource.youtube_links:
            for yt in resource.youtube_links:
                digest_lines.append(f"  - YouTube: {yt}")
    digest = "\n".join(digest_lines).strip() + "\n"

    note_path, summary_path, _ = notes_manager.save_note(
        topic=safe_title,
        content=digest,
        fmt="md",
        tags=tags or [category],
        source="resource_ingest",
        metadata={"title": title, "seed_urls": urls},
    )

    context_manager.add_context_document(
        title=title,
        source="Resource Ingest",
        category=category,
        summary=" ".join(digest_lines[:8])[:240],
        content=digest,
        tags=tags or [category],
        monetization_angle="Extract action items and data sources for strategy execution.",
        metadata={"seed_urls": urls, "exec_path": str(exec_path)},
    )

    return {
        "title": title,
        "exec_path": str(exec_path),
        "note_path": str(note_path),
        "summary_path": str(summary_path),
        "resources": len(resources),
    }


class _HtmlCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: List[str] = []
        self.links: List[str] = []
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() == "a":
            for key, value in attrs:
                if key == "href" and value:
                    self.links.append(value)
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()
        text = data.strip()
        if text:
            self.text_parts.append(text)

    def get_text(self) -> str:
        return " ".join(self.text_parts)


def _crawl_links_recursive(
    seed_links: List[str],
    max_links: int = 200,
    max_depth: int = 1,
) -> List[ResourceExtract]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    resources: List[ResourceExtract] = []
    seen: Set[str] = set()
    queue: List[Tuple[str, int]] = []

    for link in seed_links:
        normalized = _normalize_url(link)
        if not normalized:
            continue
        queue.append((normalized, 0))

    while queue and len(resources) < max_links:
        url, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        resource = _fetch_resource(url, depth=depth)
        resources.append(resource)
        if depth >= max_depth:
            continue
        for link in resource.links:
            normalized = _normalize_url(link, base_url=url)
            if not normalized or normalized in seen:
                continue
            queue.append((normalized, depth + 1))

    return resources


def _fetch_resource(url: str, depth: int = 0) -> ResourceExtract:
    headers = {"User-Agent": "Mozilla/5.0 (LifeOS Notion Ingest)"}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        status = response.status_code
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            resource = _parse_html_resource(url, response.text, status, content_type)
            resource.depth = depth
            return resource
        if content_type.startswith("text/") or "application/json" in content_type:
            resource = _parse_text_resource(url, response.text, status, content_type)
            resource.depth = depth
            return resource
        resource = _save_binary_resource(url, response.content, status, content_type)
        resource.depth = depth
        return resource
    except Exception as exc:
        return ResourceExtract(
            url=url,
            status_code=0,
            content_type="",
            title="",
            text_excerpt="",
            raw_path=None,
            file_path=None,
            links=[],
            youtube_links=[],
            depth=depth,
            error=str(exc),
        )


def _parse_html_resource(url: str, html: str, status: int, content_type: str) -> ResourceExtract:
    collector = _HtmlCollector()
    collector.feed(html)
    text = collector.get_text()
    text = _collapse_whitespace(text)
    raw_path = str(notes_manager.log_command_snapshot(["notion_crawl", url], _safe_label(url), text))
    links = _normalize_links(collector.links, base_url=url)
    links = _filter_links(links)
    youtube_links = sorted({link for link in links if _is_youtube(link)})
    return ResourceExtract(
        url=url,
        status_code=status,
        content_type=content_type,
        title=collector.title or _title_from_text(text),
        text_excerpt=text[:600],
        raw_path=raw_path,
        file_path=None,
        links=links,
        youtube_links=youtube_links,
    )


def _parse_text_resource(url: str, text: str, status: int, content_type: str) -> ResourceExtract:
    clean_text = _collapse_whitespace(text)
    raw_path = str(notes_manager.log_command_snapshot(["notion_crawl", url], _safe_label(url), clean_text))
    links = _filter_links(_extract_urls(clean_text))
    youtube_links = sorted({link for link in links if _is_youtube(link)})
    return ResourceExtract(
        url=url,
        status_code=status,
        content_type=content_type,
        title=_title_from_text(clean_text),
        text_excerpt=clean_text[:600],
        raw_path=raw_path,
        file_path=None,
        links=links,
        youtube_links=youtube_links,
    )


def _save_binary_resource(url: str, payload: bytes, status: int, content_type: str) -> ResourceExtract:
    filename = _filename_from_url(url, content_type)
    path = ASSET_DIR / filename
    path.write_bytes(payload)
    return ResourceExtract(
        url=url,
        status_code=status,
        content_type=content_type,
        title=filename,
        text_excerpt="",
        raw_path=None,
        file_path=str(path),
        links=[],
        youtube_links=[],
    )


def _safe_label(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", url)[:60].strip("-") or "notion-resource"


def _filename_from_url(url: str, content_type: str) -> str:
    slug = _safe_label(url)
    ext = ""
    if "pdf" in content_type:
        ext = ".pdf"
    elif "image" in content_type:
        ext = ".img"
    return f"{slug}{ext}"


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _filter_links(links: Iterable[str]) -> List[str]:
    cleaned: List[str] = []
    for link in links:
        if not link:
            continue
        if link.startswith("#"):
            continue
        if link.startswith("mailto:") or link.startswith("tel:") or link.startswith("javascript:"):
            continue
        cleaned.append(link)
    return cleaned


def _title_from_text(text: str) -> str:
    if not text:
        return ""
    return text.split(".")[0][:80]


def _normalize_links(links: Iterable[str], base_url: str) -> List[str]:
    normalized: List[str] = []
    for link in links:
        normalized_url = _normalize_url(link, base_url=base_url)
        if normalized_url:
            normalized.append(normalized_url)
    return normalized


def _normalize_url(url: str, base_url: Optional[str] = None) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    if base_url and url.startswith("/"):
        from urllib.parse import urljoin
        url = urljoin(base_url, url)
    if not url.startswith("http://") and not url.startswith("https://"):
        return None
    url = url.split("#", 1)[0]
    return url


def _ingest_with_headless(
    url: str,
    *,
    crawl_links: bool = True,
    max_links: int = 200,
    crawl_depth: int = 1,
    notebooklm_summary: bool = False,
) -> Dict[str, Any]:
    """Headless browser-based ingestion with full content expansion."""
    try:
        # Import here to avoid import overhead if not used
        from core.notion_scraper import scrape_notion_page
    except ImportError as e:
        return {"error": f"Headless scraper not available: {e}", "url": url}
    
    # Scrape the page with Playwright
    try:
        scraped_data = asyncio.run(scrape_notion_page(url))
    except Exception as e:
        return {"error": f"Headless scraping failed: {e}", "url": url}
    
    # Extract content from scraped data
    content = scraped_data.get("content", {})
    resources = scraped_data.get("resources", {})
    
    # Convert to NotionExtract format
    extract = NotionExtract(
        title=content.get("title", "Untitled"),
        url=url,
        text_lines=content.get("full_text", "").split("\n"),
        sections={"Full Content": content.get("full_text", "").split("\n")},
        links=[r["url"] for r in resources.get("links", [])],
        youtube_links=[r["url"] for r in resources.get("youtube", [])],
        code_blocks=[],
        action_items=[line for line in content.get("full_text", "").split("\n") if _looks_like_action(line)],
    )
    
    # Generate digest
    digest = _render_digest(extract)
    
    # Save files
    NOTION_DIR.mkdir(parents=True, exist_ok=True)
    EXEC_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save scraped JSON
    page_id = _extract_page_id(url) or "headless"
    raw_path = NOTION_DIR / f"{page_id}_headless.json"
    raw_path.write_text(json.dumps(scraped_data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Save note
    note_path, summary_path, _ = notes_manager.save_note(
        topic="notion_trading_roadmap",
        content=digest,
        fmt="md",
        tags=["notion", "trading", "resources", "headless"],
        source="notion_headless_ingest",
        metadata={"url": url, "page_id": page_id, "method": "headless"},
    )
    
    # Process YouTube videos with NotebookLM if requested
    youtube_summaries = {}
    if notebooklm_summary and extract.youtube_links:
        youtube_summaries = _summarize_youtube_videos(extract.youtube_links)
    
    # Crawl other links if requested
    resources_list: List[ResourceExtract] = []
    if crawl_links and extract.links:
        # Filter out YouTube links (already processed)
        non_youtube_links = [link for link in extract.links if not _is_youtube(link)]
        resources_list = _crawl_links_recursive(
            non_youtube_links,
            max_links=max_links,
            max_depth=crawl_depth,
        )
    
    # Build execution payload
    exec_payload = {
        "source": url,
        "title": extract.title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "headless",
        "links": extract.links,
        "youtube_links": extract.youtube_links,
        "youtube_summaries": youtube_summaries,
        "code_blocks": extract.code_blocks,
        "action_items": extract.action_items,
        "sections": extract.sections,
        "resources": [resource.__dict__ for resource in resources_list],
        "scraped_data": scraped_data.get("saved_files"),
    }
    exec_path = EXEC_DIR / "notion_headless_execution_base.json"
    exec_path.write_text(json.dumps(exec_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Add to context
    summary_text = "\n".join(extract.text_lines[:12]) if extract.text_lines else "Notion resources ingested via headless scraper."
    context_manager.add_context_document(
        title=f"Notion Trading Roadmap ({extract.title or 'Resources'}) - Headless",
        source="Notion Headless",
        category="trading",
        summary=summary_text,
        content=digest,
        tags=["notion", "trading", "resources", "headless"],
        monetization_angle="Translate fully expanded resources into backtest-ready strategies.",
        metadata={"url": url, "page_id": page_id, "method": "headless"},
    )
    
    return {
        "url": url,
        "page_id": page_id,
        "title": extract.title,
        "method": "headless",
        "note_path": str(note_path),
        "summary_path": str(summary_path),
        "raw_path": str(raw_path),
        "exec_path": str(exec_path),
        "links": len(extract.links),
        "youtube_links": len(extract.youtube_links),
        "youtube_summaries": len(youtube_summaries),
        "code_blocks": len(extract.code_blocks),
        "action_items": len(extract.action_items),
        "resources": len(resources_list),
        "scraped_files": scraped_data.get("saved_files"),
    }


def _summarize_youtube_videos(youtube_urls: List[str]) -> Dict[str, Any]:
    """Use NotebookLM MCP to summarize YouTube videos."""
    try:
        # Import MCP client
        from core.mcp_loader import get_mcp_manager
        manager = get_mcp_manager()
        
        # Check if NotebookLM server is running
        status = manager.get_server_status()
        notebooklm_status = status.get("notebooklm", {})
        
        if not notebooklm_status.get("running"):
            return {"error": "NotebookLM MCP server not running"}
        
        # For now, return placeholder - actual MCP integration would go here
        # This would involve calling the NotebookLM MCP tools to process each video
        summaries = {}
        for url in youtube_urls:
            # TODO: Implement actual NotebookLM MCP call
            # For now, just note that it would be processed
            video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]
            summaries[video_id] = {
                "url": url,
                "status": "queued_for_notebooklm",
                "summary": None,
            }
        
        return summaries
        
    except Exception as e:
        return {"error": f"NotebookLM integration failed: {e}"}
