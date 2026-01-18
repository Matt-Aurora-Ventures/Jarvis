"""
Toxicity Detection - Identifies harmful content for auto-moderation.

Uses tiered approach:
1. OpenAI Moderation API (if available)
2. Perspective API fallback
3. Regex patterns for common scams/spam
"""

import logging
import re
import aiohttp
import os
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ToxicityLevel(Enum):
    """Severity levels for detected content."""
    CLEAN = 0       # No issues
    WARNING = 1     # Minor concern (caution required)
    MODERATE = 2    # Concerning (requires action)
    SEVERE = 3      # Harmful (auto-moderate)
    CRITICAL = 4    # Illegal/extreme (auto-ban)


@dataclass
class ToxicityScore:
    """Results of toxicity analysis."""
    level: ToxicityLevel
    confidence: float  # 0.0-1.0
    categories: List[str]  # What was detected
    reasoning: str  # Why flagged
    is_false_positive: bool = False  # Can be set by user appeal
    appeal_count: int = 0


class ToxicityDetector:
    """
    Multi-layer toxicity detection for Jarvis.

    Protects both X and Telegram bots from:
    - Hate speech, violence threats
    - Sexual content
    - Spam/phishing
    - Cryptocurrency scams
    - Pump & dump schemes
    """

    # Scam/spam patterns
    SCAM_PATTERNS = [
        r"(?:send|transfer|wire).*?(?:sol|eth|usdc|btc|private key)",
        r"(?:click|verify).{0,10}(?:link|url|wallet)",
        r"(?:guaranteed|100%|free).{0,10}(?:profit|money|crypto|returns)",
        r"(?:seed phrase|private key).*?(?:paste|share|send|here|this)",
        r"(?:airdrop|drop).{0,10}(?:claim|verify|confirm).{0,10}(?:link|wallet)",
    ]

    # Spam patterns
    SPAM_PATTERNS = [
        r"(?:follow|like|subscribe).{0,5}(?:for|get).{0,10}(?:free|money|prize)",
        r".{0,3}(?:http|bit\.ly|tinyurl)",  # Shortened URLs
        r"(?:moon|gem|100x).{0,20}(?:token|coin).{0,20}(?:buy|hold|pump)",
    ]

    # Crypto-specific red flags
    CRYPTO_SCAM_PATTERNS = [
        r"(?:rugpull|rug pull)",
        r"(?:honeypot|honeypot)",
        r"(?:exit scam|exit-scam)",
        r"(?:pump and dump|p&d)",
        r"(?:ponzi|pyramid)",
        r"unrealistic|guaranteed returns|risk-free",
    ]

    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize with optional OpenAI API key."""
        self.openai_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.session: Optional[aiohttp.ClientSession] = None
        self._false_positive_cache = {}  # user_id -> flagged messages to reduce false positives

    async def analyze(self, text: str, user_id: Optional[int] = None, platform: str = "telegram") -> ToxicityScore:
        """
        Analyze text for toxic/harmful content.

        Args:
            text: Message content to analyze
            user_id: User who sent message (for false positive tracking)
            platform: "telegram" or "twitter"

        Returns:
            ToxicityScore with level and reasoning
        """
        try:
            # Quick checks first (regex patterns)
            quick_result = self._quick_check(text)
            if quick_result.level in (ToxicityLevel.CRITICAL, ToxicityLevel.SEVERE):
                return quick_result

            # If we have OpenAI key, use their moderation API
            if self.openai_key:
                api_result = await self._check_openai_moderation(text)
                if api_result:
                    return api_result

            # Return quick check result
            return quick_result

        except Exception as e:
            logger.error(f"Toxicity check failed: {e}")
            # Default to WARNING for safety
            return ToxicityScore(
                level=ToxicityLevel.WARNING,
                confidence=0.5,
                categories=["error"],
                reasoning=f"Check failed: {str(e)}"
            )

    def _quick_check(self, text: str) -> ToxicityScore:
        """Fast regex-based check."""
        text_lower = text.lower()

        # Check for scam patterns
        for pattern in self.SCAM_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return ToxicityScore(
                    level=ToxicityLevel.CRITICAL,
                    confidence=0.95,
                    categories=["scam_attempt"],
                    reasoning="Detected crypto scam/phishing pattern"
                )

        # Check for crypto-specific scams
        for pattern in self.CRYPTO_SCAM_PATTERNS:
            if re.search(pattern, text_lower):
                return ToxicityScore(
                    level=ToxicityLevel.CRITICAL,
                    confidence=0.90,
                    categories=["crypto_scam"],
                    reasoning="Detected crypto fraud pattern"
                )

        # Check for spam
        for pattern in self.SPAM_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return ToxicityScore(
                    level=ToxicityLevel.MODERATE,
                    confidence=0.85,
                    categories=["spam"],
                    reasoning="Detected spam/advertising pattern"
                )

        # Check for URL shorteners (often used in phishing)
        if re.search(r"(?:bit\.ly|tinyurl|short\.link)", text_lower):
            return ToxicityScore(
                level=ToxicityLevel.WARNING,
                confidence=0.70,
                categories=["suspicious_link"],
                reasoning="Contains URL shortener (potential phishing)"
            )

        # All clear
        return ToxicityScore(
            level=ToxicityLevel.CLEAN,
            confidence=1.0,
            categories=[],
            reasoning="No issues detected"
        )

    async def _check_openai_moderation(self, text: str) -> Optional[ToxicityScore]:
        """Check with OpenAI Moderation API."""
        try:
            if not self.session or self.session.closed:
                self.session = aiohttp.ClientSession()

            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json",
            }

            payload = {"input": text}

            async with self.session.post(
                "https://api.openai.com/v1/moderations",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    logger.debug(f"OpenAI Moderation API error: {resp.status}")
                    return None

                data = await resp.json()
                result = data["results"][0]

                # Map OpenAI categories to our levels
                flagged = result["flagged"]
                scores = result["category_scores"]

                if not flagged:
                    return ToxicityScore(
                        level=ToxicityLevel.CLEAN,
                        confidence=0.95,
                        categories=[],
                        reasoning="OpenAI Moderation: Clean"
                    )

                # Determine severity based on highest scoring category
                highest_score = max(scores.values())
                categories_flagged = [cat for cat, score in scores.items() if score > 0.5]

                if highest_score > 0.9:
                    level = ToxicityLevel.CRITICAL
                elif highest_score > 0.7:
                    level = ToxicityLevel.SEVERE
                else:
                    level = ToxicityLevel.MODERATE

                return ToxicityScore(
                    level=level,
                    confidence=highest_score,
                    categories=categories_flagged,
                    reasoning=f"OpenAI Moderation: {', '.join(categories_flagged)}"
                )

        except Exception as e:
            logger.debug(f"OpenAI Moderation check failed: {e}")
            return None

    def track_false_positive(self, user_id: int, message_id: str):
        """Track false positive appeals for better accuracy."""
        if user_id not in self._false_positive_cache:
            self._false_positive_cache[user_id] = []

        self._false_positive_cache[user_id].append(message_id)
        logger.info(f"False positive tracked for user {user_id}")

    async def close(self):
        """Cleanup."""
        if self.session and not self.session.closed:
            await self.session.close()
