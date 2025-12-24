"""
Context Manager for Jarvis.
Continuously gathers and organizes context about user activities.
Maintains shared context across all providers and conversations.
"""

import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = ROOT / "data" / "context"
MASTER_CONTEXT_FILE = CONTEXT_PATH / "master_context.json"
ACTIVITY_CONTEXT_FILE = CONTEXT_PATH / "activity_context.json"
CONVERSATION_CONTEXT_FILE = CONTEXT_PATH / "conversation_context.json"


@dataclass
class MasterContext:
    """Master context shared across all interactions."""
    user_name: str = "User"
    user_goals: List[str] = field(default_factory=list)
    current_projects: List[str] = field(default_factory=list)
    recent_topics: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    learned_patterns: List[str] = field(default_factory=list)
    last_updated: float = 0.0
    

@dataclass  
class ActivityContext:
    """Context from recent user activity."""
    current_app: str = ""
    current_window: str = ""
    recent_apps: List[str] = field(default_factory=list)
    activity_summary: str = ""
    screen_content: str = ""
    idle_time: float = 0.0
    focus_score: float = 0.0
    timestamp: float = 0.0


@dataclass
class ConversationContext:
    """Context from recent conversations."""
    recent_messages: List[Dict[str, str]] = field(default_factory=list)
    pending_tasks: List[str] = field(default_factory=list)
    mentioned_topics: List[str] = field(default_factory=list)
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    session_start: float = 0.0


def _ensure_paths():
    CONTEXT_PATH.mkdir(parents=True, exist_ok=True)


def load_master_context() -> MasterContext:
    """Load the master context."""
    _ensure_paths()
    if MASTER_CONTEXT_FILE.exists():
        try:
            with open(MASTER_CONTEXT_FILE, "r") as f:
                data = json.load(f)
                return MasterContext(**data)
        except Exception as e:
            pass
    return MasterContext()


def save_master_context(ctx: MasterContext) -> None:
    """Save the master context."""
    _ensure_paths()
    ctx.last_updated = time.time()
    with open(MASTER_CONTEXT_FILE, "w") as f:
        json.dump(asdict(ctx), f, indent=2)


def load_activity_context() -> ActivityContext:
    """Load the activity context."""
    _ensure_paths()
    if ACTIVITY_CONTEXT_FILE.exists():
        try:
            with open(ACTIVITY_CONTEXT_FILE, "r") as f:
                data = json.load(f)
                return ActivityContext(**data)
        except Exception as e:
            pass
    return ActivityContext()


def save_activity_context(ctx: ActivityContext) -> None:
    """Save the activity context."""
    _ensure_paths()
    ctx.timestamp = time.time()
    with open(ACTIVITY_CONTEXT_FILE, "w") as f:
        json.dump(asdict(ctx), f, indent=2)


def load_conversation_context() -> ConversationContext:
    """Load the conversation context."""
    _ensure_paths()
    if CONVERSATION_CONTEXT_FILE.exists():
        try:
            with open(CONVERSATION_CONTEXT_FILE, "r") as f:
                data = json.load(f)
                return ConversationContext(**data)
        except Exception as e:
            pass
    return ConversationContext()


def save_conversation_context(ctx: ConversationContext) -> None:
    """Save the conversation context."""
    _ensure_paths()
    with open(CONVERSATION_CONTEXT_FILE, "w") as f:
        json.dump(asdict(ctx), f, indent=2)


def update_activity(app: str, window: str, screen_content: str = "") -> None:
    """Update activity context with current state."""
    ctx = load_activity_context()
    ctx.current_app = app
    ctx.current_window = window
    ctx.screen_content = screen_content[:1000]  # Limit size
    
    # Track recent apps
    if app and app not in ctx.recent_apps:
        ctx.recent_apps = [app] + ctx.recent_apps[:9]
    
    save_activity_context(ctx)


def add_conversation_message(role: str, content: str) -> None:
    """Add a message to conversation context."""
    ctx = load_conversation_context()
    
    ctx.recent_messages.append({
        "role": role,
        "content": content[:500],  # Limit size
        "timestamp": time.time(),
    })
    
    # Keep last 20 messages
    ctx.recent_messages = ctx.recent_messages[-20:]
    
    # Extract topics from content
    topics = _extract_topics(content)
    for topic in topics:
        if topic not in ctx.mentioned_topics:
            ctx.mentioned_topics = [topic] + ctx.mentioned_topics[:19]
    
    save_conversation_context(ctx)


def add_action_result(action: str, success: bool, result: str) -> None:
    """Record an action result for learning."""
    ctx = load_conversation_context()
    
    ctx.action_history.append({
        "action": action,
        "success": success,
        "result": result[:200],
        "timestamp": time.time(),
    })
    
    # Keep last 50 actions
    ctx.action_history = ctx.action_history[-50:]
    
    save_conversation_context(ctx)


def learn_user_preference(key: str, value: Any) -> None:
    """Learn a user preference."""
    ctx = load_master_context()
    ctx.preferences[key] = value
    save_master_context(ctx)


def add_user_goal(goal: str) -> None:
    """Add a user goal."""
    ctx = load_master_context()
    if goal not in ctx.user_goals:
        ctx.user_goals.append(goal)
    save_master_context(ctx)


def add_current_project(project: str) -> None:
    """Add a current project."""
    ctx = load_master_context()
    if project not in ctx.current_projects:
        ctx.current_projects.append(project)
    save_master_context(ctx)


def get_full_context() -> Dict[str, Any]:
    """Get combined context for AI prompts."""
    master = load_master_context()
    activity = load_activity_context()
    conversation = load_conversation_context()
    
    return {
        "user": {
            "name": master.user_name,
            "goals": master.user_goals[:5],
            "projects": master.current_projects[:5],
            "preferences": master.preferences,
        },
        "activity": {
            "current_app": activity.current_app,
            "current_window": activity.current_window,
            "recent_apps": activity.recent_apps[:5],
            "screen_context": activity.screen_content[:500],
        },
        "conversation": {
            "recent_messages": conversation.recent_messages[-5:],
            "pending_tasks": conversation.pending_tasks[:5],
            "recent_topics": conversation.mentioned_topics[:10],
        },
        "timestamp": datetime.now().isoformat(),
    }


def get_context_summary() -> str:
    """Get a brief text summary of current context."""
    ctx = get_full_context()
    
    parts = []
    
    if ctx["activity"]["current_app"]:
        parts.append(f"Currently in: {ctx['activity']['current_app']}")
    
    if ctx["user"]["projects"]:
        parts.append(f"Projects: {', '.join(ctx['user']['projects'][:3])}")
    
    if ctx["conversation"]["recent_topics"]:
        parts.append(f"Recent topics: {', '.join(ctx['conversation']['recent_topics'][:5])}")
    
    return " | ".join(parts) if parts else "No context available"


def _extract_topics(text: str) -> List[str]:
    """Extract topic keywords from text."""
    # Simple keyword extraction
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                  "have", "has", "had", "do", "does", "did", "will", "would", "could",
                  "should", "may", "might", "must", "shall", "can", "need", "dare",
                  "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
                  "into", "through", "during", "before", "after", "above", "below",
                  "between", "under", "again", "further", "then", "once", "here",
                  "there", "when", "where", "why", "how", "all", "each", "few",
                  "more", "most", "other", "some", "such", "no", "nor", "not",
                  "only", "own", "same", "so", "than", "too", "very", "just",
                  "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
                  "you", "your", "yours", "yourself", "yourselves", "he", "him",
                  "his", "himself", "she", "her", "hers", "herself", "it", "its",
                  "itself", "they", "them", "their", "theirs", "themselves",
                  "what", "which", "who", "whom", "this", "that", "these", "those",
                  "am", "and", "but", "if", "or", "because", "until", "while"}
    
    words = text.lower().split()
    topics = []
    
    for word in words:
        # Clean word
        clean = ''.join(c for c in word if c.isalnum())
        if len(clean) > 3 and clean not in stop_words:
            topics.append(clean)
    
    # Return unique topics
    seen = set()
    unique = []
    for t in topics:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    
    return unique[:10]


def clear_session_context() -> None:
    """Clear session-specific context (keeps master context)."""
    save_conversation_context(ConversationContext())
    save_activity_context(ActivityContext())
