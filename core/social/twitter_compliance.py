"""
Twitter/X Content Compliance

Ensures all tweets comply with X/Twitter Terms of Service
and avoid regulatory issues.

Prompt #157: Twitter Content Compliance
"""

import os
import re
import logging
from dataclasses import dataclass
from typing import List, Tuple, Dict, Set
from enum import Enum

logger = logging.getLogger(__name__)


def _get_max_tweet_length() -> int:
    raw = os.getenv("X_MAX_TWEET_LENGTH") or os.getenv("TWITTER_MAX_TWEET_LENGTH")
    if raw:
        try:
            value = int(raw)
            if 1 <= value <= 4000:
                return value
        except ValueError:
            logger.warning("Invalid X_MAX_TWEET_LENGTH, falling back to 280")
    return 280


class ViolationType(str, Enum):
    """Types of content violations"""
    TOO_LONG = "too_long"
    TOO_MANY_HASHTAGS = "too_many_hashtags"
    FINANCIAL_ADVICE = "financial_advice_without_disclaimer"
    MANIPULATION = "manipulation_language"
    SPAM = "spam_indicators"
    MISLEADING = "misleading_claims"
    MISSING_DISCLOSURE = "missing_bot_disclosure"


@dataclass
class ValidationResult:
    """Result of content validation"""
    is_valid: bool
    violations: List[ViolationType]
    issues: List[str]
    suggestions: List[str]
    risk_score: float  # 0-1, higher = more risky


class TwitterCompliance:
    """
    Ensures bot follows X/Twitter Terms of Service
    and financial content regulations.
    """

    # X API and ToS limits
    RATE_LIMITS = {
        "tweets_per_15_min": 50,
        "tweets_per_24h": 2400,
        "api_calls_per_15_min": 450,
        "dm_per_24h": 500,
        "max_tweet_length": 280,
        "max_hashtags": 3,
    }

    # Words that require NFA disclaimer
    FINANCIAL_ADVICE_INDICATORS = {
        "buy", "sell", "invest", "trade", "long", "short",
        "bullish", "bearish", "profit", "gains", "returns",
        "entry", "exit", "position", "target", "stop loss",
        "take profit", "leverage", "margin"
    }

    # Words that suggest market manipulation
    MANIPULATION_WORDS = {
        "pump", "dump", "moon", "100x", "1000x", "guaranteed",
        "can't lose", "free money", "get rich", "easy money",
        "sure thing", "insider", "ape in", "send it",
        "going to explode", "next bitcoin", "next ethereum"
    }

    # Spam indicators
    SPAM_INDICATORS = {
        "follow back", "f4f", "dm me", "check my bio",
        "link in bio", "giveaway", "airdrop", "free crypto",
        "send me", "I'll send back"
    }

    # Required disclaimers
    DISCLAIMERS = {"nfa", "not financial advice", "dyor", "do your own research"}

    def __init__(self):
        self.blocked_words: Set[str] = set()
        self.load_custom_blocklist()

    def load_custom_blocklist(self):
        """Load custom blocked words from config"""
        # Could load from file or database
        pass

    def validate_tweet(self, content: str) -> ValidationResult:
        """Validate tweet content before posting"""
        violations = []
        issues = []
        suggestions = []
        risk_score = 0.0

        content_lower = content.lower()

        # Check length
        max_len = _get_max_tweet_length()
        if len(content) > max_len:
            violations.append(ViolationType.TOO_LONG)
            issues.append(f"Tweet too long: {len(content)} chars (max {max_len})")
            suggestions.append(f"Shorten the tweet to under {max_len} characters")
            risk_score += 0.3

        # Check hashtag count
        hashtag_count = content.count("#")
        if hashtag_count > self.RATE_LIMITS["max_hashtags"]:
            violations.append(ViolationType.TOO_MANY_HASHTAGS)
            issues.append(f"Too many hashtags: {hashtag_count} (max {self.RATE_LIMITS['max_hashtags']})")
            suggestions.append(f"Reduce hashtags to {self.RATE_LIMITS['max_hashtags']} or fewer")
            risk_score += 0.2

        # Check for financial advice without disclaimer
        has_financial_terms = any(term in content_lower for term in self.FINANCIAL_ADVICE_INDICATORS)
        has_disclaimer = any(disclaimer in content_lower for disclaimer in self.DISCLAIMERS)

        if has_financial_terms and not has_disclaimer:
            violations.append(ViolationType.FINANCIAL_ADVICE)
            issues.append("Financial language detected without NFA/DYOR disclaimer")
            suggestions.append("Add 'NFA' or 'Not Financial Advice' to the tweet")
            risk_score += 0.4

        # Check for manipulation language
        found_manipulation = [word for word in self.MANIPULATION_WORDS if word in content_lower]
        if found_manipulation:
            violations.append(ViolationType.MANIPULATION)
            issues.append(f"Potentially manipulative language: {', '.join(found_manipulation[:3])}")
            suggestions.append("Remove or rephrase manipulative language")
            risk_score += 0.5

        # Check for spam indicators
        found_spam = [indicator for indicator in self.SPAM_INDICATORS if indicator in content_lower]
        if found_spam:
            violations.append(ViolationType.SPAM)
            issues.append(f"Spam indicators detected: {', '.join(found_spam[:3])}")
            suggestions.append("Remove spam-like phrases")
            risk_score += 0.4

        # Check for misleading claims
        misleading_patterns = [
            r"\d+%\s*(guaranteed|certain|sure)",
            r"(will|going to)\s+(moon|100x|explode)",
            r"(can't|cannot)\s+(lose|fail)",
        ]
        for pattern in misleading_patterns:
            if re.search(pattern, content_lower):
                violations.append(ViolationType.MISLEADING)
                issues.append("Potentially misleading claims detected")
                suggestions.append("Avoid making guaranteed or certain predictions")
                risk_score += 0.5
                break

        # Cap risk score at 1.0
        risk_score = min(risk_score, 1.0)

        return ValidationResult(
            is_valid=len(violations) == 0,
            violations=violations,
            issues=issues,
            suggestions=suggestions,
            risk_score=risk_score
        )

    def validate_engagement(self, action: str, target_user: str, recent_engagements: List[str]) -> Tuple[bool, str]:
        """Validate engagement action to avoid spam behavior"""

        # Don't engage with same user too frequently
        target_engagement_count = recent_engagements.count(target_user)
        if target_engagement_count >= 3:
            return False, f"Already engaged with {target_user} {target_engagement_count} times recently"

        return True, "Engagement allowed"

    def sanitize_content(self, content: str) -> str:
        """Attempt to sanitize content to pass validation"""
        sanitized = content

        # Truncate if too long
        max_len = _get_max_tweet_length()
        if len(sanitized) > max_len:
            # Try to cut at a sentence boundary
            if len(sanitized) > max_len - 10:
                # Find last sentence end before the limit
                last_period = sanitized[:max_len - 10].rfind(".")
                last_newline = sanitized[:max_len - 10].rfind("\n")
                cut_point = max(last_period, last_newline)

                if cut_point > max(40, max_len - 80):
                    sanitized = sanitized[:cut_point + 1]
                else:
                    sanitized = sanitized[:max_len - 3] + "..."

        # Replace manipulation words
        for word in self.MANIPULATION_WORDS:
            if word in sanitized.lower():
                # Replace with safer alternatives
                replacements = {
                    "moon": "rise",
                    "pump": "move up",
                    "dump": "decline",
                    "guaranteed": "potential",
                    "100x": "significant",
                    "ape in": "consider",
                }
                replacement = replacements.get(word, "")
                if replacement:
                    pattern = re.compile(re.escape(word), re.IGNORECASE)
                    sanitized = pattern.sub(replacement, sanitized)

        # Add disclaimer if financial terms present and no disclaimer
        content_lower = sanitized.lower()
        has_financial = any(term in content_lower for term in self.FINANCIAL_ADVICE_INDICATORS)
        has_disclaimer = any(d in content_lower for d in self.DISCLAIMERS)

        if has_financial and not has_disclaimer:
            if len(sanitized) + 5 <= 280:
                sanitized = sanitized.rstrip() + " NFA"

        return sanitized

    def get_compliance_report(self, tweets: List[str]) -> Dict:
        """Generate compliance report for a batch of tweets"""
        total = len(tweets)
        valid_count = 0
        violation_counts: Dict[ViolationType, int] = {}
        total_risk = 0.0

        for tweet in tweets:
            result = self.validate_tweet(tweet)

            if result.is_valid:
                valid_count += 1

            for violation in result.violations:
                violation_counts[violation] = violation_counts.get(violation, 0) + 1

            total_risk += result.risk_score

        return {
            "total_tweets": total,
            "valid_tweets": valid_count,
            "invalid_tweets": total - valid_count,
            "compliance_rate": valid_count / total if total > 0 else 1.0,
            "violation_breakdown": {v.value: c for v, c in violation_counts.items()},
            "average_risk_score": total_risk / total if total > 0 else 0.0,
        }


# Convenience function for quick validation
def validate_tweet_content(content: str) -> Tuple[bool, List[str]]:
    """Quick validation helper"""
    compliance = TwitterCompliance()
    result = compliance.validate_tweet(content)
    return result.is_valid, result.issues


# Testing
if __name__ == "__main__":
    compliance = TwitterCompliance()

    test_tweets = [
        "🟢 $SOL looking bullish here. Strong accumulation pattern. NFA",
        "BUY BUY BUY! This is going to moon 100x guaranteed!",
        "$BTC about to pump! Get in now before it's too late! Easy money!",
        "Market looking choppy. Waiting for better setups. 🤖",
        "This is financial advice: you should definitely invest everything",
    ]

    for tweet in test_tweets:
        result = compliance.validate_tweet(tweet)
        status = "✅ VALID" if result.is_valid else "❌ INVALID"
        print(f"\n{status}: {tweet[:50]}...")
        if not result.is_valid:
            print(f"  Issues: {result.issues}")
            print(f"  Risk Score: {result.risk_score:.2f}")
