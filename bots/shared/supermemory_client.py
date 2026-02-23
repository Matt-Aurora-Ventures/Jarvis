"""
Supermemory Integration for ClawdBots
=====================================
Provides shared and individual memory capabilities for all ClawdBots.

Architecture:
- Each bot has its own short-term memory (user_id scoped)
- Each bot has its own mid-term memory (24h retention)
- All bots share long-term constructive memory (shared namespace)

Usage:
    from bots.shared.supermemory_client import get_memory_client, MemoryType

    # Get a bot-specific client
    memory = get_memory_client(bot_name="friday")

    # Store a memory
    await memory.add("User prefers concise responses", memory_type=MemoryType.SHORT_TERM)

    # Search memories
    results = await memory.search("user preferences", include_shared=True)

    # Store shared learning (all bots can access)
    await memory.add_shared_learning("API rate limits require 1s delay between calls")

Environment Variables:
    SUPERMEMORY_API_KEY - API key from console.supermemory.ai
    SUPERMEMORY_USER_PREFIX - Optional prefix for user IDs (default: jarvis)
"""

import asyncio
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Lazy import to allow graceful degradation
_supermemory_available = False
_Supermemory = None
_AsyncSupermemory = None

try:
    from supermemory import Supermemory, AsyncSupermemory
    _supermemory_available = True
    _Supermemory = Supermemory
    _AsyncSupermemory = AsyncSupermemory
except ImportError:
    logger.warning("supermemory package not installed. Run: pip install supermemory")


class MemoryType(Enum):
    """Types of memory with different retention and scope."""
    SHORT_TERM = "short_term"      # Session-specific, ephemeral
    MID_TERM = "mid_term"          # 24-hour retention
    LONG_TERM = "long_term"        # Persistent, bot-specific
    SHARED = "shared"              # Shared across all bots


@dataclass
class MemoryEntry:
    """A single memory entry."""
    content: str
    memory_type: MemoryType
    bot_name: str
    timestamp: str
    metadata: Dict[str, Any]
    score: float = 0.0


class SupermemoryClient:
    """
    Async client for Supermemory with multi-tier memory architecture.

    Each bot gets:
    - Short-term: Conversation context (ephemeral)
    - Mid-term: Recent learnings (24h TTL)
    - Long-term: Persistent bot-specific memories

    All bots share:
    - Shared namespace for collective learnings
    """

    def __init__(
        self,
        bot_name: str,
        api_key: Optional[str] = None,
        user_prefix: str = "jarvis",
    ):
        """
        Initialize the memory client.

        Args:
            bot_name: Name of the bot (friday, matt, jarvis)
            api_key: Supermemory API key (or use SUPERMEMORY_API_KEY env var)
            user_prefix: Prefix for user IDs (default: jarvis)
        """
        self.bot_name = bot_name.lower()
        self.user_prefix = user_prefix
        self._api_key = api_key or os.environ.get("SUPERMEMORY_API_KEY")

        # User IDs for different memory tiers
        self.user_id_short = f"{user_prefix}_{bot_name}_short"
        self.user_id_mid = f"{user_prefix}_{bot_name}_mid"
        self.user_id_long = f"{user_prefix}_{bot_name}_long"
        self.user_id_shared = f"{user_prefix}_shared"

        self._async_client: Optional[Any] = None
        self._sync_client: Optional[Any] = None

        if not _supermemory_available:
            logger.error("Supermemory package not available")
        elif not self._api_key:
            logger.error("SUPERMEMORY_API_KEY not set")

    @property
    def is_available(self) -> bool:
        """Check if Supermemory is properly configured."""
        return _supermemory_available and bool(self._api_key)

    def _get_async_client(self):
        """Get or create async client."""
        if not self.is_available:
            return None
        if self._async_client is None:
            self._async_client = _AsyncSupermemory(api_key=self._api_key)
        return self._async_client

    def _get_sync_client(self):
        """Get or create sync client."""
        if not self.is_available:
            return None
        if self._sync_client is None:
            self._sync_client = _Supermemory(api_key=self._api_key)
        return self._sync_client

    def _get_user_id(self, memory_type: MemoryType) -> str:
        """Get the user ID for a memory type."""
        mapping = {
            MemoryType.SHORT_TERM: self.user_id_short,
            MemoryType.MID_TERM: self.user_id_mid,
            MemoryType.LONG_TERM: self.user_id_long,
            MemoryType.SHARED: self.user_id_shared,
        }
        return mapping.get(memory_type, self.user_id_long)

    async def add(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a memory entry.

        Args:
            content: The memory content
            memory_type: Type of memory (determines scope and retention)
            metadata: Optional metadata tags

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available:
            logger.debug(f"[{self.bot_name}] Supermemory not available, skipping add")
            return False

        client = self._get_async_client()
        if not client:
            return False

        user_id = self._get_user_id(memory_type)
        meta = metadata or {}
        meta.update({
            "bot_name": self.bot_name,
            "memory_type": memory_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        try:
            # Add document with user context
            await client.memories.add(
                content=content,
                container_tag=user_id,
                metadata=meta,
            )
            logger.debug(f"[{self.bot_name}] Added {memory_type.value} memory")
            return True
        except Exception as e:
            logger.warning(f"[{self.bot_name}] Failed to add memory: {e}")
            return False

    async def add_with_container_tag(
        self,
        content: str,
        container_tag: str,
        metadata: Optional[Dict[str, Any]] = None,
        custom_id: Optional[str] = None,
    ) -> bool:
        """
        Add memory with an explicit container tag.

        This is used by lifecycle hooks that need stable cross-bot namespaces
        (for example research notebooks).
        """
        if not self.is_available:
            logger.debug(f"[{self.bot_name}] Supermemory not available, skipping add_with_container_tag")
            return False

        client = self._get_async_client()
        if not client:
            return False

        meta = metadata or {}
        meta.setdefault("bot_name", self.bot_name)
        meta.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        kwargs: Dict[str, Any] = {
            "content": content,
            "container_tag": container_tag,
            "metadata": meta,
        }
        if custom_id:
            kwargs["customId"] = custom_id

        try:
            await client.memories.add(**kwargs)
            return True
        except TypeError:
            # Some SDK versions do not support customId. Preserve dedupe signal
            # in metadata and retry without the unsupported argument.
            kwargs.pop("customId", None)
            if custom_id:
                meta.setdefault("custom_id", custom_id)
            try:
                await client.memories.add(**kwargs)
                return True
            except Exception as e:
                logger.warning(f"[{self.bot_name}] add_with_container_tag retry failed: {e}")
                return False
        except Exception as e:
            logger.warning(f"[{self.bot_name}] add_with_container_tag failed: {e}")
            return False

    async def add_shared_learning(
        self,
        content: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a shared learning accessible by all bots.

        Args:
            content: The learning content
            category: Category for filtering (e.g., "api", "user_pref", "error_fix")
            metadata: Optional additional metadata

        Returns:
            True if successful
        """
        meta = metadata or {}
        meta["category"] = category
        meta["contributed_by"] = self.bot_name
        return await self.add(content, MemoryType.SHARED, meta)

    async def search(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        include_shared: bool = True,
        limit: int = 5,
    ) -> List[MemoryEntry]:
        """
        Search memories.

        Args:
            query: Search query
            memory_type: Specific memory type to search (None = search all bot memories)
            include_shared: Whether to include shared memories
            limit: Maximum results per tier

        Returns:
            List of MemoryEntry objects sorted by relevance
        """
        if not self.is_available:
            logger.debug(f"[{self.bot_name}] Supermemory not available, returning empty")
            return []

        client = self._get_async_client()
        if not client:
            return []

        results: List[MemoryEntry] = []

        # Determine which user IDs to search
        user_ids = []
        if memory_type:
            user_ids.append(self._get_user_id(memory_type))
        else:
            # Search all bot-specific memories
            user_ids.extend([
                self.user_id_short,
                self.user_id_mid,
                self.user_id_long,
            ])

        if include_shared:
            user_ids.append(self.user_id_shared)

        # Search each tier
        for user_id in user_ids:
            try:
                response = await client.search.memories(
                    q=query,
                    container_tag=user_id,
                    limit=limit,
                )

                # Parse results
                for item in getattr(response, 'results', []):
                    # Determine memory type from user_id
                    if 'short' in user_id:
                        mtype = MemoryType.SHORT_TERM
                    elif 'mid' in user_id:
                        mtype = MemoryType.MID_TERM
                    elif 'shared' in user_id:
                        mtype = MemoryType.SHARED
                    else:
                        mtype = MemoryType.LONG_TERM

                    entry = MemoryEntry(
                        content=(
                            getattr(item, 'memory', None)
                            or getattr(item, 'chunk', None)
                            or str(item)
                        ),
                        memory_type=mtype,
                        bot_name=self.bot_name,
                        timestamp=getattr(item, 'updated_at', ''),
                        metadata=getattr(item, 'metadata', {}),
                        score=float(getattr(item, 'similarity', 0.0) or 0.0),
                    )
                    results.append(entry)

            except Exception as e:
                logger.warning(f"[{self.bot_name}] Search failed for {user_id}: {e}")

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit * 2]  # Return top results across all tiers

    async def get_context(
        self,
        query: str,
        max_tokens: int = 1000,
    ) -> str:
        """
        Get relevant context for a query, formatted for LLM injection.

        Args:
            query: The current query/message
            max_tokens: Approximate max tokens for context

        Returns:
            Formatted context string
        """
        memories = await self.search(query, include_shared=True, limit=5)

        if not memories:
            return ""

        context_parts = []
        estimated_tokens = 0

        for mem in memories:
            # Rough token estimate (4 chars per token)
            mem_tokens = len(mem.content) // 4

            if estimated_tokens + mem_tokens > max_tokens:
                break

            prefix = "[SHARED]" if mem.memory_type == MemoryType.SHARED else f"[{mem.memory_type.value}]"
            context_parts.append(f"{prefix} {mem.content}")
            estimated_tokens += mem_tokens

        return "\n".join(context_parts)

    def _is_static_profile_entry(self, entry: MemoryEntry) -> bool:
        """Heuristic split for long-lived user preferences."""
        kind = str(entry.metadata.get("profile_kind", "")).lower()
        if kind == "static":
            return True
        if entry.memory_type in (MemoryType.LONG_TERM, MemoryType.SHARED):
            return True
        text = entry.content.lower()
        return any(token in text for token in ["always", "only", "prefer", "strictly"])

    def _is_dynamic_profile_entry(self, entry: MemoryEntry) -> bool:
        """Heuristic split for current session focus and recent state."""
        kind = str(entry.metadata.get("profile_kind", "")).lower()
        if kind == "dynamic":
            return True
        if entry.memory_type in (MemoryType.SHORT_TERM, MemoryType.MID_TERM):
            return True
        text = entry.content.lower()
        return any(token in text for token in ["currently", "recent", "today", "now", "researching"])

    def format_dual_profile_prompt(
        self,
        static_profile: List[str],
        dynamic_profile: List[str],
        context_memories: List[str],
    ) -> str:
        """
        Build prompt block for preResponse injection.
        """
        lines: List[str] = ["## Supermemory Context"]

        lines.append("## Static Profile")
        if static_profile:
            lines.extend(f"- {item}" for item in static_profile)
        else:
            lines.append("- (none)")

        lines.append("## Dynamic Profile")
        if dynamic_profile:
            lines.extend(f"- {item}" for item in dynamic_profile)
        else:
            lines.append("- (none)")

        if context_memories:
            lines.append("## Relevant Memory")
            lines.extend(f"- {item}" for item in context_memories)

        return "\n".join(lines)

    async def pre_recall(
        self,
        query: str,
        *,
        limit: int = 6,
        max_profile_items: int = 4,
    ) -> Dict[str, Any]:
        """
        Lifecycle hook: query memory before LLM execution.

        Returns a dual-profile payload plus formatted prompt block for system
        prompt injection.
        """
        memories = await self.search(query=query, include_shared=True, limit=limit)

        static_profile: List[str] = []
        dynamic_profile: List[str] = []
        context_memories: List[str] = []

        for entry in memories:
            content = entry.content.strip()
            if not content:
                continue

            if self._is_static_profile_entry(entry) and len(static_profile) < max_profile_items:
                static_profile.append(content)
            elif self._is_dynamic_profile_entry(entry) and len(dynamic_profile) < max_profile_items:
                dynamic_profile.append(content)
            else:
                context_memories.append(content)

        prompt_block = self.format_dual_profile_prompt(
            static_profile=static_profile,
            dynamic_profile=dynamic_profile,
            context_memories=context_memories[:max_profile_items],
        )

        return {
            "static_profile": static_profile,
            "dynamic_profile": dynamic_profile,
            "context_memories": context_memories,
            "prompt_block": prompt_block,
            "memory_count": len(memories),
        }

    def extract_candidate_facts(
        self,
        user_message: str,
        assistant_response: str,
        *,
        max_facts: int = 5,
    ) -> List[str]:
        """
        Lightweight fact extraction for postResponse capture.
        """
        text = f"{user_message}\n{assistant_response}".strip()
        if not text:
            return []

        candidates = re.split(r"[.!?]\s+|\n+", text)
        keep_tokens = [
            "prefer",
            "only",
            "always",
            "wallet",
            "solana",
            "risk",
            "focus",
            "currently",
            "research",
            "strategy",
            "trade",
        ]

        facts: List[str] = []
        seen = set()
        for raw in candidates:
            sentence = raw.strip(" -\t\r\n")
            if len(sentence) < 20:
                continue
            lowered = sentence.lower()
            if not any(token in lowered for token in keep_tokens):
                continue
            normalized = " ".join(sentence.split())
            if normalized.lower() in seen:
                continue
            seen.add(normalized.lower())
            facts.append(normalized)
            if len(facts) >= max_facts:
                break

        return facts

    async def post_response(
        self,
        *,
        user_message: str,
        assistant_response: str,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Lifecycle hook: capture and persist facts after response generation.
        """
        if not self.is_available:
            return False

        meta = metadata or {}
        conversation_fingerprint = hashlib.sha256(
            f"{self.bot_name}:{user_message}:{assistant_response}".encode("utf-8")
        ).hexdigest()
        custom_id = f"conversation:{conversation_fingerprint[:32]}"

        convo_text = (
            f"user: {user_message.strip()}\n"
            f"assistant: {assistant_response.strip()}"
        )

        saved_conversation = await self.add_with_container_tag(
            content=convo_text,
            container_tag=self.user_id_mid,
            custom_id=custom_id,
            metadata={
                "hook": "postResponse",
                "conversation_id": conversation_id or datetime.now(timezone.utc).isoformat(),
                **meta,
            },
        )

        facts = self.extract_candidate_facts(user_message, assistant_response)
        fact_writes = []
        for fact in facts:
            fact_profile_kind = "dynamic"
            lowered = fact.lower()
            if any(token in lowered for token in ["prefer", "always", "only", "strictly"]):
                fact_profile_kind = "static"
            fact_writes.append(
                self.add(
                    fact,
                    memory_type=MemoryType.LONG_TERM,
                    metadata={
                        "hook": "postResponse",
                        "profile_kind": fact_profile_kind,
                        "source": "fact_extraction",
                        **meta,
                    },
                )
            )

        fact_results = await asyncio.gather(*fact_writes, return_exceptions=True)
        facts_ok = any(r is True for r in fact_results) if fact_results else True
        return saved_conversation or facts_ok

    async def add_research_notebook(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        custom_id: Optional[str] = None,
    ) -> bool:
        """
        Store autonomous research output in a stable shared container.
        """
        return await self.add_with_container_tag(
            content=content,
            container_tag="research_notebooks",
            custom_id=custom_id,
            metadata={
                "source": "research_notebook",
                **(metadata or {}),
            },
        )

    async def ingest_conversation(
        self,
        messages: List[Dict[str, str]],
        conversation_id: Optional[str] = None,
    ) -> bool:
        """
        Ingest a conversation for memory extraction.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            conversation_id: Optional ID to link messages

        Returns:
            True if successful
        """
        if not self.is_available:
            return False

        # The supermemory SDK has changed across versions and may not expose a
        # dedicated "conversations" resource. We preserve the intent by storing
        # the conversation as a mid-term memory entry.
        try:
            convo_text = "\n".join(
                f"{m.get('role','').strip()}: {m.get('content','').strip()}"
                for m in messages
                if m.get("content")
            )
            if not convo_text.strip():
                return False

            return await self.add(
                convo_text,
                memory_type=MemoryType.MID_TERM,
                metadata={
                    "bot_name": self.bot_name,
                    "conversation_id": conversation_id or datetime.now(timezone.utc).isoformat(),
                    "source": "conversation_ingest",
                },
            )
        except Exception as e:
            logger.warning(f"[{self.bot_name}] Failed to ingest conversation: {e}")
            return False

    def search_sync(
        self,
        query: str,
        limit: int = 5,
    ) -> List[MemoryEntry]:
        """Synchronous version of search."""
        if not self.is_available:
            return []

        client = self._get_sync_client()
        if not client:
            return []

        results = []
        try:
            response = client.search.memories(
                q=query,
                container_tag=self.user_id_long,
                limit=limit,
            )
            for item in getattr(response, 'results', []):
                entry = MemoryEntry(
                    content=(
                        getattr(item, 'memory', None)
                        or getattr(item, 'chunk', None)
                        or str(item)
                    ),
                    memory_type=MemoryType.LONG_TERM,
                    bot_name=self.bot_name,
                    timestamp=getattr(item, 'updated_at', ''),
                    metadata=getattr(item, 'metadata', {}),
                    score=float(getattr(item, 'similarity', 0.0) or 0.0),
                )
                results.append(entry)
        except Exception as e:
            logger.warning(f"[{self.bot_name}] Sync search failed: {e}")

        return results


# Global client cache
_clients: Dict[str, SupermemoryClient] = {}


def get_memory_client(bot_name: str) -> SupermemoryClient:
    """
    Get or create a memory client for a bot.

    Args:
        bot_name: Name of the bot (friday, matt, jarvis)

    Returns:
        SupermemoryClient instance
    """
    bot_name = bot_name.lower()
    if bot_name not in _clients:
        _clients[bot_name] = SupermemoryClient(bot_name=bot_name)
    return _clients[bot_name]


# Convenience functions for quick access
async def remember(bot_name: str, content: str, shared: bool = False) -> bool:
    """Quick function to add a memory."""
    client = get_memory_client(bot_name)
    if shared:
        return await client.add_shared_learning(content)
    return await client.add(content)


async def recall(bot_name: str, query: str, include_shared: bool = True) -> List[MemoryEntry]:
    """Quick function to search memories."""
    client = get_memory_client(bot_name)
    return await client.search(query, include_shared=include_shared)


async def get_context_for_query(bot_name: str, query: str) -> str:
    """Quick function to get LLM-ready context."""
    client = get_memory_client(bot_name)
    return await client.get_context(query)
