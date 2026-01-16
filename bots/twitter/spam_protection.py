"""
Spam Bot Protection for Jarvis Twitter

Automatically detects and blocks/mutes spam bots that:
- Quote tweet Jarvis with scam links
- Have low follower counts with bot-like patterns
- Use spammy keywords (airdrop, claim now, etc.)

This protects Jarvis from visibility attacks by low-quality bot accounts.
"""

import asyncio
import json
import logging
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Generator

logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SPAM_DB = DATA_DIR / "jarvis_spam_protection.db"


@dataclass
class SpamScore:
    """Score breakdown for spam detection."""
    total: float
    reasons: List[str]
    is_spam: bool
    user_id: str
    username: str


# Spam detection thresholds
SPAM_THRESHOLD = 0.6  # Block if score >= 0.6
MIN_FOLLOWERS = 50  # Very low follower count threshold
NEW_ACCOUNT_DAYS = 30  # Consider accounts < 30 days old as suspicious
SUSPICIOUS_RATIO = 0.1  # Following/Followers ratio threshold (many follows, few followers)

# Spam keywords (weighted)
SPAM_KEYWORDS = {
    # High confidence spam
    "airdrop": 0.4,
    "claim now": 0.5,
    "free tokens": 0.4,
    "giveaway": 0.3,
    "whitelist": 0.25,
    "presale": 0.25,
    "claim your": 0.5,
    "limited spots": 0.4,
    "act fast": 0.3,
    "hurry up": 0.3,
    "don't miss": 0.2,
    "exclusive access": 0.25,
    # Medium confidence
    "join now": 0.2,
    "link in bio": 0.15,
    "dm for": 0.2,
    "send dm": 0.2,
    # Bot patterns
    "follow back": 0.15,
    "f4f": 0.2,
    "follow for follow": 0.2,
}

# Spam URL patterns
SPAM_URL_PATTERNS = [
    r"x\.com/\w+CTO",  # Common scam pattern
    r"t\.co/\w+",  # Shortened links in quotes (suspicious)
    r"bit\.ly",
    r"tinyurl",
    r"linktr\.ee",
]

# Bot username patterns (random numbers, repetitive chars)
BOT_USERNAME_PATTERNS = [
    r"[a-z]+\d{6,}",  # name followed by many numbers
    r"\d{8,}",  # Just numbers
    r"(.)\1{4,}",  # Repeating characters
    r"[a-z]+_\d{4,}",  # name_numbers pattern
]


class SpamProtection:
    """
    Automated spam protection for Jarvis Twitter account.

    Monitors quote tweets and blocks/mutes spam bots automatically.
    """

    def __init__(self):
        self._db_path = SPAM_DB
        self._init_db()
        self._last_scan_time = None
        self._scan_interval = 300  # 5 minutes between scans

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with automatic cleanup."""
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initialize the spam protection database."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Use direct connection since _get_connection may not work before init
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()

            # Track blocked/muted users
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blocked_users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    reason TEXT,
                    spam_score REAL,
                    blocked_at TEXT,
                    quote_tweet_id TEXT
                )
            """)

            # Track scanned quote tweets (avoid rescanning)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scanned_quotes (
                    tweet_id TEXT PRIMARY KEY,
                    author_id TEXT,
                    is_spam INTEGER,
                    scanned_at TEXT
                )
            """)

            # Track our own tweets for scanning
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jarvis_tweets (
                    tweet_id TEXT PRIMARY KEY,
                    posted_at TEXT,
                    last_scanned TEXT
                )
            """)

            conn.commit()
        finally:
            conn.close()

    def calculate_spam_score(self, user: Dict[str, Any], tweet_text: str) -> SpamScore:
        """
        Calculate spam score for a user/tweet combination.

        Returns SpamScore with breakdown of why account was flagged.
        """
        score = 0.0
        reasons = []

        username = user.get("username", "")
        user_id = user.get("id", "")
        followers = user.get("followers_count", 0)
        following = user.get("following_count", 0)
        tweet_count = user.get("tweet_count", 0)
        description = user.get("description", "").lower()
        created_at = user.get("created_at", "")

        text_lower = tweet_text.lower()
        combined_text = f"{text_lower} {description}"

        # 1. Check follower count
        if followers < MIN_FOLLOWERS:
            score += 0.3
            reasons.append(f"Low followers: {followers}")
        elif followers < 100:
            score += 0.15
            reasons.append(f"Few followers: {followers}")

        # 2. Check following/followers ratio (bots often follow many, have few followers)
        if followers > 0 and following > 0:
            ratio = followers / following
            if ratio < SUSPICIOUS_RATIO:
                score += 0.2
                reasons.append(f"Suspicious ratio: {followers}/{following}")

        # 3. Check account age
        if created_at:
            try:
                # Parse various date formats
                for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S+00:00", "%Y-%m-%d"]:
                    try:
                        created = datetime.strptime(created_at.split(".")[0].replace("+00:00", ""), "%Y-%m-%d %H:%M:%S")
                        break
                    except ValueError:
                        continue
                else:
                    created = None

                if created:
                    age_days = (datetime.utcnow() - created).days
                    if age_days < NEW_ACCOUNT_DAYS:
                        score += 0.25
                        reasons.append(f"New account: {age_days} days")
                    elif age_days < 90:
                        score += 0.1
                        reasons.append(f"Young account: {age_days} days")
            except Exception as e:
                logger.debug(f"Could not parse date {created_at}: {e}")

        # 4. Check for spam keywords
        keyword_score = 0
        matched_keywords = []
        for keyword, weight in SPAM_KEYWORDS.items():
            if keyword in combined_text:
                keyword_score += weight
                matched_keywords.append(keyword)

        if keyword_score > 0:
            score += min(keyword_score, 0.5)  # Cap at 0.5
            reasons.append(f"Spam keywords: {', '.join(matched_keywords[:3])}")

        # 5. Check for spam URL patterns
        for pattern in SPAM_URL_PATTERNS:
            if re.search(pattern, tweet_text, re.IGNORECASE):
                score += 0.3
                reasons.append(f"Spam URL pattern detected")
                break

        # 6. Check username for bot patterns
        for pattern in BOT_USERNAME_PATTERNS:
            if re.search(pattern, username, re.IGNORECASE):
                score += 0.2
                reasons.append(f"Bot-like username: {username}")
                break

        # 7. Low tweet count with spam content = likely bot
        if tweet_count < 50 and keyword_score > 0.2:
            score += 0.15
            reasons.append(f"Low tweets ({tweet_count}) + spam content")

        # Determine if spam
        is_spam = score >= SPAM_THRESHOLD

        return SpamScore(
            total=min(score, 1.0),
            reasons=reasons,
            is_spam=is_spam,
            user_id=user_id,
            username=username
        )

    def was_already_scanned(self, tweet_id: str) -> bool:
        """Check if a quote tweet was already scanned."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM scanned_quotes WHERE tweet_id = ?", (tweet_id,))
            return cursor.fetchone() is not None

    def is_user_blocked(self, user_id: str) -> bool:
        """Check if a user is already blocked."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM blocked_users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None

    def record_scan(self, tweet_id: str, author_id: str, is_spam: bool):
        """Record that a quote tweet was scanned."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO scanned_quotes (tweet_id, author_id, is_spam, scanned_at)
                VALUES (?, ?, ?, ?)
            """, (tweet_id, author_id, 1 if is_spam else 0, datetime.now(timezone.utc).isoformat()))
            conn.commit()

    def record_block(self, user_id: str, username: str, reason: str, spam_score: float, quote_tweet_id: str):
        """Record that a user was blocked."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO blocked_users (user_id, username, reason, spam_score, blocked_at, quote_tweet_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, reason, spam_score, datetime.now(timezone.utc).isoformat(), quote_tweet_id))
            conn.commit()

    def record_jarvis_tweet(self, tweet_id: str):
        """Record a Jarvis tweet for future scanning."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO jarvis_tweets (tweet_id, posted_at, last_scanned)
                VALUES (?, ?, NULL)
            """, (tweet_id, datetime.now(timezone.utc).isoformat()))
            conn.commit()

    def get_tweets_to_scan(self, limit: int = 10) -> List[str]:
        """Get Jarvis tweets that need quote tweet scanning."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get recent tweets that haven't been scanned recently
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            cursor.execute("""
                SELECT tweet_id FROM jarvis_tweets
                WHERE last_scanned IS NULL OR last_scanned < ?
                ORDER BY posted_at DESC
                LIMIT ?
            """, (cutoff, limit))

            return [r[0] for r in cursor.fetchall()]

    def mark_tweet_scanned(self, tweet_id: str):
        """Mark a Jarvis tweet as scanned."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE jarvis_tweets SET last_scanned = ? WHERE tweet_id = ?
            """, (datetime.now(timezone.utc).isoformat(), tweet_id))
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Get spam protection statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM blocked_users")
            total_blocked = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM scanned_quotes")
            total_scanned = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM scanned_quotes WHERE is_spam = 1")
            spam_detected = cursor.fetchone()[0]

            # Recent blocks (last 24h)
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            cursor.execute("SELECT COUNT(*) FROM blocked_users WHERE blocked_at > ?", (cutoff,))
            recent_blocks = cursor.fetchone()[0]

            return {
                "total_blocked": total_blocked,
                "total_scanned": total_scanned,
                "spam_detected": spam_detected,
                "recent_blocks_24h": recent_blocks,
                "detection_rate": (spam_detected / total_scanned * 100) if total_scanned > 0 else 0
            }


# Singleton
_spam_protection: Optional[SpamProtection] = None


def get_spam_protection() -> SpamProtection:
    """Get the spam protection singleton."""
    global _spam_protection
    if _spam_protection is None:
        _spam_protection = SpamProtection()
    return _spam_protection


async def scan_and_protect(twitter_client, tweet_ids: List[str] = None) -> Dict[str, Any]:
    """
    Scan quote tweets and auto-block spam bots.

    Args:
        twitter_client: TwitterClient instance
        tweet_ids: Specific tweet IDs to scan (or None to scan recent tweets)

    Returns:
        Dict with scan results
    """
    protection = get_spam_protection()

    blocked_count = 0
    scanned_count = 0
    spam_found = []

    # Get tweets to scan
    if tweet_ids is None:
        tweet_ids = protection.get_tweets_to_scan(limit=5)

    if not tweet_ids:
        logger.debug("No tweets to scan for spam")
        return {"scanned": 0, "blocked": 0}

    for tweet_id in tweet_ids:
        try:
            # Get quote tweets
            quotes = await twitter_client.get_quote_tweets(tweet_id, max_results=20)

            for quote in quotes:
                quote_id = quote.get("id", "")
                author = quote.get("author", {})
                author_id = author.get("id", "")
                text = quote.get("text", "")

                if not author_id or not quote_id:
                    continue

                # Skip if already scanned
                if protection.was_already_scanned(quote_id):
                    continue

                # Skip if user already blocked
                if protection.is_user_blocked(author_id):
                    protection.record_scan(quote_id, author_id, True)
                    continue

                scanned_count += 1

                # Calculate spam score
                spam_score = protection.calculate_spam_score(author, text)

                # Record the scan
                protection.record_scan(quote_id, author_id, spam_score.is_spam)

                if spam_score.is_spam:
                    logger.warning(
                        f"SPAM DETECTED: @{spam_score.username} "
                        f"(score: {spam_score.total:.2f}) - {', '.join(spam_score.reasons)}"
                    )

                    # Block and mute
                    blocked = await twitter_client.block_user(author_id)
                    muted = await twitter_client.mute_user(author_id)

                    if blocked or muted:
                        blocked_count += 1
                        protection.record_block(
                            author_id,
                            spam_score.username,
                            "; ".join(spam_score.reasons),
                            spam_score.total,
                            quote_id
                        )
                        spam_found.append({
                            "username": spam_score.username,
                            "score": spam_score.total,
                            "reasons": spam_score.reasons
                        })

            # Mark tweet as scanned
            protection.mark_tweet_scanned(tweet_id)

        except Exception as e:
            logger.error(f"Error scanning tweet {tweet_id}: {e}")

    if blocked_count > 0:
        logger.info(f"Spam protection: Blocked {blocked_count} bots from {scanned_count} scanned")

    return {
        "scanned": scanned_count,
        "blocked": blocked_count,
        "spam_found": spam_found
    }
