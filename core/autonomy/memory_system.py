"""
Memory System
Remember users, conversations, and context over time.

Enhanced with video game AI-inspired features:
- Richer world model (time awareness, user context)
- Emotional memory (sentiment tagging on entries)
- Quest/goal management (long-term objectives)
- Adaptive learning (complexity preferences)
- Memory pruning (importance tagging, archival)
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "memory"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class MemoryImportance(str, Enum):
    """Importance level for memory entries (for pruning)"""
    CORE = "core"          # Never prune - fundamental facts
    IMPORTANT = "important" # Keep long-term
    NORMAL = "normal"       # Standard retention
    TEMPORARY = "temporary" # Archive after completion
    ARCHIVED = "archived"   # Historical only


class GoalStatus(str, Enum):
    """Status for user goals/quests"""
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    PAUSED = "paused"


@dataclass
class EmotionalContext:
    """Emotional metadata for memory entries"""
    sentiment: str = "neutral"  # positive, neutral, negative, frustrated, excited
    intensity: float = 0.5      # 0.0-1.0
    trigger: str = ""           # What caused this emotion
    timestamp: str = ""


@dataclass
class UserGoal:
    """A user's long-term goal (quest)"""
    goal_id: str
    title: str
    description: str
    status: str = GoalStatus.ACTIVE
    created_at: str = ""
    updated_at: str = ""
    target_date: Optional[str] = None
    progress_notes: List[str] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    priority: int = 1  # 1=highest, 5=lowest


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
    
    # === NEW: Video Game AI-Inspired Fields ===
    
    # Emotional memory - track emotional patterns over time
    emotional_history: List[Dict[str, Any]] = field(default_factory=list)
    current_emotional_state: str = "neutral"
    
    # Adaptive learning - communication preferences
    preferred_complexity: str = "normal"  # simple, normal, detailed, technical
    response_length_pref: str = "normal"  # brief, normal, detailed
    successful_approaches: List[str] = field(default_factory=list)
    unsuccessful_approaches: List[str] = field(default_factory=list)
    
    # Goals/quests
    active_goals: List[Dict[str, Any]] = field(default_factory=list)
    completed_goals: List[Dict[str, Any]] = field(default_factory=list)
    
    # World model - broader context
    timezone: Optional[str] = None
    typical_active_hours: List[int] = field(default_factory=list)
    known_context: Dict[str, Any] = field(default_factory=dict)  # job, interests, etc.
    
    # Memory importance
    importance: str = MemoryImportance.NORMAL


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

    # =========================================================================
    # VIDEO GAME AI-INSPIRED ENHANCEMENTS
    # =========================================================================

    # --- Emotional Memory ---
    
    def record_emotional_event(
        self,
        user_id: str,
        sentiment: str,
        intensity: float = 0.5,
        trigger: str = ""
    ):
        """Record an emotional event for a user (like an NPC remembering how you treated them)"""
        if user_id not in self.users:
            return
        
        user = self.users[user_id]
        event = {
            "sentiment": sentiment,
            "intensity": min(1.0, max(0.0, intensity)),
            "trigger": trigger,
            "timestamp": datetime.utcnow().isoformat()
        }
        user.emotional_history.append(event)
        user.emotional_history = user.emotional_history[-20:]  # Keep last 20
        user.current_emotional_state = sentiment
        self._save_data()
        logger.debug(f"Recorded emotional event for {user_id}: {sentiment}")

    def get_emotional_trend(self, user_id: str) -> Dict[str, Any]:
        """Get emotional trend analysis for a user"""
        user = self.users.get(user_id)
        if not user or not user.emotional_history:
            return {"trend": "neutral", "recent": [], "dominant": "neutral"}
        
        recent = user.emotional_history[-5:]
        sentiment_counts = {}
        for event in user.emotional_history:
            s = event.get("sentiment", "neutral")
            sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
        
        dominant = max(sentiment_counts, key=sentiment_counts.get) if sentiment_counts else "neutral"
        
        return {
            "trend": user.current_emotional_state,
            "recent": recent,
            "dominant": dominant,
            "history_length": len(user.emotional_history)
        }

    # --- Goal/Quest Management ---
    
    def add_user_goal(
        self,
        user_id: str,
        title: str,
        description: str = "",
        target_date: Optional[str] = None,
        priority: int = 1
    ) -> Optional[str]:
        """Add a goal (quest) for a user - like an RPG quest log"""
        if user_id not in self.users:
            return None
        
        user = self.users[user_id]
        goal_id = f"goal_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(user.active_goals)}"
        now = datetime.utcnow().isoformat()
        
        goal = {
            "goal_id": goal_id,
            "title": title,
            "description": description,
            "status": GoalStatus.ACTIVE,
            "created_at": now,
            "updated_at": now,
            "target_date": target_date,
            "progress_notes": [],
            "milestones": [],
            "priority": priority
        }
        user.active_goals.append(goal)
        self._save_data()
        logger.info(f"Added goal '{title}' for user {user_id}")
        return goal_id

    def update_goal_progress(
        self,
        user_id: str,
        goal_id: str,
        note: str,
        new_status: Optional[str] = None
    ):
        """Update progress on a user's goal"""
        if user_id not in self.users:
            return
        
        user = self.users[user_id]
        for goal in user.active_goals:
            if goal.get("goal_id") == goal_id:
                goal["progress_notes"].append({
                    "note": note,
                    "timestamp": datetime.utcnow().isoformat()
                })
                goal["updated_at"] = datetime.utcnow().isoformat()
                if new_status:
                    goal["status"] = new_status
                    if new_status == GoalStatus.COMPLETED:
                        user.active_goals.remove(goal)
                        user.completed_goals.append(goal)
                        logger.info(f"Goal '{goal['title']}' completed for user {user_id}")
                self._save_data()
                return
    
    def get_active_goals(self, user_id: str) -> List[Dict[str, Any]]:
        """Get a user's active goals (quest log)"""
        user = self.users.get(user_id)
        if not user:
            return []
        return sorted(user.active_goals, key=lambda g: g.get("priority", 5))

    def get_goal_reminder_text(self, user_id: str) -> Optional[str]:
        """Generate a reminder about pending goals (like an NPC reminding about quests)"""
        goals = self.get_active_goals(user_id)
        if not goals:
            return None
        
        high_priority = [g for g in goals if g.get("priority", 5) <= 2]
        if not high_priority:
            return None
        
        reminders = []
        for goal in high_priority[:3]:
            title = goal.get("title", "Unknown")
            target = goal.get("target_date")
            if target:
                reminders.append(f"• {title} (target: {target})")
            else:
                reminders.append(f"• {title}")
        
        return "Active goals:\n" + "\n".join(reminders)

    # --- Adaptive Learning ---
    
    def record_approach_outcome(
        self,
        user_id: str,
        approach: str,
        successful: bool
    ):
        """Record whether an approach worked (like a game AI learning what tactics work)"""
        if user_id not in self.users:
            return
        
        user = self.users[user_id]
        if successful:
            if approach not in user.successful_approaches:
                user.successful_approaches.append(approach)
                user.successful_approaches = user.successful_approaches[-10:]
            # Remove from unsuccessful if it was there
            if approach in user.unsuccessful_approaches:
                user.unsuccessful_approaches.remove(approach)
        else:
            if approach not in user.unsuccessful_approaches:
                user.unsuccessful_approaches.append(approach)
                user.unsuccessful_approaches = user.unsuccessful_approaches[-10:]
        
        self._save_data()

    def set_user_complexity_preference(self, user_id: str, complexity: str):
        """Set user's preferred communication complexity (adaptive difficulty)"""
        if user_id in self.users:
            self.users[user_id].preferred_complexity = complexity
            self._save_data()

    def get_communication_style(self, user_id: str) -> Dict[str, str]:
        """Get recommended communication style for a user"""
        user = self.users.get(user_id)
        if not user:
            return {"complexity": "normal", "length": "normal", "avoid": []}
        
        return {
            "complexity": user.preferred_complexity,
            "length": user.response_length_pref,
            "avoid": user.unsuccessful_approaches[:3],
            "prefer": user.successful_approaches[:3]
        }

    # --- World Model ---
    
    def update_user_context(self, user_id: str, key: str, value: Any):
        """Update broader context about a user (job, interests, timezone, etc.)"""
        if user_id not in self.users:
            return
        
        user = self.users[user_id]
        user.known_context[key] = value
        self._save_data()

    def get_time_aware_greeting(self, user_id: str) -> str:
        """Get a time-aware greeting based on user's timezone"""
        user = self.users.get(user_id)
        now = datetime.utcnow()
        
        # If we know their timezone, adjust
        hour = now.hour
        if user and user.timezone:
            # Simple timezone offset handling (could be enhanced)
            try:
                offset = int(user.timezone.replace("UTC", "").replace("+", ""))
                hour = (now.hour + offset) % 24
            except (ValueError, AttributeError):
                pass
        
        if 5 <= hour < 12:
            return "Good morning"
        elif 12 <= hour < 17:
            return "Good afternoon"
        elif 17 <= hour < 21:
            return "Good evening"
        else:
            return "Hey"

    def record_active_hour(self, user_id: str):
        """Record when a user is active (to learn patterns)"""
        if user_id not in self.users:
            return
        
        hour = datetime.utcnow().hour
        user = self.users[user_id]
        if hour not in user.typical_active_hours:
            user.typical_active_hours.append(hour)
            user.typical_active_hours = sorted(set(user.typical_active_hours))[-10:]
        self._save_data()

    # --- Memory Pruning ---
    
    def set_memory_importance(self, user_id: str, importance: str):
        """Set importance level for a user's memory (affects pruning)"""
        if user_id in self.users:
            self.users[user_id].importance = importance
            self._save_data()

    def prune_low_importance_memories(self, days_threshold: int = 30):
        """Archive or remove low-importance memories older than threshold"""
        cutoff = datetime.utcnow() - timedelta(days=days_threshold)
        archived_count = 0
        
        for user_id, user in list(self.users.items()):
            if user.importance in [MemoryImportance.TEMPORARY, MemoryImportance.ARCHIVED]:
                try:
                    last_seen = datetime.fromisoformat(user.last_seen)
                    if last_seen < cutoff:
                        user.importance = MemoryImportance.ARCHIVED
                        archived_count += 1
                except Exception:
                    pass
        
        if archived_count > 0:
            self._save_data()
            logger.info(f"Archived {archived_count} low-importance user memories")

    def get_enhanced_user_context(self, user_id: str) -> Optional[str]:
        """Get comprehensive context for reply generation (enhanced version)"""
        user = self.users.get(user_id)
        if not user:
            return None
        
        parts = []
        
        # Basic info
        if user.interaction_count > 1:
            parts.append(f"Returning user ({user.interaction_count} interactions)")
        if user.is_influencer:
            parts.append(f"Influencer ({user.follower_count} followers)")
        
        # Emotional context
        if user.current_emotional_state != "neutral":
            parts.append(f"Currently {user.current_emotional_state}")
        
        # Communication preferences
        if user.preferred_complexity != "normal":
            parts.append(f"Prefers {user.preferred_complexity} explanations")
        
        # Active goals
        active = self.get_active_goals(user_id)
        if active:
            top_goal = active[0].get("title", "")
            parts.append(f"Working on: {top_goal}")
        
        # Topics and sentiment
        if user.sentiment_toward_us != "neutral":
            parts.append(f"Generally {user.sentiment_toward_us} toward us")
        if user.topics_discussed:
            parts.append(f"Interests: {', '.join(user.topics_discussed[:3])}")
        
        # Known context
        if user.known_context:
            for key, val in list(user.known_context.items())[:2]:
                parts.append(f"{key}: {val}")
        
        return " | ".join(parts) if parts else None


# Singleton
_memory_system: Optional[MemorySystem] = None

def get_memory_system() -> MemorySystem:
    global _memory_system
    if _memory_system is None:
        _memory_system = MemorySystem()
    return _memory_system
