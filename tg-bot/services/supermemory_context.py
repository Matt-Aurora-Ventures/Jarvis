"""
Telegram -> Supermemory context bridge.

Goal: on each user prompt, retrieve the most relevant long-term context and
inject it into the LLM prompt (like a "user prompt submit hook").

This is intentionally lightweight:
- Retrieval only (default) to avoid spamming the memory store.
- Storage helpers exist but must be called explicitly.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    v = (os.environ.get(name, "") or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class SupermemoryHit:
    tag: str
    content: str
    score: float
    metadata: Dict[str, Any]


class SupermemoryContextBridge:
    def __init__(self):
        self.api_key = (os.environ.get("SUPERMEMORY_API_KEY") or "").strip()
        self.enabled = bool(self.api_key) and _env_bool("SUPERMEMORY_CONTEXT_ENABLED", True)

        # Tag strategy:
        # - per-chat tag for group-level memory
        # - optional per-user tag for preferences
        # - optional shared tag for cross-bot learnings
        self.shared_tag = (os.environ.get("SUPERMEMORY_SHARED_TAG") or "kr8tiv_shared").strip()
        self.chat_tag_prefix = (os.environ.get("SUPERMEMORY_TG_CHAT_PREFIX") or "tg_chat").strip()
        self.user_tag_prefix = (os.environ.get("SUPERMEMORY_TG_USER_PREFIX") or "tg_user").strip()

        self._client: Any = None

    def is_available(self) -> bool:
        return self.enabled

    def _get_client(self):
        if not self.is_available():
            return None
        if self._client is None:
            try:
                from supermemory import AsyncSupermemory
            except Exception as e:
                logger.debug(f"Supermemory import failed: {e}")
                return None
            self._client = AsyncSupermemory(api_key=self.api_key)
        return self._client

    def _tags_for(self, chat_id: Optional[int], user_id: Optional[int], include_shared: bool) -> List[str]:
        tags: List[str] = []
        if chat_id is not None:
            tags.append(f"{self.chat_tag_prefix}_{chat_id}")
        if user_id is not None:
            tags.append(f"{self.user_tag_prefix}_{user_id}")
        if include_shared and self.shared_tag:
            tags.append(self.shared_tag)
        # Stable de-dup while preserving order.
        seen = set()
        out: List[str] = []
        for t in tags:
            if t and t not in seen:
                out.append(t)
                seen.add(t)
        return out

    async def search(
        self,
        query: str,
        *,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        include_shared: bool = True,
        limit: int = 5,
        threshold: float = 0.0,
    ) -> List[SupermemoryHit]:
        client = self._get_client()
        if not client:
            return []

        hits: List[SupermemoryHit] = []
        for tag in self._tags_for(chat_id, user_id, include_shared):
            try:
                resp = await client.search.memories(
                    q=query,
                    container_tag=tag,
                    limit=limit,
                    search_mode="hybrid",
                    threshold=threshold,
                )
            except Exception as e:
                logger.debug(f"Supermemory search failed for {tag}: {e}")
                continue

            for item in getattr(resp, "results", []) or []:
                content = (
                    getattr(item, "memory", None)
                    or getattr(item, "chunk", None)
                    or getattr(item, "content", None)
                    or str(item)
                )
                if not content:
                    continue
                hits.append(
                    SupermemoryHit(
                        tag=tag,
                        content=str(content).strip(),
                        score=float(getattr(item, "similarity", 0.0) or 0.0),
                        metadata=dict(getattr(item, "metadata", {}) or {}),
                    )
                )

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[: max(1, limit * 2)]

    async def get_context(
        self,
        query: str,
        *,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        include_shared: bool = True,
        limit: int = 5,
        max_chars: int = 1800,
        threshold: float = 0.0,
    ) -> str:
        """Return a compact, LLM-ready context block."""
        hits = await self.search(
            query,
            chat_id=chat_id,
            user_id=user_id,
            include_shared=include_shared,
            limit=limit,
            threshold=threshold,
        )
        if not hits:
            return ""

        parts: List[str] = []
        used = 0
        for h in hits:
            line = f"[{h.tag}] {h.content}".strip()
            if not line:
                continue
            if used + len(line) + 1 > max_chars:
                break
            parts.append(line)
            used += len(line) + 1

        return "\n".join(parts).strip()

    async def add(
        self,
        content: str,
        *,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        tag: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Best-effort add. Call explicitly; we do not auto-ingest all messages."""
        client = self._get_client()
        if not client:
            return False

        target_tag = (tag or "").strip()
        if not target_tag:
            # Prefer per-chat when available, otherwise per-user.
            if chat_id is not None:
                target_tag = f"{self.chat_tag_prefix}_{chat_id}"
            elif user_id is not None:
                target_tag = f"{self.user_tag_prefix}_{user_id}"
            else:
                target_tag = self.shared_tag

        try:
            await client.add(
                content=content,
                container_tag=target_tag,
                metadata=metadata or {},
            )
            return True
        except Exception as e:
            logger.debug(f"Supermemory add failed ({target_tag}): {e}")
            return False


_bridge: Optional[SupermemoryContextBridge] = None


def get_supermemory_bridge() -> SupermemoryContextBridge:
    global _bridge
    if _bridge is None:
        _bridge = SupermemoryContextBridge()
    return _bridge

