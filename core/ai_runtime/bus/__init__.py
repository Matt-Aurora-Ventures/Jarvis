"""
Local Unix Socket Message Bus

Secure inter-agent communication that never leaves the machine.
"""

from .socket_bus import SecureMessageBus, BusMessage
from .schemas import MessageSchema

__all__ = ["SecureMessageBus", "BusMessage", "MessageSchema"]
