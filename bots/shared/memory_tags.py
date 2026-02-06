"""
Memory tag system for access control between ClawdBots.

Tags from UNIFIED_GSD:
- company_core: Shared, all read, Matt write
- technical_stack: Jarvis owns, Matt+Jarvis read
- marketing_creative: Friday owns, Matt+Friday read
- crypto_ops: Jarvis owns, Matt+Jarvis read
- ops_logs: Matt owns, all read

Usage:
    from bots.shared.memory_tags import MemoryTagManager

    mgr = MemoryTagManager()
    if mgr.can_write("jarvis", "technical_stack"):
        # write to technical_stack memory
        pass
    tags = mgr.get_accessible_tags("friday")
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class MemoryTagManager:
    """Tag-based access control for shared memory between ClawdBots."""

    TAG_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
        "company_core": {"read": ["matt", "friday", "jarvis"], "write": ["matt"]},
        "technical_stack": {"read": ["matt", "jarvis"], "write": ["jarvis"]},
        "marketing_creative": {"read": ["matt", "friday"], "write": ["friday"]},
        "crypto_ops": {"read": ["matt", "jarvis"], "write": ["jarvis"]},
        "ops_logs": {"read": ["matt", "friday", "jarvis"], "write": ["matt"]},
    }

    def can_read(self, bot_name: str, tag: str) -> bool:
        """Check if bot can read from this tag."""
        perms = self.TAG_PERMISSIONS.get(tag)
        if not perms:
            return False
        return bot_name.lower() in perms.get("read", [])

    def can_write(self, bot_name: str, tag: str) -> bool:
        """Check if bot can write to this tag."""
        perms = self.TAG_PERMISSIONS.get(tag)
        if not perms:
            return False
        return bot_name.lower() in perms.get("write", [])

    def get_accessible_tags(self, bot_name: str) -> List[str]:
        """Get all tags this bot can read."""
        bot = bot_name.lower()
        return [
            tag
            for tag, perms in self.TAG_PERMISSIONS.items()
            if bot in perms.get("read", [])
        ]
