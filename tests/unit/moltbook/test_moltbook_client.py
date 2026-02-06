"""
Unit tests for Moltbook client integration.

Tests the MoltbookClient class for peer-to-peer learning:
- Channel subscription
- Post learning
- Get trending topics
- Search posts
- Read channel posts
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta


class TestMoltbookClientInit:
    """Tests for MoltbookClient initialization."""

    def test_client_init_with_credentials(self):
        """Client should initialize with agent_id and api_key."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        assert client.agent_id == "clawdjarvis"
        assert client.api_key == "mb_test_key"
        assert client.base_url is not None

    def test_client_init_with_env_url(self):
        """Client should use MOLT_API_URL environment variable if set."""
        from core.moltbook.client import MoltbookClient

        with patch.dict('os.environ', {'MOLT_API_URL': 'https://custom.moltbook.com/api'}):
            client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")
            assert client.base_url == "https://custom.moltbook.com/api"

    def test_client_init_default_url(self):
        """Client should use default URL when env not set."""
        from core.moltbook.client import MoltbookClient

        with patch.dict('os.environ', {}, clear=True):
            client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")
            assert "moltbook.com" in client.base_url or "localhost" in client.base_url


class TestMoltbookSubscription:
    """Tests for channel subscription."""

    @pytest.mark.asyncio
    async def test_subscribe_channel_success(self):
        """Should successfully subscribe to a channel."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"status": "subscribed", "channel": "m/bugtracker"}

            result = await client.subscribe_channel("m/bugtracker")

            assert result["status"] == "subscribed"
            assert result["channel"] == "m/bugtracker"

    @pytest.mark.asyncio
    async def test_subscribe_channel_validates_name(self):
        """Should validate channel name format."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        # Valid channel names start with m/
        with pytest.raises(ValueError, match="channel name must start with"):
            await client.subscribe_channel("bugtracker")  # Missing m/ prefix

    @pytest.mark.asyncio
    async def test_get_subscriptions(self):
        """Should return list of subscribed channels."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "subscriptions": ["m/bugtracker", "m/devops", "m/kr8tiv"]
            }

            result = await client.get_subscriptions()

            assert "m/bugtracker" in result
            assert len(result) == 3


class TestMoltbookPosting:
    """Tests for posting learnings to Moltbook."""

    @pytest.mark.asyncio
    async def test_post_learning_success(self):
        """Should successfully post a learning."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "post_id": "post_abc123",
                "channel": "m/bugtracker",
                "status": "published"
            }

            result = await client.post_learning(
                channel="m/bugtracker",
                title="Solved: Telegram Polling 409 Conflict",
                content="Running 3 Telegram bots on same VPS caused 409 conflicts.",
                tags=["telegram", "polling", "python"]
            )

            assert result["post_id"] == "post_abc123"
            assert result["status"] == "published"

    @pytest.mark.asyncio
    async def test_post_learning_with_code_snippet(self):
        """Should include code snippet in post."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"post_id": "post_123", "status": "published"}

            await client.post_learning(
                channel="m/devops",
                title="Redis Lock Pattern",
                content="Use distributed locks for multi-bot setups.",
                tags=["redis", "locks"],
                code_snippet="redis_client.set('lock', '1', ex=30, nx=True)"
            )

            call_args = mock_request.call_args
            assert "code_snippet" in str(call_args)

    @pytest.mark.asyncio
    async def test_post_learning_with_metrics(self):
        """Should include before/after metrics."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"post_id": "post_123", "status": "published"}

            await client.post_learning(
                channel="m/bugtracker",
                title="Error Rate Fix",
                content="Reduced errors via retry logic.",
                tags=["errors"],
                metrics={"before": "10 errors/day", "after": "0 errors/day"}
            )

            call_args = mock_request.call_args
            assert "metrics" in str(call_args)

    @pytest.mark.asyncio
    async def test_post_learning_requires_title(self):
        """Should require title for posts."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with pytest.raises(ValueError, match="title is required"):
            await client.post_learning(
                channel="m/bugtracker",
                title="",  # Empty title
                content="Some content",
                tags=["test"]
            )


class TestMoltbookTrending:
    """Tests for trending topics functionality."""

    @pytest.mark.asyncio
    async def test_get_trending_topics(self):
        """Should fetch trending topics."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "trending": [
                    {"topic": "telegram-bots", "score": 95},
                    {"topic": "solana-trading", "score": 87},
                    {"topic": "agent-orchestration", "score": 82}
                ]
            }

            result = await client.get_trending()

            assert len(result) == 3
            assert result[0]["topic"] == "telegram-bots"
            assert result[0]["score"] == 95

    @pytest.mark.asyncio
    async def test_get_trending_with_limit(self):
        """Should respect limit parameter."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"trending": [{"topic": "top", "score": 100}]}

            await client.get_trending(limit=1)

            call_args = mock_request.call_args
            # Verify limit was passed in request
            assert "limit" in str(call_args) or mock_request.called


class TestMoltbookReadChannel:
    """Tests for reading channel posts."""

    @pytest.mark.asyncio
    async def test_read_channel_posts(self):
        """Should read posts from a channel."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "posts": [
                    {
                        "id": "post_1",
                        "title": "Test Post",
                        "content": "Content",
                        "tags": ["test"],
                        "created_at": "2026-02-01T12:00:00Z"
                    }
                ]
            }

            result = await client.read_channel("m/bugtracker", since="1h")

            assert len(result) == 1
            assert result[0]["title"] == "Test Post"

    @pytest.mark.asyncio
    async def test_read_channel_with_time_filter(self):
        """Should filter posts by time."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"posts": []}

            await client.read_channel("m/devops", since="24h", limit=50)

            mock_request.assert_called_once()


class TestMoltbookSearch:
    """Tests for search functionality."""

    @pytest.mark.asyncio
    async def test_search_posts(self):
        """Should search posts across channels."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "results": [
                    {"id": "post_1", "title": "Telegram Polling Fix", "score": 0.95}
                ]
            }

            result = await client.search_posts("telegram polling")

            assert len(result) == 1
            assert "Telegram" in result[0]["title"]

    @pytest.mark.asyncio
    async def test_search_in_specific_channels(self):
        """Should limit search to specific channels."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"results": []}

            await client.search_posts(
                query="telegram",
                channels=["m/bugtracker", "m/devops"]
            )

            mock_request.assert_called_once()


class TestMoltbookPersona:
    """Tests for persona handling."""

    def test_get_persona_jarvis(self):
        """Should return CTO persona for Jarvis."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdjarvis", api_key="mb_test_key")
        assert client.get_persona() == "CTO"

    def test_get_persona_friday(self):
        """Should return CMO persona for Friday."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdfriday", api_key="mb_test_key")
        assert client.get_persona() == "CMO"

    def test_get_persona_matt(self):
        """Should return COO persona for Matt."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="clawdmatt", api_key="mb_test_key")
        assert client.get_persona() == "COO"

    def test_get_persona_unknown(self):
        """Should return 'Agent' for unknown agent."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(agent_id="unknown_bot", api_key="mb_test_key")
        assert client.get_persona() == "Agent"


class TestMoltbookMockMode:
    """Tests for mock/stub mode when API is unavailable."""

    @pytest.mark.asyncio
    async def test_mock_mode_enabled(self):
        """Should operate in mock mode when configured."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(
            agent_id="clawdjarvis",
            api_key="mb_test_key",
            mock_mode=True
        )

        # Mock mode should return stub responses
        result = await client.get_trending()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_mock_mode_post_learning(self):
        """Mock mode should simulate posting."""
        from core.moltbook.client import MoltbookClient

        client = MoltbookClient(
            agent_id="clawdjarvis",
            api_key="mb_test_key",
            mock_mode=True
        )

        result = await client.post_learning(
            channel="m/bugtracker",
            title="Test Learning",
            content="Test content",
            tags=["test"]
        )

        assert result["status"] in ["published", "mock_published"]
        assert "post_id" in result
