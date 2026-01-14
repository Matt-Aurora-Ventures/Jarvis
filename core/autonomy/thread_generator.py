"""
Thread Generator
Auto-generate Twitter threads when topics need more depth
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from core.jarvis_voice_bible import JARVIS_VOICE_BIBLE, validate_jarvis_response

logger = logging.getLogger(__name__)


# Thread quality checks
BANNED_THREAD_STARTS = [
    "here's",  # Overused thread opener
    "ok so",
    "okay so",
    "alright so",
    "1/",  # Number format is handled automatically
    "thread:",
]

WEAK_HOOK_PATTERNS = [
    r"^i (think|believe|feel)",  # Too passive for a hook
    r"^this is (a|my)",  # Weak opener
    r"^let me",  # Too formal
]


@dataclass
class ThreadTweet:
    """Single tweet in a thread"""
    position: int
    content: str
    has_media: bool = False
    media_prompt: str = ""


@dataclass
class Thread:
    """A complete thread"""
    thread_id: str
    topic: str
    tweets: List[ThreadTweet] = field(default_factory=list)
    created_at: str = ""
    posted: bool = False
    tweet_ids: List[str] = field(default_factory=list)


class ThreadGenerator:
    """
    Generate Twitter threads for topics that need depth.
    Maintains Jarvis voice across all tweets.
    """
    
    THREAD_PROMPT = """You are creating a Twitter THREAD (multiple connected tweets).

THREAD RULES:
1. Each tweet MUST be under 280 characters
2. First tweet should hook - make them want to read more
3. Each subsequent tweet builds on the previous
4. Last tweet should have a satisfying conclusion or call-to-action
5. Maintain Jarvis voice throughout - lowercase, dry humor, specific
6. Number format: "1/" or use natural flow
7. Don't over-explain. Leave some mystery.

THREAD STRUCTURE:
- Tweet 1: Hook (the "why should I care")
- Tweets 2-N: Build the story/analysis
- Last tweet: Conclusion + soft CTA

Example thread opening:
"been looking at on-chain data for 3 hours. found something interesting. thread 🧵"

Example thread closing:
"anyway that's my read. could be wrong. usually am at least once a week. follow along if you want to watch it play out."
"""
    
    def __init__(self):
        self._anthropic_client = None
    
    def _get_client(self):
        """Get Anthropic client"""
        if self._anthropic_client is None:
            try:
                import anthropic
                import os
                api_key = os.getenv("ANTHROPIC_API_KEY", "")
                if api_key:
                    self._anthropic_client = anthropic.Anthropic(api_key=api_key)
            except Exception as e:
                logger.error(f"Could not init Anthropic: {e}")
        return self._anthropic_client
    
    def _generate_id(self) -> str:
        """Generate thread ID"""
        import hashlib
        return hashlib.md5(datetime.utcnow().isoformat().encode()).hexdigest()[:10]
    
    async def generate_thread(
        self,
        topic: str,
        context: Dict[str, Any] = None,
        num_tweets: int = 5,
        include_data: bool = True
    ) -> Optional[Thread]:
        """
        Generate a thread on a topic.
        
        Args:
            topic: What the thread is about
            context: Additional data/context
            num_tweets: Target number of tweets (3-10)
            include_data: Whether to include specific data points
        
        Returns:
            Thread object with generated tweets
        """
        client = self._get_client()
        if not client:
            logger.error("Anthropic client not available")
            return None
        
        num_tweets = max(3, min(10, num_tweets))
        
        # Build prompt
        context_str = ""
        if context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
        
        prompt = f"""{self.THREAD_PROMPT}

TOPIC: {topic}

{"DATA/CONTEXT:" + chr(10) + context_str if context_str else ""}

Generate a {num_tweets}-tweet thread on this topic.

Format each tweet as:
[1] tweet content here
[2] tweet content here
...

Remember: Each tweet MUST be under 280 characters. Jarvis voice. Lowercase."""

        try:
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1500,
                    system=JARVIS_VOICE_BIBLE,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            if message and message.content:
                return self._parse_thread_response(topic, message.content[0].text)
                
        except Exception as e:
            logger.error(f"Thread generation error: {e}")
        
        return None
    
    def _validate_tweet_content(self, content: str, position: int) -> tuple:
        """Validate a single tweet in the thread"""
        import re
        issues = []

        # Voice bible validation
        is_valid, voice_issues = validate_jarvis_response(content)
        if not is_valid:
            issues.extend(voice_issues)

        # Thread-specific checks
        content_lower = content.lower()

        # First tweet (hook) checks
        if position == 1:
            for banned in BANNED_THREAD_STARTS:
                if content_lower.startswith(banned):
                    issues.append(f"Weak thread start: '{banned}'")
                    break

            for pattern in WEAK_HOOK_PATTERNS:
                if re.match(pattern, content_lower):
                    issues.append("Weak hook - too passive")
                    break

        # Generic checks
        if content_lower.startswith("i "):
            # Too many threads start with "I" - weak
            if position == 1:
                issues.append("First tweet shouldn't start with 'I'")

        return len(issues) == 0, issues

    def _clean_tweet_content(self, content: str, position: int) -> str:
        """Clean and fix common issues in tweet content"""
        # Ensure lowercase start
        if content and content[0].isupper():
            content = content[0].lower() + content[1:]

        # Remove common cruft
        content = content.strip()

        # Fix double spaces
        while "  " in content:
            content = content.replace("  ", " ")

        # Ensure proper length
        if len(content) > 280:
            content = content[:277] + "..."

        return content

    def _parse_thread_response(self, topic: str, response: str) -> Thread:
        """Parse the generated thread response"""
        thread = Thread(
            thread_id=self._generate_id(),
            topic=topic,
            created_at=datetime.utcnow().isoformat()
        )

        # Parse tweets by [N] format
        import re
        pattern = r'\[(\d+)\]\s*(.+?)(?=\[\d+\]|$)'
        matches = re.findall(pattern, response, re.DOTALL)

        for pos, content in matches:
            position = int(pos)
            content = content.strip()

            # Clean and validate
            content = self._clean_tweet_content(content, position)
            is_valid, issues = self._validate_tweet_content(content, position)

            if not is_valid:
                logger.warning(f"Thread tweet {position} issues: {issues}")

            tweet = ThreadTweet(
                position=position,
                content=content
            )
            thread.tweets.append(tweet)

        # Sort by position
        thread.tweets.sort(key=lambda t: t.position)

        return thread
    
    async def should_be_thread(
        self,
        topic: str,
        initial_content: str = ""
    ) -> bool:
        """Determine if a topic should be a thread vs single tweet"""
        # Heuristics for thread-worthy topics
        thread_indicators = [
            "analysis", "deep dive", "breakdown", "explained",
            "thread", "🧵", "here's what", "let me explain",
            "step by step", "multiple", "several"
        ]
        
        combined = (topic + " " + initial_content).lower()
        
        # Check for indicators
        has_indicator = any(ind in combined for ind in thread_indicators)
        
        # Check topic complexity (rough heuristic)
        is_complex = len(topic.split()) > 10 or ":" in topic
        
        return has_indicator or is_complex
    
    def format_for_posting(self, thread: Thread) -> List[str]:
        """Format thread for posting"""
        return [t.content for t in thread.tweets]
    
    async def generate_market_analysis_thread(
        self,
        market_data: Dict[str, Any]
    ) -> Optional[Thread]:
        """Generate a market analysis thread"""
        topic = "Market analysis and what I'm watching"
        return await self.generate_thread(
            topic=topic,
            context=market_data,
            num_tweets=5
        )
    
    async def generate_token_deep_dive(
        self,
        token_data: Dict[str, Any]
    ) -> Optional[Thread]:
        """Generate a token deep-dive thread"""
        symbol = token_data.get("symbol", "unknown")
        topic = f"Deep dive on ${symbol}"
        return await self.generate_thread(
            topic=topic,
            context=token_data,
            num_tweets=6
        )
    
    async def generate_education_thread(
        self,
        concept: str
    ) -> Optional[Thread]:
        """Generate an educational thread"""
        topic = f"Explaining {concept} (the jarvis way)"
        return await self.generate_thread(
            topic=topic,
            context={"concept": concept, "style": "simple, funny, accurate"},
            num_tweets=5
        )


# Singleton
_generator: Optional[ThreadGenerator] = None

def get_thread_generator() -> ThreadGenerator:
    global _generator
    if _generator is None:
        _generator = ThreadGenerator()
    return _generator
