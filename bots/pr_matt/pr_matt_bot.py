"""
PR Matt - Marketing Communications Filter Bot

Purpose: Filter public communications to maintain professionalism while preserving authenticity.
         "Every autist needs a little PR" - Matt, 2026-01-31

Features:
- Reviews X/Twitter posts before publishing
- Flags inappropriate language, aggressive tone, unsubstantiated claims
- Suggests professional alternatives
- Learns from approved/rejected messages
- Uses KR8TIV AI Marketing Guide for voice/tone guidelines

Architecture:
- Input: Draft message (text, platform, context)
- Analysis: Grok AI reviews against brand guidelines
- Output: APPROVED / NEEDS_REVISION / BLOCKED + suggestions

References:
- docs/KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md (voice/tone guidelines)
- docs/TELEGRAM_AUDIT_RESULTS_JAN_26_31.md (Task #2)

"""

import asyncio
import logging
import os
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Literal
from dataclasses import dataclass, asdict
from pathlib import Path
import aiohttp
from aiohttp import ClientTimeout

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class MessageReview:
    """Result of PR Matt's review of a message."""
    original_message: str
    platform: Literal["twitter", "telegram", "linkedin", "general"]
    decision: Literal["APPROVED", "NEEDS_REVISION", "BLOCKED"]
    concerns: List[str]
    suggested_revision: Optional[str]
    reasoning: str
    confidence: float  # 0.0-1.0
    reviewed_at: str


class PRMattBot:
    """
    PR Matt Bot - Marketing Communications Filter

    Guards against:
    - Excessive profanity in public communications
    - Unsubstantiated claims ("we're the best", "guaranteed returns")
    - Aggressive or hostile tone
    - Generic buzzwords without substance
    - Overpromising or hype

    Preserves:
    - Authentic founder voice
    - Technical credibility
    - Honest/transparent communication
    - Appropriate casualness (within limits)
    """

    # Profanity that's absolutely forbidden in public communications
    HARD_BLOCKED_WORDS = [
        "fucking", "fuck", "shit", "damn", "hell", "bitch",
        "ass", "crap", "piss", "cock", "dick", "pussy"
    ]

    # Warning signs that trigger review
    WARNING_PATTERNS = [
        r"we'?re (?:the best|number one|top|leading)",  # Unsubstantiated claims
        r"guaranteed|promise|will definitely|100%",  # Overpromising
        r"revolutionary|paradigm shift|game-?changing|disrupt",  # Generic buzzwords
        r"(?:to the moon|wen moon|lambo|wagmi)",  # Crypto bro language
        r"(?:dump|rug|scam) (?:them|you|it)",  # Malicious intent
        r"fuck (?:them|you|off|this)",  # Aggressive profanity
    ]

    # Acceptable casual language (borderline but okay)
    ACCEPTABLE_CASUAL = [
        "honestly", "basically", "tbh", "ngl", "literally",
        "crazy", "insane", "wild", "bonkers"
    ]

    def __init__(
        self,
        xai_api_key: str,
        marketing_guide_path: Optional[str] = None,
        review_history_path: Optional[str] = None,
    ):
        self.xai_api_key = xai_api_key
        self.marketing_guide_path = marketing_guide_path or "docs/KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md"
        self.review_history_path = review_history_path or "bots/pr_matt/.review_history.jsonl"
        self._session: Optional[aiohttp.ClientSession] = None
        self._marketing_guide_content: Optional[str] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    async def start(self):
        """Initialize the bot."""
        self._session = aiohttp.ClientSession(
            timeout=ClientTimeout(total=60)
        )
        await self._load_marketing_guide()
        logger.info("PR Matt bot started")

    async def stop(self):
        """Clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("PR Matt bot stopped")

    async def _load_marketing_guide(self):
        """Load the marketing guide for reference."""
        try:
            guide_path = Path(self.marketing_guide_path)
            if guide_path.exists():
                self._marketing_guide_content = guide_path.read_text(encoding='utf-8')
                logger.info(f"Loaded marketing guide ({len(self._marketing_guide_content)} chars)")
            else:
                logger.warning(f"Marketing guide not found at {guide_path}")
                self._marketing_guide_content = ""
        except Exception as e:
            logger.error(f"Error loading marketing guide: {e}")
            self._marketing_guide_content = ""

    def _quick_filter(self, message: str) -> Tuple[bool, List[str]]:
        """
        Fast rule-based filter before AI review.
        Returns (should_block, concerns)
        """
        concerns = []
        message_lower = message.lower()

        # Check for hard-blocked words
        for word in self.HARD_BLOCKED_WORDS:
            if re.search(rf'\b{re.escape(word)}\b', message_lower):
                concerns.append(f"Contains inappropriate language: '{word}'")

        # Check warning patterns
        for pattern in self.WARNING_PATTERNS:
            if re.search(pattern, message_lower):
                match = re.search(pattern, message_lower)
                concerns.append(f"Warning pattern detected: '{match.group()}'")

        should_block = len(concerns) > 0
        return should_block, concerns

    async def _review_with_grok(
        self,
        message: str,
        platform: str,
        concerns: List[str]
    ) -> Dict:
        """Use Grok AI to review the message against brand guidelines."""

        # Build context from marketing guide
        guide_excerpt = ""
        if self._marketing_guide_content:
            # Extract relevant sections (tone, voice, examples)
            guide_excerpt = self._marketing_guide_content[:3000]  # First 3K chars

        prompt = f"""You are PR Matt, the communications filter for KR8TIV AI. Your job is to review draft messages and ensure they maintain professionalism while preserving authenticity.

BRAND GUIDELINES (from marketing guide):
{guide_excerpt}

KEY PRINCIPLES:
- Authentic but professional
- Technical depth + accessibility
- Honest about challenges
- NO excessive profanity in public communications
- NO unsubstantiated claims ("we're the best")
- NO generic buzzwords without substance

ACCEPTABLE:
- "We're building something that actually works - no hype, just code"
- "Honestly, we found a critical security issue today. Fixed it."
- Technical language, mild emphasis words (crazy, wild, honestly)

NOT ACCEPTABLE:
- "We're gonna make so much fucking money"
- "This project is trash" (even if true - phrase constructively)
- "Revolutionary paradigm shift" (buzzwords without substance)

PLATFORM: {platform}

DRAFT MESSAGE:
{message}

AUTOMATIC CONCERNS FLAGGED:
{json.dumps(concerns, indent=2) if concerns else "None"}

TASK: Review this message and provide:
1. DECISION: APPROVED / NEEDS_REVISION / BLOCKED
2. CONCERNS: List of specific issues (if any)
3. SUGGESTED_REVISION: Professional alternative (if needed)
4. REASONING: Why this decision was made

Respond ONLY with valid JSON in this exact format:
{{
  "decision": "APPROVED|NEEDS_REVISION|BLOCKED",
  "concerns": ["concern1", "concern2"],
  "suggested_revision": "alternative text or null",
  "reasoning": "explanation of decision"
}}
"""

        try:
            async with self._session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "grok-beta",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are PR Matt, a communications filter. Respond only with valid JSON."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,  # Low temperature for consistent filtering
                    "max_tokens": 500
                }
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Grok API error: {resp.status} - {error_text}")
                    return {
                        "decision": "NEEDS_REVISION",
                        "concerns": ["AI review failed - manual review recommended"],
                        "suggested_revision": None,
                        "reasoning": f"Grok API error: {resp.status}"
                    }

                data = await resp.json()
                content = data["choices"][0]["message"]["content"]

                # Extract JSON from response (Grok sometimes adds markdown)
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    logger.error(f"Could not parse Grok response: {content}")
                    return {
                        "decision": "NEEDS_REVISION",
                        "concerns": ["AI response parse error"],
                        "suggested_revision": None,
                        "reasoning": "Could not parse AI review"
                    }

        except Exception as e:
            logger.error(f"Error calling Grok API: {e}")
            return {
                "decision": "NEEDS_REVISION",
                "concerns": [f"AI review error: {str(e)}"],
                "suggested_revision": None,
                "reasoning": f"Exception during review: {str(e)}"
            }

    async def review_message(
        self,
        message: str,
        platform: Literal["twitter", "telegram", "linkedin", "general"] = "general",
        context: Optional[str] = None
    ) -> MessageReview:
        """
        Review a message and return approval decision.

        Args:
            message: The draft message to review
            platform: Where this will be posted
            context: Optional context about why/when this is being posted

        Returns:
            MessageReview with decision and suggestions
        """
        logger.info(f"PR Matt reviewing {platform} message ({len(message)} chars)")

        # Quick rule-based filter first
        quick_blocked, quick_concerns = self._quick_filter(message)

        # Always get AI review for consistency
        ai_result = await self._review_with_grok(message, platform, quick_concerns)

        # Combine results
        all_concerns = list(set(quick_concerns + ai_result.get("concerns", [])))

        # Determine final decision
        decision = ai_result["decision"]
        if quick_blocked and decision == "APPROVED":
            # Rule-based filter overrides AI approval if hard blocks detected
            decision = "BLOCKED" if len(quick_concerns) >= 3 else "NEEDS_REVISION"

        review = MessageReview(
            original_message=message,
            platform=platform,
            decision=decision,
            concerns=all_concerns,
            suggested_revision=ai_result.get("suggested_revision"),
            reasoning=ai_result.get("reasoning", ""),
            confidence=0.8,  # TODO: Calculate based on agreement between filters
            reviewed_at=datetime.now(timezone.utc).isoformat()
        )

        # Log review to history
        await self._log_review(review)

        logger.info(f"PR Matt decision: {decision} (concerns: {len(all_concerns)})")
        return review

    async def _log_review(self, review: MessageReview):
        """Log review to history file for learning."""
        try:
            history_file = Path(self.review_history_path)
            history_file.parent.mkdir(parents=True, exist_ok=True)

            with open(history_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(asdict(review)) + '\n')

        except Exception as e:
            logger.error(f"Error logging review: {e}")

    async def get_review_stats(self) -> Dict:
        """Get statistics about past reviews."""
        try:
            history_file = Path(self.review_history_path)
            if not history_file.exists():
                return {"total": 0}

            reviews = []
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    reviews.append(json.loads(line))

            stats = {
                "total": len(reviews),
                "approved": sum(1 for r in reviews if r["decision"] == "APPROVED"),
                "needs_revision": sum(1 for r in reviews if r["decision"] == "NEEDS_REVISION"),
                "blocked": sum(1 for r in reviews if r["decision"] == "BLOCKED"),
                "by_platform": {}
            }

            for platform in ["twitter", "telegram", "linkedin", "general"]:
                platform_reviews = [r for r in reviews if r["platform"] == platform]
                stats["by_platform"][platform] = {
                    "total": len(platform_reviews),
                    "approved": sum(1 for r in platform_reviews if r["decision"] == "APPROVED")
                }

            return stats

        except Exception as e:
            logger.error(f"Error getting review stats: {e}")
            return {"error": str(e)}


async def main():
    """Test PR Matt bot with sample messages."""
    xai_api_key = os.getenv("XAI_API_KEY", "")
    if not xai_api_key:
        print("Error: XAI_API_KEY environment variable not set")
        return

    async with PRMattBot(xai_api_key) as pr_matt:
        # Test cases
        test_messages = [
            ("We're building something that actually works - no hype, just code.", "twitter"),
            ("We're gonna make so much fucking money lol", "twitter"),
            ("Found a critical bug today. Fixed it. That's the job.", "twitter"),
            ("This revolutionary paradigm shift will disrupt the entire ecosystem!", "twitter"),
            ("GSD framework is working exceptionally well for us.", "twitter"),
        ]

        for message, platform in test_messages:
            print(f"\n{'='*80}")
            print(f"Message: {message}")
            print(f"Platform: {platform}")
            print("-" * 80)

            review = await pr_matt.review_message(message, platform)

            print(f"Decision: {review.decision}")
            print(f"Concerns: {review.concerns}")
            if review.suggested_revision:
                print(f"Suggested: {review.suggested_revision}")
            print(f"Reasoning: {review.reasoning}")

        # Show stats
        print(f"\n{'='*80}")
        print("REVIEW STATS:")
        stats = await pr_matt.get_review_stats()
        print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
