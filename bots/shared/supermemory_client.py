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
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}

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

    @staticmethod
    def _mesh_memory_label(memory_type: Optional[MemoryType], metadata: Optional[Dict[str, Any]]) -> str:
        if memory_type == MemoryType.SHORT_TERM:
            return "short"
        if memory_type == MemoryType.MID_TERM:
            return "mid"
        if memory_type == MemoryType.LONG_TERM:
            return "long"
        if memory_type == MemoryType.SHARED:
            return "shared"

        explicit = str((metadata or {}).get("memory_type", "")).strip().lower()
        if explicit in {"short", "short_term"}:
            return "short"
        if explicit in {"mid", "mid_term"}:
            return "mid"
        if explicit in {"long", "long_term"}:
            return "long"
        if explicit == "shared":
            return "shared"
        return "custom"

    @staticmethod
    def _hash_metadata(metadata: Dict[str, Any]) -> str:
        canonical = json.dumps(metadata, separators=(",", ":"), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _mesh_sync_enabled() -> bool:
        return _env_flag("JARVIS_USE_MESH_SYNC", _env_flag("JARVIS_MESH_SYNC_ENABLED", False))

    @staticmethod
    def _mesh_attestation_enabled() -> bool:
        return _env_flag("JARVIS_USE_MESH_ATTEST", _env_flag("JARVIS_MESH_ATTESTATION_ENABLED", False))

    async def _after_successful_write_emit_mesh(
        self,
        *,
        content: str,
        container_tag: str,
        metadata: Optional[Dict[str, Any]] = None,
        memory_type: Optional[MemoryType] = None,
        conversation_id: Optional[str] = None,
        source_hook: Optional[str] = None,
        emit_mesh: bool = True,
    ) -> Dict[str, Any]:
        """
        Post-write lifecycle: publish -> validate -> attest.

        Mesh failures never propagate back into the original memory write path.
        """
        meta = dict(metadata or {})
        if not emit_mesh:
            return {"status": "skipped", "reason": "emit_mesh_disabled"}
        if bool(meta.get("_mesh_internal")):
            return {"status": "skipped", "reason": "mesh_internal"}
        if not self._mesh_sync_enabled():
            return {"status": "skipped", "reason": "mesh_sync_disabled"}

        try:
            from services.compute.mesh_sync_service import get_mesh_sync_service
        except Exception as exc:
            logger.warning("[%s] Mesh sync import failed: %s", self.bot_name, exc)
            return {"status": "failed", "reason": "mesh_sync_import_failed", "error": str(exc)}

        mesh_sync_service = get_mesh_sync_service()
        event_id = str(meta.get("event_id") or uuid.uuid4().hex)
        normalized_source_hook = source_hook or str(meta.get("hook") or "").strip() or None
        state_delta = {
            "event_id": event_id,
            "bot_name": self.bot_name,
            "container_tag": container_tag,
            "memory_type": self._mesh_memory_label(memory_type, meta),
            "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "metadata_hash": self._hash_metadata(meta),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "conversation_id": conversation_id or meta.get("conversation_id"),
            "source_hook": normalized_source_hook,
            "schema_version": 1,
        }

        publish_result = await mesh_sync_service.publish_state_delta(state_delta)
        if not bool(publish_result.get("published")):
            return {
                "status": str(publish_result.get("status", "pending_publish")),
                "event_id": event_id,
                "state_hash": publish_result.get("state_hash"),
                "reason": publish_result.get("reason"),
            }

        envelope = publish_result.get("envelope")
        if not isinstance(envelope, dict):
            mesh_sync_service.record_outbox_event(
                event_id=event_id,
                status="invalid_envelope",
                state_hash=str(publish_result.get("state_hash") or ""),
                state_delta=state_delta,
                reason="missing_envelope",
            )
            return {"status": "invalid_envelope", "event_id": event_id, "reason": "missing_envelope"}

        is_valid, validation_reason = mesh_sync_service.validate_envelope(envelope)
        if not is_valid:
            mesh_sync_service.record_outbox_event(
                event_id=event_id,
                status="invalid_envelope",
                state_hash=str(publish_result.get("state_hash") or envelope.get("state_hash") or ""),
                state_delta=state_delta,
                envelope=envelope,
                reason=validation_reason,
            )
            return {"status": "invalid_envelope", "event_id": event_id, "reason": validation_reason}

        state_hash = str(envelope.get("state_hash") or publish_result.get("state_hash") or "").strip()
        if not self._mesh_attestation_enabled():
            return {"status": "published", "event_id": event_id, "state_hash": state_hash}

        try:
            from services.compute.mesh_attestation_service import get_mesh_attestation_service
        except Exception as exc:
            mesh_sync_service.record_outbox_event(
                event_id=event_id,
                status="pending_commit",
                state_hash=state_hash,
                state_delta=state_delta,
                envelope=envelope,
                reason=f"attestation_import_failed:{exc}",
            )
            return {"status": "pending_commit", "event_id": event_id, "state_hash": state_hash, "error": str(exc)}

        attestation_service = get_mesh_attestation_service()
        commit_result = await attestation_service.commit_state_hash(
            state_hash,
            event_id=event_id,
            node_pubkey=self.bot_name,
            metadata={
                "container_tag": container_tag,
                "memory_type": state_delta["memory_type"],
                "source_hook": state_delta.get("source_hook"),
            },
        )
        if str(commit_result.get("status")) == "committed":
            mesh_sync_service.record_outbox_event(
                event_id=event_id,
                status="committed",
                state_hash=state_hash,
                state_delta=state_delta,
                envelope=envelope,
            )
            return {
                "status": "committed",
                "event_id": event_id,
                "state_hash": state_hash,
                "signature": commit_result.get("signature"),
            }

        mesh_sync_service.record_outbox_event(
            event_id=event_id,
            status="pending_commit",
            state_hash=state_hash,
            state_delta=state_delta,
            envelope=envelope,
            reason=str(commit_result.get("error") or commit_result.get("reason") or "commit_failed"),
        )
        return {
            "status": "pending_commit",
            "event_id": event_id,
            "state_hash": state_hash,
            "reason": commit_result.get("reason"),
            "error": commit_result.get("error"),
        }

    async def add(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        emit_mesh: bool = True,
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
            if bool(meta.get("_mesh_internal")):
                return True
            try:
                await self._after_successful_write_emit_mesh(
                    content=content,
                    container_tag=user_id,
                    metadata=meta,
                    memory_type=memory_type,
                    conversation_id=meta.get("conversation_id"),
                    source_hook=str(meta.get("hook") or "").strip() or None,
                    emit_mesh=emit_mesh,
                )
            except Exception as mesh_exc:
                logger.warning(f"[{self.bot_name}] Mesh lifecycle failed after add(): {mesh_exc}")
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
        *,
        emit_mesh: bool = True,
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
            if not bool(meta.get("_mesh_internal")):
                try:
                    await self._after_successful_write_emit_mesh(
                        content=content,
                        container_tag=container_tag,
                        metadata=meta,
                        memory_type=None,
                        conversation_id=meta.get("conversation_id"),
                        source_hook=str(meta.get("hook") or "").strip() or None,
                        emit_mesh=emit_mesh,
                    )
                except Exception as mesh_exc:
                    logger.warning(f"[{self.bot_name}] Mesh lifecycle failed after add_with_container_tag(): {mesh_exc}")
            return True
        except TypeError:
            # Some SDK versions do not support customId. Preserve dedupe signal
            # in metadata and retry without the unsupported argument.
            kwargs.pop("customId", None)
            if custom_id:
                meta.setdefault("custom_id", custom_id)
            try:
                await client.memories.add(**kwargs)
                if not bool(meta.get("_mesh_internal")):
                    try:
                        await self._after_successful_write_emit_mesh(
                            content=content,
                            container_tag=container_tag,
                            metadata=meta,
                            memory_type=None,
                            conversation_id=meta.get("conversation_id"),
                            source_hook=str(meta.get("hook") or "").strip() or None,
                            emit_mesh=emit_mesh,
                        )
                    except Exception as mesh_exc:
                        logger.warning(
                            f"[{self.bot_name}] Mesh lifecycle failed after add_with_container_tag() retry: {mesh_exc}"
                        )
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

        payload = {
            "static_profile": static_profile,
            "dynamic_profile": dynamic_profile,
            "context_memories": context_memories,
            "prompt_block": prompt_block,
            "memory_count": len(memories),
        }
        _record_hook_telemetry(
            self.bot_name,
            "pre_recall",
            {
                "query": query,
                "memory_count": len(memories),
                "static_profile": list(static_profile),
                "dynamic_profile": list(dynamic_profile),
                "context_count": len(context_memories),
            },
        )
        return payload

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
        success = saved_conversation or facts_ok
        _record_hook_telemetry(
            self.bot_name,
            "post_response",
            {
                "conversation_id": conversation_id,
                "saved_conversation": bool(saved_conversation),
                "facts_count": len(facts),
                "facts_extracted": list(facts),
                "success": bool(success),
            },
        )
        return success

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
_hook_telemetry: Dict[str, Dict[str, Any]] = {}


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


def _record_hook_telemetry(bot_name: str, hook_name: str, payload: Dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    entry = dict(payload)
    entry["timestamp"] = now

    bot_map = _hook_telemetry.setdefault(bot_name, {})
    bot_map[hook_name] = entry


def get_hook_telemetry(bot_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Read latest hook telemetry for operator diagnostics.

    If bot_name is omitted, prefer `jarvis` and otherwise return first available.
    """
    if bot_name:
        return dict(_hook_telemetry.get(bot_name.lower(), {}))
    if "jarvis" in _hook_telemetry:
        return dict(_hook_telemetry["jarvis"])
    if _hook_telemetry:
        first_bot = next(iter(_hook_telemetry))
        return dict(_hook_telemetry[first_bot])
    return {}


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
