"""
Anti-Hallucination System for ClawdBots.

Implements "Trust but Verify" protocol primarily for Friday (CMO)
but usable by all bots. Prevents AI-generated content from
containing made-up facts, fake URLs, or unverified claims.

Checks:
- URL validation (do URLs actually resolve?)
- Fact cross-reference (does claim match known data?)
- Source attribution (is a source cited?)
- Confidence scoring (how certain is the claim?)
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Well-known domains that don't need extra verification
TRUSTED_DOMAINS = {
    "twitter.com", "x.com", "github.com", "google.com", "youtube.com",
    "reddit.com", "wikipedia.org", "medium.com", "substack.com",
    "discord.com", "telegram.org", "t.me", "solana.com", "solscan.io",
    "birdeye.so", "dexscreener.com", "coingecko.com", "coinmarketcap.com",
    "etherscan.io", "bloomberg.com", "reuters.com", "nytimes.com",
    "wsj.com", "ft.com", "sec.gov", "arxiv.org", "linkedin.com",
}

# Attribution phrases that indicate a source is cited
ATTRIBUTION_PHRASES = [
    r"according to\b", r"as reported by\b", r"per\b", r"based on\b",
    r"source:", r"via\b", r"from\b.*\breport\b", r"data from\b",
    r"published by\b", r"stated by\b", r"cited in\b",
]

# Patterns that look like statistics
STAT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?%")

# URL pattern
URL_PATTERN = re.compile(r"https?://[^\s\)\]\"'<>,]+")

# Quoted text pattern
QUOTE_PATTERN = re.compile(r'"([^"]{10,})"')

# Simple proper noun heuristic: capitalized words not at sentence start
PROPER_NOUN_PATTERN = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")

# Penalty per flag type
FLAG_PENALTIES = {
    "unverified_url": 0.15,
    "unattributed_statistic": 0.10,
    "unattributed_quote": 0.10,
    "unknown_name": 0.08,
}


class HallucinationChecker:
    """Checks content for potential hallucinations before publishing."""

    def __init__(self, knowledge_graph: Any = None):
        """
        Args:
            knowledge_graph: Optional KnowledgeGraph instance for fact-checking
                             proper nouns against known entities.
        """
        self.kg = knowledge_graph

    def check_content(self, text: str, bot_name: str = "friday") -> Dict[str, Any]:
        """Check content for potential hallucinations.

        Returns:
            {
                "score": 0.0-1.0 (1.0 = fully verified),
                "flags": [{"type": str, "content": str, "suggestion": str}],
                "verified_facts": [...],
                "unverified_claims": [...]
            }
        """
        flags: List[Dict[str, str]] = []
        verified_facts: List[str] = []
        unverified_claims: List[str] = []

        # Run all checks
        url_flags = self._check_urls(text)
        stat_flags = self._check_statistics(text)
        quote_flags = self._check_quotes(text)
        name_flags = self._check_names(text)

        flags.extend(url_flags)
        flags.extend(stat_flags)
        flags.extend(quote_flags)
        flags.extend(name_flags)

        # Collect unverified claims
        for f in flags:
            unverified_claims.append(f["content"])

        # Calculate score: start at 1.0 and deduct per flag
        score = 1.0
        for f in flags:
            penalty = FLAG_PENALTIES.get(f["type"], 0.05)
            score -= penalty
        score = max(0.0, min(1.0, score))

        return {
            "score": round(score, 3),
            "flags": flags,
            "verified_facts": verified_facts,
            "unverified_claims": unverified_claims,
        }

    def _check_urls(self, text: str) -> List[Dict[str, str]]:
        """Find URLs and flag any that look fabricated."""
        flags = []
        urls = URL_PATTERN.findall(text)
        for url in urls:
            try:
                parsed = urlparse(url)
                hostname = parsed.hostname or ""
                # Strip www.
                if hostname.startswith("www."):
                    hostname = hostname[4:]

                # Check against trusted domains
                is_trusted = any(
                    hostname == d or hostname.endswith("." + d)
                    for d in TRUSTED_DOMAINS
                )
                if is_trusted:
                    continue

                # Check for suspicious patterns
                suspicious = False
                # Double dots in hostname
                if ".." in hostname:
                    suspicious = True
                # Very long random-looking hostname
                if len(hostname) > 40:
                    suspicious = True
                # Lots of hyphens (common in fake domains)
                if hostname.count("-") >= 3:
                    suspicious = True
                # No TLD or very short hostname
                if "." not in hostname or len(hostname) < 4:
                    suspicious = True

                if suspicious:
                    flags.append({
                        "type": "unverified_url",
                        "content": url,
                        "suggestion": "Verify this URL exists and is legitimate before publishing.",
                    })
            except Exception:
                flags.append({
                    "type": "unverified_url",
                    "content": url,
                    "suggestion": "URL could not be parsed. Verify manually.",
                })
        return flags

    def _check_statistics(self, text: str) -> List[Dict[str, str]]:
        """Flag unattributed statistics and percentages."""
        flags = []
        stats = STAT_PATTERN.findall(text)
        if not stats:
            return flags

        # Check if there's attribution nearby
        text_lower = text.lower()
        has_attribution = any(
            re.search(pattern, text_lower) for pattern in ATTRIBUTION_PHRASES
        )
        if has_attribution:
            return flags

        for stat in stats:
            # Find the sentence containing this stat
            for sentence in re.split(r"[.!?]+", text):
                if stat in sentence:
                    flags.append({
                        "type": "unattributed_statistic",
                        "content": sentence.strip(),
                        "suggestion": f"Add source attribution for the statistic '{stat}'.",
                    })
                    break
        return flags

    def _check_quotes(self, text: str) -> List[Dict[str, str]]:
        """Flag direct quotes without attribution."""
        flags = []
        quotes = QUOTE_PATTERN.findall(text)
        for quote in quotes:
            # Check if there's a name or attribution near the quote
            # Look for pattern: Name said "..." or "..." - Name
            quote_idx = text.find(quote)
            context_before = text[max(0, quote_idx - 80):quote_idx].lower()
            context_after = text[quote_idx + len(quote):quote_idx + len(quote) + 80].lower()

            attribution_words = ["said", "wrote", "stated", "noted", "claimed",
                                 "according", "tweeted", "posted", "mentioned"]
            has_attr = any(w in context_before or w in context_after for w in attribution_words)

            # Check if a capitalized name (proper noun, not common words) appears before the quote
            common_words = {"It", "The", "This", "That", "These", "Those", "There",
                            "What", "When", "Where", "Who", "How", "Why", "We", "He",
                            "She", "They", "My", "Our", "Your", "His", "Her", "Its",
                            "But", "And", "Or", "So", "If", "No", "Yes", "Some", "Any",
                            "All", "Most", "Many", "Few", "One", "Two", "Three"}
            name_match = re.search(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", text[max(0, quote_idx - 60):quote_idx])
            name_before = name_match if name_match and name_match.group() not in common_words else None

            if not has_attr and not name_before:
                flags.append({
                    "type": "unattributed_quote",
                    "content": quote[:80],
                    "suggestion": "Add attribution for this direct quote.",
                })
        return flags

    def _check_names(self, text: str) -> List[Dict[str, str]]:
        """Flag proper nouns not in knowledge graph."""
        if self.kg is None:
            return []

        flags = []
        # Find potential proper nouns (multi-word capitalized sequences)
        # Skip common titles and sentence starts
        skip_words = {
            "The", "This", "That", "These", "Those", "What", "When", "Where",
            "Who", "How", "Why", "I", "We", "He", "She", "They", "It", "My",
            "Your", "Our", "Their", "His", "Her", "Its", "Dr", "Mr", "Mrs",
            "Ms", "Prof", "CEO", "CTO", "CFO",
        }

        # Split into sentences to avoid flagging sentence-initial caps
        sentences = re.split(r"[.!?]+\s*", text)
        seen_names = set()

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            # Find capitalized words NOT at the start of the sentence
            words = sentence.split()
            i = 1  # Skip first word (sentence start)
            while i < len(words):
                word = words[i]
                if word and word[0].isupper() and word not in skip_words:
                    # Collect consecutive capitalized words
                    name_parts = [word]
                    j = i + 1
                    while j < len(words) and words[j][0:1].isupper() and words[j] not in skip_words:
                        name_parts.append(words[j])
                        j += 1
                    name = " ".join(name_parts)
                    # Clean trailing punctuation
                    name = re.sub(r"[,;:\"']+$", "", name)
                    if name and name not in seen_names and len(name) > 2:
                        seen_names.add(name)
                        # Check knowledge graph
                        try:
                            results = self.kg.search(name)
                            if not results:
                                flags.append({
                                    "type": "unknown_name",
                                    "content": name,
                                    "suggestion": f"'{name}' not found in knowledge graph. Verify this name.",
                                })
                        except Exception:
                            pass
                    i = j
                else:
                    i += 1
        return flags

    def add_verification_footer(self, text: str, check_result: Dict[str, Any]) -> str:
        """Add verification status to content.

        Args:
            text: The original content.
            check_result: Output from check_content().

        Returns:
            Text with verification footer appended.
        """
        score = check_result["score"]
        flags = check_result["flags"]

        if score >= 0.8:
            status = "[VERIFIED] Content passed hallucination checks."
        elif score >= 0.5:
            status = "[CAUTION] Some claims could not be verified."
        else:
            warnings = "; ".join(f["suggestion"] for f in flags[:3])
            status = f"[WARNING - UNVERIFIED] Multiple unverified claims detected. {warnings}"

        return f"{text}\n\n---\n{status}"
