"""
Bot Personality Configuration System.

Provides standardized loading and validation of bot personalities
including SOUL, IDENTITY, and BOOTSTRAP markdown files.

Usage:
    from core.personality import get_loader, Personality, validate_personality

    # Load a bot personality
    loader = get_loader()
    personality = loader.load("clawdjarvis")

    # Get all personalities
    all_bots = loader.get_all()

    # Validate a personality
    errors = validate_personality(personality)
"""

from core.personality.model import Personality
from core.personality.loader import (
    PersonalityLoader,
    PersonalityNotFoundError,
    PersonalityLoadError,
    get_loader,
    _reset_loader,
)
from core.personality.validator import (
    validate_personality,
    ValidationError,
    ErrorSeverity,
)

__all__ = [
    # Model
    "Personality",

    # Loader
    "PersonalityLoader",
    "PersonalityNotFoundError",
    "PersonalityLoadError",
    "get_loader",
    "_reset_loader",

    # Validator
    "validate_personality",
    "ValidationError",
    "ErrorSeverity",
]
