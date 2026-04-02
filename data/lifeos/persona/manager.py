"""
Persona Manager

Manages loading, switching, and applying personas.

Features:
- Load personas from files or templates
- Switch between personas
- Apply persona styling to responses
- Track persona state
- Persist persona preferences
"""

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from lifeos.persona.persona import (
    Persona,
    PersonaState,
    PersonaTrait,
    SpeakingStyle,
)

logger = logging.getLogger(__name__)


class PersonaManager:
    """
    Manages AI personas and their application.

    Handles loading, switching, and styling based on active persona.
    """

    def __init__(
        self,
        personas_dir: Optional[Path] = None,
        default_persona: Optional[str] = None,
    ):
        """
        Initialize persona manager.

        Args:
            personas_dir: Directory containing persona JSON files
            default_persona: Name of default persona to load
        """
        self._personas_dir = personas_dir
        self._personas: Dict[str, Persona] = {}
        self._active_persona: Optional[Persona] = None
        self._active_name: Optional[str] = None
        self._state_history: List[PersonaState] = []
        self._style_callbacks: List[Callable[[str, Persona], str]] = []

        # Load built-in templates
        from lifeos.persona.templates import _BUILTIN_TEMPLATES
        for name, template in _BUILTIN_TEMPLATES.items():
            self._personas[name] = template.create()

        # Load custom personas
        if personas_dir and personas_dir.exists():
            self._load_personas_from_dir(personas_dir)

        # Set default
        if default_persona and default_persona in self._personas:
            self.set_active(default_persona)

    def _load_personas_from_dir(self, directory: Path) -> None:
        """Load all persona files from a directory."""
        for file_path in directory.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                persona = Persona.from_dict(data)
                self._personas[persona.name.lower()] = persona
                logger.debug(f"Loaded persona: {persona.name}")
            except Exception as e:
                logger.error(f"Failed to load persona from {file_path}: {e}")

    def register_persona(self, persona: Persona) -> None:
        """Register a persona."""
        name = persona.name.lower()
        self._personas[name] = persona
        logger.debug(f"Registered persona: {persona.name}")

    def unregister_persona(self, name: str) -> bool:
        """Unregister a persona."""
        name = name.lower()
        if name in self._personas:
            del self._personas[name]
            if self._active_name == name:
                self._active_persona = None
                self._active_name = None
            return True
        return False

    def get_persona(self, name: str) -> Optional[Persona]:
        """Get a persona by name."""
        return self._personas.get(name.lower())

    def list_personas(self) -> List[str]:
        """List all available persona names."""
        return list(self._personas.keys())

    def set_active(self, name: str) -> bool:
        """
        Set the active persona.

        Args:
            name: Persona name

        Returns:
            True if persona was activated
        """
        name = name.lower()
        if name not in self._personas:
            logger.warning(f"Persona not found: {name}")
            return False

        self._active_persona = self._personas[name]
        self._active_name = name
        self._state_history.clear()
        logger.info(f"Activated persona: {self._active_persona.name}")
        return True

    def get_active(self) -> Optional[Persona]:
        """Get the active persona."""
        return self._active_persona

    def get_active_name(self) -> Optional[str]:
        """Get the active persona name."""
        return self._active_name

    # =========================================================================
    # State Management
    # =========================================================================

    def set_state(self, state: PersonaState) -> None:
        """Set the current persona state."""
        if self._active_persona:
            self._state_history.append(self._active_persona.current_state)
            self._active_persona.current_state = state
            logger.debug(f"Persona state changed to: {state.value}")

    def get_state(self) -> Optional[PersonaState]:
        """Get the current persona state."""
        if self._active_persona:
            return self._active_persona.current_state
        return None

    def restore_state(self) -> bool:
        """Restore the previous state."""
        if self._active_persona and self._state_history:
            self._active_persona.current_state = self._state_history.pop()
            return True
        return False

    def reset_state(self) -> None:
        """Reset to normal state."""
        if self._active_persona:
            self._active_persona.current_state = PersonaState.NORMAL
            self._state_history.clear()

    # =========================================================================
    # Prompt Generation
    # =========================================================================

    def get_system_prompt(self, context_type: Optional[str] = None) -> str:
        """
        Get the system prompt for the active persona.

        Args:
            context_type: Optional context for adaptation

        Returns:
            System prompt string
        """
        if not self._active_persona:
            return "You are a helpful AI assistant."

        persona = self._active_persona
        if context_type:
            persona = persona.adapt_for_context(context_type)

        prompt = persona.get_system_prompt()

        # Add state modifier
        state_modifier = persona.get_state_modifier()
        if state_modifier:
            prompt += f"\n\nCurrent mode: {state_modifier}"

        return prompt

    def get_full_prompt(
        self,
        user_message: str,
        context_type: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get a complete prompt structure.

        Args:
            user_message: The user's message
            context_type: Optional context for adaptation
            additional_context: Additional context to include

        Returns:
            Dict with system_prompt and messages
        """
        system_prompt = self.get_system_prompt(context_type)

        # Add additional context to system prompt if provided
        if additional_context:
            context_str = "\n\nContext:\n"
            for key, value in additional_context.items():
                context_str += f"- {key}: {value}\n"
            system_prompt += context_str

        return {
            "system_prompt": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }

    # =========================================================================
    # Response Styling
    # =========================================================================

    def add_style_callback(
        self,
        callback: Callable[[str, Persona], str],
    ) -> None:
        """Add a callback for response styling."""
        self._style_callbacks.append(callback)

    async def style_response(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Style a response according to the active persona.

        This applies any registered style callbacks.

        Args:
            response: Raw response text
            context: Optional context

        Returns:
            Styled response
        """
        if not self._active_persona:
            return response

        styled = response

        # Apply registered callbacks
        for callback in self._style_callbacks:
            try:
                styled = callback(styled, self._active_persona)
            except Exception as e:
                logger.error(f"Style callback failed: {e}")

        return styled

    def format_error(self, error: str) -> str:
        """Format an error message in persona style."""
        if not self._active_persona or not self._active_persona.error_templates:
            return f"I encountered an error: {error}"

        import random
        template = random.choice(self._active_persona.error_templates)

        try:
            return template.format(error=error)
        except KeyError:
            return template

    def get_greeting(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Get a greeting from the active persona."""
        if not self._active_persona:
            return "Hello!"

        greeting = self._active_persona.get_greeting(context)
        return greeting or "Hello!"

    def get_thinking_phrase(self) -> str:
        """Get a thinking phrase from the active persona."""
        if not self._active_persona:
            return "Processing..."

        phrase = self._active_persona.get_thinking_phrase()
        return phrase or "Processing..."

    # =========================================================================
    # Persistence
    # =========================================================================

    def save_persona(self, name: str, path: Path) -> bool:
        """Save a persona to a file."""
        name = name.lower()
        if name not in self._personas:
            return False

        try:
            persona = self._personas[name]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(persona.to_dict(), f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Failed to save persona: {e}")
            return False

    def load_persona(self, path: Path) -> Optional[Persona]:
        """Load a persona from a file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            persona = Persona.from_dict(data)
            self.register_persona(persona)
            return persona
        except Exception as e:
            logger.error(f"Failed to load persona: {e}")
            return None

    # =========================================================================
    # Stats and Info
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "total_personas": len(self._personas),
            "active_persona": self._active_name,
            "active_state": self._active_persona.current_state.value if self._active_persona else None,
            "available_personas": self.list_personas(),
            "style_callbacks": len(self._style_callbacks),
        }

    def get_persona_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a persona."""
        persona = self.get_persona(name)
        if not persona:
            return None

        return {
            "name": persona.name,
            "description": persona.description,
            "traits": [t.value for t in persona.traits],
            "version": persona.version,
            "author": persona.author,
        }
