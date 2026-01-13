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
    is_question: bool = False
    is_positive: bool = False
    is_negative: bool = False
    has_alpha_request: bool = False
    engagement_potential: float = 0.0
    priority_score: float = 0.0
    should_reply: bool = True
    skip_reason: str = ""


class ReplyPrioritizer:
    """
    Prioritize which mentions to reply to.
    Score by value, skip low-quality, prioritize high-value.
    """
    
    # Thresholds
    MIN_REPLY_SCORE = 10.0
    INFLUENCER_THRESHOLD = 10000
    SPAM_KEYWORDS = [
        "follow me", "check my", "dm me", "send me", "airdrop",
        "giveaway", "free", "claim", "whitelist", "presale scam"
    ]
    QUESTION_INDICATORS = ["?", "what", "how", "why", "when", "where", "which", "can you", "do you"]
    ALPHA_KEYWORDS = ["alpha", "call", "signal", "prediction", "price", "target", "pump"]
    
    def __init__(self):
        self.processed_ids: set = set()
        self.daily_reply_count = 0
        self.max_daily_replies = 50
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
        
        # Questions are high value
        if score.is_question:
            priority += 25
        
        # Alpha requests are valuable (shows engagement)
        if score.has_alpha_request:
            priority += 10
        
        # Positive sentiment bonus
        if score.is_positive:
            priority += 10
        
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
