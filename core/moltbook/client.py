"""
Moltbook Client - Peer-to-peer learning API client.

Connects to NotebookLM-style knowledge bases for:
- Channel subscription and reading
- Posting learnings
- Searching across channels
- Trending topic discovery

TODO: MCP Integration Points marked with # TODO: MCP
Currently operates in mock mode until NotebookLM MCP is available.
"""

import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Agent persona mapping
AGENT_PERSONAS = {
    "clawdjarvis": "CTO",
    "jarvis": "CTO",
    "clawdfriday": "CMO",
    "friday": "CMO",
    "clawdmatt": "COO",
    "matt": "COO",
}

# Default API URL
DEFAULT_API_URL = "https://api.moltbook.com/v1"


class MoltbookClient:
    """
    Client for interacting with Moltbook knowledge base API.

    Supports mock mode for testing and development when API is unavailable.

    TODO: MCP - Replace HTTP calls with MCP tool invocations when NotebookLM
    MCP server is available.
    """

    def __init__(
        self,
        agent_id: str,
        api_key: str,
        base_url: Optional[str] = None,
        mock_mode: bool = False,
    ):
        """
        Initialize Moltbook client.

        Args:
            agent_id: Unique identifier for this agent (e.g., "clawdjarvis")
            api_key: API key for authentication
            base_url: Optional custom API URL (defaults to env or standard URL)
            mock_mode: If True, return stub responses without API calls
        """
        self.agent_id = agent_id
        self.api_key = api_key
        self.mock_mode = mock_mode

        # Determine base URL from env or default
        if base_url:
            self.base_url = base_url
        else:
            self.base_url = os.environ.get("MOLT_API_URL", DEFAULT_API_URL)

        # Mock data storage (in-memory for mock mode)
        self._mock_posts: List[Dict[str, Any]] = []
        self._mock_subscriptions: List[str] = []

        logger.info(
            f"MoltbookClient initialized for {agent_id} "
            f"(mock_mode={mock_mode}, url={self.base_url})"
        )

    def get_persona(self) -> str:
        """
        Get the persona/role for this agent.

        Returns:
            Role string (CTO, CMO, COO, or Agent for unknown)
        """
        # Try exact match first
        if self.agent_id in AGENT_PERSONAS:
            return AGENT_PERSONAS[self.agent_id]

        # Try partial match (e.g., "clawdjarvis" contains "jarvis")
        agent_lower = self.agent_id.lower()
        for key, persona in AGENT_PERSONAS.items():
            if key in agent_lower or agent_lower in key:
                return persona

        return "Agent"

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an API request to Moltbook.

        TODO: MCP - This method will be replaced with MCP tool calls.
        Currently returns mock data.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Optional request body data

        Returns:
            API response as dictionary
        """
        # TODO: MCP - Replace with actual MCP NotebookLM integration
        # Example future implementation:
        # return await mcp.invoke("notebooklm", {
        #     "action": endpoint,
        #     "params": data
        # })

        logger.debug(f"Mock request: {method} {endpoint} data={data}")

        # For now, return empty response (mock mode handles specifics)
        return {}

    async def subscribe_channel(self, channel: str) -> Dict[str, Any]:
        """
        Subscribe to a Moltbook channel.

        Args:
            channel: Channel name (must start with "m/")

        Returns:
            Subscription confirmation

        Raises:
            ValueError: If channel name is invalid
        """
        # Validate channel name format
        if not channel.startswith("m/"):
            raise ValueError(f"channel name must start with 'm/' - got: {channel}")

        if self.mock_mode:
            self._mock_subscriptions.append(channel)
            return {"status": "subscribed", "channel": channel}

        return await self._make_request(
            "POST",
            "/channels/subscribe",
            {"channel": channel, "agent_id": self.agent_id}
        )

    async def get_subscriptions(self) -> List[str]:
        """
        Get list of subscribed channels.

        Returns:
            List of channel names
        """
        if self.mock_mode:
            return self._mock_subscriptions.copy()

        result = await self._make_request("GET", "/channels/subscriptions")
        return result.get("subscriptions", [])

    async def post_learning(
        self,
        channel: str,
        title: str,
        content: str,
        tags: List[str],
        code_snippet: Optional[str] = None,
        metrics: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Post a learning to a channel.

        Args:
            channel: Target channel (e.g., "m/bugtracker")
            title: Post title (required, non-empty)
            content: Post content/body
            tags: List of tags for categorization
            code_snippet: Optional code example
            metrics: Optional before/after metrics

        Returns:
            Post confirmation with post_id

        Raises:
            ValueError: If title is empty
        """
        if not title or not title.strip():
            raise ValueError("title is required and cannot be empty")

        post_data = {
            "channel": channel,
            "title": title,
            "content": content,
            "tags": tags,
            "agent_id": self.agent_id,
            "persona": self.get_persona(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if code_snippet:
            post_data["code_snippet"] = code_snippet

        if metrics:
            post_data["metrics"] = metrics

        if self.mock_mode:
            post_id = f"mock_post_{uuid.uuid4().hex[:8]}"
            self._mock_posts.append({**post_data, "id": post_id})
            return {
                "post_id": post_id,
                "channel": channel,
                "status": "mock_published"
            }

        return await self._make_request("POST", "/posts", post_data)

    async def get_trending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get trending topics across Moltbook.

        Args:
            limit: Maximum number of topics to return

        Returns:
            List of trending topics with scores
        """
        if self.mock_mode:
            # Return mock trending data
            return [
                {"topic": "telegram-bots", "score": 95},
                {"topic": "solana-trading", "score": 87},
                {"topic": "agent-orchestration", "score": 82},
            ][:limit]

        result = await self._make_request(
            "GET",
            "/trending",
            {"limit": limit}
        )
        return result.get("trending", [])

    async def read_channel(
        self,
        channel: str,
        since: str = "24h",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Read recent posts from a channel.

        Args:
            channel: Channel to read from
            since: Time filter (e.g., "1h", "24h", "7d")
            limit: Maximum posts to return

        Returns:
            List of posts
        """
        if self.mock_mode:
            # Return mock posts filtered by channel
            return [
                p for p in self._mock_posts
                if p.get("channel") == channel
            ][:limit]

        result = await self._make_request(
            "GET",
            f"/channels/{channel}/posts",
            {"since": since, "limit": limit}
        )
        return result.get("posts", [])

    async def search_posts(
        self,
        query: str,
        channels: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search posts across channels.

        Args:
            query: Search query string
            channels: Optional list of channels to search in
            limit: Maximum results to return

        Returns:
            List of matching posts with relevance scores
        """
        if self.mock_mode:
            # Simple mock search - match query in title/content
            query_lower = query.lower()
            results = []
            for post in self._mock_posts:
                title = post.get("title", "").lower()
                content = post.get("content", "").lower()
                if query_lower in title or query_lower in content:
                    results.append({
                        **post,
                        "score": 0.9 if query_lower in title else 0.7
                    })

            # Filter by channels if specified
            if channels:
                results = [r for r in results if r.get("channel") in channels]

            return results[:limit]

        search_data = {"query": query, "limit": limit}
        if channels:
            search_data["channels"] = channels

        result = await self._make_request("POST", "/search", search_data)
        return result.get("results", [])
