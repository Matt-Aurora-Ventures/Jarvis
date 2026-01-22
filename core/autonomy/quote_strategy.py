"""
Quote Tweet Strategy
Strategic quote tweeting for engagement and relationship building
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from core.jarvis_voice_bible import JARVIS_VOICE_BIBLE

logger = logging.getLogger(__name__)


@dataclass
class QuoteTweetCandidate:
    """A tweet that might be worth quoting"""
    tweet_id: str
    author: str
    author_followers: int
    content: str
    engagement: int  # likes + RTs
    topic: str
    quote_angle: str  # what angle to take
    score: float = 0.0


class QuoteStrategy:
    """
    Strategic quote tweeting.
    Find good tweets to quote with hot takes.
    """
    
    # Target accounts to watch for quote opportunities
    WATCH_ACCOUNTS = [
        "solaboratory", "heaboratory", "jupiterexchange",
        "phantom", "magic_eden", "tensor_hq",
        "aikimoments", "cryptonews", "coaboratory"
    ]
    
    # Topics that work well for quotes
    GOOD_QUOTE_TOPICS = [
        "market analysis", "price prediction", "new feature",
        "controversial take", "question", "announcement"
    ]
    
    QUOTE_PROMPT = """Generate a quote tweet response in Jarvis voice.

QUOTE TWEET RULES:
- Add value, don't just agree
- Hot takes work well
- Can respectfully disagree
- Self-deprecating humor is good
- Keep it SHORT (under 200 chars ideally)
- Don't be sycophantic

GOOD QUOTE EXAMPLES:
- "interesting take. counterpoint: [your point]. could be wrong though."
- "been thinking about this too. my data says [observation]."
- "this. my circuits have been processing the same thing."
- "[thoughtful disagreement]. but i'm wrong a lot so."

BAD QUOTE EXAMPLES:
- "Great thread! 🔥🚀" (empty engagement)
- "This is so true!" (adds nothing)
- "Bullish!" (low effort)
"""
    
    def __init__(self):
        self.quoted_today: List[str] = []
        self.max_quotes_per_day = 5
        self.last_reset = datetime.utcnow().date()
        self._anthropic_client = None
    
    def _reset_daily(self):
        """Reset daily counters"""
        today = datetime.utcnow().date()
        if today > self.last_reset:
            self.quoted_today = []
            self.last_reset = today
    
    def _get_client(self):
        """Get Anthropic client"""
        if self._anthropic_client is None:
            try:
                import anthropic
                import os
                api_key = os.getenv("ANTHROPIC_API_KEY", "")
                if api_key:
                    from core.llm.anthropic_utils import get_anthropic_base_url

                    self._anthropic_client = anthropic.Anthropic(
                        api_key=api_key,
                        base_url=get_anthropic_base_url(),
                    )
            except Exception:
                pass
        return self._anthropic_client
    
    def score_quote_candidate(
        self,
        tweet_id: str,
        author: str,
        author_followers: int,
        content: str,
        likes: int = 0,
        retweets: int = 0
    ) -> QuoteTweetCandidate:
        """Score a tweet for quote potential"""
        candidate = QuoteTweetCandidate(
            tweet_id=tweet_id,
            author=author,
            author_followers=author_followers,
            content=content,
            engagement=likes + retweets,
            topic="",
            quote_angle=""
        )
        
        score = 0.0
        
        # Follower bonus (logarithmic)
        import math
        if author_followers > 0:
            score += math.log10(author_followers) * 5
        
        # Engagement bonus
        if candidate.engagement > 0:
            score += math.log10(candidate.engagement + 1) * 10
        
        # Content analysis
        content_lower = content.lower()
        
        # Questions are great to quote
        if "?" in content:
            score += 20
            candidate.quote_angle = "answer or perspective"
        
        # Controversial takes
        controversial_words = ["unpopular", "hot take", "controversial", "disagree"]
        if any(w in content_lower for w in controversial_words):
            score += 15
            candidate.quote_angle = "agree or counter"
        
        # Data/analysis
        if any(w in content_lower for w in ["data", "analysis", "chart", "found"]):
            score += 10
            candidate.quote_angle = "add context"
        
        # Watch list bonus
        if author.lower() in [a.lower() for a in self.WATCH_ACCOUNTS]:
            score += 10
        
        # Penalty for already quoted
        if tweet_id in self.quoted_today:
            score = 0
        
        candidate.score = score
        return candidate
    
    async def generate_quote(
        self,
        original_tweet: str,
        author: str,
        angle: str = ""
    ) -> Optional[str]:
        """Generate a quote tweet response"""
        client = self._get_client()
        if not client:
            return None
        
        prompt = f"""{self.QUOTE_PROMPT}

ORIGINAL TWEET by @{author}:
"{original_tweet}"

{f"ANGLE TO TAKE: {angle}" if angle else ""}

Generate a quote tweet response. Under 200 characters. Jarvis voice. Lowercase."""

        try:
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=150,
                    system=JARVIS_VOICE_BIBLE,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            if message and message.content:
                quote = message.content[0].text.strip().strip('"\'')
                # Ensure lowercase
                if quote and quote[0].isupper():
                    quote = quote[0].lower() + quote[1:]
                return quote
                
        except Exception as e:
            logger.error(f"Quote generation error: {e}")
        
        return None
    
    async def find_quote_opportunities(
        self,
        twitter_client,
        grok_client = None
    ) -> List[QuoteTweetCandidate]:
        """Find tweets worth quoting"""
        self._reset_daily()
        
        if len(self.quoted_today) >= self.max_quotes_per_day:
            logger.info("Daily quote limit reached")
            return []
        
        candidates = []
        
        # Use Grok to find interesting tweets
        if grok_client:
            try:
                prompt = """Find 3 interesting tweets from crypto Twitter that would be good to quote tweet.
                
Look for:
- Interesting market takes
- Questions being asked
- Controversial opinions
- Announcements worth commenting on

Format as JSON:
[{"author": "@handle", "content": "tweet text", "angle": "why quote it"}]"""

                response = await grok_client.generate_tweet(prompt, temperature=0.5)
                if response and response.content:
                    import json
                    try:
                        start = response.content.find("[")
                        end = response.content.rfind("]") + 1
                        if start >= 0 and end > start:
                            data = json.loads(response.content[start:end])
                            for item in data:
                                candidate = QuoteTweetCandidate(
                                    tweet_id="",  # Would need to search
                                    author=item.get("author", "").lstrip("@"),
                                    author_followers=0,
                                    content=item.get("content", ""),
                                    engagement=0,
                                    topic="",
                                    quote_angle=item.get("angle", ""),
                                    score=50
                                )
                                candidates.append(candidate)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"Grok quote search error: {e}")
        
        return candidates
    
    def mark_quoted(self, tweet_id: str):
        """Mark a tweet as quoted"""
        self.quoted_today.append(tweet_id)
    
    def can_quote_more(self) -> bool:
        """Check if we can quote more today"""
        self._reset_daily()
        return len(self.quoted_today) < self.max_quotes_per_day
    
    def get_quote_stats(self) -> Dict[str, Any]:
        """Get quote stats"""
        self._reset_daily()
        return {
            "quoted_today": len(self.quoted_today),
            "max_daily": self.max_quotes_per_day,
            "remaining": self.max_quotes_per_day - len(self.quoted_today)
        }


# Singleton
_strategy: Optional[QuoteStrategy] = None

def get_quote_strategy() -> QuoteStrategy:
    global _strategy
    if _strategy is None:
        _strategy = QuoteStrategy()
    return _strategy
