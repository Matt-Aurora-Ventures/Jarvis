"""
Web Content Extraction and Organization System.
Extracts content from web pages and organizes into structured files.
"""

import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from core import storage_utils

ROOT = Path(__file__).resolve().parents[1]
ORGANIZER_PATH = ROOT / "data" / "web_organizer"


class WebOrganizer:
    """Extracts and organizes web content automatically."""
    
    def __init__(self):
        self.storage = storage_utils.get_storage(ORGANIZER_PATH)
        self.content_types = {
            "article": ["article", "blog", "post", "news"],
            "research": ["research", "paper", "study", "journal"],
            "tutorial": ["tutorial", "guide", "howto", "learn"],
            "documentation": ["docs", "documentation", "api", "reference"],
            "product": ["product", "service", "tool", "software"],
            "company": ["company", "about", "team", "mission"]
        }
    
    def extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content from URL using curl."""
        try:
            # Use curl to get the page content
            result = subprocess.run([
                "curl", "-s", "-L",
                "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                url
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {"success": False, "error": f"Failed to fetch: {result.stderr}"}
            
            html_content = result.stdout
            
            # Extract key information
            extracted = self._parse_html_content(html_content, url)
            extracted["success"] = True
            extracted["url"] = url
            extracted["extracted_at"] = datetime.now().isoformat()
            
            return extracted
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _parse_html_content(self, html: str, url: str) -> Dict[str, Any]:
        """Parse HTML content and extract key information."""
        content = {
            "title": self._extract_title(html),
            "description": self._extract_description(html),
            "main_content": self._extract_main_content(html),
            "links": self._extract_links(html, url),
            "images": self._extract_images(html, url),
            "metadata": self._extract_metadata(html),
            "content_type": self._determine_content_type(html, url)
        }
        
        return content
    
    def _extract_title(self, html: str) -> str:
        """Extract page title."""
        # Try title tag first
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            # Clean up title
            title = re.sub(r'\s+', ' ', title)
            return title
        
        # Try h1 tag
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
        if h1_match:
            title = h1_match.group(1).strip()
            title = re.sub(r'<[^>]+>', '', title)  # Remove HTML tags
            title = re.sub(r'\s+', ' ', title)
            return title
        
        return "Untitled"
    
    def _extract_description(self, html: str) -> str:
        """Extract page description."""
        # Try meta description
        meta_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if meta_match:
            return meta_match.group(1).strip()
        
        # Try og:description
        og_match = re.search(r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if og_match:
            return og_match.group(1).strip()
        
        # Try first paragraph
        p_match = re.search(r'<p[^>]*>(.*?)</p>', html, re.IGNORECASE | re.DOTALL)
        if p_match:
            desc = p_match.group(1).strip()
            desc = re.sub(r'<[^>]+>', '', desc)  # Remove HTML tags
            desc = re.sub(r'\s+', ' ', desc)
            if len(desc) > 50:
                return desc[:200] + "..." if len(desc) > 200 else desc
        
        return ""
    
    def _extract_main_content(self, html: str) -> str:
        """Extract main content from the page."""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Try common content selectors
        content_selectors = [
            r'<main[^>]*>(.*?)</main>',
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]*class=["\'][^"\']*content[^"\']*["\'][^>]*>(.*?)</div>',
            r'<div[^>]*id=["\'][^"\']*content[^"\']*["\'][^>]*>(.*?)</div>'
        ]
        
        for selector in content_selectors:
            match = re.search(selector, html, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1)
                # Clean up HTML
                content = re.sub(r'<[^>]+>', '\n', content)  # Replace tags with newlines
                content = re.sub(r'\n+', '\n', content)  # Multiple newlines to single
                content = re.sub(r'\s+', ' ', content)  # Multiple spaces to single
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                return '\n'.join(lines[:20])  # First 20 meaningful lines
        
        # Fallback: extract all paragraph text
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.IGNORECASE | re.DOTALL)
        if paragraphs:
            content = []
            for p in paragraphs:
                text = re.sub(r'<[^>]+>', '', p).strip()
                text = re.sub(r'\s+', ' ', text)
                if len(text) > 20:  # Only meaningful paragraphs
                    content.append(text)
            return '\n'.join(content[:10])  # First 10 paragraphs
        
        return ""
    
    def _extract_links(self, html: str, base_url: str) -> List[Dict[str, str]]:
        """Extract links from the page."""
        link_pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
        matches = re.findall(link_pattern, html, re.IGNORECASE | re.DOTALL)
        
        links = []
        for href, text in matches:
            href = href.strip()
            text = re.sub(r'<[^>]+>', '', text).strip()
            text = re.sub(r'\s+', ' ', text)
            
            # Convert relative URLs to absolute
            if href.startswith('/'):
                parsed = urlparse(base_url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            elif not href.startswith(('http://', 'https://')):
                href = urljoin(base_url, href)
            
            # Skip empty links and anchors
            if href and not href.startswith('#') and text:
                links.append({
                    "url": href,
                    "text": text[:100],  # Limit text length
                    "domain": urlparse(href).netloc
                })
        
        return links[:20]  # Limit to first 20 links
    
    def _extract_images(self, html: str, base_url: str) -> List[Dict[str, str]]:
        """Extract images from the page."""
        img_pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\']'
        matches = re.findall(img_pattern, html, re.IGNORECASE)
        
        images = []
        for src, alt in matches:
            src = src.strip()
            alt = alt.strip()
            
            # Convert relative URLs to absolute
            if src.startswith('/'):
                parsed = urlparse(base_url)
                src = f"{parsed.scheme}://{parsed.netloc}{src}"
            elif not src.startswith(('http://', 'https://')):
                src = urljoin(base_url, src)
            
            images.append({
                "url": src,
                "alt": alt[:100]
            })
        
        return images[:10]  # Limit to first 10 images
    
    def _extract_metadata(self, html: str) -> Dict[str, str]:
        """Extract metadata from the page."""
        metadata = {}
        
        # Common meta tags
        meta_patterns = {
            "author": r'<meta[^>]*name=["\']author["\'][^>]*content=["\']([^"\']+)["\']',
            "keywords": r'<meta[^>]*name=["\']keywords["\'][^>]*content=["\']([^"\']+)["\']',
            "published_date": r'<meta[^>]*property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']',
            "site_name": r'<meta[^>]*property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)["\']'
        }
        
        for key, pattern in meta_patterns.items():
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                metadata[key] = match.group(1).strip()
        
        return metadata
    
    def _determine_content_type(self, html: str, url: str) -> str:
        """Determine the type of content based on URL and content."""
        url_lower = url.lower()
        html_lower = html.lower()
        
        # Check URL patterns first
        for content_type, keywords in self.content_types.items():
            for keyword in keywords:
                if keyword in url_lower:
                    return content_type
        
        # Check content patterns
        for content_type, keywords in self.content_types.items():
            for keyword in keywords:
                if keyword in html_lower:
                    return content_type
        
        return "general"
    
    def organize_and_save(self, url: str) -> Dict[str, Any]:
        """Extract content and organize into files."""
        # Extract content
        extracted = self.extract_content(url)
        
        if not extracted["success"]:
            return extracted
        
        # Create organized filename
        safe_title = re.sub(r'[^\w\s-]', '', extracted["title"])
        safe_title = re.sub(r'[-\s]+', '-', safe_title)
        filename = f"{extracted['content_type']}_{safe_title[:50]}_{int(time.time())}"
        
        # Save as structured data
        self.storage.save_txt(f"extracted_{filename}", extracted)
        
        # Create markdown summary
        markdown_content = self._create_markdown_summary(extracted)
        self.storage.save_md(f"summary_{filename}", markdown_content)
        
        # Add to index
        self._add_to_index(extracted, filename)
        
        extracted["saved_as"] = filename
        return extracted
    
    def _create_markdown_summary(self, extracted: Dict[str, Any]) -> str:
        """Create a markdown summary of the extracted content."""
        md = f"# {extracted['title']}\n\n"
        md += f"**URL:** {extracted['url']}\n"
        md += f"**Type:** {extracted['content_type']}\n"
        md += f"**Extracted:** {extracted['extracted_at']}\n\n"
        
        if extracted["description"]:
            md += f"## Description\n{extracted['description']}\n\n"
        
        if extracted["metadata"]:
            md += "## Metadata\n"
            for key, value in extracted["metadata"].items():
                md += f"- **{key}:** {value}\n"
            md += "\n"
        
        if extracted["main_content"]:
            md += "## Main Content\n\n"
            md += extracted["main_content"][:1000]
            if len(extracted["main_content"]) > 1000:
                md += "\n\n... (content truncated)"
            md += "\n\n"
        
        if extracted["links"]:
            md += "## Key Links\n\n"
            for link in extracted["links"][:10]:
                md += f"- [{link['text']}]({link['url']})\n"
            md += "\n"
        
        return md
    
    def _add_to_index(self, extracted: Dict[str, Any], filename: str):
        """Add extracted content to the index."""
        index = self.storage.load_txt("content_index", "list") or []
        
        index_entry = {
            "filename": filename,
            "title": extracted["title"],
            "url": extracted["url"],
            "content_type": extracted["content_type"],
            "extracted_at": extracted["extracted_at"],
            "description": extracted["description"][:200]
        }
        
        index.append(index_entry)
        
        # Keep only last 100 entries
        if len(index) > 100:
            index = index[-100:]
        
        self.storage.save_txt("content_index", index)
    
    def search_content(self, query: str, content_type: str = None) -> List[Dict[str, Any]]:
        """Search through extracted content."""
        index = self.storage.load_txt("content_index", "list") or []
        
        results = []
        query_lower = query.lower()
        
        for entry in index:
            # Filter by content type if specified
            if content_type and entry["content_type"] != content_type:
                continue
            
            # Search in title, description, and URL
            searchable_text = f"{entry['title']} {entry['description']} {entry['url']}"
            if query_lower in searchable_text.lower():
                results.append(entry)
        
        return results
    
    def get_content_summary(self) -> Dict[str, Any]:
        """Get summary of all organized content."""
        index = self.storage.load_txt("content_index", "list") or []
        
        summary = {
            "total_items": len(index),
            "content_types": {},
            "recent_items": index[-10:],
            "domains": {}
        }
        
        for entry in index:
            # Count content types
            content_type = entry["content_type"]
            summary["content_types"][content_type] = summary["content_types"].get(content_type, 0) + 1
            
            # Count domains
            domain = entry["url"].split('/')[2] if '/' in entry["url"] else "unknown"
            summary["domains"][domain] = summary["domains"].get(domain, 0) + 1
        
        return summary


# Global web organizer instance
_organizer: Optional[WebOrganizer] = None


def get_web_organizer() -> WebOrganizer:
    """Get the global web organizer instance."""
    global _organizer
    if not _organizer:
        _organizer = WebOrganizer()
    return _organizer
