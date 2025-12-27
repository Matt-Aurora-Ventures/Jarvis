"""
Research Engine for Jarvis.
Autonomous web research, content extraction, and knowledge compilation.
"""

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import re

from core import config, context_manager, providers, guardian

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "research.db"
RESEARCH_QUEUE_PATH = ROOT / "data" / "research_queue.json"


class ResearchEngine:
    """Autonomous research engine that continuously learns from the web."""
    
    def __init__(self):
        self._init_db()
        self._load_queue()
        
    def _init_db(self):
        """Initialize SQLite database for research storage."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    url TEXT,
                    title TEXT,
                    content TEXT,
                    insights TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_graph (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept TEXT NOT NULL,
                    related_concepts TEXT,
                    summary TEXT,
                    examples TEXT,
                    applications TEXT,
                    confidence REAL DEFAULT 0.0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    details TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def _load_queue(self):
        """Load research queue."""
        if RESEARCH_QUEUE_PATH.exists():
            with open(RESEARCH_QUEUE_PATH, "r") as f:
                self.queue = json.load(f)
        else:
            self.queue = {
                "priority_topics": [
                    "autonomous agent architectures",
                    "LLM prompt engineering",
                    "AI self-improvement techniques",
                    "multi-agent systems",
                    "AI safety frameworks",
                    "free AI APIs and tools",
                    "open source AI projects",
                    "AGI development approaches",
                    "neural network optimization",
                    "AI consciousness theories"
                ],
                "active_research": [],
                "completed": [],
                "failed": []
            }
    
    def _save_queue(self):
        """Save research queue."""
        with open(RESEARCH_QUEUE_PATH, "w") as f:
            json.dump(self.queue, f, indent=2)
    
    def _log_action(self, action: str, details: Dict[str, Any]):
        """Log research action."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO research_log (action, details) VALUES (?, ?)",
                (action, json.dumps(details))
            )
            conn.commit()

    def _extract_keywords(self, topic: str) -> List[str]:
        words = re.findall(r"[a-z0-9]{3,}", topic.lower())
        stopwords = {
            "the", "and", "for", "with", "from", "that", "this", "into",
            "about", "what", "how", "are", "you", "your", "our", "their",
            "latest", "new", "best", "free", "open", "source", "systems",
        }
        return [w for w in words if w not in stopwords][:12]

    def _score_result(self, result: Dict[str, str], keywords: List[str]) -> int:
        url = result.get("url", "")
        title = (result.get("title") or "").lower()
        snippet = (result.get("snippet") or "").lower()
        domain = urllib.parse.urlparse(url).netloc.lower()

        preferred_domains = [
            "arxiv.org",
            "github.com",
            "huggingface.co",
            "paperswithcode.com",
            "openai.com",
            "microsoft.com",
            "google.com",
            "aws.amazon.com",
            "nvidia.com",
            "developer.apple.com",
            "solana.com",
            "docs.solana.com",
            "base.org",
            "docs.base.org",
            "bnbchain.org",
            "docs.bnbchain.org",
            "hyperliquid.xyz",
            "docs.hyperliquid.xyz",
            "jup.ag",
            "raydium.io",
            "orca.so",
            "uniswap.org",
            "pancakeswap.finance",
            "aerodrome.finance",
            "velodrome.finance",
        ]
        blocked_domains = [
            "pinterest.",
            "tiktok.",
            "instagram.",
            "facebook.",
            "reddit.com",
            "medium.com",
            "quora.com",
        ]

        score = 0
        if any(domain.endswith(d) or d in domain for d in preferred_domains):
            score += 3
        if any(blocked in domain for blocked in blocked_domains):
            score -= 3
        if url.endswith(".pdf"):
            score += 1
        for kw in keywords:
            if kw in title:
                score += 2
            elif kw in snippet:
                score += 1
        return score

    def _select_results(
        self,
        search_results: List[Dict[str, str]],
        keywords: List[str],
        max_pages: int,
    ) -> List[Dict[str, str]]:
        scored = []
        for result in search_results:
            url = result.get("url", "")
            if not url or url.startswith("javascript:"):
                continue
            score = self._score_result(result, keywords)
            scored.append((score, result))

        scored.sort(key=lambda item: item[0], reverse=True)

        selected = []
        seen_domains = set()
        for score, result in scored:
            if len(selected) >= max_pages:
                break
            if score < 1:
                continue
            domain = urllib.parse.urlparse(result.get("url", "")).netloc.lower()
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            selected.append(result)

        if not selected:
            selected = [result for _, result in scored[:max_pages]]

        return selected
    
    def search_web(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Search the web for information."""
        results = []
        
        # Method 1: DuckDuckGo Instant Answer API (no blocking)
        try:
            import requests
            
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            # Extract results from RelatedTopics
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if "Text" in topic and "FirstURL" in topic:
                    url = topic.get("FirstURL", "")
                    # Skip DuckDuckGo internal URLs
                    if url.startswith("https://duckduckgo.com/c/"):
                        continue
                    
                    results.append({
                        "title": topic.get("Text", "").split(" - ")[0],
                        "url": url,
                        "snippet": topic.get("Text", "")
                    })
            
            if results:
                self._log_action("search_completed", {"query": query, "results": len(results), "method": "ddg_api"})
                return results
                
        except Exception as e:
            self._log_action("ddg_api_error", {"query": query, "error": str(e)})
        
        # Method 2: DuckDuckGo HTML (fallback)
        try:
            import requests
            from bs4 import BeautifulSoup
            
            url = "https://duckduckgo.com/html/"
            params = {"q": query}
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            for result in soup.select(".result")[:max_results]:
                title_elem = result.select_one(".result__title a")
                snippet_elem = result.select_one(".result__snippet")
                
                if title_elem and snippet_elem:
                    url = title_elem.get("href", "")
                    # Clean DuckDuckGo redirect URLs
                    if url.startswith("/l/?uddg="):
                        import urllib.parse
                        url = urllib.parse.unquote(url.split("uddg=")[1].split("&")[0])
                    
                    results.append({
                        "title": title_elem.get_text().strip(),
                        "url": url,
                        "snippet": snippet_elem.get_text().strip()
                    })
            
            if results:
                self._log_action("search_completed", {"query": query, "results": len(results), "method": "ddg_html"})
                return results
                
        except Exception as e:
            self._log_action("ddg_html_error", {"query": query, "error": str(e)})

        # Method 2b: DuckDuckGo Lite (alternate HTML)
        try:
            import requests
            from bs4 import BeautifulSoup

            url = "https://lite.duckduckgo.com/lite/"
            params = {"q": query}
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            response = requests.post(url, data=params, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            candidates = soup.select("a.result-link")
            if not candidates:
                candidates = soup.select("a[href^='http']")

            for link in candidates[:max_results]:
                href = link.get("href", "").strip()
                title = link.get_text().strip()
                if not href or not title:
                    continue
                results.append(
                    {
                        "title": title,
                        "url": href,
                        "snippet": title,
                    }
                )

            if results:
                self._log_action("search_completed", {"query": query, "results": len(results), "method": "ddg_lite"})
                return results
        except Exception as e:
            self._log_action("ddg_lite_error", {"query": query, "error": str(e)})
        
        # Method 3: Use Brave Search API if available (free tier)
        try:
            # Check if we have Brave API key
            from core import secrets
            brave_key = getattr(secrets, 'get_brave_key', lambda: None)()
            
            if brave_key:
                url = "https://api.search.brave.com/res/v1/web/search"
                params = {"q": query, "count": max_results}
                headers = {"Accept": "application/json", "X-Subscription-Token": brave_key}
                
                response = requests.get(url, params=params, headers=headers, timeout=10)
                data = response.json()
                
                for item in data.get("web", {}).get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", "")
                    })
                
                if results:
                    self._log_action("search_completed", {"query": query, "results": len(results), "method": "brave"})
                    return results
                    
        except Exception as e:
            self._log_action("brave_error", {"query": query, "error": str(e)})
        
        self._log_action("search_failed", {"query": query, "methods_tried": 4})
        return []
    
    def extract_content(self, url: str) -> Optional[str]:
        """Extract full content from a URL."""
        try:
            import requests
            from bs4 import BeautifulSoup
            import urllib.parse
            import re
            
            # Handle DuckDuckGo redirects
            if "//duckduckgo.com/l/" in url:
                # Extract actual URL from DuckDuckGo redirect
                parsed = urllib.parse.urlparse(url)
                query = urllib.parse.parse_qs(parsed.query)
                if 'uddg' in query:
                    url = urllib.parse.unquote(query['uddg'][0])
            
            self._log_action("extracting_content", {"url": url})
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive"
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Try readability first
            try:
                from readability import Document
                doc = Document(response.content)
                soup = BeautifulSoup(doc.summary(), "html.parser")
            except Exception as e:
                # Fallback to manual extraction
                self._log_action("readability_failed", {"url": url, "error": str(e)})
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Remove unwanted elements
                for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'noscript']):
                    element.decompose()
                
                # Try to find main content
                main_content = None
                
                # Look for common content containers
                for selector in ['main', 'article', '[role="main"]', '.content', '#content', '.post-content', '.entry-content']:
                    main_content = soup.select_one(selector)
                    if main_content:
                        break
                
                if main_content:
                    soup = main_content
                else:
                    # Remove navigation menus
                    for nav in soup.find_all(['nav', 'menu']):
                        nav.decompose()
            
            # Remove remaining scripts and styles
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract text
            content = soup.get_text()
            
            # Clean up text
            # Remove multiple newlines
            content = re.sub(r'\n\s*\n', '\n\n', content)
            # Remove extra whitespace
            content = re.sub(r' +', ' ', content)
            # Remove leading/trailing whitespace on each line
            lines = [line.strip() for line in content.split('\n')]
            content = '\n'.join(line for line in lines if line)
            
            # Limit size but keep important parts
            if len(content) > 10000:
                content = content[:10000] + "\n\n[Content truncated...]"
            
            # Check if we got meaningful content
            if len(content) < 100:
                self._log_action("content_too_short", {"url": url, "length": len(content)})
                return None
            
            self._log_action("content_extracted", {
                "url": url,
                "content_length": len(content),
                "preview": content[:200] + "..."
            })
            
            return content
            
        except requests.exceptions.RequestException as e:
            self._log_action("extract_http_error", {"url": url, "error": str(e)})
            return None
        except Exception as e:
            self._log_action("extract_error", {"url": url, "error": str(e)})
            return None
    
    def process_content(self, topic: str, content: str, url: str = "", focus: str = "") -> Dict[str, Any]:
        """Process content to extract insights."""
        focus_clause = f"\nFocus on: {focus}\n" if focus else "\n"
        prompt = f"""Analyze this research content about {topic}:{focus_clause}

{content[:5000]}

Extract:
1. Key insights and findings
2. Practical applications
3. Related concepts
4. Actionable improvements for an AI assistant
5. Code examples or patterns mentioned

Output as JSON with keys: insights, applications, concepts, improvements, examples"""
        
        try:
            response = providers.ask_llm(prompt, max_output_tokens=1500)
            if response:
                try:
                    return json.loads(response)
                except Exception as e:
                    return {
                        "insights": [response],
                        "applications": [],
                        "concepts": [],
                        "improvements": [],
                        "examples": []
                    }
        except Exception as e:
            self._log_action("processing_error", {"topic": topic, "error": str(e)})
        
        return {"insights": [], "applications": [], "concepts": [], "improvements": [], "examples": []}
    
    def store_research(self, topic: str, url: str, title: str, content: str, insights: Dict[str, Any]):
        """Store research in database."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO research_notes 
                (topic, url, title, content, insights)
                VALUES (?, ?, ?, ?, ?)
            """, (topic, url, title, content, json.dumps(insights)))
            conn.commit()
    
    def update_knowledge_graph(self, insights: Dict[str, Any]):
        """Update knowledge graph with new concepts."""
        concepts = insights.get("concepts", [])
        
        with sqlite3.connect(DB_PATH) as conn:
            for concept in concepts:
                # Check if concept exists
                cursor = conn.execute(
                    "SELECT id FROM knowledge_graph WHERE concept = ?",
                    (concept,)
                )
                
                if not cursor.fetchone():
                    conn.execute("""
                        INSERT INTO knowledge_graph 
                        (concept, related_concepts, summary, examples, applications, confidence)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        concept,
                        json.dumps(concepts[:5]),
                        json.dumps(insights.get("insights", [])[:3]),
                        json.dumps(insights.get("examples", [])[:3]),
                        json.dumps(insights.get("applications", [])[:3]),
                        0.8
                    ))
            
            conn.commit()
    
    def _summarize_research(self, topic: str, sources: List[Dict[str, Any]], focus: str = "") -> str:
        if not sources:
            return ""
        focus_clause = f" Focus on: {focus}." if focus else ""
        prompt = (
            f"Create a concise, deep research summary about {topic}.{focus_clause}\n\n"
            "Sources and insights:\n"
            f"{json.dumps([{'title': s['title'], 'url': s['url'], 'insights': s.get('insights', [])} for s in sources], indent=2)}\n\n"
            "Provide:\n"
            "1. Executive summary (2 short paragraphs)\n"
            "2. Key findings (5-7 bullets)\n"
            "3. Open questions or risks\n"
        )
        try:
            response = providers.ask_llm(prompt, max_output_tokens=700)
            if response:
                return response.strip()
        except Exception:
            pass

        findings = []
        for source in sources:
            findings.extend(source.get("insights", [])[:2])
        findings = [item for item in findings if item][:8]
        if not findings:
            return "No summary available."
        bullets = "\n".join(f"- {item}" for item in findings)
        return f"Key findings:\n{bullets}"

    def research_topic(self, topic: str, max_pages: int = 5, focus: str = "") -> Dict[str, Any]:
        """Research a topic comprehensively."""
        self._log_action("research_started", {"topic": topic})
        
        # Search for content
        search_results = self.search_web(topic, max_results=20)
        
        if not search_results:
            self._log_action("research_failed", {"topic": topic, "reason": "no_results"})
            return {"success": False, "error": "No search results"}
        
        keywords = self._extract_keywords(topic)
        selected_results = self._select_results(search_results, keywords, max_pages)

        # Process top results
        processed = 0
        sources: List[Dict[str, Any]] = []
        for i, result in enumerate(selected_results):
            url = result["url"]
            if not url or url.startswith("javascript:"):
                self._log_action("skipping_invalid_url", {"index": i, "url": url})
                continue
                
            self._log_action("processing_result", {"index": i, "url": url})
            content = self.extract_content(url)
            
            if content:
                self._log_action("content_extracted_for_storage", {
                    "index": i,
                    "url": url,
                    "length": len(content)
                })
                
                if len(content) > 500:
                    insights = self.process_content(topic, content, url, focus=focus)
                    
                    # Store research
                    self.store_research(topic, url, result["title"], content, insights)
                    self._log_action("research_stored", {"index": i, "url": url})
                    
                    # Update knowledge graph
                    self.update_knowledge_graph(insights)
                    
                    processed += 1
                    time.sleep(2)  # Rate limiting
                    sources.append({
                        "title": result.get("title", ""),
                        "url": url,
                        "insights": insights.get("insights", [])[:5],
                        "applications": insights.get("applications", [])[:3],
                    })
                else:
                    self._log_action("content_too_short_for_storage", {
                        "index": i,
                        "url": url,
                        "length": len(content)
                    })
            else:
                self._log_action("failed_to_extract_content", {"index": i, "url": url})
        
        summary = self._summarize_research(topic, sources, focus=focus)
        key_findings = []
        for source in sources:
            key_findings.extend(source.get("insights", [])[:2])
        key_findings = [item for item in key_findings if item][:10]

        self._log_action("research_completed", {
            "topic": topic,
            "pages_processed": processed,
            "sources": len(sources),
        })
        
        return {
            "success": True,
            "topic": topic,
            "pages_processed": processed,
            "total_results": len(search_results),
            "summary": summary,
            "sources": [{"title": s["title"], "url": s["url"]} for s in sources],
            "key_findings": key_findings,
        }
    
    def get_research_summary(self, topic: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get research summary."""
        with sqlite3.connect(DB_PATH) as conn:
            if topic:
                cursor = conn.execute("""
                    SELECT topic, url, title, insights, timestamp
                    FROM research_notes
                    WHERE topic LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (f"%{topic}%", limit))
            else:
                cursor = conn.execute("""
                    SELECT topic, url, title, insights, timestamp
                    FROM research_notes
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "topic": row[0],
                    "url": row[1],
                    "title": row[2],
                    "insights": json.loads(row[3]),
                    "timestamp": row[4]
                })
            
            return results
    
    def get_knowledge_graph(self, concept: str = None) -> List[Dict[str, Any]]:
        """Get knowledge graph entries."""
        with sqlite3.connect(DB_PATH) as conn:
            if concept:
                cursor = conn.execute("""
                    SELECT concept, related_concepts, summary, examples, applications, confidence
                    FROM knowledge_graph
                    WHERE concept LIKE ? OR related_concepts LIKE ?
                    ORDER BY confidence DESC
                """, (f"%{concept}%", f"%{concept}%"))
            else:
                cursor = conn.execute("""
                    SELECT concept, related_concepts, summary, examples, applications, confidence
                    FROM knowledge_graph
                    ORDER BY confidence DESC
                    LIMIT 50
                """)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "concept": row[0],
                    "related_concepts": json.loads(row[1]),
                    "summary": json.loads(row[2]),
                    "examples": json.loads(row[3]),
                    "applications": json.loads(row[4]),
                    "confidence": row[5]
                })
            
            return results


# Global research engine instance
_research_engine: Optional[ResearchEngine] = None


def get_research_engine() -> ResearchEngine:
    """Get the global research engine instance."""
    global _research_engine
    if not _research_engine:
        _research_engine = ResearchEngine()
    return _research_engine
