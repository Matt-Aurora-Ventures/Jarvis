"""
Reply Prioritizer
Score and filter mentions to prioritize valuable interactions
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MentionScore:
    """Scored mention for prioritization"""
    tweet_id: str
    user_id: str
    username: str
    text: str
    follower_count: int = 0
    is_verified: bool = False
    is_influencer: bool = False
    is_micro_influencer: bool = False
    is_question: bool = False
    is_positive: bool = False
    is_negative: bool = False
    has_alpha_request: bool = False
    crypto_topic: Optional[str] = None
    is_high_value: bool = False
    is_thread_context: bool = False
    is_direct_mention: bool = False  # "hey jarvis" etc - strong intent
    cashtags: List[str] = None  # $BTC, $SOL etc mentioned
    engagement_potential: float = 0.0
    priority_score: float = 0.0
    should_reply: bool = True
    skip_reason: str = ""
    suggested_tone: str = "default"  # default, appreciative, helpful, playful

    def __post_init__(self):
        if self.cashtags is None:
            self.cashtags = []


class ReplyPrioritizer:
    """
    Prioritize which mentions to reply to.
    Score by value, skip low-quality, prioritize high-value.
    """
    
    # Thresholds
    MIN_REPLY_SCORE = 10.0
    INFLUENCER_THRESHOLD = 10000
    MICRO_INFLUENCER_THRESHOLD = 1000

    SPAM_KEYWORDS = [
        "follow me", "check my", "dm me", "send me", "airdrop",
        "giveaway", "free", "claim", "whitelist", "presale scam",
        "limited time", "hurry", "act now", "don't miss", "click link",
        "check bio", "link in bio", "join now", "before too late"
    ]

    QUESTION_INDICATORS = [
        "?", "what", "how", "why", "when", "where", "which", "can you",
        "do you", "will you", "would you", "could you", "should", "is it",
        "thoughts on", "opinion on", "think about", "view on", "take on"
    ]

    ALPHA_KEYWORDS = ["alpha", "call", "signal", "prediction", "price", "target", "pump", "entry", "exit", "tp", "sl"]

    # Cashtag patterns for token detection
    CASHTAG_PATTERN = r'\$([A-Z]{2,10})\b'

    # Direct mention patterns (shows strong intent)
    DIRECT_MENTION_PATTERNS = [
        "hey jarvis", "@jarvis", "jarvis can you", "jarvis what",
        "yo jarvis", "jarvis please", "jarvis help"
    ]

    # Crypto-specific engagement topics
    CRYPTO_TOPICS = {
        "market": ["market", "btc", "eth", "sol", "solana", "bitcoin", "crypto", "bull", "bear"],
        "trading": ["buy", "sell", "long", "short", "trade", "position", "entry", "exit"],
        "memes": ["memecoin", "degen", "ape", "pump", "moon", "wen", "ser", "gm", "gn"],
        "tech": ["ai", "agent", "autonomous", "bot", "code", "build", "dev"],
        "opinion": ["bullish", "bearish", "thoughts", "think", "believe", "feel"],
    }

    # High-value interaction types
    HIGH_VALUE_PATTERNS = [
        r"love your (work|content|posts|takes)",
        r"(you|jarvis) (are|is) (amazing|great|helpful|genius)",
        r"(saved|helped) me",
        r"best (bot|ai|account)",
        r"(following|followed) for (years|months|awhile)",
    ]
    
    def __init__(self):
        self.processed_ids: set = set()
        self.daily_reply_count = 0
        self.max_daily_replies = 50
        self.max_processed_ids = 5000  # Limit memory growth
        self.last_reset = datetime.utcnow().date()
    
    def _reset_daily_count(self):
        """Reset daily reply count"""
        today = datetime.utcnow().date()
        if today > self.last_reset:
            self.daily_reply_count = 0
            self.last_reset = today
    
    def _is_spam(self, text: str) -> bool:
        """Check if text is spam"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.SPAM_KEYWORDS)
    
    def _is_question(self, text: str) -> bool:
        """Check if text is a question"""
        text_lower = text.lower()
        return any(q in text_lower for q in self.QUESTION_INDICATORS)
    
    def _has_alpha_request(self, text: str) -> bool:
        """Check if asking for alpha/calls"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.ALPHA_KEYWORDS)

    def _detect_crypto_topic(self, text: str) -> Optional[str]:
        """Detect which crypto topic the mention is about"""
        import re
        text_lower = text.lower()
        for topic, keywords in self.CRYPTO_TOPICS.items():
            if any(kw in text_lower for kw in keywords):
                return topic
        return None

    def _is_high_value_engagement(self, text: str) -> bool:
        """Check if this is a high-value positive engagement"""
        import re
        text_lower = text.lower()
        for pattern in self.HIGH_VALUE_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _is_thread_reply(self, text: str) -> bool:
        """Detect if this is a reply in a thread context"""
        text_lower = text.lower()
        thread_indicators = ["in this thread", "above", "earlier you said", "you mentioned", "following up"]
        return any(ind in text_lower for ind in thread_indicators)

    def _extract_cashtags(self, text: str) -> List[str]:
        """Extract cashtags ($BTC, $SOL, etc.) from text"""
        import re
        matches = re.findall(self.CASHTAG_PATTERN, text.upper())
        return list(set(matches))  # Dedupe

    def _is_direct_mention(self, text: str) -> bool:
        """Check if this is a direct mention of Jarvis (strong intent)"""
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in self.DIRECT_MENTION_PATTERNS)

    def _calculate_engagement_potential(self, score: 'MentionScore') -> float:
        """Calculate engagement potential score for virality"""
        potential = 0.0

        # Base from follower reach
        if score.follower_count > 0:
            import math
            potential += math.log10(score.follower_count + 1) * 2

        # Verified = wider reach
        if score.is_verified:
            potential += 15

        # Questions get more engagement
        if score.is_question:
            potential += 10

        # Crypto topics trend
        if score.crypto_topic:
            potential += 5

        return potential

    def _detect_sentiment(self, text: str) -> tuple:
        """Simple sentiment detection"""
        text_lower = text.lower()
        
        positive_words = ["love", "great", "amazing", "thanks", "appreciate", "best", "good", "nice", "helpful"]
        negative_words = ["hate", "suck", "wrong", "bad", "worst", "scam", "fake", "trash", "garbage"]
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        return pos_count > 0, neg_count > 0
    
    def score_mention(
        self,
        tweet_id: str,
        user_id: str,
        username: str,
        text: str,
        follower_count: int = 0,
        is_verified: bool = False,
        user_memory: Optional[Any] = None
    ) -> MentionScore:
        """
        Score a mention for reply priority.
        
        Returns MentionScore with priority and should_reply decision.
        """
        score = MentionScore(
            tweet_id=tweet_id,
            user_id=user_id,
            username=username,
            text=text,
            follower_count=follower_count,
            is_verified=is_verified
        )
        
        # Skip if already processed
        if tweet_id in self.processed_ids:
            score.should_reply = False
            score.skip_reason = "already_processed"
            return score
        
        # Skip spam
        if self._is_spam(text):
            score.should_reply = False
            score.skip_reason = "spam"
            return score
        
        # Detect characteristics
        score.is_question = self._is_question(text)
        score.has_alpha_request = self._has_alpha_request(text)
        score.is_positive, score.is_negative = self._detect_sentiment(text)
        score.is_influencer = follower_count >= self.INFLUENCER_THRESHOLD
        score.is_micro_influencer = follower_count >= self.MICRO_INFLUENCER_THRESHOLD
        score.crypto_topic = self._detect_crypto_topic(text)
        score.is_high_value = self._is_high_value_engagement(text)
        score.is_thread_context = self._is_thread_reply(text)
        score.is_direct_mention = self._is_direct_mention(text)
        score.cashtags = self._extract_cashtags(text)

        # Calculate priority score
        priority = 0.0

        # Base score from follower count (logarithmic)
        if follower_count > 0:
            import math
            priority += math.log10(follower_count + 1) * 5  # 0-30 points

        # Verified users get bonus
        if is_verified:
            priority += 20

        # Influencers get bonus
        if score.is_influencer:
            priority += 15
        elif score.is_micro_influencer:
            priority += 8

        # Questions are high value
        if score.is_question:
            priority += 25

        # Alpha requests are valuable (shows engagement)
        if score.has_alpha_request:
            priority += 10

        # High-value engagement (praise, appreciation)
        if score.is_high_value:
            priority += 20
            score.suggested_tone = "appreciative"

        # Crypto topic bonus - shows relevance
        if score.crypto_topic:
            priority += 5
            if score.crypto_topic == "tech":
                score.suggested_tone = "technical"
            elif score.crypto_topic == "memes":
                score.suggested_tone = "playful"

        # Thread context - they're engaged
        if score.is_thread_context:
            priority += 10

        # Direct mention - strong intent to engage with Jarvis
        if score.is_direct_mention:
            priority += 30  # High priority - they called us out directly

        # Cashtags show specific crypto interest
        if score.cashtags:
            priority += 5 * min(len(score.cashtags), 3)  # Up to 15 pts for multiple
            # Major coins get slight boost
            major_coins = {"BTC", "ETH", "SOL", "BNB"}
            if any(tag in major_coins for tag in score.cashtags):
                priority += 5

        # Positive sentiment bonus
        if score.is_positive:
            priority += 10
            if not score.suggested_tone or score.suggested_tone == "default":
                score.suggested_tone = "appreciative"

        # Negative sentiment - still engage but lower priority
        if score.is_negative:
            priority -= 5

        # User memory bonuses
        if user_memory:
            if hasattr(user_memory, 'interaction_count') and user_memory.interaction_count > 2:
                priority += 15  # Returning user bonus
            if hasattr(user_memory, 'engagement_quality'):
                if user_memory.engagement_quality == "high":
                    priority += 10
                elif user_memory.engagement_quality == "spam":
                    priority -= 50

        # Set helpful tone for questions
        if score.is_question and score.suggested_tone == "default":
            score.suggested_tone = "helpful"

        # Calculate engagement potential (virality score)
        score.engagement_potential = self._calculate_engagement_potential(score)

        score.priority_score = priority
        
        # Decision: reply if above threshold
        score.should_reply = priority >= self.MIN_REPLY_SCORE
        
        if not score.should_reply:
            score.skip_reason = "low_priority"
        
        return score
    
    def prioritize_mentions(
        self,
        mentions: List[Dict[str, Any]],
        memory_system=None
    ) -> List[MentionScore]:
        """
        Prioritize a list of mentions.
        
        Returns sorted list of MentionScore (highest priority first).
        """
        self._reset_daily_count()
        
        scored = []
        for mention in mentions:
            user_memory = None
            if memory_system:
                user_memory = memory_system.get_user(mention.get("user_id", ""))
            
            # Handle both 'username' and 'author_username' keys
            username = mention.get("username") or mention.get("author_username") or "unknown"
            user_id = mention.get("user_id") or mention.get("author_id") or ""
            
            score = self.score_mention(
                tweet_id=str(mention.get("id", "")),
                user_id=str(user_id),
                username=username,
                text=mention.get("text", ""),
                follower_count=mention.get("follower_count", 0),
                is_verified=mention.get("is_verified", False),
                user_memory=user_memory
            )
            scored.append(score)
        
        # Sort by priority (highest first)
        scored.sort(key=lambda x: x.priority_score, reverse=True)
        
        # Limit replies per day
        remaining = self.max_daily_replies - self.daily_reply_count
        for i, score in enumerate(scored):
            if score.should_reply and i >= remaining:
                score.should_reply = False
                score.skip_reason = "daily_limit"
        
        return scored
    
    def mark_replied(self, tweet_id: str):
        """Mark a tweet as replied to"""
        self.processed_ids.add(tweet_id)
        self.daily_reply_count += 1

        # Prune old IDs if too many (FIFO-ish removal)
        if len(self.processed_ids) > self.max_processed_ids:
            # Remove oldest 20%
            remove_count = len(self.processed_ids) // 5
            ids_list = list(self.processed_ids)
            for _ in range(remove_count):
                if ids_list:
                    self.processed_ids.discard(ids_list.pop(0))
    
    def get_reply_stats(self) -> Dict[str, Any]:
        """Get reply statistics"""
        self._reset_daily_count()
        return {
            "daily_replies": self.daily_reply_count,
            "max_daily": self.max_daily_replies,
            "remaining": self.max_daily_replies - self.daily_reply_count,
            "processed_count": len(self.processed_ids)
        }


# Singleton
_prioritizer: Optional[ReplyPrioritizer] = None

def get_reply_prioritizer() -> ReplyPrioritizer:
    global _prioritizer
    if _prioritizer is None:
        _prioritizer = ReplyPrioritizer()
    return _prioritizer
