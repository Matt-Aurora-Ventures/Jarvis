"""
Jarvis Admin - Intelligent Telegram moderation with personality.

Features:
- Persistent memory for all messages and users
- Intelligent spam/scam detection
- Self-upgrade detection and queueing
- Jarvis voice in all responses
- Only takes commands from admins
- Contextual moderation decisions
"""
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
import threading
import hashlib

# Paths
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ADMIN_DB = DATA_DIR / "jarvis_admin.db"
UPGRADE_QUEUE = DATA_DIR / "self_upgrade_queue.json"


# =============================================================================
# JARVIS VOICE - Response templates in character
# =============================================================================

JARVIS_VOICE = {
    # Moderation messages
    "spam_deleted": [
        "removed spam. my circuits don't tolerate that.",
        "deleted. sensors detected spam patterns.",
        "that message got yeeted. spam filters working.",
        "spam removed. keeping the signal clean.",
    ],
    "scam_deleted": [
        "scam alert. message deleted, user warned. stay vigilant.",
        "removed potential scam. my algorithms are tingling - be careful out there.",
        "deleted suspicious message. if it sounds too good to be true, my sensors agree.",
    ],
    "user_warned": [
        "⚠️ heads up @{username} - that looked like spam. one more and you're out.",
        "⚠️ warning @{username} - keep it clean or my circuits will have to act.",
    ],
    "user_banned": [
        "banned @{username}. repeated violations. my patience has limits.",
        "@{username} removed. the chat is better for it.",
    ],
    "user_muted": [
        "⏸️ muted @{username} for {hours}h. cooling off period initiated.",
        "⏸️ @{username} needs a timeout. muted for {hours} hours.",
        "⏸️ taking @{username} offline for {hours}h. too much noise.",
    ],
    "rate_limited": [
        "slow down @{username}. my sensors are overheating from your message rate.",
        "easy there @{username}. quality over quantity.",
        "@{username} you're flooding the chat. take a breath.",
    ],
    "mistake_footer": "\n\nif this was a mistake, reach out to @MattFromKr8tiv - even AIs misfire sometimes.",
    
    # Response to non-admin commands
    "not_admin": [
        "appreciate the input, but i only take orders from matt.",
        "nice try. my command circuits are admin-locked.",
        "i hear you, but my instruction set is read-only for non-admins.",
    ],
    "dm_rejected": [
        "i don't process private commands. keep it in the group or talk to matt.",
        "DMs aren't my thing for commands. official requests go through matt.",
    ],
    
    # Self-upgrade detection
    "upgrade_queued": "interesting. i've noted this for potential improvement. will process through console.",
    "feature_request": "logged that feature request. matt will see it in the queue.",
    
    # General responses
    "greeting": [
        "hey. jarvis here. what's moving?",
        "circuits online. how can i help?",
        "present and processing.",
    ],
}


@dataclass
class UserProfile:
    """Profile for a Telegram user."""
    user_id: int
    username: str
    first_seen: str
    message_count: int = 0
    warning_count: int = 0
    is_banned: bool = False
    is_trusted: bool = False
    spam_score: float = 0.0
    last_message_at: str = ""
    notes: str = ""


@dataclass
class MessageRecord:
    """Record of a message for analysis."""
    message_id: int
    user_id: int
    username: str
    text: str
    timestamp: str
    chat_id: int
    was_deleted: bool = False
    deletion_reason: str = ""
    

class JarvisAdmin:
    """Intelligent Telegram admin with Jarvis personality."""
    
    def __init__(self, db_path: Path = ADMIN_DB):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
        
        # Load admin IDs
        admin_str = os.environ.get("TELEGRAM_ADMIN_IDS", "8527130908")
        self.admin_ids = set(int(x.strip()) for x in admin_str.split(",") if x.strip().isdigit())
        
        # Spam detection patterns - comprehensive list
        self.spam_patterns = [
            r"join\s+(now|here|us)",
            r"(t\.me|telegram\.me)/\w+",  # Telegram links (suspicious)
            r"(bit\.ly|tinyurl|goo\.gl|shorturl|is\.gd|v\.gd|rb\.gy|cutt\.ly)",  # URL shorteners
            r"(airdrop|giveaway|free\s+\$)",
            r"(dm\s+me|check\s+dm|sent\s+you|message\s+me)",
            r"(100x|1000x|guaranteed|profit|make\s+money)",
            r"(click\s+here|limited\s+time|act\s+fast)",
            r"(@\w+bot)",  # Other bots
            r"(buy\s+(a\s+)?sol\s+wallet|buying\s+sol\s+wallet)",
            r"(purchase\s+wallet|sell\s+wallet)",
            r"(whatsapp|telegram\s+@|contact\s+(me|us)\s+on)",
            r"(sex|porn|xxx|dating|hookup|onlyfans)",  # Adult spam
            r"(casino|bet\s+now|gambling|free\s+spins)",  # Gambling spam
            r"(earn\s+\$\d+|make\s+\$\d+\s+daily)",  # Income spam
            r"(promo\s+code|discount\s+code|coupon)",  # Promo spam
            r"(follow\s+back|f4f|l4l|s4s)",  # Follow spam
            r"(crypto\s+signals?|trading\s+signals?)",  # Signal selling
            r"(presale|pre-sale|whitelist\s+spot)",  # Presale spam
            r"(pump\s+group|pump\s+and\s+dump)",  # Pump spam
            r"(recover\s+wallet|lost\s+crypto|stolen\s+funds)",  # Recovery scam
            r"(metamask|trustwallet|phantom)\s+support",  # Fake support
            r"(binance|coinbase|kraken)\s+(support|help)",  # Exchange scam
            r"(investment\s+plan|roi\s+guaranteed)",  # Investment scam
        ]

        # Scam keywords - expanded list
        self.scam_keywords = [
            "send sol", "send eth", "send btc", "send usdt", "send usdc",
            "wallet connect", "validate wallet", "verify wallet", "sync wallet",
            "claim reward", "claim airdrop", "claim tokens",
            "investment opportunity", "double your", "triple your",
            "act now", "urgent action", "verify account",
            "technical support", "customer support chat",
            "winning notification", "you have won",
            "reset password", "account suspended", "unusual activity",
            "minimum deposit", "withdrawal fee",
        ]

        # Rate limiting - track message times per user
        self._message_times: Dict[int, List[float]] = {}
        self.rate_limit_window = 60  # seconds
        self.rate_limit_max = 10  # max messages per window
    
    def _init_db(self):
        """Initialize the SQLite database."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # User profiles
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_seen TEXT,
                    message_count INTEGER DEFAULT 0,
                    warning_count INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    is_trusted INTEGER DEFAULT 0,
                    spam_score REAL DEFAULT 0.0,
                    last_message_at TEXT,
                    notes TEXT
                )
            """)
            
            # Message history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    user_id INTEGER,
                    username TEXT,
                    text TEXT,
                    timestamp TEXT,
                    chat_id INTEGER,
                    was_deleted INTEGER DEFAULT 0,
                    deletion_reason TEXT
                )
            """)
            
            # Moderation actions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mod_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT,
                    user_id INTEGER,
                    message_id INTEGER,
                    reason TEXT,
                    timestamp TEXT,
                    reversed INTEGER DEFAULT 0
                )
            """)
            
            # Self-upgrade ideas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS upgrade_ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idea TEXT,
                    source_user_id INTEGER,
                    source_message TEXT,
                    detected_at TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 0
                )
            """)
            
            conn.commit()
            conn.close()
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin."""
        return user_id in self.admin_ids
    
    def get_random_response(self, category: str, **kwargs) -> str:
        """Get a random response from a category, formatted with kwargs."""
        import random
        responses = JARVIS_VOICE.get(category, ["..."])
        response = random.choice(responses)
        if kwargs:
            response = response.format(**kwargs)
        return response
    
    # =========================================================================
    # User Management
    # =========================================================================
    
    def get_user(self, user_id: int) -> Optional[UserProfile]:
        """Get user profile."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return UserProfile(
                    user_id=row[0], username=row[1], first_seen=row[2],
                    message_count=row[3], warning_count=row[4],
                    is_banned=bool(row[5]), is_trusted=bool(row[6]),
                    spam_score=row[7], last_message_at=row[8], notes=row[9] or ""
                )
            return None
    
    def update_user(self, user_id: int, username: str, increment_messages: bool = True):
        """Update or create user profile."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc).isoformat()
            
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            exists = cursor.fetchone()
            
            if exists:
                if increment_messages:
                    cursor.execute("""
                        UPDATE users SET username = ?, message_count = message_count + 1, 
                        last_message_at = ? WHERE user_id = ?
                    """, (username, now, user_id))
                else:
                    cursor.execute("""
                        UPDATE users SET username = ?, last_message_at = ? WHERE user_id = ?
                    """, (username, now, user_id))
            else:
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_seen, message_count, last_message_at)
                    VALUES (?, ?, ?, 1, ?)
                """, (user_id, username, now, now))
            
            conn.commit()
            conn.close()
    
    def warn_user(self, user_id: int) -> int:
        """Warn a user, returns new warning count."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET warning_count = warning_count + 1 WHERE user_id = ?
            """, (user_id,))
            cursor.execute("SELECT warning_count FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.commit()
            conn.close()
            return row[0] if row else 1
    
    def ban_user(self, user_id: int, reason: str):
        """Ban a user."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
            cursor.execute("""
                INSERT INTO mod_actions (action_type, user_id, reason, timestamp)
                VALUES ('ban', ?, ?, ?)
            """, (user_id, reason, datetime.now(timezone.utc).isoformat()))
            conn.commit()
            conn.close()

    def mute_user(self, user_id: int, reason: str, duration_hours: int = 24):
        """Mute a user for a duration (tracked in mod_actions)."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            unmute_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
            cursor.execute("""
                INSERT INTO mod_actions (action_type, user_id, reason, timestamp, reversed)
                VALUES ('mute', ?, ?, ?, 0)
            """, (user_id, f"{reason}|unmute_at:{unmute_at.isoformat()}",
                  datetime.now(timezone.utc).isoformat()))
            conn.commit()
            conn.close()

    def is_rate_limited(self, user_id: int) -> Tuple[bool, int]:
        """
        Check if user is sending messages too fast.
        Returns: (is_limited, message_count_in_window)
        """
        now = time.time()
        if user_id not in self._message_times:
            self._message_times[user_id] = []

        # Clean old timestamps
        self._message_times[user_id] = [
            t for t in self._message_times[user_id]
            if now - t < self.rate_limit_window
        ]

        # Add current timestamp
        self._message_times[user_id].append(now)

        count = len(self._message_times[user_id])
        return count > self.rate_limit_max, count

    def trust_user(self, user_id: int):
        """Mark a user as trusted (reduced spam sensitivity)."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_trusted = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()

    def clear_warnings(self, user_id: int):
        """Clear warnings for a user."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET warning_count = 0 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
    
    # =========================================================================
    # Message Analysis
    # =========================================================================
    
    def record_message(self, message_id: int, user_id: int, username: str, 
                       text: str, chat_id: int):
        """Record a message for analysis."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (message_id, user_id, username, text, timestamp, chat_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (message_id, user_id, username, text, 
                  datetime.now(timezone.utc).isoformat(), chat_id))
            conn.commit()
            conn.close()
    
    def get_user_recent_messages(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get recent messages from a user."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT text, timestamp FROM messages 
                WHERE user_id = ? ORDER BY id DESC LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            conn.close()
            return [{"text": r[0], "timestamp": r[1]} for r in rows]
    
    def analyze_spam(self, text: str, user_id: int) -> Tuple[bool, float, str]:
        """
        Analyze if a message is spam.
        Returns: (is_spam, confidence, reason)
        """
        text_lower = text.lower()
        confidence = 0.0
        reasons = []

        # Check rate limiting first
        is_rate_limited, msg_count = self.is_rate_limited(user_id)
        if is_rate_limited:
            confidence += 0.5
            reasons.append(f"rate_limited: {msg_count} msgs in {self.rate_limit_window}s")

        # Check regex patterns
        for pattern in self.spam_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                confidence += 0.3
                reasons.append(f"pattern: {pattern[:20]}")

        # Check scam keywords
        for keyword in self.scam_keywords:
            if keyword in text_lower:
                confidence += 0.4
                reasons.append(f"keyword: {keyword}")

        # Check for excessive links
        link_count = len(re.findall(r'https?://|t\.me/|telegram\.me/', text_lower))
        if link_count >= 2:
            confidence += 0.3
            reasons.append(f"multiple links: {link_count}")

        # Check for all caps (shouting)
        if len(text) > 20 and text.isupper():
            confidence += 0.2
            reasons.append("all caps")

        # Check for excessive emojis/special chars
        special_ratio = sum(1 for c in text if ord(c) > 127) / max(len(text), 1)
        if special_ratio > 0.3:
            confidence += 0.15
            reasons.append(f"excessive special chars: {special_ratio:.0%}")

        # Check user history
        user = self.get_user(user_id)
        if user:
            # New users are more suspicious
            if user.message_count < 3:
                confidence += 0.1
                reasons.append("new user")

            # Previous warnings increase suspicion
            if user.warning_count > 0:
                confidence += 0.2 * user.warning_count
                reasons.append(f"prior warnings: {user.warning_count}")

            # Trusted users get benefit of doubt
            if user.is_trusted:
                confidence *= 0.3
                reasons.append("trusted user - reduced")

            # Admin immunity
            if self.is_admin(user_id):
                confidence = 0.0
                reasons = ["admin - immune"]

        # Cap at 1.0
        confidence = min(confidence, 1.0)

        is_spam = confidence >= 0.5
        reason = ", ".join(reasons) if reasons else "clean"

        return is_spam, confidence, reason
    
    def detect_command_attempt(self, text: str, user_id: int) -> Tuple[bool, str]:
        """
        Detect if a non-admin is trying to give commands.
        Returns: (is_command_attempt, command_type)
        """
        if self.is_admin(user_id):
            return False, ""
        
        text_lower = text.lower()
        
        # Command patterns
        command_patterns = [
            (r"jarvis[,\s]+(do|make|create|add|fix|change|update|delete|ban|remove)", "direct_command"),
            (r"(set|configure|enable|disable)\s+(the\s+)?\w+", "config_command"),
            (r"(you\s+should|you\s+need\s+to|please\s+make)", "instruction"),
            (r"(remember|forget|ignore)\s+(that|this|when)", "memory_command"),
        ]
        
        for pattern, cmd_type in command_patterns:
            if re.search(pattern, text_lower):
                return True, cmd_type
        
        return False, ""
    
    def detect_upgrade_opportunity(self, text: str, user_id: int) -> Optional[str]:
        """
        Detect if a message reveals an upgrade opportunity.
        Returns the upgrade idea if detected.
        """
        text_lower = text.lower()
        
        # Only process if from admin or looks like genuine feedback
        if not self.is_admin(user_id):
            # Check for organic feature requests/bug reports
            feedback_patterns = [
                r"(would\s+be\s+nice|wish\s+jarvis|would\s+be\s+cool)\s+if",
                r"(bug|broken|doesn't\s+work|not\s+working)",
                r"(feature\s+request|suggestion|idea)",
                r"(can\s+jarvis|does\s+jarvis|will\s+jarvis)",
            ]
            
            for pattern in feedback_patterns:
                if re.search(pattern, text_lower):
                    return text[:500]  # Capture the feedback
        else:
            # Admin messages are always worth checking
            if any(kw in text_lower for kw in ["add", "fix", "improve", "change", "need", "should"]):
                return text[:500]
        
        return None
    
    def queue_upgrade(self, idea: str, user_id: int, source_message: str):
        """Queue an upgrade idea for console processing."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO upgrade_ideas (idea, source_user_id, source_message, detected_at)
                VALUES (?, ?, ?, ?)
            """, (idea, user_id, source_message, datetime.now(timezone.utc).isoformat()))
            conn.commit()
            conn.close()
        
        # Also write to JSON for console pickup
        try:
            queue = []
            if UPGRADE_QUEUE.exists():
                queue = json.loads(UPGRADE_QUEUE.read_text())
            
            queue.append({
                "idea": idea,
                "user_id": user_id,
                "source": source_message[:200],
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending"
            })
            
            UPGRADE_QUEUE.write_text(json.dumps(queue, indent=2))
        except:
            pass
    
    # =========================================================================
    # Context Analysis
    # =========================================================================
    
    def get_chat_context(self, chat_id: int, limit: int = 20) -> List[Dict]:
        """Get recent chat context."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT username, text, timestamp FROM messages 
                WHERE chat_id = ? ORDER BY id DESC LIMIT ?
            """, (chat_id, limit))
            rows = cursor.fetchall()
            conn.close()
            return [{"username": r[0], "text": r[1], "timestamp": r[2]} for r in reversed(rows)]
    
    def get_moderation_stats(self) -> Dict:
        """Get moderation statistics."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Total users
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Banned users
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
            banned_users = cursor.fetchone()[0]
            
            # Total messages
            cursor.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]
            
            # Deleted messages
            cursor.execute("SELECT COUNT(*) FROM messages WHERE was_deleted = 1")
            deleted_messages = cursor.fetchone()[0]
            
            # Pending upgrades
            cursor.execute("SELECT COUNT(*) FROM upgrade_ideas WHERE status = 'pending'")
            pending_upgrades = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "total_users": total_users,
                "banned_users": banned_users,
                "total_messages": total_messages,
                "deleted_messages": deleted_messages,
                "pending_upgrades": pending_upgrades,
            }


# Singleton
_jarvis_admin: Optional[JarvisAdmin] = None

def get_jarvis_admin() -> JarvisAdmin:
    """Get the singleton JarvisAdmin instance."""
    global _jarvis_admin
    if _jarvis_admin is None:
        _jarvis_admin = JarvisAdmin()
    return _jarvis_admin
