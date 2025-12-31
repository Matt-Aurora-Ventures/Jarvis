#!/usr/bin/env python3
"""
Deep Notion Extractor - Recursively fetches ALL nested content.

The Notion public API (loadPageChunk) often doesn't return all child blocks
in a single request. This module makes multiple requests to ensure we get
all nested content from toggles, sub-headers, and other container blocks.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "notion_deep"


def extract_page_id(url: str) -> Optional[str]:
    """Extract and format page ID from Notion URL."""
    match = re.search(r"([a-f0-9]{32})", url)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


def fetch_page_chunk(page_id: str, cursor: Dict = None, limit: int = 100) -> Dict[str, Any]:
    """Fetch a single chunk from Notion's public API."""
    url = "https://www.notion.so/api/v3/loadPageChunk"
    payload = {
        "pageId": page_id,
        "limit": limit,
        "cursor": cursor or {"stack": []},
        "chunkNumber": 0,
        "verticalColumns": False,
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_block_children(block_id: str, limit: int = 100) -> Dict[str, Any]:
    """Fetch children of a specific block using syncRecordValues."""
    url = "https://www.notion.so/api/v3/syncRecordValues"

    # Format block ID without dashes for the API
    clean_id = block_id.replace("-", "")

    payload = {
        "requests": [
            {
                "pointer": {
                    "table": "block",
                    "id": block_id
                },
                "version": -1
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching block {block_id}: {e}")
        return {}


def deep_fetch_notion_page(
    url: str,
    max_iterations: int = 50,
    delay_ms: int = 200,
) -> Dict[str, Any]:
    """
    Recursively fetch ALL blocks from a Notion page.

    Uses multiple API calls to ensure nested content is retrieved.
    """
    page_id = extract_page_id(url)
    if not page_id:
        return {"error": "Invalid URL - could not extract page ID"}

    print(f"Fetching page: {page_id}")

    all_blocks: Dict[str, Any] = {}
    blocks_to_fetch: Set[str] = {page_id}
    fetched: Set[str] = set()
    iteration = 0

    while blocks_to_fetch and iteration < max_iterations:
        iteration += 1
        current_batch = list(blocks_to_fetch)[:10]  # Fetch 10 at a time
        blocks_to_fetch -= set(current_batch)

        for block_id in current_batch:
            if block_id in fetched:
                continue
            fetched.add(block_id)

            print(f"  Iteration {iteration}: Fetching {block_id}...")

            try:
                # Try fetching as a page first
                data = fetch_page_chunk(block_id)
                record_map = data.get("recordMap", {})
                blocks = record_map.get("block", {})

                if not blocks:
                    # Try syncRecordValues for individual blocks
                    sync_data = fetch_block_children(block_id)
                    blocks = sync_data.get("recordMap", {}).get("block", {})

                # Merge blocks
                for bid, bdata in blocks.items():
                    if bid not in all_blocks:
                        all_blocks[bid] = bdata

                    # Queue children for fetching
                    value = bdata.get("value", {})
                    children = value.get("content", []) or []
                    for child_id in children:
                        if child_id not in fetched and child_id not in all_blocks:
                            blocks_to_fetch.add(child_id)

                time.sleep(delay_ms / 1000)

            except Exception as e:
                print(f"    Error: {e}")
                continue

        print(f"  Total blocks: {len(all_blocks)}, Remaining to fetch: {len(blocks_to_fetch)}")

    return {
        "page_id": page_id,
        "url": url,
        "total_blocks": len(all_blocks),
        "iterations": iteration,
        "blocks": all_blocks,
    }


def extract_text_from_rich_text(prop: Any) -> Tuple[str, List[str]]:
    """Extract plain text and links from Notion rich text property."""
    if not prop:
        return "", []

    chunks = []
    links = []

    for segment in prop:
        if not segment:
            continue
        if isinstance(segment, list):
            text = segment[0]
            chunks.append(str(text))
            # Check for link formatting
            if len(segment) > 1:
                for fmt in segment[1]:
                    if isinstance(fmt, list) and fmt and fmt[0] == "a":
                        links.append(fmt[1])
        else:
            chunks.append(str(segment))

    return "".join(chunks).strip(), links


def extract_block_content(block: Dict[str, Any]) -> Dict[str, Any]:
    """Extract content from a single block."""
    value = block.get("value", {})
    block_type = value.get("type", "unknown")

    # Get title/text
    props = value.get("properties", {})
    title_prop = props.get("title", [])
    text, links = extract_text_from_rich_text(title_prop)

    # Get code language if applicable
    language = ""
    if block_type == "code":
        lang_prop = props.get("language", [])
        if lang_prop and isinstance(lang_prop, list) and lang_prop[0]:
            language = str(lang_prop[0][0])

    # Extract URLs from the block JSON
    raw = json.dumps(value, ensure_ascii=True)
    embedded_urls = re.findall(r"https?://[^\"\\\s]+", raw)

    return {
        "type": block_type,
        "text": text,
        "links": links,
        "language": language,
        "embedded_urls": embedded_urls,
        "children": value.get("content", []) or [],
    }


def build_content_tree(blocks: Dict[str, Any], root_id: str) -> Dict[str, Any]:
    """Build a hierarchical content tree from flat blocks."""

    def walk(block_id: str, depth: int = 0) -> Dict[str, Any]:
        if block_id not in blocks:
            return {"id": block_id, "missing": True}

        block = blocks[block_id]
        content = extract_block_content(block)

        result = {
            "id": block_id,
            "depth": depth,
            **content,
        }

        # Recursively process children
        if content["children"]:
            result["children_content"] = [
                walk(child_id, depth + 1)
                for child_id in content["children"]
            ]

        return result

    return walk(root_id)


def extract_all_youtube_links(blocks: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract all YouTube links from blocks."""
    youtube_links = []
    seen_urls = set()

    youtube_patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]+)',
        r'https?://youtu\.be/([A-Za-z0-9_-]+)',
        r'https?://(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]+)',
    ]

    for block_id, block in blocks.items():
        content = extract_block_content(block)
        all_urls = content["links"] + content["embedded_urls"]

        for url in all_urls:
            if url in seen_urls:
                continue

            for pattern in youtube_patterns:
                match = re.search(pattern, url)
                if match:
                    seen_urls.add(url)
                    video_id = match.group(1)
                    youtube_links.append({
                        "url": url,
                        "video_id": video_id,
                        "found_in_block": block_id,
                        "context": content["text"][:100] if content["text"] else "",
                    })
                    break

    return youtube_links


def extract_all_external_links(blocks: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract all external (non-Notion, non-YouTube) links."""
    external_links = []
    seen_urls = set()

    skip_domains = [
        "notion.so", "notion.site", "youtube.com", "youtu.be",
        "s3.us-west-2.amazonaws.com",  # Notion assets
    ]

    for block_id, block in blocks.items():
        content = extract_block_content(block)
        all_urls = content["links"] + content["embedded_urls"]

        for url in all_urls:
            if url in seen_urls:
                continue

            # Skip internal/asset URLs
            if any(domain in url for domain in skip_domains):
                continue

            seen_urls.add(url)
            external_links.append({
                "url": url,
                "found_in_block": block_id,
                "context": content["text"][:100] if content["text"] else "",
            })

    return external_links


def extract_sections(blocks: Dict[str, Any], root_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """Extract content organized by section headers."""
    sections = {}
    current_section = "Overview"
    sections[current_section] = []

    # Find root block to get top-level content order
    root_block = blocks.get(root_id, {})
    root_content = root_block.get("value", {}).get("content", [])

    def process_block(block_id: str, depth: int = 0) -> None:
        nonlocal current_section

        if block_id not in blocks:
            return

        block = blocks[block_id]
        content = extract_block_content(block)

        # Update current section on header blocks
        if content["type"] in ["header", "sub_header", "sub_sub_header"]:
            if content["text"]:
                current_section = content["text"]
                if current_section not in sections:
                    sections[current_section] = []

        # Add content to current section
        if content["text"]:
            sections.setdefault(current_section, []).append({
                "block_id": block_id,
                "type": content["type"],
                "text": content["text"],
                "depth": depth,
                "links": content["links"],
                "embedded_urls": content["embedded_urls"],
            })

        # Process children
        for child_id in content["children"]:
            process_block(child_id, depth + 1)

    for block_id in root_content:
        process_block(block_id, 0)

    return sections


def deep_extract_notion(
    url: str,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Main entry point for deep Notion extraction.
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fetch all blocks
    fetch_result = deep_fetch_notion_page(url)

    if "error" in fetch_result:
        return fetch_result

    blocks = fetch_result["blocks"]
    page_id = fetch_result["page_id"]

    # Extract page title
    root_block = blocks.get(page_id, {})
    root_props = root_block.get("value", {}).get("properties", {})
    title_prop = root_props.get("title", [])
    title, _ = extract_text_from_rich_text(title_prop)
    title = title or "Untitled"

    # Build structured extracts
    sections = extract_sections(blocks, page_id)
    youtube_links = extract_all_youtube_links(blocks)
    external_links = extract_all_external_links(blocks)

    # Count block types
    type_counts = {}
    for block in blocks.values():
        btype = block.get("value", {}).get("type", "unknown")
        type_counts[btype] = type_counts.get(btype, 0) + 1

    result = {
        "url": url,
        "page_id": page_id,
        "title": title,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_blocks": len(blocks),
            "fetch_iterations": fetch_result["iterations"],
            "sections": len(sections),
            "youtube_links": len(youtube_links),
            "external_links": len(external_links),
            "block_types": type_counts,
        },
        "sections": sections,
        "youtube_links": youtube_links,
        "external_links": external_links,
    }

    # Save outputs
    timestamp = int(time.time())
    base_name = f"notion_deep_{timestamp}"

    # Save full JSON
    json_path = output_dir / f"{base_name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Save raw blocks for reference
    raw_path = output_dir / f"{base_name}_raw.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({"blocks": blocks}, f, indent=2, ensure_ascii=False)

    # Save markdown
    md_path = output_dir / f"{base_name}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"**Source:** {url}\n")
        f.write(f"**Extracted:** {result['extracted_at']}\n\n")
        f.write(f"## Stats\n\n")
        for k, v in result['stats'].items():
            f.write(f"- {k}: {v}\n")
        f.write("\n## Content by Section\n\n")

        for section_name, items in sections.items():
            f.write(f"### {section_name}\n\n")
            for item in items:
                indent = "  " * item.get("depth", 0)
                f.write(f"{indent}- {item['text']}\n")
                for link in item.get("links", []):
                    f.write(f"{indent}  - Link: {link}\n")
            f.write("\n")

        if youtube_links:
            f.write("## YouTube Links\n\n")
            for yt in youtube_links:
                f.write(f"- [{yt['video_id']}]({yt['url']})\n")
                if yt.get("context"):
                    f.write(f"  - Context: {yt['context']}\n")
            f.write("\n")

        if external_links:
            f.write("## External Links\n\n")
            for link in external_links:
                f.write(f"- {link['url']}\n")
                if link.get("context"):
                    f.write(f"  - Context: {link['context']}\n")

    result["saved_files"] = {
        "json": str(json_path),
        "raw": str(raw_path),
        "markdown": str(md_path),
    }

    print(f"\n{'='*60}")
    print(f"Deep Extraction Complete!")
    print(f"{'='*60}")
    print(f"Title: {title}")
    print(f"Total blocks: {result['stats']['total_blocks']}")
    print(f"Sections: {result['stats']['sections']}")
    print(f"YouTube links: {result['stats']['youtube_links']}")
    print(f"External links: {result['stats']['external_links']}")
    print(f"Files saved: {result['saved_files']}")

    return result


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "https://wonderful-kick-36b.notion.site/Free-Algo-Trading-Roadmap-Resources-Discord-7fa3d54e7a3046cc87bc787694fdeaf6"

    print(f"Starting deep extraction of: {url}")
    result = deep_extract_notion(url)
