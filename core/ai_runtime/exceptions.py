"""
AI Runtime Exceptions

All exceptions are designed to be caught and logged - they should never crash the main application.
"""


class AIRuntimeException(Exception):
    """Base exception for AI runtime errors."""
    pass


class AIUnavailableException(AIRuntimeException):
    """AI service is unavailable - application should continue without AI."""
    pass


class AITimeoutException(AIRuntimeException):
    """AI operation timed out - application should continue."""
    pass


class BusException(AIRuntimeException):
    """Message bus error."""
    pass


class AgentException(AIRuntimeException):
    """Agent-specific error."""
    pass


class SecurityException(AIRuntimeException):
    """Security violation detected."""
    pass


class MemoryException(AIRuntimeException):
    """Memory store error."""
    pass
