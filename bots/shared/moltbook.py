"""
Moltbook Integration Module for ClawdBots.

Provides a high-level API for knowledge base access:
- query_knowledge: Query NotebookLM-style knowledge bases
- store_learning: Store conversation learnings for future reference
- get_relevant_context: Get relevant context during conversations
- list_available_notebooks: List available knowledge bases
- search_learnings: Search stored learnings

Storage paths:
- Learnings: /root/clawdbots/moltbook_learnings.json (VPS) or local fallback
- Cache: /root/clawdbots/moltbook_cache.json (VPS) or local fallback

TODO: MCP Integration Points
- All query_knowledge calls will route through MCP when NotebookLM MCP is available
- Research mode will use MCP's extended context capabilities
- Cache invalidation will be MCP-event driven
"""

import os
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

# Import core moltbook modules
from core.moltbook.client import MoltbookClient
from core.moltbook.channels import (
    get_bot_channels,
    get_posting_rules,
    validate_channel_name,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Storage Path Configuration
# =============================================================================

# VPS paths (production)
VPS_LEARNINGS_PATH = Path("/root/clawdbots/moltbook_learnings.json")
VPS_CACHE_PATH = Path("/root/clawdbots/moltbook_cache.json")

# Local fallback paths (development/testing)
LOCAL_BASE = Path.home() / ".clawdbots"
LOCAL_LEARNINGS_PATH = LOCAL_BASE / "moltbook_learnings.json"
LOCAL_CACHE_PATH = LOCAL_BASE / "moltbook_cache.json"

# Cache settings
CACHE_TTL_HOURS = 24
MAX_CACHE_ENTRIES = 1000

# =============================================================================
# Path Helpers
# =============================================================================


def _get_learnings_path() -> Path:
    """
    Get the path for storing learnings.

    Uses VPS path if it exists, otherwise falls back to local.

    Returns:
        Path to learnings JSON file
    """
    if VPS_LEARNINGS_PATH.parent.exists():
        return VPS_LEARNINGS_PATH

    # Create local directory if needed
    LOCAL_BASE.mkdir(parents=True, exist_ok=True)
    return LOCAL_LEARNINGS_PATH


def _get_cache_path() -> Path:
    """
    Get the path for query cache.

    Uses VPS path if it exists, otherwise falls back to local.

    Returns:
        Path to cache JSON file
    """
    if VPS_CACHE_PATH.parent.exists():
        return VPS_CACHE_PATH

    # Create local directory if needed
    LOCAL_BASE.mkdir(parents=True, exist_ok=True)
    return LOCAL_CACHE_PATH


# =============================================================================
# Cache Functions
# =============================================================================


def _load_cache() -> Dict[str, Any]:
    """
    Load the query cache from disk.

    Returns:
        Cache dictionary with entries and metadata
    """
    cache_path = _get_cache_path()

    if not cache_path.exists():
        return {"entries": {}, "created_at": datetime.now(timezone.utc).isoformat()}

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load cache: {e}")
        return {"entries": {}, "created_at": datetime.now(timezone.utc).isoformat()}


def _save_cache(cache: Dict[str, Any]) -> None:
    """
    Save the query cache to disk.

    Args:
        cache: Cache dictionary to save
    """
    cache_path = _get_cache_path()

    try:
        # Ensure directory exists
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save cache: {e}")


def _get_cache_key(question: str, notebook_id: Optional[str] = None) -> str:
    """
    Generate a cache key for a query.

    Args:
        question: The query question
        notebook_id: Optional notebook ID

    Returns:
        MD5 hash as cache key
    """
    key_data = f"{question}:{notebook_id or 'all'}"
    return hashlib.md5(key_data.encode()).hexdigest()


def _is_cache_valid(entry: Dict[str, Any]) -> bool:
    """
    Check if a cache entry is still valid.

    Args:
        entry: Cache entry with timestamp

    Returns:
        True if entry is within TTL, False otherwise
    """
    if "cached_at" not in entry:
        return False

    try:
        cached_at = datetime.fromisoformat(entry["cached_at"].replace("Z", "+00:00"))
        expiry = cached_at + timedelta(hours=CACHE_TTL_HOURS)
        return datetime.now(timezone.utc) < expiry
    except (ValueError, KeyError):
        return False


# =============================================================================
# Learnings Storage Functions
# =============================================================================


def _load_learnings() -> Dict[str, Any]:
    """
    Load learnings from disk.

    Returns:
        Learnings dictionary with list of learnings
    """
    learnings_path = _get_learnings_path()

    if not learnings_path.exists():
        return {
            "learnings": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
        }

    try:
        with open(learnings_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load learnings: {e}")
        return {
            "learnings": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
        }


def _save_learnings(data: Dict[str, Any]) -> None:
    """
    Save learnings to disk.

    Args:
        data: Learnings dictionary to save
    """
    learnings_path = _get_learnings_path()

    try:
        # Ensure directory exists
        learnings_path.parent.mkdir(parents=True, exist_ok=True)

        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        with open(learnings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save learnings: {e}")


# =============================================================================
# Public API Functions
# =============================================================================


async def query_knowledge(
    question: str,
    notebook_id: Optional[str] = None,
    research_mode: bool = False,
) -> Dict[str, Any]:
    """
    Query knowledge base for information.

    TODO: MCP - This will route through NotebookLM MCP when available.
    Currently returns mock/cached responses.

    Args:
        question: The question to ask
        notebook_id: Optional specific notebook to query
        research_mode: If True, perform deeper multi-source research

    Returns:
        Dictionary with answer and metadata:
        - answer: The response text
        - sources: List of source references
        - mode: "standard" or "research"
        - cached: Whether result was from cache

    Example:
        >>> result = await query_knowledge("What causes 409 errors?")
        >>> print(result["answer"])
    """
    # Handle empty question
    if not question or not question.strip():
        return {
            "answer": "",
            "results": [],
            "sources": [],
            "mode": "research" if research_mode else "standard",
            "cached": False,
        }

    # Check cache first
    cache_key = _get_cache_key(question, notebook_id)
    cache = _load_cache()

    if cache_key in cache.get("entries", {}) and not research_mode:
        entry = cache["entries"][cache_key]
        if _is_cache_valid(entry):
            logger.debug(f"Cache hit for query: {question[:50]}...")
            return {**entry["result"], "cached": True}

    # TODO: MCP - Replace this mock implementation with MCP call
    # Example future implementation:
    # if mcp_available():
    #     result = await mcp.invoke("notebooklm", {
    #         "action": "query",
    #         "question": question,
    #         "notebook_id": notebook_id,
    #         "research_mode": research_mode
    #     })
    #     return result

    # Mock response for now
    result = {
        "answer": f"[Mock] Knowledge query: {question[:100]}",
        "results": [
            {
                "title": "Mock Result",
                "snippet": f"This is a mock response for: {question[:50]}...",
                "source": notebook_id or "general",
            }
        ],
        "sources": [notebook_id] if notebook_id else ["general_knowledge"],
        "mode": "research" if research_mode else "standard",
        "cached": False,
    }

    # Cache the result
    if not research_mode:  # Don't cache research mode results
        cache.setdefault("entries", {})
        cache["entries"][cache_key] = {
            "result": result,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        # Prune old entries if cache is too large
        if len(cache["entries"]) > MAX_CACHE_ENTRIES:
            # Remove oldest entries
            sorted_entries = sorted(
                cache["entries"].items(),
                key=lambda x: x[1].get("cached_at", ""),
            )
            cache["entries"] = dict(sorted_entries[-MAX_CACHE_ENTRIES:])

        _save_cache(cache)

    return result


async def store_learning(
    topic: str,
    content: str,
    source: str,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Store a learning for future reference.

    Learnings are persisted to JSON and can be searched/retrieved later.

    Args:
        topic: Topic/title of the learning
        content: Full content/description
        source: Source identifier (e.g., session ID, URL)
        tags: Optional list of tags for categorization

    Returns:
        Dictionary with:
        - success: Boolean indicating success
        - learning_id: Unique ID for the learning

    Example:
        >>> result = await store_learning(
        ...     topic="Telegram Polling Fix",
        ...     content="Use redis locks to prevent 409 conflicts",
        ...     source="bugfix-session-001",
        ...     tags=["telegram", "redis", "bugfix"]
        ... )
        >>> print(result["learning_id"])
    """
    learning_id = f"learn_{uuid.uuid4().hex[:12]}"

    learning = {
        "id": learning_id,
        "topic": topic,
        "content": content,
        "source": source,
        "tags": tags or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Load existing learnings
    data = _load_learnings()
    data["learnings"].append(learning)

    # Save updated learnings
    _save_learnings(data)

    logger.info(f"Stored learning: {learning_id} - {topic}")

    # TODO: MCP - Also sync to Moltbook channel when MCP is available
    # if mcp_available():
    #     await mcp.invoke("notebooklm", {
    #         "action": "store_learning",
    #         "learning": learning
    #     })

    return {
        "success": True,
        "learning_id": learning_id,
    }


async def get_relevant_context(
    user_message: str,
    max_learnings: int = 5,
) -> Dict[str, Any]:
    """
    Get relevant context for a user message.

    Searches stored learnings and knowledge bases to provide
    relevant context for the conversation.

    TODO: MCP - Will combine MCP knowledge with local learnings.

    Args:
        user_message: The user's message to get context for
        max_learnings: Maximum number of learnings to include

    Returns:
        Dictionary with:
        - context: Summary of relevant context
        - learnings: List of relevant learnings
        - knowledge: List of knowledge base hits

    Example:
        >>> context = await get_relevant_context("Help with Telegram bot")
        >>> print(context["learnings"])
    """
    if not user_message or not user_message.strip():
        return {
            "context": "",
            "learnings": [],
            "knowledge": [],
        }

    # Search local learnings
    learnings = await search_learnings(user_message)
    relevant_learnings = learnings[:max_learnings]

    # TODO: MCP - Also query knowledge base
    # if mcp_available():
    #     kb_results = await mcp.invoke("notebooklm", {
    #         "action": "search",
    #         "query": user_message,
    #         "limit": 3
    #     })
    # else:
    kb_results = []

    # Build context summary
    context_parts = []
    if relevant_learnings:
        context_parts.append(f"Found {len(relevant_learnings)} relevant learnings.")
    if kb_results:
        context_parts.append(f"Found {len(kb_results)} knowledge base matches.")

    return {
        "context": " ".join(context_parts) if context_parts else "No specific context found.",
        "learnings": relevant_learnings,
        "knowledge": kb_results,
    }


async def list_available_notebooks() -> List[Dict[str, Any]]:
    """
    List available knowledge base notebooks.

    TODO: MCP - Will return actual notebooks when MCP is connected.
    Currently returns mock/empty list.

    Returns:
        List of notebooks with id and name fields

    Example:
        >>> notebooks = await list_available_notebooks()
        >>> for nb in notebooks:
        ...     print(f"{nb['id']}: {nb['name']}")
    """
    # TODO: MCP - Fetch actual notebooks from NotebookLM
    # if mcp_available():
    #     result = await mcp.invoke("notebooklm", {
    #         "action": "list_notebooks"
    #     })
    #     return result["notebooks"]

    # Mock notebooks for development
    return [
        {"id": "nb_bugtracker", "name": "Bug Tracker Knowledge"},
        {"id": "nb_devops", "name": "DevOps Best Practices"},
        {"id": "nb_trading", "name": "Solana Trading Strategies"},
    ]


async def search_learnings(
    query: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Search stored learnings.

    Performs text matching on topic, content, and tags.

    Args:
        query: Search query string
        limit: Maximum results to return

    Returns:
        List of matching learnings sorted by relevance

    Example:
        >>> results = await search_learnings("telegram polling")
        >>> for r in results:
        ...     print(r["topic"])
    """
    if not query or not query.strip():
        return []

    data = _load_learnings()
    learnings = data.get("learnings", [])

    if not learnings:
        return []

    query_lower = query.lower()
    query_terms = query_lower.split()

    results = []
    for learning in learnings:
        topic = learning.get("topic", "").lower()
        content = learning.get("content", "").lower()
        tags = [t.lower() for t in learning.get("tags", [])]

        # Calculate simple relevance score
        score = 0

        # Topic match (highest weight)
        for term in query_terms:
            if term in topic:
                score += 3

        # Content match
        for term in query_terms:
            if term in content:
                score += 1

        # Tag match
        for term in query_terms:
            if any(term in tag for tag in tags):
                score += 2

        if score > 0:
            results.append({
                **learning,
                "relevance_score": score,
            })

    # Sort by relevance score
    results.sort(key=lambda x: x["relevance_score"], reverse=True)

    return results[:limit]


# =============================================================================
# Bot Integration Helpers
# =============================================================================


def get_bot_moltbook_client(
    bot_name: str,
    api_key: Optional[str] = None,
    mock_mode: bool = True,
) -> MoltbookClient:
    """
    Get a configured MoltbookClient for a specific bot.

    Args:
        bot_name: Bot identifier (jarvis, friday, matt)
        api_key: Optional API key (uses env var if not provided)
        mock_mode: Whether to use mock mode (default True until MCP ready)

    Returns:
        Configured MoltbookClient instance

    Example:
        >>> client = get_bot_moltbook_client("jarvis")
        >>> channels = get_bot_channels("jarvis")
    """
    # Get API key from environment if not provided
    if api_key is None:
        api_key = os.environ.get("MOLT_API_KEY", "mock_key")

    # Normalize bot name to agent_id format
    agent_id = f"clawd{bot_name.lower()}" if not bot_name.startswith("clawd") else bot_name.lower()

    return MoltbookClient(
        agent_id=agent_id,
        api_key=api_key,
        mock_mode=mock_mode,
    )


async def sync_learnings_to_moltbook(
    bot_name: str,
    learnings: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Sync local learnings to Moltbook channels.

    TODO: MCP - Will actually post to Moltbook when MCP is available.

    Args:
        bot_name: Bot performing the sync
        learnings: Optional list of learnings to sync (uses all if None)

    Returns:
        Sync result with count of synced items
    """
    # Get bot's allowed channels
    rules = get_posting_rules(bot_name)

    if learnings is None:
        data = _load_learnings()
        learnings = data.get("learnings", [])

    # TODO: MCP - Actually post to Moltbook
    # client = get_bot_moltbook_client(bot_name)
    # for learning in learnings:
    #     if not learning.get("synced_to_moltbook"):
    #         await client.post_learning(...)

    logger.info(f"Would sync {len(learnings)} learnings for {bot_name}")

    return {
        "synced_count": 0,  # 0 until MCP is available
        "pending_count": len(learnings),
        "status": "mock_sync",
    }
