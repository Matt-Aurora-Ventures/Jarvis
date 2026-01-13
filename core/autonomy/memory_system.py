"""
Memory System
Remember users, conversations, and context over time
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "memory"
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class UserMemory:
    """Memory about a specific user"""
    user_id: str
    username: str
    first_seen: str
    last_seen: str
    interaction_count: int = 0
    sentiment_toward_us: str = "neutral"  # positive, neutral, negative
    topics_discussed: List[str] = field(default_factory=list)
    favorite_tokens: List[str] = field(default_factory=list)
    is_influencer: bool = False
    follower_count: int = 0
    engagement_quality: str = "normal"  # high, normal, low, spam
    notes: List[str] = field(default_factory=list)
    last_interaction_summary: str = ""


@dataclass
class ConversationMemory:
    """Memory of a conversation thread"""
    thread_id: str
    user_id: str
    started_at: str
    last_message_at: str
    topic: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    resolved: bool = False
    sentiment: str = "neutral"


class MemorySystem:
    """
    Long-term memory for Jarvis.
    Remembers users, conversations, and learns preferences.
    """
    
    def __init__(self):
        self.users_file = DATA_DIR / "users.json"
        self.conversations_file = DATA_DIR / "conversations.json"
        self.context_file = DATA_DIR / "context.json"
        
        self.users: Dict[str, UserMemory] = {}
        self.conversations: Dict[str, ConversationMemory] = {}
        self.context: Dict[str, Any] = {}
        
        self._load_data()
    
    def _load_data(self):
        """Load memory from disk"""
        try:
            if self.users_file.exists():
                data = json.loads(self.users_file.read_text())
                self.users = {k: UserMemory(**v) for k, v in data.items()}
            
            if self.conversations_file.exists():
                data = json.loads(self.conversations_file.read_text())
                self.conversations = {k: ConversationMemory(**v) for k, v in data.items()}
            
            if self.context_file.exists():
                self.context = json.loads(self.context_file.read_text())
                
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
    
    def _save_data(self):
        """Save memory to disk"""
        try:
            self.users_file.write_text(json.dumps(
                {k: asdict(v) for k, v in self.users.items()},
                indent=2
            ))
            self.conversations_file.write_text(json.dumps(
                {k: asdict(v) for k, v in list(self.conversations.items())[-500:]},
                indent=2
            ))
            self.context_file.write_text(json.dumps(self.context, indent=2))
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
    def remember_user(
        self,
        user_id: str,
        username: str,
        follower_count: int = 0,
        is_influencer: bool = False
    ) -> UserMemory:
        """Remember or update a user"""
        now = datetime.utcnow().isoformat()
        
        if user_id in self.users:
            user = self.users[user_id]
            user.last_seen = now
            user.interaction_count += 1
            user.username = username  # Update in case changed
            if follower_count > 0:
                user.follower_count = follower_count
            if is_influencer:
                user.is_influencer = True
        else:
            user = UserMemory(
                user_id=user_id,
                username=username,
                first_seen=now,
                last_seen=now,
                interaction_count=1,
                follower_count=follower_count,
                is_influencer=is_influencer
            )
            self.users[user_id] = user
        
        self._save_data()
        return user
    
    def get_user(self, user_id: str) -> Optional[UserMemory]:
        """Get user memory"""
        return self.users.get(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[UserMemory]:
        """Get user by username"""
        username_lower = username.lower().lstrip("@")
        for user in self.users.values():
            if user.username.lower() == username_lower:
                return user
        return None
    
    def update_user_sentiment(self, user_id: str, sentiment: str):
        """Update how a user feels about us"""
        if user_id in self.users:
            self.users[user_id].sentiment_toward_us = sentiment
            self._save_data()
    
    def add_user_topic(self, user_id: str, topic: str):
        """Add a topic this user discusses"""
        if user_id in self.users:
            if topic not in self.users[user_id].topics_discussed:
                self.users[user_id].topics_discussed.append(topic)
                self._save_data()
    
    def add_user_note(self, user_id: str, note: str):
        """Add a note about a user"""
        if user_id in self.users:
            self.users[user_id].notes.append(f"{datetime.utcnow().isoformat()}: {note}")
            self.users[user_id].notes = self.users[user_id].notes[-10:]  # Keep last 10
            self._save_data()
    
    def mark_user_quality(self, user_id: str, quality: str):
        """Mark user engagement quality (high, normal, low, spam)"""
        if user_id in self.users:
            self.users[user_id].engagement_quality = quality
            self._save_data()
    
    def remember_conversation(
        self,
        thread_id: str,
        user_id: str,
        topic: str,
        message: str,
        is_from_user: bool = True
    ) -> ConversationMemory:
        """Remember a conversation"""
        now = datetime.utcnow().isoformat()
        
        if thread_id in self.conversations:
            conv = self.conversations[thread_id]
            conv.last_message_at = now
            conv.messages.append({
                "from": "user" if is_from_user else "jarvis",
                "content": message,
                "at": now
            })
        else:
            conv = ConversationMemory(
                thread_id=thread_id,
                user_id=user_id,
                started_at=now,
                last_message_at=now,
                topic=topic,
                messages=[{
                    "from": "user" if is_from_user else "jarvis",
                    "content": message,
                    "at": now
                }]
            )
            self.conversations[thread_id] = conv
        
        self._save_data()
        return conv
    
    def get_conversation_context(self, thread_id: str) -> Optional[str]:
        """Get context for a conversation thread"""
        if thread_id not in self.conversations:
            return None
        
        conv = self.conversations[thread_id]
        context_parts = [f"Topic: {conv.topic}"]
        
        # Get last 5 messages for context
        for msg in conv.messages[-5:]:
            sender = "User" if msg["from"] == "user" else "Jarvis"
            context_parts.append(f"{sender}: {msg['content']}")
        
        return "\n".join(context_parts)
    
    def get_user_context(self, user_id: str) -> Optional[str]:
        """Get context about a user for reply generation"""
        user = self.users.get(user_id)
        if not user:
            return None
        
        parts = []
        if user.interaction_count > 1:
            parts.append(f"Returning user ({user.interaction_count} interactions)")
        if user.is_influencer:
            parts.append(f"Influencer ({user.follower_count} followers)")
        if user.sentiment_toward_us != "neutral":
            parts.append(f"Generally {user.sentiment_toward_us} toward us")
        if user.topics_discussed:
            parts.append(f"Previously discussed: {', '.join(user.topics_discussed[:3])}")
        if user.notes:
            parts.append(f"Note: {user.notes[-1]}")
        
        return " | ".join(parts) if parts else None
    
    def set_context(self, key: str, value: Any):
        """Set a context value"""
        self.context[key] = value
        self._save_data()
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a context value"""
        return self.context.get(key, default)
    
    def get_frequent_users(self, min_interactions: int = 3) -> List[UserMemory]:
        """Get users who interact frequently"""
        return [u for u in self.users.values() if u.interaction_count >= min_interactions]
    
    def get_influencers(self) -> List[UserMemory]:
        """Get influencer users"""
        return [u for u in self.users.values() if u.is_influencer]
    
    def cleanup_old_conversations(self, days: int = 7):
        """Remove old conversations"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        to_remove = []
        
        for thread_id, conv in self.conversations.items():
            try:
                last_msg = datetime.fromisoformat(conv.last_message_at)
                if last_msg < cutoff:
                    to_remove.append(thread_id)
            except Exception:
                pass
        
        for thread_id in to_remove:
            del self.conversations[thread_id]
        
        if to_remove:
            self._save_data()
            logger.info(f"Cleaned up {len(to_remove)} old conversations")


# Singleton
_memory_system: Optional[MemorySystem] = None

def get_memory_system() -> MemorySystem:
    global _memory_system
    if _memory_system is None:
        _memory_system = MemorySystem()
    return _memory_system
