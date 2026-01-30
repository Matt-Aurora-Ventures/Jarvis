"""
Enhanced Memory System - Video Game AI-inspired memory for Jarvis.

Implements 5 enhancements from game AI research:
1. Richer World Model — time awareness, user context, environmental state
2. Emotional Memory — sentiment tagging, emotional context
3. Quest/Goal Management — long-term objective tracking like quests
4. Adaptive Learning — complexity adjustment based on user feedback
5. Memory Pruning — archive old memories, importance tagging

Reference: https://www.youtube.com/watch?v=rl_T1V1y3zE (Game AI memory systems)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import logging
import asyncio

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. RICHER WORLD MODEL - Time awareness and environmental context
# ═══════════════════════════════════════════════════════════════════════════════

class TimeOfDay(Enum):
    """Time periods for contextual awareness."""
    NIGHT = "night"           # 00:00 - 06:00
    MORNING = "morning"       # 06:00 - 12:00
    AFTERNOON = "afternoon"   # 12:00 - 18:00
    EVENING = "evening"       # 18:00 - 24:00


class MarketPhase(Enum):
    """Crypto market phases for trading context."""
    ACCUMULATION = "accumulation"   # Low volatility, sideways
    MARKUP = "markup"               # Trending up
    DISTRIBUTION = "distribution"   # High volatility top
    MARKDOWN = "markdown"           # Trending down
    UNKNOWN = "unknown"


@dataclass
class WorldState:
    """
    Current world/environmental state for context-aware responses.
    
    Like a game's world state that NPCs reference.
    """
    # Time context
    current_time: datetime = field(default_factory=datetime.utcnow)
    time_of_day: TimeOfDay = TimeOfDay.MORNING
    day_of_week: int = 0  # 0=Monday
    is_weekend: bool = False
    
    # Market context
    market_phase: MarketPhase = MarketPhase.UNKNOWN
    market_sentiment: float = 0.5  # 0=fear, 1=greed
    sol_price: Optional[float] = None
    btc_price: Optional[float] = None
    
    # Session context
    session_start: datetime = field(default_factory=datetime.utcnow)
    messages_in_session: int = 0
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    # User activity patterns
    user_timezone_offset: int = 0  # Hours from UTC
    typical_active_hours: List[int] = field(default_factory=lambda: list(range(9, 22)))
    
    def update_time(self) -> None:
        """Update time-based fields."""
        self.current_time = datetime.utcnow()
        hour = self.current_time.hour
        
        if 0 <= hour < 6:
            self.time_of_day = TimeOfDay.NIGHT
        elif 6 <= hour < 12:
            self.time_of_day = TimeOfDay.MORNING
        elif 12 <= hour < 18:
            self.time_of_day = TimeOfDay.AFTERNOON
        else:
            self.time_of_day = TimeOfDay.EVENING
            
        self.day_of_week = self.current_time.weekday()
        self.is_weekend = self.day_of_week >= 5
        
    def get_greeting_context(self) -> str:
        """Get appropriate greeting based on time/context."""
        self.update_time()
        
        greetings = {
            TimeOfDay.NIGHT: "burning the midnight oil",
            TimeOfDay.MORNING: "starting the day",
            TimeOfDay.AFTERNOON: "in the afternoon grind",
            TimeOfDay.EVENING: "winding down",
        }
        
        base = greetings.get(self.time_of_day, "")
        
        if self.is_weekend:
            base += " on the weekend"
            
        return base
    
    def to_context_string(self) -> str:
        """Convert to context string for prompts."""
        self.update_time()
        
        parts = [
            f"Time: {self.current_time.strftime('%Y-%m-%d %H:%M UTC')} ({self.time_of_day.value})",
            f"Day: {'Weekend' if self.is_weekend else 'Weekday'}",
        ]
        
        if self.market_sentiment != 0.5:
            sentiment = "fearful" if self.market_sentiment < 0.4 else "greedy" if self.market_sentiment > 0.6 else "neutral"
            parts.append(f"Market sentiment: {sentiment} ({self.market_sentiment:.2f})")
            
        if self.sol_price:
            parts.append(f"SOL: ${self.sol_price:.2f}")
            
        if self.messages_in_session > 0:
            parts.append(f"Session messages: {self.messages_in_session}")
            
        return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. EMOTIONAL MEMORY - Sentiment tagging and emotional context
# ═══════════════════════════════════════════════════════════════════════════════

class Emotion(Enum):
    """Basic emotions for memory tagging."""
    NEUTRAL = "neutral"
    EXCITED = "excited"       # Good trade, discovery
    FRUSTRATED = "frustrated" # Losses, errors
    CURIOUS = "curious"       # Questions, exploration
    CONFIDENT = "confident"   # Successful predictions
    ANXIOUS = "anxious"       # Risk, uncertainty
    GRATEFUL = "grateful"     # Thanks, appreciation


@dataclass
class EmotionalContext:
    """
    Emotional context for a memory or interaction.
    
    Games use this to make NPCs respond appropriately to player mood.
    """
    primary_emotion: Emotion = Emotion.NEUTRAL
    intensity: float = 0.5  # 0.0 to 1.0
    sentiment_score: float = 0.5  # 0=negative, 1=positive
    
    # Emotional triggers detected
    triggers: List[str] = field(default_factory=list)
    
    # Response tone adjustment
    suggested_tone: str = "professional"
    
    def analyze_text(self, text: str) -> None:
        """
        Analyze text for emotional content.
        
        Simple keyword-based detection (can be enhanced with ML).
        """
        text_lower = text.lower()
        
        # Emotion detection patterns
        emotion_patterns = {
            Emotion.EXCITED: ["moon", "pump", "lfg", "let's go", "amazing", "incredible", "huge"],
            Emotion.FRUSTRATED: ["rug", "loss", "scam", "damn", "fuck", "lost", "down bad"],
            Emotion.CURIOUS: ["what", "how", "why", "?", "wondering", "curious", "explain"],
            Emotion.CONFIDENT: ["sure", "definitely", "certain", "know", "obvious", "clearly"],
            Emotion.ANXIOUS: ["worried", "nervous", "risk", "afraid", "scared", "uncertain"],
            Emotion.GRATEFUL: ["thanks", "thank you", "appreciate", "grateful", "helpful"],
        }
        
        # Count emotion indicators
        emotion_scores: Dict[Emotion, int] = {}
        for emotion, patterns in emotion_patterns.items():
            score = sum(1 for p in patterns if p in text_lower)
            if score > 0:
                emotion_scores[emotion] = score
                self.triggers.extend([p for p in patterns if p in text_lower])
                
        # Set primary emotion
        if emotion_scores:
            self.primary_emotion = max(emotion_scores, key=emotion_scores.get)
            self.intensity = min(1.0, emotion_scores[self.primary_emotion] / 3)
        else:
            self.primary_emotion = Emotion.NEUTRAL
            self.intensity = 0.3
            
        # Calculate sentiment
        positive_words = ["good", "great", "nice", "love", "profit", "gain", "win", "up"]
        negative_words = ["bad", "terrible", "hate", "loss", "fail", "down", "rug", "scam"]
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        if pos_count + neg_count > 0:
            self.sentiment_score = pos_count / (pos_count + neg_count)
        else:
            self.sentiment_score = 0.5
            
        # Suggest tone based on emotion
        tone_map = {
            Emotion.EXCITED: "enthusiastic",
            Emotion.FRUSTRATED: "empathetic",
            Emotion.CURIOUS: "educational",
            Emotion.CONFIDENT: "affirmative",
            Emotion.ANXIOUS: "reassuring",
            Emotion.GRATEFUL: "warm",
            Emotion.NEUTRAL: "professional",
        }
        self.suggested_tone = tone_map.get(self.primary_emotion, "professional")
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "primary_emotion": self.primary_emotion.value,
            "intensity": self.intensity,
            "sentiment_score": self.sentiment_score,
            "triggers": self.triggers,
            "suggested_tone": self.suggested_tone,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. QUEST/GOAL MANAGEMENT - Long-term objective tracking
# ═══════════════════════════════════════════════════════════════════════════════

class QuestStatus(Enum):
    """Status of a quest/goal."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"
    ON_HOLD = "on_hold"


class QuestPriority(Enum):
    """Priority levels for quests."""
    CRITICAL = 1    # Must do immediately
    HIGH = 2        # Important, do soon
    MEDIUM = 3      # Normal priority
    LOW = 4         # Nice to have
    SOMEDAY = 5     # Eventually


@dataclass
class QuestMilestone:
    """A milestone/checkpoint within a quest."""
    id: str
    description: str
    completed: bool = False
    completed_at: Optional[datetime] = None
    evidence: Optional[str] = None  # Proof of completion


@dataclass
class Quest:
    """
    A long-term goal or objective, like a quest in a game.
    
    Users can set trading goals, learning objectives, etc.
    """
    id: str
    user_id: str
    title: str
    description: str
    
    # Status tracking
    status: QuestStatus = QuestStatus.ACTIVE
    priority: QuestPriority = QuestPriority.MEDIUM
    progress: float = 0.0  # 0.0 to 1.0
    
    # Milestones
    milestones: List[QuestMilestone] = field(default_factory=list)
    
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    deadline: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Metadata
    category: str = "general"  # trading, learning, portfolio, etc.
    tags: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    
    # Rewards/outcomes
    target_value: Optional[float] = None  # e.g., target profit
    actual_value: Optional[float] = None
    
    def add_milestone(self, description: str) -> QuestMilestone:
        """Add a new milestone to the quest."""
        milestone = QuestMilestone(
            id=f"{self.id}_m{len(self.milestones)+1}",
            description=description,
        )
        self.milestones.append(milestone)
        self._update_progress()
        return milestone
    
    def complete_milestone(self, milestone_id: str, evidence: Optional[str] = None) -> bool:
        """Mark a milestone as completed."""
        for milestone in self.milestones:
            if milestone.id == milestone_id:
                milestone.completed = True
                milestone.completed_at = datetime.utcnow()
                milestone.evidence = evidence
                self._update_progress()
                return True
        return False
    
    def _update_progress(self) -> None:
        """Update progress based on completed milestones."""
        if not self.milestones:
            return
        completed = sum(1 for m in self.milestones if m.completed)
        self.progress = completed / len(self.milestones)
        
        # Auto-complete quest if all milestones done
        if self.progress >= 1.0 and self.status == QuestStatus.ACTIVE:
            self.status = QuestStatus.COMPLETED
            self.completed_at = datetime.utcnow()
    
    def is_overdue(self) -> bool:
        """Check if quest is past deadline."""
        if not self.deadline:
            return False
        return datetime.utcnow() > self.deadline and self.status == QuestStatus.ACTIVE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "progress": self.progress,
            "milestones": [
                {
                    "id": m.id,
                    "description": m.description,
                    "completed": m.completed,
                    "completed_at": m.completed_at.isoformat() if m.completed_at else None,
                }
                for m in self.milestones
            ],
            "created_at": self.created_at.isoformat(),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "category": self.category,
            "tags": self.tags,
        }


class QuestManager:
    """
    Manages user quests/goals.
    
    Like a quest log in an RPG.
    """
    
    def __init__(self):
        self.quests: Dict[str, Quest] = {}  # quest_id -> Quest
        self.user_quests: Dict[str, List[str]] = {}  # user_id -> [quest_ids]
        
    def create_quest(
        self,
        user_id: str,
        title: str,
        description: str,
        category: str = "general",
        priority: QuestPriority = QuestPriority.MEDIUM,
        deadline: Optional[datetime] = None,
        milestones: Optional[List[str]] = None,
    ) -> Quest:
        """Create a new quest for a user."""
        quest_id = hashlib.sha256(
            f"{user_id}:{title}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:12]
        
        quest = Quest(
            id=quest_id,
            user_id=user_id,
            title=title,
            description=description,
            category=category,
            priority=priority,
            deadline=deadline,
        )
        
        # Add milestones if provided
        if milestones:
            for milestone_desc in milestones:
                quest.add_milestone(milestone_desc)
                
        self.quests[quest_id] = quest
        
        if user_id not in self.user_quests:
            self.user_quests[user_id] = []
        self.user_quests[user_id].append(quest_id)
        
        return quest
    
    def get_user_quests(
        self,
        user_id: str,
        status: Optional[QuestStatus] = None,
        category: Optional[str] = None,
    ) -> List[Quest]:
        """Get quests for a user with optional filters."""
        quest_ids = self.user_quests.get(user_id, [])
        quests = [self.quests[qid] for qid in quest_ids if qid in self.quests]
        
        if status:
            quests = [q for q in quests if q.status == status]
        if category:
            quests = [q for q in quests if q.category == category]
            
        # Sort by priority and deadline
        quests.sort(key=lambda q: (q.priority.value, q.deadline or datetime.max))
        return quests
    
    def get_active_quests(self, user_id: str) -> List[Quest]:
        """Get active quests for context injection."""
        return self.get_user_quests(user_id, status=QuestStatus.ACTIVE)
    
    def get_overdue_quests(self, user_id: str) -> List[Quest]:
        """Get overdue quests that need attention."""
        active = self.get_active_quests(user_id)
        return [q for q in active if q.is_overdue()]
    
    def format_quest_summary(self, user_id: str) -> str:
        """Format active quests as context string."""
        active = self.get_active_quests(user_id)
        if not active:
            return "No active goals."
            
        lines = ["📋 Active Goals:"]
        for quest in active[:5]:  # Limit to 5 for context
            progress_bar = "█" * int(quest.progress * 5) + "░" * (5 - int(quest.progress * 5))
            status = "⚠️ OVERDUE" if quest.is_overdue() else f"{int(quest.progress*100)}%"
            lines.append(f"  • {quest.title} [{progress_bar}] {status}")
            
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ADAPTIVE LEARNING - Complexity adjustment based on feedback
# ═══════════════════════════════════════════════════════════════════════════════

class ExpertiseLevel(Enum):
    """User expertise levels for adaptive responses."""
    BEGINNER = 1      # New to crypto/trading
    INTERMEDIATE = 2  # Some experience
    ADVANCED = 3      # Experienced trader
    EXPERT = 4        # Deep knowledge


@dataclass
class UserProfile:
    """
    User profile for adaptive behavior.
    
    Like a game's difficulty adjustment based on player skill.
    """
    user_id: str
    
    # Expertise tracking
    expertise_level: ExpertiseLevel = ExpertiseLevel.INTERMEDIATE
    expertise_confidence: float = 0.5  # How confident we are in the assessment
    
    # Communication preferences (learned from feedback)
    prefers_detailed: bool = True      # Long explanations vs. short
    prefers_technical: bool = False    # Technical jargon vs. simple
    prefers_emoji: bool = True         # Use emojis
    prefers_charts: bool = True        # Include chart references
    
    # Feedback history
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0
    clarification_requests: int = 0  # Times user asked for clarification
    
    # Topics they've shown expertise in
    known_topics: List[str] = field(default_factory=list)
    confused_topics: List[str] = field(default_factory=list)
    
    # Learning rate
    learning_rate: float = 0.1  # How fast to adjust
    
    def record_feedback(self, positive: bool, topic: Optional[str] = None) -> None:
        """Record user feedback to adjust behavior."""
        if positive:
            self.positive_feedback_count += 1
            if topic and topic not in self.known_topics:
                self.known_topics.append(topic)
        else:
            self.negative_feedback_count += 1
            
        # Adjust expertise confidence based on feedback ratio
        total = self.positive_feedback_count + self.negative_feedback_count
        if total > 5:
            self.expertise_confidence = min(0.9, self.positive_feedback_count / total)
            
    def record_clarification(self, topic: Optional[str] = None) -> None:
        """Record when user asks for clarification."""
        self.clarification_requests += 1
        
        if topic and topic not in self.confused_topics:
            self.confused_topics.append(topic)
            
        # Many clarifications = lower expertise or prefer more detail
        if self.clarification_requests > 5:
            self.prefers_detailed = True
            
    def upgrade_expertise(self) -> bool:
        """Upgrade expertise level if feedback suggests higher skill."""
        if self.expertise_confidence > 0.7 and self.expertise_level.value < 4:
            if self.positive_feedback_count > 10:
                self.expertise_level = ExpertiseLevel(self.expertise_level.value + 1)
                self.expertise_confidence = 0.5  # Reset confidence for new level
                return True
        return False
    
    def get_response_style(self) -> Dict[str, Any]:
        """Get recommended response style based on profile."""
        style = {
            "detail_level": "detailed" if self.prefers_detailed else "concise",
            "use_jargon": self.prefers_technical,
            "use_emoji": self.prefers_emoji,
            "include_charts": self.prefers_charts,
            "explain_basics": self.expertise_level.value <= 2,
            "assume_knowledge": self.expertise_level.value >= 3,
        }
        
        # Adjust for known/confused topics
        style["known_topics"] = self.known_topics
        style["needs_explanation"] = self.confused_topics
        
        return style
    
    def to_context_string(self) -> str:
        """Format profile for prompt injection."""
        level_names = {
            ExpertiseLevel.BEGINNER: "beginner",
            ExpertiseLevel.INTERMEDIATE: "intermediate",
            ExpertiseLevel.ADVANCED: "advanced",
            ExpertiseLevel.EXPERT: "expert",
        }
        
        parts = [f"User expertise: {level_names[self.expertise_level]}"]
        
        if self.prefers_detailed:
            parts.append("Prefers: detailed explanations")
        else:
            parts.append("Prefers: concise responses")
            
        if self.known_topics:
            parts.append(f"Familiar with: {', '.join(self.known_topics[:5])}")
            
        return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. MEMORY PRUNING - Archive old memories, importance tagging
# ═══════════════════════════════════════════════════════════════════════════════

class ImportanceLevel(Enum):
    """Memory importance levels."""
    CRITICAL = 5     # Never forget (user preferences, major events)
    HIGH = 4         # Important (significant trades, lessons)
    MEDIUM = 3       # Normal (regular interactions)
    LOW = 2          # Less important (casual chat)
    TRIVIAL = 1      # Can forget (greetings, small talk)


@dataclass
class EnhancedMemoryEntry:
    """
    Enhanced memory entry with all the new features.
    """
    id: str
    content: str
    
    # Core metadata
    user_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    source: str = "telegram"
    
    # Importance and pruning
    importance: ImportanceLevel = ImportanceLevel.MEDIUM
    importance_score: float = 0.5  # Fine-grained 0.0-1.0
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    decay_rate: float = 0.01  # How fast importance decays
    
    # Emotional context
    emotional_context: Optional[EmotionalContext] = None
    
    # World state at creation
    world_state_snapshot: Optional[Dict[str, Any]] = None
    
    # Relationships
    related_memory_ids: List[str] = field(default_factory=list)
    related_quest_ids: List[str] = field(default_factory=list)
    
    # Archive status
    is_archived: bool = False
    archived_at: Optional[datetime] = None
    
    def calculate_current_importance(self) -> float:
        """
        Calculate current importance with time decay.
        
        Memories decay in importance over time unless accessed.
        """
        base_importance = self.importance_score
        
        # Apply time decay
        age_days = (datetime.utcnow() - self.created_at).days
        decay = self.decay_rate * age_days
        
        # Access boosts importance
        access_boost = min(0.2, self.access_count * 0.02)
        
        # Critical memories don't decay
        if self.importance == ImportanceLevel.CRITICAL:
            return base_importance
            
        current = max(0.1, base_importance - decay + access_boost)
        return min(1.0, current)
    
    def should_archive(self, threshold: float = 0.2) -> bool:
        """Check if memory should be archived."""
        if self.importance == ImportanceLevel.CRITICAL:
            return False
        return self.calculate_current_importance() < threshold
    
    def touch(self) -> None:
        """Record access to this memory."""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()
        
    def archive(self) -> None:
        """Archive this memory."""
        self.is_archived = True
        self.archived_at = datetime.utcnow()


class MemoryPruner:
    """
    Handles memory pruning and archival.
    
    Like a game's save system that compresses old data.
    """
    
    def __init__(
        self,
        archive_threshold: float = 0.2,
        max_active_memories: int = 1000,
    ):
        self.archive_threshold = archive_threshold
        self.max_active_memories = max_active_memories
        
    def prune_memories(
        self,
        memories: List[EnhancedMemoryEntry],
    ) -> Tuple[List[EnhancedMemoryEntry], List[EnhancedMemoryEntry]]:
        """
        Prune memories, returning (active, archived).
        
        Algorithm:
        1. Never archive CRITICAL memories
        2. Archive memories below importance threshold
        3. If still too many, archive lowest importance first
        """
        active = []
        to_archive = []
        
        for memory in memories:
            if memory.is_archived:
                to_archive.append(memory)
            elif memory.should_archive(self.archive_threshold):
                memory.archive()
                to_archive.append(memory)
            else:
                active.append(memory)
                
        # If still too many active, archive lowest importance
        if len(active) > self.max_active_memories:
            # Sort by current importance
            active.sort(key=lambda m: m.calculate_current_importance(), reverse=True)
            
            # Archive excess
            to_archive_count = len(active) - self.max_active_memories
            for memory in active[-to_archive_count:]:
                if memory.importance != ImportanceLevel.CRITICAL:
                    memory.archive()
                    to_archive.append(memory)
                    
            active = active[:-to_archive_count]
            
        return active, to_archive
    
    def summarize_archived(
        self,
        archived: List[EnhancedMemoryEntry],
        max_summaries: int = 10,
    ) -> List[str]:
        """
        Create summaries of archived memories for compressed storage.
        
        Groups related memories and creates digest.
        """
        if not archived:
            return []
            
        # Group by date (weekly)
        weekly_groups: Dict[str, List[EnhancedMemoryEntry]] = {}
        for memory in archived:
            week_key = memory.created_at.strftime("%Y-W%W")
            if week_key not in weekly_groups:
                weekly_groups[week_key] = []
            weekly_groups[week_key].append(memory)
            
        summaries = []
        for week_key, memories in sorted(weekly_groups.items())[-max_summaries:]:
            # Count by importance
            high_count = sum(1 for m in memories if m.importance.value >= 4)
            total = len(memories)
            
            # Sample content
            sample = memories[0].content[:100] if memories else ""
            
            summary = f"Week {week_key}: {total} memories ({high_count} important). Sample: {sample}..."
            summaries.append(summary)
            
        return summaries


# ═══════════════════════════════════════════════════════════════════════════════
# ENHANCED MEMORY MANAGER - Combines all features
# ═══════════════════════════════════════════════════════════════════════════════

class EnhancedMemoryManager:
    """
    Complete enhanced memory system combining all 5 features.
    
    This is the main interface for Jarvis to use.
    """
    
    def __init__(self):
        # World state (shared)
        self.world_state = WorldState()
        
        # Quest management
        self.quest_manager = QuestManager()
        
        # User profiles (adaptive learning)
        self.user_profiles: Dict[str, UserProfile] = {}
        
        # Enhanced memories
        self.memories: Dict[str, EnhancedMemoryEntry] = {}
        self.user_memories: Dict[str, List[str]] = {}  # user_id -> [memory_ids]
        
        # Memory pruner
        self.pruner = MemoryPruner()
        
        # Archived memories (compressed storage)
        self.archived_summaries: Dict[str, List[str]] = {}  # user_id -> [summaries]
        
    def get_user_profile(self, user_id: str) -> UserProfile:
        """Get or create user profile."""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(user_id=user_id)
        return self.user_profiles[user_id]
    
    def add_memory(
        self,
        user_id: str,
        content: str,
        importance: ImportanceLevel = ImportanceLevel.MEDIUM,
        source: str = "telegram",
        analyze_emotion: bool = True,
    ) -> EnhancedMemoryEntry:
        """Add a new memory with all enhancements."""
        # Generate ID
        memory_id = hashlib.sha256(
            f"{user_id}:{content}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Analyze emotional context
        emotional_context = None
        if analyze_emotion:
            emotional_context = EmotionalContext()
            emotional_context.analyze_text(content)
            
        # Capture world state snapshot
        self.world_state.update_time()
        world_snapshot = {
            "time": self.world_state.current_time.isoformat(),
            "time_of_day": self.world_state.time_of_day.value,
            "market_sentiment": self.world_state.market_sentiment,
        }
        
        # Create entry
        entry = EnhancedMemoryEntry(
            id=memory_id,
            content=content,
            user_id=user_id,
            importance=importance,
            importance_score=importance.value / 5.0,
            source=source,
            emotional_context=emotional_context,
            world_state_snapshot=world_snapshot,
        )
        
        self.memories[memory_id] = entry
        
        if user_id not in self.user_memories:
            self.user_memories[user_id] = []
        self.user_memories[user_id].append(memory_id)
        
        return entry
    
    def get_context_for_response(self, user_id: str) -> Dict[str, Any]:
        """
        Get full context for generating a response.
        
        Combines all 5 enhancement systems.
        """
        # 1. World state
        self.world_state.update_time()
        self.world_state.messages_in_session += 1
        
        # 2. User profile (adaptive)
        profile = self.get_user_profile(user_id)
        
        # 3. Active quests
        quests = self.quest_manager.get_active_quests(user_id)
        overdue = self.quest_manager.get_overdue_quests(user_id)
        
        # 4. Recent memories with emotional context
        recent_memory_ids = self.user_memories.get(user_id, [])[-10:]
        recent_memories = [
            self.memories[mid] for mid in recent_memory_ids
            if mid in self.memories and not self.memories[mid].is_archived
        ]
        
        # Touch accessed memories
        for mem in recent_memories:
            mem.touch()
            
        return {
            # World model
            "world_state": self.world_state.to_context_string(),
            "greeting_context": self.world_state.get_greeting_context(),
            
            # Adaptive learning
            "user_profile": profile.to_context_string(),
            "response_style": profile.get_response_style(),
            
            # Quest tracking
            "active_quests": [q.to_dict() for q in quests[:3]],
            "quest_summary": self.quest_manager.format_quest_summary(user_id),
            "overdue_quests": [q.title for q in overdue],
            
            # Emotional context from recent messages
            "recent_emotions": [
                m.emotional_context.to_dict() if m.emotional_context else None
                for m in recent_memories[-3:]
            ],
            
            # Suggested tone based on recent emotions
            "suggested_tone": self._determine_tone(recent_memories),
        }
    
    def _determine_tone(self, recent_memories: List[EnhancedMemoryEntry]) -> str:
        """Determine suggested tone from recent emotional context."""
        if not recent_memories:
            return "professional"
            
        # Get most recent emotional context
        for mem in reversed(recent_memories):
            if mem.emotional_context:
                return mem.emotional_context.suggested_tone
                
        return "professional"
    
    def prune_user_memories(self, user_id: str) -> Dict[str, int]:
        """Prune old memories for a user."""
        memory_ids = self.user_memories.get(user_id, [])
        memories = [self.memories[mid] for mid in memory_ids if mid in self.memories]
        
        active, archived = self.pruner.prune_memories(memories)
        
        # Generate summaries for archived
        if archived:
            summaries = self.pruner.summarize_archived(archived)
            if user_id not in self.archived_summaries:
                self.archived_summaries[user_id] = []
            self.archived_summaries[user_id].extend(summaries)
            
        return {
            "active": len(active),
            "archived": len(archived),
            "summaries_created": len(self.archived_summaries.get(user_id, [])),
        }
    
    def record_feedback(
        self,
        user_id: str,
        positive: bool,
        topic: Optional[str] = None,
    ) -> None:
        """Record user feedback for adaptive learning."""
        profile = self.get_user_profile(user_id)
        profile.record_feedback(positive, topic)
        
        # Check for expertise upgrade
        if profile.upgrade_expertise():
            logger.info(f"User {user_id} upgraded to {profile.expertise_level.name}")


# Singleton instance
_enhanced_memory_manager: Optional[EnhancedMemoryManager] = None


def get_enhanced_memory_manager() -> EnhancedMemoryManager:
    """Get the global enhanced memory manager instance."""
    global _enhanced_memory_manager
    if _enhanced_memory_manager is None:
        _enhanced_memory_manager = EnhancedMemoryManager()
    return _enhanced_memory_manager
