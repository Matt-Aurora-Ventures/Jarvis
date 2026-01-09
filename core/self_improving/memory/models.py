"""
Data models for Jarvis self-improving memory system.

These dataclasses represent the core memory types:
- Facts: Knowledge about entities (people, projects, concepts)
- Reflections: Self-improvement notes from failures
- Predictions: Track prediction accuracy for trust calibration
- Interactions: Conversation history with feedback
- Entities: People, projects, and concepts the user works with
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import json


@dataclass
class Entity:
    """A person, project, company, or concept the user interacts with."""

    name: str
    entity_type: str  # person, project, company, concept
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "attributes": self.attributes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Entity":
        attrs = row.get("attributes", "{}")
        if isinstance(attrs, str):
            attrs = json.loads(attrs) if attrs else {}
        return cls(
            id=row.get("id"),
            name=row.get("name", ""),
            entity_type=row.get("entity_type", "unknown"),
            attributes=attrs,
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else lambda: datetime.now(timezone.utc)(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else lambda: datetime.now(timezone.utc)(),
        )


@dataclass
class Fact:
    """A specific piece of knowledge about an entity."""

    entity: str  # Entity name or ID
    fact: str  # The actual knowledge
    confidence: float = 0.8  # 0.0-1.0
    source: str = "conversation"  # How we learned this
    learned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    entity_id: Optional[int] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity": self.entity,
            "entity_id": self.entity_id,
            "fact": self.fact,
            "confidence": self.confidence,
            "source": self.source,
            "learned_at": self.learned_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Fact":
        return cls(
            id=row.get("id"),
            entity=row.get("entity", ""),
            entity_id=row.get("entity_id"),
            fact=row.get("fact", ""),
            confidence=float(row.get("confidence", 0.8)),
            source=row.get("source", "unknown"),
            learned_at=datetime.fromisoformat(row["learned_at"]) if row.get("learned_at") else lambda: datetime.now(timezone.utc)(),
        )


@dataclass
class Reflection:
    """A self-improvement note from analyzing failures."""

    trigger: str  # What situation triggered this reflection
    what_happened: str  # Factual description
    why_failed: str  # Analysis of the failure
    lesson: str  # Concrete rule to remember
    new_approach: str = ""  # How to handle this differently
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    applied: bool = False  # Has this been used?
    applied_count: int = 0  # How many times applied
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "trigger": self.trigger,
            "what_happened": self.what_happened,
            "why_failed": self.why_failed,
            "lesson": self.lesson,
            "new_approach": self.new_approach,
            "created_at": self.created_at.isoformat(),
            "applied": self.applied,
            "applied_count": self.applied_count,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Reflection":
        return cls(
            id=row.get("id"),
            trigger=row.get("trigger", ""),
            what_happened=row.get("what_happened", ""),
            why_failed=row.get("why_failed", ""),
            lesson=row.get("lesson", ""),
            new_approach=row.get("new_approach", ""),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else lambda: datetime.now(timezone.utc)(),
            applied=bool(row.get("applied", 0)),
            applied_count=int(row.get("applied_count", 0)),
        )


@dataclass
class Prediction:
    """A prediction for tracking accuracy and building trust."""

    prediction: str  # What we predicted
    confidence: float  # 0.0-1.0
    domain: str = "general"  # calendar, email, trading, research, etc.
    deadline: Optional[datetime] = None  # When outcome should be known
    outcome: Optional[str] = None  # What actually happened
    was_correct: Optional[bool] = None  # Did we get it right?
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "prediction": self.prediction,
            "confidence": self.confidence,
            "domain": self.domain,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "outcome": self.outcome,
            "was_correct": self.was_correct,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Prediction":
        return cls(
            id=row.get("id"),
            prediction=row.get("prediction", ""),
            confidence=float(row.get("confidence", 0.5)),
            domain=row.get("domain", "general"),
            deadline=datetime.fromisoformat(row["deadline"]) if row.get("deadline") else None,
            outcome=row.get("outcome"),
            was_correct=bool(row["was_correct"]) if row.get("was_correct") is not None else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else lambda: datetime.now(timezone.utc)(),
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row.get("resolved_at") else None,
        )


@dataclass
class Interaction:
    """A conversation interaction with optional feedback."""

    user_input: str
    jarvis_response: str
    feedback: Optional[str] = None  # positive, negative, confused, retry
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_input": self.user_input,
            "jarvis_response": self.jarvis_response,
            "feedback": self.feedback,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Interaction":
        meta = row.get("metadata", "{}")
        if isinstance(meta, str):
            meta = json.loads(meta) if meta else {}
        return cls(
            id=row.get("id"),
            user_input=row.get("user_input", ""),
            jarvis_response=row.get("jarvis_response", ""),
            feedback=row.get("feedback"),
            session_id=row.get("session_id"),
            timestamp=datetime.fromisoformat(row["timestamp"]) if row.get("timestamp") else lambda: datetime.now(timezone.utc)(),
            metadata=meta,
        )


@dataclass
class ContextBundle:
    """A bundle of context retrieved for a query."""

    query: str
    facts: List[Fact] = field(default_factory=list)
    reflections: List[Reflection] = field(default_factory=list)
    recent_interactions: List[Interaction] = field(default_factory=list)
    related_entities: List[Entity] = field(default_factory=list)
    predictions: List[Prediction] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Format context for inclusion in a prompt."""
        sections = []

        if self.facts:
            fact_lines = [f"- {f.entity}: {f.fact} (confidence: {f.confidence:.0%})" for f in self.facts[:10]]
            sections.append(f"**Relevant Facts:**\n" + "\n".join(fact_lines))

        if self.reflections:
            refl_lines = [f"- Lesson: {r.lesson}" for r in self.reflections[:5]]
            sections.append(f"**Past Lessons:**\n" + "\n".join(refl_lines))

        if self.recent_interactions:
            interaction_lines = []
            for i in self.recent_interactions[:5]:
                interaction_lines.append(f"- User: {i.user_input[:100]}...")
            sections.append(f"**Recent Context:**\n" + "\n".join(interaction_lines))

        return "\n\n".join(sections) if sections else ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "facts": [f.to_dict() for f in self.facts],
            "reflections": [r.to_dict() for r in self.reflections],
            "recent_interactions": [i.to_dict() for i in self.recent_interactions],
            "related_entities": [e.to_dict() for e in self.related_entities],
            "predictions": [p.to_dict() for p in self.predictions],
        }
