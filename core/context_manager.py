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
CONTEXT_DOCS_PATH = ROOT / "data" / "context_docs"
DOC_INDEX_FILE = CONTEXT_DOCS_PATH / "index.json"


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
    conversation_summaries: List[Dict[str, str]] = field(default_factory=list)
    key_facts: List[Dict[str, Any]] = field(default_factory=list)
    user_corrections: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ContextDocument:
    """Structured context document metadata."""
    doc_id: str
    title: str
    source: str
    category: str
    summary: str
    path: str
    created_at: float
    tags: List[str] = field(default_factory=list)
    monetization_angle: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


def _ensure_paths():
    CONTEXT_PATH.mkdir(parents=True, exist_ok=True)
    CONTEXT_DOCS_PATH.mkdir(parents=True, exist_ok=True)


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
        "content": content[:800],  # Increased limit
        "timestamp": time.time(),
    })

    # Keep last 30 messages (increased from 20)
    ctx.recent_messages = ctx.recent_messages[-30:]

    # Auto-summarize when we have too many messages
    if len(ctx.recent_messages) >= 25:
        _auto_summarize_context(ctx)

    # Extract topics from content with importance scoring
    topics = _extract_topics(content)
    for topic in topics:
        if topic not in ctx.mentioned_topics:
            ctx.mentioned_topics = [topic] + ctx.mentioned_topics[:29]  # Keep 30 topics

    # Extract key facts from user messages
    if role == "user":
        facts = _extract_key_facts(content)
        for fact in facts:
            ctx.key_facts.append({
                "fact": fact,
                "timestamp": time.time(),
            })
        ctx.key_facts = ctx.key_facts[-50:]  # Keep 50 facts

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


def _extract_key_facts(text: str) -> List[str]:
    """Extract key facts from user input that should be remembered.

    Looks for statements like:
    - "I am...", "I'm...", "My name is..."
    - "I work at...", "I like...", "I prefer..."
    - Statements containing names, preferences, or personal info
    """
    import re

    facts = []
    lowered = text.lower()

    # Personal identity patterns
    identity_patterns = [
        r"(?:i am|i'm|my name is|call me)\s+([^,.!?]+)",
        r"(?:i work at|i work for|i'm at)\s+([^,.!?]+)",
        r"(?:i live in|i'm from|i'm based in)\s+([^,.!?]+)",
    ]

    for pattern in identity_patterns:
        match = re.search(pattern, lowered)
        if match:
            facts.append(text[match.start():match.end()])

    # Preference patterns
    preference_patterns = [
        r"(?:i prefer|i like|i want|i need|i always)\s+([^,.!?]+)",
        r"(?:don't|do not)\s+(?:like|want|need)\s+([^,.!?]+)",
    ]

    for pattern in preference_patterns:
        match = re.search(pattern, lowered)
        if match:
            facts.append(text[match.start():match.end()])

    # Remember/note patterns - explicit memory requests
    remember_patterns = [
        r"(?:remember that|note that|keep in mind|don't forget)\s+(.+)",
        r"(?:my|the)\s+\w+\s+(?:is|are)\s+([^,.!?]+)",
    ]

    for pattern in remember_patterns:
        match = re.search(pattern, lowered)
        if match:
            facts.append(text[match.start():match.end()])

    return facts[:5]  # Max 5 facts per message


def _auto_summarize_context(ctx: 'ConversationContext') -> None:
    """Auto-summarize old messages to preserve context without bloat."""
    if len(ctx.recent_messages) < 20:
        return

    # Take oldest 10 messages and create a summary
    old_messages = ctx.recent_messages[:10]

    # Build a simple summary
    topics = set()
    actions = []
    user_requests = []

    for msg in old_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Extract topics
        for topic in _extract_topics(content):
            topics.add(topic)

        # Track user requests
        if role == "user":
            user_requests.append(content[:100])

    summary = {
        "timestamp": time.time(),
        "message_count": len(old_messages),
        "topics": list(topics)[:15],
        "key_requests": user_requests[:5],
    }

    ctx.conversation_summaries.append(summary)
    ctx.conversation_summaries = ctx.conversation_summaries[-10:]  # Keep 10 summaries

    # Remove summarized messages
    ctx.recent_messages = ctx.recent_messages[10:]


def add_user_correction(original: str, correction: str) -> None:
    """Record when user corrects Jarvis - important for learning."""
    ctx = load_conversation_context()
    ctx.user_corrections.append({
        "original": original[:200],
        "correction": correction[:200],
        "timestamp": time.time(),
    })
    ctx.user_corrections = ctx.user_corrections[-20:]  # Keep 20 corrections
    save_conversation_context(ctx)


def get_key_facts_summary() -> str:
    """Get a summary of key facts about the user."""
    ctx = load_conversation_context()
    if not ctx.key_facts:
        return ""

    recent_facts = ctx.key_facts[-10:]
    return "\n".join(f"- {f['fact']}" for f in recent_facts)


def get_conversation_summaries_text() -> str:
    """Get summarized history from older conversations."""
    ctx = load_conversation_context()
    if not ctx.conversation_summaries:
        return ""

    lines = []
    for summary in ctx.conversation_summaries[-3:]:  # Last 3 summaries
        topics = ", ".join(summary.get("topics", [])[:5])
        lines.append(f"Previous discussion: {topics}")

    return "\n".join(lines)


def clear_session_context() -> None:
    """Clear session-specific context (keeps master context)."""
    ctx = ConversationContext()
    save_conversation_context(ctx)


# === Context document utilities ===

def _load_doc_index() -> Dict[str, ContextDocument]:
    _ensure_paths()
    if not DOC_INDEX_FILE.exists():
        return {}
    try:
        with open(DOC_INDEX_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}
    docs: Dict[str, ContextDocument] = {}
    for doc_id, payload in raw.items():
        try:
            docs[doc_id] = ContextDocument(**payload)
        except TypeError:
            continue
    return docs


def _save_doc_index(index: Dict[str, ContextDocument]) -> None:
    _ensure_paths()
    serializable = {doc_id: asdict(doc) for doc_id, doc in index.items()}
    with open(DOC_INDEX_FILE, "w", encoding="utf-8") as handle:
        json.dump(serializable, handle, indent=2)


def add_context_document(
    title: str,
    source: str,
    category: str,
    summary: str,
    content: str,
    tags: Optional[List[str]] = None,
    monetization_angle: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> ContextDocument:
    """Persist a rich context document and register its metadata."""
    _ensure_paths()
    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip() or "context"
    timestamp = datetime.now()
    doc_id = f"{timestamp.strftime('%Y%m%d%H%M%S')}_{safe_title.replace(' ', '_')[:40]}"
    file_name = f"{doc_id}.md"
    file_path = CONTEXT_DOCS_PATH / file_name

    body = [
        f"# {title}",
        "",
        f"**Source:** {source}",
        f"**Category:** {category}",
        f"**Created:** {timestamp.isoformat()}",
    ]
    if monetization_angle:
        body.append(f"**Monetization Angle:** {monetization_angle}")
    if tags:
        body.append(f"**Tags:** {', '.join(tags)}")
    body.extend(["", "## Summary", "", summary.strip(), "", "## Details", "", content.strip(), ""])

    file_path.write_text("\n".join(body), encoding="utf-8")

    index = _load_doc_index()
    doc = ContextDocument(
        doc_id=doc_id,
        title=title,
        source=source,
        category=category,
        summary=summary,
        path=str(file_path),
        created_at=timestamp.timestamp(),
        tags=tags or [],
        monetization_angle=monetization_angle,
        metadata=metadata or {},
    )
    index[doc_id] = doc
    _save_doc_index(index)
    return doc


def list_context_documents(limit: int = 20, category: Optional[str] = None) -> List[ContextDocument]:
    """Return recent context docs, optionally filtered by category."""
    index = _load_doc_index()
    docs = sorted(index.values(), key=lambda doc: doc.created_at, reverse=True)
    if category:
        docs = [doc for doc in docs if doc.category == category]
    return docs[:limit]


def get_context_document(doc_id: str) -> Optional[ContextDocument]:
    """Fetch a single document metadata entry."""
    return _load_doc_index().get(doc_id)


class ContextManager:
    """Class wrapper for context management operations."""

    def __init__(self):
        _ensure_paths()
        self.master = load_master_context()
        self.activity = load_activity_context()
        self.conversation = load_conversation_context()

    def refresh(self) -> None:
        """Reload all contexts from disk."""
        self.master = load_master_context()
        self.activity = load_activity_context()
        self.conversation = load_conversation_context()

    def get_full_context(self) -> Dict[str, Any]:
        """Get combined context for AI prompts."""
        return get_full_context()

    def get_context_summary(self) -> str:
        """Get a brief text summary of current context."""
        return get_context_summary()

    def update_activity(self, app: str, window: str, screen_content: str = "") -> None:
        """Update activity context with current state."""
        update_activity(app, window, screen_content)
        self.activity = load_activity_context()

    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation context."""
        add_conversation_message(role, content)
        self.conversation = load_conversation_context()

    def add_action(self, action: str, success: bool, result: str) -> None:
        """Record an action result for learning."""
        add_action_result(action, success, result)
        self.conversation = load_conversation_context()

    def learn_preference(self, key: str, value: Any) -> None:
        """Learn a user preference."""
        learn_user_preference(key, value)
        self.master = load_master_context()

    def add_goal(self, goal: str) -> None:
        """Add a user goal."""
        add_user_goal(goal)
        self.master = load_master_context()

    def add_project(self, project: str) -> None:
        """Add a current project."""
        add_current_project(project)
        self.master = load_master_context()

    def clear_session(self) -> None:
        """Clear session-specific context."""
        clear_session_context()
        self.conversation = load_conversation_context()
