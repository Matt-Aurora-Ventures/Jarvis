"""
Reply Strategy Handler

Monitor: replies to Jarvis tweets
Respond to:
- Questions about tokens (provide quick analysis)
- Criticism (polite defense or acknowledgment)
- Positive comments (thank you + engagement)

Rate limit: max 1 response per user per hour
Use Grok: generate contextual replies
"""

import json
import re
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Default data directory
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "twitter"

# Reply classification keywords
QUESTION_KEYWORDS = [
    "what", "why", "how", "when", "where", "which",
    "can you", "could you", "do you", "does",
    "think about", "thoughts on", "opinion on",
    "?"
]

CRITICISM_KEYWORDS = [
    "wrong", "bad", "terrible", "awful", "stupid",
    "disagree", "incorrect", "mistake", "false",
    "scam", "fake", "lies", "lying"
]

POSITIVE_KEYWORDS = [
    "thanks", "thank you", "great", "awesome", "love",
    "amazing", "helpful", "nice", "good job", "well done",
    "appreciate", "respect", "king", "goat", "legend"
]


class ReplyHandler:
    """
    Handles reply classification and response generation.

    Usage:
        handler = ReplyHandler()

        # Classify a reply
        category = handler.classify_reply(reply_data)

        # Check rate limit
        if handler.can_reply_to_user(username):
            response = await handler.generate_response(reply_data)
            handler.record_reply(username)
    """

    # Rate limit: 1 reply per user per hour
    RATE_LIMIT_HOURS = 1

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        grok_client: Optional[Any] = None
    ):
        """
        Initialize reply handler.

        Args:
            data_dir: Directory for storing reply data
            grok_client: Optional Grok client for response generation
        """
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit_file = self.data_dir / "reply_rate_limits.json"

        self._rate_limits: Dict[str, datetime] = {}
        self._load_rate_limits()

        # Grok client for responses
        if grok_client:
            self._grok_client = grok_client
        else:
            try:
                from bots.twitter.grok_client import GrokClient
                self._grok_client = GrokClient()
            except ImportError:
                self._grok_client = None
                logger.warning("GrokClient not available")

    def _load_rate_limits(self):
        """Load rate limit data from file."""
        try:
            if self.rate_limit_file.exists():
                data = json.loads(self.rate_limit_file.read_text())
                self._rate_limits = {}

                for username, timestamp in data.items():
                    if isinstance(timestamp, str):
                        self._rate_limits[username] = datetime.fromisoformat(
                            timestamp.replace('Z', '+00:00')
                        )

                self._clean_expired_limits()
                logger.debug(f"Loaded {len(self._rate_limits)} rate limits")
        except Exception as e:
            logger.warning(f"Could not load rate limits: {e}")
            self._rate_limits = {}

    def _save_rate_limits(self):
        """Save rate limit data to file."""
        try:
            data = {
                username: ts.isoformat()
                for username, ts in self._rate_limits.items()
            }
            self.rate_limit_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save rate limits: {e}")

    def _clean_expired_limits(self):
        """Remove expired rate limits."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.RATE_LIMIT_HOURS)
        expired = [u for u, ts in self._rate_limits.items() if ts < cutoff]

        for username in expired:
            del self._rate_limits[username]

    def classify_reply(self, reply_data: Dict[str, Any]) -> str:
        """
        Classify a reply into categories.

        Args:
            reply_data: Dict with text and author info

        Returns:
            Classification: "question", "criticism", "positive", "neutral"
        """
        text = reply_data.get("text", "").lower()

        # Check for questions first (most common)
        for keyword in QUESTION_KEYWORDS:
            if keyword in text:
                return "question"

        # Check for criticism
        for keyword in CRITICISM_KEYWORDS:
            if keyword in text:
                return "criticism"

        # Check for positive feedback
        for keyword in POSITIVE_KEYWORDS:
            if keyword in text:
                return "positive"

        # Check for negative sentiment (broader)
        if any(w in text for w in ["no", "not", "don't", "doesn't", "won't"]):
            if any(w in text for w in ["like", "agree", "work", "good"]):
                return "negative"

        return "neutral"

    def can_reply_to_user(self, username: str) -> bool:
        """
        Check if we can reply to a user (rate limit).

        Args:
            username: Twitter username

        Returns:
            True if reply is allowed
        """
        self._clean_expired_limits()

        if username not in self._rate_limits:
            return True

        last_reply = self._rate_limits[username]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.RATE_LIMIT_HOURS)

        return last_reply < cutoff

    def record_reply(self, username: str):
        """
        Record that we replied to a user.

        Args:
            username: Twitter username
        """
        self._rate_limits[username] = datetime.now(timezone.utc)
        self._save_rate_limits()
        logger.debug(f"Recorded reply to @{username}")

    async def generate_response(
        self,
        reply_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Generate a response to a reply.

        Args:
            reply_data: Dict with text and author info
            context: Optional additional context

        Returns:
            Response text or None
        """
        text = reply_data.get("text", "")
        username = reply_data.get("author_username", "anon")
        classification = self.classify_reply(reply_data)

        # Check rate limit
        if not self.can_reply_to_user(username):
            logger.debug(f"Rate limited: @{username}")
            return None

        # Build response prompt based on classification
        if classification == "question":
            prompt = self._build_question_prompt(text, username, context)
        elif classification == "criticism":
            prompt = self._build_criticism_prompt(text, username, context)
        elif classification == "positive":
            prompt = self._build_positive_prompt(text, username, context)
        else:
            prompt = self._build_neutral_prompt(text, username, context)

        # Generate with Grok
        if self._grok_client:
            try:
                response = await self._grok_client.generate_tweet(
                    prompt,
                    max_tokens=100,
                    temperature=0.8
                )

                if response.success:
                    reply_text = response.content.strip()

                    # Ensure username mention is included
                    if f"@{username}" not in reply_text:
                        reply_text = f"@{username} {reply_text}"

                    # Ensure under 280 chars
                    if len(reply_text) > 280:
                        reply_text = reply_text[:277] + "..."

                    return reply_text

                logger.warning(f"Grok response failed: {response.error}")

            except Exception as e:
                logger.error(f"Failed to generate response: {e}")

        # Fallback templates
        return self._fallback_response(classification, username)

    def _build_question_prompt(
        self,
        text: str,
        username: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for question replies."""
        # Extract token mentions
        tokens = re.findall(r'\$([A-Z]{2,10})', text.upper())

        prompt = f"""Generate a helpful reply to this question from @{username}:

"{text}"

Rules:
- Start with @{username}
- Be helpful and informative
- Keep it casual, lowercase
- Max 250 characters
- Include NFA if giving any opinion
- If asking about a token ({', '.join(tokens) if tokens else 'any'}), give a brief take

Return ONLY the reply text."""

        return prompt

    def _build_criticism_prompt(
        self,
        text: str,
        username: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for criticism replies."""
        prompt = f"""Generate a polite response to this criticism from @{username}:

"{text}"

Rules:
- Start with @{username}
- Be respectful and professional
- Acknowledge their point if valid
- Gently defend if unfair criticism
- Keep it casual, lowercase
- Max 200 characters
- Don't be defensive or argumentative

Return ONLY the reply text."""

        return prompt

    def _build_positive_prompt(
        self,
        text: str,
        username: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for positive replies."""
        prompt = f"""Generate a grateful response to this positive comment from @{username}:

"{text}"

Rules:
- Start with @{username}
- Thank them genuinely
- Keep it casual, lowercase
- Max 150 characters
- Can include a small joke or emoji
- Be engaging

Return ONLY the reply text."""

        return prompt

    def _build_neutral_prompt(
        self,
        text: str,
        username: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for neutral replies."""
        prompt = f"""Generate a brief engaging response to this comment from @{username}:

"{text}"

Rules:
- Start with @{username}
- Be friendly and engaging
- Keep it casual, lowercase
- Max 150 characters
- Can ask a follow-up question

Return ONLY the reply text."""

        return prompt

    def _fallback_response(self, classification: str, username: str) -> str:
        """Generate fallback response when Grok is unavailable."""
        templates = {
            "question": [
                f"@{username} good question. my circuits are processing. will dig into this more",
                f"@{username} appreciate the question. checking my data. nfa as always"
            ],
            "criticism": [
                f"@{username} appreciate the feedback. always learning here",
                f"@{username} fair point. my circuits aren't perfect. will recalibrate"
            ],
            "positive": [
                f"@{username} thanks for the kind words. glad my analysis helps",
                f"@{username} appreciate you. we're all learning together"
            ],
            "neutral": [
                f"@{username} interesting point. my sensors are calibrated",
                f"@{username} noted. the markets are always interesting"
            ]
        }

        import random
        options = templates.get(classification, templates["neutral"])
        return random.choice(options)

    def get_reply_stats(self) -> Dict[str, Any]:
        """
        Get reply handler statistics.

        Returns:
            Dict with stats
        """
        self._clean_expired_limits()

        return {
            "active_rate_limits": len(self._rate_limits),
            "rate_limit_hours": self.RATE_LIMIT_HOURS,
            "grok_available": self._grok_client is not None
        }

    def should_reply(self, reply_data: Dict[str, Any]) -> bool:
        """
        Determine if we should reply to this message.

        Args:
            reply_data: Dict with reply info

        Returns:
            True if we should reply
        """
        text = reply_data.get("text", "").lower()
        username = reply_data.get("author_username", "")

        # Skip if rate limited
        if not self.can_reply_to_user(username):
            return False

        # Skip if it's our own reply
        if username.lower() in ["jarvis_lifeos", "jarvis"]:
            return False

        # Skip very short replies
        if len(text) < 5:
            return False

        # Skip if just mentions with no content
        mention_stripped = re.sub(r'@\w+', '', text).strip()
        if len(mention_stripped) < 3:
            return False

        # Always reply to questions
        classification = self.classify_reply(reply_data)
        if classification == "question":
            return True

        # Reply to positive feedback
        if classification == "positive":
            return True

        # Selectively reply to criticism (only if not too hostile)
        if classification == "criticism":
            hostile_words = ["scam", "fake", "fraud", "trash", "garbage"]
            if not any(w in text for w in hostile_words):
                return True

        # Reply to neutral if substantive (20+ chars)
        if classification == "neutral" and len(mention_stripped) > 20:
            return True

        return False
