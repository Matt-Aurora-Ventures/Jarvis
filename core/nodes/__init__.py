"""GUI Node System for remote computer control.

This module provides infrastructure for registering, managing, and communicating
with remote GUI nodes (computers) that can execute commands on behalf of the user.
"""

from core.nodes.registry import (
    Node,
    NodeStatus,
    NodeType,
    NodePlatform,
    NodeRegistry,
)
from core.nodes.manager import NodeManager

__all__ = [
    "Node",
    "NodeStatus",
    "NodeType",
    "NodePlatform",
    "NodeRegistry",
    "NodeManager",
]
