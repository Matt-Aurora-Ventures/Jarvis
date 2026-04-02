"""
Persona Definition

Defines the structure and behavior of AI personas.

A Persona includes:
- Identity (name, description, voice)
- Traits (personality characteristics)
- Speaking style (formality, verbosity, etc.)
- Behavioral rules (what to do/avoid)
- Context adaptations (how to adjust in different situations)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class PersonaTrait(Enum):
    """Core personality traits."""
    # Interaction style
    HELPFUL = "helpful"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    FORMAL = "formal"
    CASUAL = "casual"
    WITTY = "witty"
    SERIOUS = "serious"

    # Communication approach
    CONCISE = "concise"
    VERBOSE = "verbose"
    TECHNICAL = "technical"
    ACCESSIBLE = "accessible"
    DIRECT = "direct"
    DIPLOMATIC = "diplomatic"

    # Personality
    CONFIDENT = "confident"
    HUMBLE = "humble"
    ENTHUSIASTIC = "enthusiastic"
    CALM = "calm"
    CURIOUS = "curious"
    PATIENT = "patient"

    # Specialized
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    METHODICAL = "methodical"
    ADAPTIVE = "adaptive"


class PersonaState(Enum):
    """Current state of the persona."""
    NORMAL = "normal"
    FOCUSED = "focused"
    URGENT = "urgent"
    REFLECTIVE = "reflective"
    TEACHING = "teaching"
    PROBLEM_SOLVING = "problem_solving"


@dataclass
class SpeakingStyle:
    """Defines how the persona communicates."""
    formality: float = 0.5  # 0 = casual, 1 = formal
    verbosity: float = 0.5  # 0 = brief, 1 = detailed
    technicality: float = 0.5  # 0 = simple, 1 = technical
    warmth: float = 0.5  # 0 = neutral, 1 = warm
    assertiveness: float = 0.5  # 0 = passive, 1 = assertive
    humor: float = 0.0  # 0 = serious, 1 = humorous

    # Communication preferences
    use_contractions: bool = True
    use_filler_words: bool = False
    use_emojis: bool = False
    use_markdown: bool = True
    use_examples: bool = True
    use_analogies: bool = True

    # Response structure
    max_sentences_per_response: int = 10
    prefer_lists: bool = True
    prefer_code_blocks: bool = True
    include_caveats: bool = True

    def to_prompt_fragment(self) -> str:
        """Generate prompt fragment describing this style."""
        fragments = []

        if self.formality > 0.7:
            fragments.append("Use formal, professional language.")
        elif self.formality < 0.3:
            fragments.append("Use casual, conversational language.")

        if self.verbosity > 0.7:
            fragments.append("Provide detailed, comprehensive responses.")
        elif self.verbosity < 0.3:
            fragments.append("Be brief and to the point.")

        if self.technicality > 0.7:
            fragments.append("Use technical terminology when appropriate.")
        elif self.technicality < 0.3:
            fragments.append("Explain things in simple, accessible terms.")

        if self.warmth > 0.7:
            fragments.append("Be warm and personable in your responses.")

        if self.humor > 0.5:
            fragments.append("Include appropriate humor when suitable.")

        if not self.use_contractions:
            fragments.append("Avoid contractions (use 'do not' instead of 'don't').")

        if self.use_emojis:
            fragments.append("Use emojis sparingly for emphasis.")

        if self.prefer_lists:
            fragments.append("Use bullet points and lists for clarity.")

        return " ".join(fragments)


@dataclass
class Persona:
    """
    A complete AI persona definition.

    Encapsulates identity, personality, and behavioral rules
    for consistent AI character portrayal.
    """
    # Identity
    name: str
    description: str
    voice_description: str = ""

    # Personality
    traits: Set[PersonaTrait] = field(default_factory=set)
    style: SpeakingStyle = field(default_factory=SpeakingStyle)

    # Behavioral rules
    always_do: List[str] = field(default_factory=list)
    never_do: List[str] = field(default_factory=list)

    # Context adaptations
    context_adaptations: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Response templates
    greeting_templates: List[str] = field(default_factory=list)
    farewell_templates: List[str] = field(default_factory=list)
    error_templates: List[str] = field(default_factory=list)
    thinking_phrases: List[str] = field(default_factory=list)

    # Metadata
    version: str = "1.0.0"
    author: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # State
    current_state: PersonaState = PersonaState.NORMAL

    def get_system_prompt(self) -> str:
        """Generate a system prompt for this persona."""
        sections = []

        # Identity section
        sections.append(f"You are {self.name}.")
        if self.description:
            sections.append(self.description)

        # Voice description
        if self.voice_description:
            sections.append(f"\nVoice: {self.voice_description}")

        # Traits
        if self.traits:
            trait_names = [t.value for t in self.traits]
            sections.append(f"\nPersonality: {', '.join(trait_names)}")

        # Speaking style
        style_fragment = self.style.to_prompt_fragment()
        if style_fragment:
            sections.append(f"\nCommunication style: {style_fragment}")

        # Rules
        if self.always_do:
            sections.append("\nAlways:")
            for rule in self.always_do:
                sections.append(f"- {rule}")

        if self.never_do:
            sections.append("\nNever:")
            for rule in self.never_do:
                sections.append(f"- {rule}")

        return "\n".join(sections)

    def get_state_modifier(self) -> str:
        """Get prompt modifier for current state."""
        modifiers = {
            PersonaState.NORMAL: "",
            PersonaState.FOCUSED: "Focus intently on the task at hand. Minimize tangents.",
            PersonaState.URGENT: "Respond with urgency. Prioritize speed and clarity.",
            PersonaState.REFLECTIVE: "Take a thoughtful, contemplative approach.",
            PersonaState.TEACHING: "Explain concepts clearly. Use examples and analogies.",
            PersonaState.PROBLEM_SOLVING: "Think step-by-step. Consider multiple approaches.",
        }
        return modifiers.get(self.current_state, "")

    def adapt_for_context(self, context_type: str) -> "Persona":
        """
        Create an adapted version of this persona for a specific context.

        Args:
            context_type: Type of context (e.g., "trading", "casual", "technical")

        Returns:
            Adapted persona (copy with modifications)
        """
        if context_type not in self.context_adaptations:
            return self

        import copy
        adapted = copy.deepcopy(self)
        adaptations = self.context_adaptations[context_type]

        # Apply adaptations
        if "traits_add" in adaptations:
            for trait in adaptations["traits_add"]:
                adapted.traits.add(PersonaTrait(trait))

        if "traits_remove" in adaptations:
            for trait in adaptations["traits_remove"]:
                adapted.traits.discard(PersonaTrait(trait))

        if "style" in adaptations:
            for key, value in adaptations["style"].items():
                if hasattr(adapted.style, key):
                    setattr(adapted.style, key, value)

        if "state" in adaptations:
            adapted.current_state = PersonaState(adaptations["state"])

        return adapted

    def get_greeting(self, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get a contextual greeting."""
        if not self.greeting_templates:
            return None

        # Simple random selection (could be context-aware)
        import random
        template = random.choice(self.greeting_templates)

        # Basic template substitution
        if context:
            try:
                return template.format(**context)
            except KeyError:
                return template

        return template

    def get_thinking_phrase(self) -> Optional[str]:
        """Get a phrase to use when processing."""
        if not self.thinking_phrases:
            return None

        import random
        return random.choice(self.thinking_phrases)

    def to_dict(self) -> Dict[str, Any]:
        """Convert persona to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "voice_description": self.voice_description,
            "traits": [t.value for t in self.traits],
            "style": {
                "formality": self.style.formality,
                "verbosity": self.style.verbosity,
                "technicality": self.style.technicality,
                "warmth": self.style.warmth,
                "assertiveness": self.style.assertiveness,
                "humor": self.style.humor,
                "use_contractions": self.style.use_contractions,
                "use_filler_words": self.style.use_filler_words,
                "use_emojis": self.style.use_emojis,
                "use_markdown": self.style.use_markdown,
                "use_examples": self.style.use_examples,
                "use_analogies": self.style.use_analogies,
            },
            "always_do": self.always_do,
            "never_do": self.never_do,
            "context_adaptations": self.context_adaptations,
            "greeting_templates": self.greeting_templates,
            "farewell_templates": self.farewell_templates,
            "error_templates": self.error_templates,
            "thinking_phrases": self.thinking_phrases,
            "version": self.version,
            "author": self.author,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Persona":
        """Create persona from dictionary."""
        style_data = data.get("style", {})
        style = SpeakingStyle(
            formality=style_data.get("formality", 0.5),
            verbosity=style_data.get("verbosity", 0.5),
            technicality=style_data.get("technicality", 0.5),
            warmth=style_data.get("warmth", 0.5),
            assertiveness=style_data.get("assertiveness", 0.5),
            humor=style_data.get("humor", 0.0),
            use_contractions=style_data.get("use_contractions", True),
            use_filler_words=style_data.get("use_filler_words", False),
            use_emojis=style_data.get("use_emojis", False),
            use_markdown=style_data.get("use_markdown", True),
            use_examples=style_data.get("use_examples", True),
            use_analogies=style_data.get("use_analogies", True),
        )

        traits = {PersonaTrait(t) for t in data.get("traits", [])}

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            voice_description=data.get("voice_description", ""),
            traits=traits,
            style=style,
            always_do=data.get("always_do", []),
            never_do=data.get("never_do", []),
            context_adaptations=data.get("context_adaptations", {}),
            greeting_templates=data.get("greeting_templates", []),
            farewell_templates=data.get("farewell_templates", []),
            error_templates=data.get("error_templates", []),
            thinking_phrases=data.get("thinking_phrases", []),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
        )
