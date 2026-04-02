"""
Character/Persona System

Manages AI personalities and speaking styles.

Features:
- Persona definitions with traits and behaviors
- System prompt generation
- Response style adaptation
- Context-aware personality shifts
- Multi-persona support

Usage:
    from lifeos.persona import PersonaManager, Persona

    manager = PersonaManager()
    manager.load_persona("jarvis")

    prompt = manager.get_system_prompt()
    styled = await manager.style_response("Here is the data", context)
"""

from lifeos.persona.persona import (
    Persona,
    PersonaTrait,
    SpeakingStyle,
    PersonaState,
)
from lifeos.persona.manager import PersonaManager
from lifeos.persona.templates import (
    PersonaTemplate,
    get_template,
    list_templates,
)

__all__ = [
    # Core classes
    "Persona",
    "PersonaTrait",
    "SpeakingStyle",
    "PersonaState",
    # Manager
    "PersonaManager",
    # Templates
    "PersonaTemplate",
    "get_template",
    "list_templates",
]
