#!/usr/bin/env python3
"""
Enhanced Search Pipeline - Improves query formation, result quality, and ingestion
Fixes the "nonsensical web search" issue identified in the audit
"""

import json
import re
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set
from urllib.parse import urlparse
import sqlite3

from core import providers
from core.guardian import guard

ROOT = Path(__file__).resolve().parents[1]
SEARCH_CACHE_PATH = ROOT / "data" / "search_cache.db"
QUALITY_THRESHOLDS_PATH = ROOT / "data" / "search_quality.json"


class SearchQueryOptimizer:
    """Optimizes search queries for better results."""
    
    def __init__(self):
        self.quality_patterns = self._load_quality_patterns()
    
    def _load_quality_patterns(self) -> Dict[str, List[str]]:
        """Load patterns for high-quality queries."""
        return {
            "technical": [
                "tutorial", "guide", "documentation", "api", "example",
                "implementation", "best practices", "architecture", "pattern"
            ],
            "research": [
                "study", "research", "analysis", "findings", "paper", 
                "survey", "evaluation", "comparison", "benchmark"
            ],
            "practical": [
                "how to", "step by step", "practical", "real world",
                "case study", "implementation", "deployment", "production"
            ],
            "current": [
                "2024", "2025", "latest", "recent", "modern", "current",
                "state of the art", "cutting edge"
            ]
        }
    
    def optimize_query(self, topic: str, intent: str = "general", focus: str = "") -> str:
        """Optimize a search query for better results."""
        
        # Base query cleaning
        base_query = topic.strip().lower()
        
        # Remove overly broad terms
        broad_terms = ["what", "how", "why", "when", "where", "and", "the", "a", "an"]
        words = base_query.split()
        words = [w for w in words if w not in broad_terms and len(w) > 2]
        
        # Add intent-specific modifiers
        if intent == "technical":
            words.extend(["tutorial", "implementation"])
        elif intent == "research":
            words.extend(["research", "findings"])
        elif intent == "practical":
            words.extend(["practical", "guide"])
        
        # Add focus terms
        if focus:
            focus_words = focus.lower().split()
            words.extend(focus_words[:3])  # Limit focus terms
        
        # Add current year for recent content
        if "2024" not in base_query and "2025" not in base_query:
            words.append("2025")
        
        # Remove duplicates and limit length
        words = list(dict.fromkeys(words))  # Preserve order, remove duplicates
        if len(words) > 8:
            words = words[:8]
        
        optimized_query = " ".join(words)
        
        # Special handling for different domains
        if "ai" in base_query or "machine learning" in base_query:
            optimized_query += " neural networks"
        elif "crypto" in base_query or "trading" in base_query:
            optimized_query += " strategies analysis"
        elif "autonomous" in base_query:
            optimized_query += " agent architecture"
        
        return optimized_query
    
    def generate_query_variations(self, base_query: str, max_variations: int = 3) -> List[str]:
        """Generate variations of a query for better coverage."""
        variations = [base_query]
        
        # Variation 1: Add "tutorial" or "guide"
        if "tutorial" not in base_query and "guide" not in base_query:
            variations.append(f"{base_query} tutorial guide")
        
        # Variation 2: Add "implementation" or "example"
        if "implementation" not in base_query:
            variations.append(f"{base_query} implementation example")
        
        # Variation 3: Add "research" or "study"
        if "research" not in base_query and "study" not in base_query:
            variations.append(f"{base_query} research study")
        
        return variations[:max_variations]


class SearchResultQualityScorer:
    """Scores and filters search results for quality."""
    
    def __init__(self):
        self.quality_signals = self._init_quality_signals()
        self.domain_blacklist = self._load_domain_blacklist()
    
    def _init_quality_signals(self) -> Dict[str, float]:
        """Initialize quality scoring signals."""
        return {
            # High-quality domains
            "github.com": 0.9,
            "stackoverflow.com": 0.8,
            "medium.com": 0.7,
            "dev.to": 0.7,
            "arxiv.org": 0.9,
            "paperswithcode.com": 0.8,
            " towardsdatascience.com": 0.7,
            "realpython.com": 0.8,
            "docs.python.org": 0.9,
            "pytorch.org": 0.8,
            "tensorflow.org": 0.8,
            "openai.com": 0.8,
            "anthropic.com": 0.8,
            
            # Medium quality
            "wikipedia.org": 0.6,
            "reddit.com": 0.5,
            "youtube.com": 0.5,
            
            # Low quality (spam, content farms)
            "buzzfeed.com": 0.1,
            "huffpost.com": 0.2,
        }
    
    def _load_domain_blacklist(self) -> Set[str]:
        """Load domains to always exclude."""
        return {
            "ads.google.com",
            "facebook.com/tr",
            "twitter.com/intent",
            "linkedin.com/share",
            "pinterest.com/pin",
        }
    
    def score_result(self, result: Dict[str, str]) -> float:
        """Score a single search result."""
        score = 0.5  # Base score
        
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        
        # Domain quality
        domain = urlparse(url).netloc.lower()
        if domain in self.quality_signals:
            score = self.quality_signals[domain]
        
        # Title quality signals
        title_lower = title.lower()
        if any(signal in title_lower for signal in ["tutorial", "guide", "how to"]):
            score += 0.2
        if any(signal in title_lower for signal in ["2024", "2025", "latest"]):
            score += 0.1
        if any(signal in title_lower for signal in ["clickbait", "you won't believe"]):
            score -= 0.3
        
        # Snippet quality
        snippet_lower = snippet.lower()
        if len(snippet) > 100:  # Substantial content
            score += 0.1
        if any(signal in snippet_lower for signal in ["example", "implementation", "code"]):
            score += 0.15
        
        # URL structure
        if "blog" in url or "tutorial" in url or "docs" in url:
            score += 0.1
        if len(url.split('/')) > 6:  # Deep URLs often better
            score += 0.05
        
        # Penalty for short content
        if len(snippet) < 50:
            score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    def filter_results(self, results: List[Dict[str, str]], min_score: float = 0.3) -> List[Dict[str, str]]:
        """Filter results by quality score."""
        filtered = []
        
        for result in results:
            # Check blacklist
            url = result.get("url", "")
            domain = urlparse(url).netloc.lower()
            if any(blacklisted in domain for blacklisted in self.domain_blacklist):
                continue
            
            # Score and filter
            score = self.score_result(result)
            if score >= min_score:
                result["quality_score"] = score
                filtered.append(result)
        
        # Sort by score
        filtered.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        return filtered


class SearchCache:
    """Caches search results to avoid redundant requests."""
    
    def __init__(self):
        self._init_cache_db()
    
    def _init_cache_db(self):
        """Initialize cache database."""
        SEARCH_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(SEARCH_CACHE_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    query_hash TEXT PRIMARY KEY,
                    query TEXT,
                    results TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content_cache (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT,
                    content TEXT,
                    title TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    content_length INTEGER
                )
            """)
            
            # Clean old entries (older than 7 days)
            week_ago = datetime.now() - timedelta(days=7)
            conn.execute("DELETE FROM search_cache WHERE timestamp < ?", (week_ago,))
            conn.execute("DELETE FROM content_cache WHERE timestamp < ?", (week_ago,))
            conn.commit()
    
    def _hash_query(self, query: str) -> str:
        """Generate hash for query."""
        return hashlib.md5(query.lower().encode()).hexdigest()
    
    def _hash_url(self, url: str) -> str:
        """Generate hash for URL."""
        return hashlib.md5(url.encode()).hexdigest()
    
    def get_search_results(self, query: str) -> Optional[List[Dict[str, str]]]:
        """Get cached search results."""
        query_hash = self._hash_query(query)
        
        with sqlite3.connect(SEARCH_CACHE_PATH) as conn:
            cursor = conn.execute(
                "SELECT results, access_count FROM search_cache WHERE query_hash = ?",
                (query_hash,)
            )
            row = cursor.fetchone()
            
            if row:
                # Update access count
                conn.execute(
                    "UPDATE search_cache SET access_count = access_count + 1 WHERE query_hash = ?",
                    (query_hash,)
                )
                conn.commit()
                
                try:
                    return json.loads(row[0])
                except:
                    return None
        
        return None
    
    def cache_search_results(self, query: str, results: List[Dict[str, str]]):
        """Cache search results."""
        query_hash = self._hash_query(query)
        
        with sqlite3.connect(SEARCH_CACHE_PATH) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO search_cache 
                   (query_hash, query, results, timestamp) 
                   VALUES (?, ?, ?, ?)""",
                (query_hash, query, json.dumps(results), datetime.now())
            )
            conn.commit()
    
    def get_content(self, url: str) -> Optional[str]:
        """Get cached content."""
        url_hash = self._hash_url(url)
        
        with sqlite3.connect(SEARCH_CACHE_PATH) as conn:
            cursor = conn.execute(
                "SELECT content FROM content_cache WHERE url_hash = ?",
                (url_hash,)
            )
            row = cursor.fetchone()
            
            if row:
                return row[0]
        
        return None
    
    def cache_content(self, url: str, content: str, title: str = ""):
        """Cache content."""
        url_hash = self._hash_url(url)
        
        with sqlite3.connect(SEARCH_CACHE_PATH) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO content_cache 
                   (url_hash, url, content, title, timestamp, content_length) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (url_hash, url, content, title, datetime.now(), len(content))
            )
            conn.commit()


class EnhancedSearchPipeline:
    """Enhanced search pipeline with quality controls."""
    
    def __init__(self):
        self.query_optimizer = SearchQueryOptimizer()
        self.quality_scorer = SearchResultQualityScorer()
        self.cache = SearchCache()
        self.guardian = guard()
    
    def search(self, topic: str, intent: str = "general", focus: str = "", max_results: int = 10) -> Dict[str, Any]:
        """Enhanced search with query optimization and quality filtering."""
        
        # Optimize query
        optimized_query = self.query_optimizer.optimize_query(topic, intent, focus)
        
        # Check cache first
        cached_results = self.cache.get_search_results(optimized_query)
        if cached_results:
            return {
                "success": True,
                "query": optimized_query,
                "results": cached_results[:max_results],
                "cached": True,
                "total_found": len(cached_results)
            }
        
        # Generate query variations for better coverage
        variations = self.query_optimizer.generate_query_variations(optimized_query)
        all_results = []
        
        # Search with variations
        for variation in variations:
            try:
                # Use existing search_web method but with optimized query
                results = self._basic_search(variation, max_results=20)
                all_results.extend(results)
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                continue
        
        # Remove duplicates
        seen_urls = set()
        deduplicated = []
        for result in all_results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduplicated.append(result)
        
        # Quality scoring and filtering
        quality_filtered = self.quality_scorer.filter_results(deduplicated, min_score=0.3)
        
        # Cache results
        self.cache.cache_search_results(optimized_query, quality_filtered)
        
        return {
            "success": True,
            "query": optimized_query,
            "results": quality_filtered[:max_results],
            "cached": False,
            "total_found": len(quality_filtered)
        }
    
    def _basic_search(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Basic search using existing research engine."""
        # Import here to avoid circular imports
        from core import research_engine
        engine = research_engine.ResearchEngine()
        return engine.search_web(query, max_results)
    
    def extract_content(self, url: str, use_cache: bool = True) -> Optional[str]:
        """Extract content with caching and improved reliability."""
        
        # Check cache first
        if use_cache:
            cached_content = self.cache.get_content(url)
            if cached_content:
                return cached_content
        
        # Extract content
        try:
            from core import research_engine
            engine = research_engine.ResearchEngine()
            content = engine.extract_content(url)
            
            if content and len(content) > 200:  # Only cache substantial content
                self.cache.cache_content(url, content)
            
            return content
            
        except Exception as e:
            return None
    
    def process_insights(self, topic: str, content: str, focus: str = "") -> Dict[str, Any]:
        """Process content with improved insight extraction."""
        
        focus_clause = f"\nFocus on: {focus}\n" if focus else "\n"
        
        prompt = f"""Analyze this content about {topic} for actionable insights:{focus_clause}

Content:
{content[:4000]}

Extract and categorize:
1. KEY_FINDINGS: 3-5 specific, factual discoveries
2. PRACTICAL_APPLICATIONS: 2-3 concrete implementations  
3. TECHNICAL_PATTERNS: Code patterns, architectures, or algorithms mentioned
4. RISKS_LIMITATIONS: Potential issues or constraints
5. NEXT_STEPS: Actionable recommendations for an AI assistant

Requirements:
- Be specific and factual, avoid generic statements
- Include concrete details, names, or measurable data when available
- Focus on information that can be implemented or used
- Output as JSON with the exact keys listed above

Example format:
{{
  "KEY_FINDINGS": ["Specific finding 1", "Specific finding 2"],
  "PRACTICAL_APPLICATIONS": ["Application 1", "Application 2"], 
  "TECHNICAL_PATTERNS": ["Pattern 1", "Pattern 2"],
  "RISKS_LIMITATIONS": ["Risk 1", "Risk 2"],
  "NEXT_STEPS": ["Step 1", "Step 2"]
}}"""
        
        try:
            response = providers.generate_text(prompt, max_output_tokens=700)
            if response:
                try:
                    insights = json.loads(response)
                    
                    # Validate structure
                    required_keys = ["KEY_FINDINGS", "PRACTICAL_APPLICATIONS", "TECHNICAL_PATTERNS", "RISKS_LIMITATIONS", "NEXT_STEPS"]
                    for key in required_keys:
                        if key not in insights:
                            insights[key] = []
                    
                    # Quality check - ensure we have meaningful content
                    total_items = sum(len(insights[key]) for key in required_keys)
                    if total_items < 3:
                        return self._fallback_insights(content)
                    
                    return insights
                    
                except json.JSONDecodeError:
                    return self._parse_text_insights(response)
                    
        except Exception as e:
            pass
        
        return self._fallback_insights(content)
    
    def _parse_text_insights(self, text: str) -> Dict[str, Any]:
        """Parse insights from non-JSON response."""
        insights = {
            "KEY_FINDINGS": [],
            "PRACTICAL_APPLICATIONS": [],
            "TECHNICAL_PATTERNS": [],
            "RISKS_LIMITATIONS": [],
            "NEXT_STEPS": []
        }
        
        lines = text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect section headers
            if any(key in line.upper() for key in ["KEY FINDINGS", "FINDINGS"]):
                current_section = "KEY_FINDINGS"
            elif any(key in line.upper() for key in ["PRACTICAL", "APPLICATION"]):
                current_section = "PRACTICAL_APPLICATIONS"
            elif any(key in line.upper() for key in ["TECHNICAL", "PATTERN", "CODE"]):
                current_section = "TECHNICAL_PATTERNS"
            elif any(key in line.upper() for key in ["RISK", "LIMITATION"]):
                current_section = "RISKS_LIMITATIONS"
            elif any(key in line.upper() for key in ["NEXT", "STEP", "RECOMMEND"]):
                current_section = "NEXT_STEPS"
            elif current_section and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                # Extract bullet point
                cleaned = line.lstrip('-•* ').strip()
                if len(cleaned) > 10:  # Skip very short items
                    insights[current_section].append(cleaned)
        
        return insights
    
    def _fallback_insights(self, content: str) -> Dict[str, Any]:
        """Fallback insight extraction when LLM fails."""
        insights = {
            "KEY_FINDINGS": ["Content analysis failed - manual review needed"],
            "PRACTICAL_APPLICATIONS": [],
            "TECHNICAL_PATTERNS": [],
            "RISKS_LIMITATIONS": ["Processing error occurred"],
            "NEXT_STEPS": ["Retry content processing", "Check content quality"]
        }
        
        # Try to extract some basic information
        if len(content) > 500:
            insights["KEY_FINDINGS"].append(f"Content contains {len(content)} characters of information")
        
        return insights


# Global instance
_enhanced_pipeline = None

def get_enhanced_search_pipeline() -> EnhancedSearchPipeline:
    """Get the global enhanced search pipeline instance."""
    global _enhanced_pipeline
    if _enhanced_pipeline is None:
        _enhanced_pipeline = EnhancedSearchPipeline()
    return _enhanced_pipeline


if __name__ == "__main__":
    # Test the enhanced pipeline
    pipeline = EnhancedSearchPipeline()
    
    # Test search
    result = pipeline.search("autonomous AI agents", intent="technical", max_results=5)
    print("Search Results:")
    print(json.dumps(result, indent=2))
    
    # Test content extraction
    if result["results"]:
        url = result["results"][0]["url"]
        content = pipeline.extract_content(url)
        if content:
            print(f"\nExtracted {len(content)} characters from {url}")
            
            # Test insight processing
            insights = pipeline.process_insights("autonomous AI agents", content)
            print("\nProcessed Insights:")
            print(json.dumps(insights, indent=2))
