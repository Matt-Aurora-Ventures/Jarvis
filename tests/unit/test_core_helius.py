"""
Comprehensive unit tests for core/helius.py - Helius RPC/API integration.

Tests cover:
1. RPC Integration
   - Enhanced getTransaction
   - getAsset enriched data
   - getAssetBatch for multiple tokens
   - Account history queries

2. WebSocket Subscriptions
   - Subscribe to account changes
   - Subscribe to token transfers
   - Parse transaction events
   - Reconnection handling

3. Webhook Management
   - Create webhooks for addresses
   - Update webhook configuration
   - Delete webhooks
   - Webhook delivery verification

4. Token Metadata
   - Fetch NFT metadata
   - Fetch fungible token metadata
   - Parse metadata JSON
   - Cache metadata locally

5. Error Handling
   - Rate limiting (429)
   - API key validation
   - Network errors
   - Fallback to standard RPC
"""

import pytest
import asyncio
import json
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import sys
import aiohttp

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_api_key():
    """Provide a mock Helius API key."""
    return "test-helius-api-key-12345"


@pytest.fixture
def sample_transaction_data():
    """Sample enhanced transaction data from Helius API."""
    return {
        "signature": "5UfDuX7ZwNwLJw3yYe6C9ykPMwHx4MvnKq8qFJBvLG8DXYW9NFGepBMRzqGx3eVCjNQKEfMZJLxdVHJz8jGm3JVR",
        "slot": 123456789,
        "timestamp": 1704067200,
        "fee": 5000,
        "feePayer": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "type": "SWAP",
        "source": "JUPITER",
        "description": "Swapped 1 SOL for 10000 TEST tokens",
        "tokenTransfers": [
            {
                "mint": "TEST1111111111111111111111111111111111111111",
                "fromUserAccount": "LP_ADDRESS",
                "toUserAccount": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
                "tokenAmount": 10000.0,
            }
        ],
        "nativeTransfers": [
            {
                "fromUserAccount": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
                "toUserAccount": "LP_ADDRESS",
                "amount": 1000000000,
            }
        ],
        "accountData": [],
        "instructions": [],
    }


@pytest.fixture
def sample_asset_data():
    """Sample asset data from Helius getAsset API."""
    return {
        "interface": "FungibleToken",
        "id": "TEST1111111111111111111111111111111111111111",
        "content": {
            "json_uri": "https://example.com/metadata.json",
            "metadata": {
                "name": "Test Token",
                "symbol": "TEST",
                "description": "A test token for unit testing",
            },
            "files": [
                {"uri": "https://example.com/logo.png", "mime": "image/png"}
            ],
        },
        "authorities": [
            {"address": "AUTHORITY_ADDRESS", "scopes": ["full"]}
        ],
        "compression": {"compressed": False},
        "grouping": [],
        "royalty": {"basis_points": 0},
        "creators": [],
        "ownership": {
            "owner": "OWNER_ADDRESS",
            "delegated": False,
        },
        "supply": {"total": 1000000000, "circulating": 900000000},
        "mutable": True,
        "burnt": False,
        "token_info": {
            "decimals": 9,
            "supply": 1000000000,
            "mint_authority": "AUTHORITY_ADDRESS",
            "freeze_authority": None,
        },
    }


@pytest.fixture
def sample_webhook_data():
    """Sample webhook configuration."""
    return {
        "webhookID": "webhook-123-456",
        "webhookURL": "https://myapp.com/webhook",
        "transactionTypes": ["SWAP", "TRANSFER"],
        "accountAddresses": ["9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"],
        "webhookType": "enhanced",
        "authHeader": "Bearer test-token",
    }


def create_mock_response(status=200, json_data=None, text_data=None, headers=None):
    """Helper to create mock aiohttp response."""
    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.headers = headers or {}
    if json_data is not None:
        mock_response.json = AsyncMock(return_value=json_data)
    if text_data is not None:
        mock_response.text = AsyncMock(return_value=text_data)
    return mock_response


def create_mock_context_manager(response):
    """Helper to create async context manager for response."""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=response)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


# =============================================================================
# HeliusClient Initialization Tests
# =============================================================================

class TestHeliusClientInit:
    """Tests for HeliusClient initialization."""

    def test_init_with_api_key(self, mock_api_key, monkeypatch):
        """Test client initialization with API key."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient
        client = HeliusClient(api_key=mock_api_key)

        assert client.api_key == mock_api_key
        assert "helius" in client.rpc_url.lower()

    def test_init_with_custom_urls(self, mock_api_key, monkeypatch):
        """Test client initialization with custom URLs."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient
        custom_rpc = "https://custom-rpc.example.com"
        custom_api = "https://custom-api.example.com"

        client = HeliusClient(
            api_key=mock_api_key,
            rpc_url=custom_rpc,
            api_url=custom_api,
        )

        assert client.rpc_url == custom_rpc
        assert client.api_url == custom_api

    def test_init_from_environment(self, monkeypatch):
        """Test client initialization from environment variable."""
        from core.helius import HeliusClient

        # Mock _load_api_key to simulate loading from environment
        with patch("core.helius._load_api_key", return_value="env-api-key-789"):
            client = HeliusClient()
            assert client.api_key == "env-api-key-789"

    def test_init_no_api_key_raises(self, monkeypatch):
        """Test that missing API key raises ValueError."""
        from core.helius import HeliusClient

        # Mock _load_api_key to return None (no key found)
        with patch("core.helius._load_api_key", return_value=None):
            with pytest.raises(ValueError, match="API key"):
                HeliusClient()

    def test_init_sets_default_timeout(self, mock_api_key, monkeypatch):
        """Test default timeout configuration."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient
        client = HeliusClient(api_key=mock_api_key)

        assert client.timeout > 0
        assert client.timeout == 30

    def test_init_with_custom_timeout(self, mock_api_key, monkeypatch):
        """Test custom timeout configuration."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient
        client = HeliusClient(api_key=mock_api_key, timeout=60)

        assert client.timeout == 60


# =============================================================================
# RPC Integration Tests - getTransaction
# =============================================================================

class TestHeliusGetTransaction:
    """Tests for enhanced getTransaction API."""

    @pytest.mark.asyncio
    async def test_get_transaction_success(self, mock_api_key, sample_transaction_data, monkeypatch):
        """Test successful transaction fetch."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, [sample_transaction_data])
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        result = await client.get_transaction(sample_transaction_data["signature"])

        assert result is not None
        assert result["signature"] == sample_transaction_data["signature"]
        assert result["type"] == "SWAP"

    @pytest.mark.asyncio
    async def test_get_transaction_not_found(self, mock_api_key, monkeypatch):
        """Test transaction not found returns None."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, [])
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        result = await client.get_transaction("nonexistent-sig")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_transaction_api_error(self, mock_api_key, monkeypatch):
        """Test API error handling for get_transaction."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(500, text_data="Internal Server Error")
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        result = await client.get_transaction("any-sig")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_transaction_with_options(self, mock_api_key, sample_transaction_data, monkeypatch):
        """Test get_transaction with additional options."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, [sample_transaction_data])
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        result = await client.get_transaction(
            sample_transaction_data["signature"],
            commitment="finalized",
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_transactions_batch(self, mock_api_key, sample_transaction_data, monkeypatch):
        """Test fetching multiple transactions in batch."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        tx2 = sample_transaction_data.copy()
        tx2["signature"] = "second-signature-12345"

        mock_response = create_mock_response(200, [sample_transaction_data, tx2])
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        results = await client.get_transactions_batch([
            sample_transaction_data["signature"],
            "second-signature-12345",
        ])

        assert len(results) == 2


# =============================================================================
# RPC Integration Tests - getAsset
# =============================================================================

class TestHeliusGetAsset:
    """Tests for getAsset enriched data API."""

    @pytest.mark.asyncio
    async def test_get_asset_success(self, mock_api_key, sample_asset_data, monkeypatch):
        """Test successful asset data fetch."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"result": sample_asset_data})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        result = await client.get_asset(sample_asset_data["id"])

        assert result is not None
        assert result["interface"] == "FungibleToken"
        assert result["content"]["metadata"]["symbol"] == "TEST"

    @pytest.mark.asyncio
    async def test_get_asset_nft(self, mock_api_key, monkeypatch):
        """Test fetching NFT asset data."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        nft_data = {
            "interface": "V1_NFT",
            "id": "NFT1111111111111111111111111111111111111111",
            "content": {
                "json_uri": "https://arweave.net/nft-metadata.json",
                "metadata": {
                    "name": "Cool NFT #123",
                    "symbol": "CNFT",
                    "description": "A very cool NFT",
                },
                "files": [
                    {"uri": "https://arweave.net/image.png", "mime": "image/png"}
                ],
            },
            "royalty": {"basis_points": 500},
            "creators": [
                {"address": "CREATOR_ADDRESS", "share": 100}
            ],
        }

        mock_response = create_mock_response(200, {"result": nft_data})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        result = await client.get_asset(nft_data["id"])

        assert result["interface"] == "V1_NFT"
        assert result["royalty"]["basis_points"] == 500

    @pytest.mark.asyncio
    async def test_get_asset_not_found(self, mock_api_key, monkeypatch):
        """Test asset not found returns None."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"result": None})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        result = await client.get_asset("nonexistent-token")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_asset_batch_success(self, mock_api_key, sample_asset_data, monkeypatch):
        """Test fetching multiple assets in batch."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        asset2 = sample_asset_data.copy()
        asset2["id"] = "TOKEN2222222222222222222222222222222222222"
        asset2["content"] = sample_asset_data["content"].copy()
        asset2["content"]["metadata"] = sample_asset_data["content"]["metadata"].copy()
        asset2["content"]["metadata"]["symbol"] = "TOK2"

        mock_response = create_mock_response(200, {"result": [sample_asset_data, asset2]})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        results = await client.get_assets_batch([
            sample_asset_data["id"],
            asset2["id"],
        ])

        assert len(results) == 2
        assert results[0]["content"]["metadata"]["symbol"] == "TEST"
        assert results[1]["content"]["metadata"]["symbol"] == "TOK2"

    @pytest.mark.asyncio
    async def test_get_asset_batch_partial_failure(self, mock_api_key, sample_asset_data, monkeypatch):
        """Test batch where some assets don't exist."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"result": [sample_asset_data, None]})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        results = await client.get_assets_batch([
            sample_asset_data["id"],
            "nonexistent-token",
        ])

        valid_results = [r for r in results if r is not None]
        assert len(valid_results) == 1


# =============================================================================
# Account History Tests
# =============================================================================

class TestHeliusAccountHistory:
    """Tests for account history queries."""

    @pytest.mark.asyncio
    async def test_get_account_transactions(self, mock_api_key, sample_transaction_data, monkeypatch):
        """Test fetching account transaction history."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, [sample_transaction_data])
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.get.return_value = mock_cm

        results = await client.get_account_transactions(
            "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_account_transactions_with_limit(self, mock_api_key, monkeypatch):
        """Test account transactions with limit parameter."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        txs = [{"signature": f"sig-{i}"} for i in range(10)]

        mock_response = create_mock_response(200, txs)
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.get.return_value = mock_cm

        results = await client.get_account_transactions(
            "SOME_ADDRESS",
            limit=10,
        )

        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_get_account_transactions_with_type_filter(self, mock_api_key, monkeypatch):
        """Test filtering account transactions by type."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        swap_tx = {"signature": "swap-sig", "type": "SWAP"}

        mock_response = create_mock_response(200, [swap_tx])
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.get.return_value = mock_cm

        results = await client.get_account_transactions(
            "SOME_ADDRESS",
            tx_type="SWAP",
        )

        assert all(tx.get("type") == "SWAP" for tx in results)

    @pytest.mark.asyncio
    async def test_get_account_transactions_empty(self, mock_api_key, monkeypatch):
        """Test empty account history returns empty list."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, [])
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.get.return_value = mock_cm

        results = await client.get_account_transactions("NEW_ADDRESS")

        assert results == []


# =============================================================================
# WebSocket Subscription Tests
# =============================================================================

class TestHeliusWebSocket:
    """Tests for WebSocket subscriptions."""

    @pytest.mark.asyncio
    async def test_subscribe_account_changes(self, mock_api_key, monkeypatch):
        """Test subscribing to account changes."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.receive = AsyncMock(return_value=MagicMock(
            type=aiohttp.WSMsgType.TEXT,
            data=json.dumps({"jsonrpc": "2.0", "result": 1, "id": 1}),
        ))
        client._ws = mock_ws

        sub_id = await client.subscribe_account(
            "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
        )

        assert sub_id == 1
        mock_ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsubscribe_account(self, mock_api_key, monkeypatch):
        """Test unsubscribing from account changes."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.receive = AsyncMock(return_value=MagicMock(
            type=aiohttp.WSMsgType.TEXT,
            data=json.dumps({"jsonrpc": "2.0", "result": True, "id": 2}),
        ))
        client._ws = mock_ws
        client._subscriptions = {1: "account"}

        result = await client.unsubscribe(1)

        assert result is True
        mock_ws.send_json.assert_called_once()

    def test_parse_account_notification(self, mock_api_key, monkeypatch):
        """Test parsing account change notification."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)

        notification = {
            "jsonrpc": "2.0",
            "method": "accountNotification",
            "params": {
                "subscription": 1,
                "result": {
                    "context": {"slot": 12345},
                    "value": {
                        "data": ["base64data", "base64"],
                        "executable": False,
                        "lamports": 1000000000,
                        "owner": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                        "rentEpoch": 123,
                    },
                },
            },
        }

        result = client._parse_notification(notification)

        assert result is not None
        assert result["subscription_id"] == 1
        assert result["slot"] == 12345

    def test_websocket_reconnection(self, mock_api_key, monkeypatch):
        """Test WebSocket reconnection logic."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)
        client._reconnect_attempts = 0

        backoff = client._calculate_backoff()
        assert backoff >= 1

        client._reconnect_attempts = 3
        backoff = client._calculate_backoff()
        assert backoff >= 8

    def test_websocket_max_reconnect_reached(self, mock_api_key, monkeypatch):
        """Test behavior when max reconnect attempts reached."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)
        client._reconnect_attempts = 10

        backoff = client._calculate_backoff()
        assert backoff <= 60

    @pytest.mark.asyncio
    async def test_subscribe_token_transfers(self, mock_api_key, monkeypatch):
        """Test subscribing to token transfers for a mint."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.receive = AsyncMock(return_value=MagicMock(
            type=aiohttp.WSMsgType.TEXT,
            data=json.dumps({"jsonrpc": "2.0", "result": 2, "id": 1}),
        ))
        client._ws = mock_ws

        sub_id = await client.subscribe_token_transfers("TOKEN_MINT_ADDRESS")

        assert sub_id == 2


# =============================================================================
# Webhook Management Tests
# =============================================================================

class TestHeliusWebhooks:
    """Tests for webhook management API."""

    @pytest.mark.asyncio
    async def test_create_webhook_success(self, mock_api_key, sample_webhook_data, monkeypatch):
        """Test successful webhook creation."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, sample_webhook_data)
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        webhook = await client.create_webhook(
            url="https://myapp.com/webhook",
            addresses=["9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"],
            transaction_types=["SWAP", "TRANSFER"],
        )

        assert webhook is not None
        assert webhook["webhookID"] == "webhook-123-456"

    @pytest.mark.asyncio
    async def test_create_webhook_with_auth_header(self, mock_api_key, sample_webhook_data, monkeypatch):
        """Test webhook creation with auth header."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, sample_webhook_data)
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        webhook = await client.create_webhook(
            url="https://myapp.com/webhook",
            addresses=["ADDRESS"],
            auth_header="Bearer my-secret-token",
        )

        assert webhook["authHeader"] == "Bearer test-token"

    @pytest.mark.asyncio
    async def test_update_webhook(self, mock_api_key, sample_webhook_data, monkeypatch):
        """Test updating webhook configuration."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        updated_data = sample_webhook_data.copy()
        updated_data["webhookURL"] = "https://newapp.com/webhook"

        mock_response = create_mock_response(200, updated_data)
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.put.return_value = mock_cm

        result = await client.update_webhook(
            webhook_id="webhook-123-456",
            url="https://newapp.com/webhook",
        )

        assert result["webhookURL"] == "https://newapp.com/webhook"

    @pytest.mark.asyncio
    async def test_delete_webhook(self, mock_api_key, monkeypatch):
        """Test deleting a webhook."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"success": True})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.delete.return_value = mock_cm

        result = await client.delete_webhook("webhook-123-456")

        assert result is True

    @pytest.mark.asyncio
    async def test_list_webhooks(self, mock_api_key, sample_webhook_data, monkeypatch):
        """Test listing all webhooks."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, [sample_webhook_data])
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.get.return_value = mock_cm

        webhooks = await client.list_webhooks()

        assert len(webhooks) == 1
        assert webhooks[0]["webhookID"] == "webhook-123-456"

    @pytest.mark.asyncio
    async def test_get_webhook_by_id(self, mock_api_key, sample_webhook_data, monkeypatch):
        """Test getting a specific webhook by ID."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, sample_webhook_data)
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.get.return_value = mock_cm

        webhook = await client.get_webhook("webhook-123-456")

        assert webhook is not None
        assert webhook["webhookID"] == "webhook-123-456"


# =============================================================================
# Token Metadata Tests
# =============================================================================

class TestHeliusTokenMetadata:
    """Tests for token metadata fetching and caching."""

    @pytest.mark.asyncio
    async def test_get_token_metadata_success(self, mock_api_key, sample_asset_data, monkeypatch):
        """Test fetching token metadata."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"result": sample_asset_data})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        metadata = await client.get_token_metadata(sample_asset_data["id"])

        assert metadata is not None
        assert metadata["name"] == "Test Token"
        assert metadata["symbol"] == "TEST"

    @pytest.mark.asyncio
    async def test_get_token_metadata_cached(self, mock_api_key, sample_asset_data, monkeypatch):
        """Test that token metadata is cached."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"result": sample_asset_data})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm
        client._metadata_cache = {}

        # First call - should fetch
        metadata1 = await client.get_token_metadata(sample_asset_data["id"])

        # Second call - should use cache
        metadata2 = await client.get_token_metadata(sample_asset_data["id"])

        assert metadata1 == metadata2
        # Should only call API once
        assert client._session.post.call_count == 1

    @pytest.mark.asyncio
    async def test_get_token_metadata_cache_expiry(self, mock_api_key, sample_asset_data, monkeypatch):
        """Test that metadata cache expires correctly."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"result": sample_asset_data})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key, cache_ttl=60)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        # Pre-populate cache with expired entry
        expired_time = datetime.now() - timedelta(seconds=120)
        client._metadata_cache[sample_asset_data["id"]] = {
            "data": {"name": "Old Data", "symbol": "OLD"},
            "timestamp": expired_time,
        }

        metadata = await client.get_token_metadata(sample_asset_data["id"])

        # Should fetch fresh data
        assert metadata["name"] == "Test Token"

    @pytest.mark.asyncio
    async def test_parse_metadata_json(self, mock_api_key, monkeypatch):
        """Test parsing external metadata JSON."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        external_json = {
            "name": "External Token",
            "symbol": "EXT",
            "description": "A token with external metadata",
            "image": "https://example.com/image.png",
            "attributes": [
                {"trait_type": "rarity", "value": "rare"}
            ],
        }

        mock_response = create_mock_response(200, external_json)
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.get.return_value = mock_cm

        metadata = await client.fetch_external_metadata(
            "https://example.com/metadata.json"
        )

        assert metadata["name"] == "External Token"
        assert metadata["image"] == "https://example.com/image.png"

    @pytest.mark.asyncio
    async def test_get_token_metadata_not_found(self, mock_api_key, monkeypatch):
        """Test token metadata not found returns None."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"result": None})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        metadata = await client.get_token_metadata("nonexistent")
        assert metadata is None


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestHeliusErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_rate_limit_429_response(self, mock_api_key, monkeypatch):
        """Test handling 429 rate limit response."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient, HeliusRateLimitError

        mock_response = create_mock_response(429, text_data="Rate limited", headers={"Retry-After": "5"})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        with pytest.raises(HeliusRateLimitError):
            await client.get_transaction("any-sig")

    def test_rate_limit_backoff(self, mock_api_key, monkeypatch):
        """Test rate limit backoff logic."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)
        client._rate_limit_backoff = 0

        # Trigger rate limit
        client._record_rate_limit()

        assert client._rate_limit_backoff > 0

        # Second trigger should increase backoff
        first_backoff = client._rate_limit_backoff
        client._record_rate_limit()

        assert client._rate_limit_backoff > first_backoff

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, mock_api_key, monkeypatch):
        """Test handling invalid API key (401/403)."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient, HeliusAuthError

        mock_response = create_mock_response(401, text_data="Invalid API key")
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        with pytest.raises(HeliusAuthError):
            await client.get_transaction("any-sig")

    @pytest.mark.asyncio
    async def test_network_error(self, mock_api_key, monkeypatch):
        """Test handling network errors."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.side_effect = aiohttp.ClientError("Connection failed")

        result = await client.get_transaction("any-sig")
        assert result is None

    @pytest.mark.asyncio
    async def test_timeout_error(self, mock_api_key, monkeypatch):
        """Test handling timeout errors."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.side_effect = asyncio.TimeoutError()

        result = await client.get_transaction("any-sig")
        assert result is None

    @pytest.mark.asyncio
    async def test_json_decode_error(self, mock_api_key, monkeypatch):
        """Test handling malformed JSON response."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=json.JSONDecodeError("err", "", 0))

        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        result = await client.get_transaction("any-sig")
        assert result is None

    @pytest.mark.asyncio
    async def test_server_error_500(self, mock_api_key, monkeypatch):
        """Test handling 500 server error."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(500, text_data="Internal Server Error")
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        result = await client.get_transaction("any-sig")
        assert result is None


# =============================================================================
# Fallback to Standard RPC Tests
# =============================================================================

class TestHeliusFallback:
    """Tests for fallback to standard RPC."""

    @pytest.mark.asyncio
    async def test_fallback_on_helius_failure(self, mock_api_key, monkeypatch):
        """Test fallback to standard RPC when Helius fails."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        # First call fails
        mock_response_fail = create_mock_response(503)
        mock_cm_fail = create_mock_context_manager(mock_response_fail)

        # Fallback succeeds
        mock_response_success = create_mock_response(200, {"result": 12345})
        mock_cm_success = create_mock_context_manager(mock_response_success)

        client = HeliusClient(api_key=mock_api_key)
        client.fallback_rpc_url = "https://api.mainnet-beta.solana.com"
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.side_effect = [mock_cm_fail, mock_cm_success]

        result = await client.get_slot()

        # Should have tried fallback
        assert client._session.post.call_count == 2

    @pytest.mark.asyncio
    async def test_no_fallback_configured(self, mock_api_key, monkeypatch):
        """Test behavior when no fallback RPC is configured."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(503, text_data="Service Unavailable")
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client.fallback_rpc_url = None
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        result = await client.get_slot()
        assert result is None

    @pytest.mark.asyncio
    async def test_fallback_also_fails(self, mock_api_key, monkeypatch):
        """Test when both Helius and fallback fail."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(503, text_data="Service Unavailable")
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client.fallback_rpc_url = "https://api.mainnet-beta.solana.com"
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm  # Both fail

        result = await client.get_slot()
        assert result is None


# =============================================================================
# Session Management Tests
# =============================================================================

class TestHeliusSessionManagement:
    """Tests for session lifecycle management."""

    @pytest.mark.asyncio
    async def test_session_creation(self, mock_api_key, monkeypatch):
        """Test that session is created on connect."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)

        await client.connect()

        assert client._session is not None
        assert not client._session.closed

        await client.close()

    @pytest.mark.asyncio
    async def test_session_closure(self, mock_api_key, monkeypatch):
        """Test that session is properly closed."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)

        await client.connect()
        await client.close()

        assert client._session is None or client._session.closed

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_api_key, monkeypatch):
        """Test using client as async context manager."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        async with HeliusClient(api_key=mock_api_key) as client:
            assert client._session is not None

        # Session should be closed after exiting context
        assert client._session is None or client._session.closed

    @pytest.mark.asyncio
    async def test_multiple_close_calls_safe(self, mock_api_key, monkeypatch):
        """Test that multiple close calls don't raise errors."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        client = HeliusClient(api_key=mock_api_key)

        await client.connect()
        await client.close()
        await client.close()  # Should not raise
        await client.close()  # Should not raise


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestHeliusUtilities:
    """Tests for utility functions."""

    def test_has_api_key_true(self, monkeypatch):
        """Test has_api_key returns True when key exists."""
        monkeypatch.setenv("HELIUS_API_KEY", "test-key")
        import importlib
        import core.helius
        importlib.reload(core.helius)
        from core.helius import has_api_key

        assert has_api_key() is True

    def test_has_api_key_false(self, monkeypatch):
        """Test has_api_key returns False when no key."""
        from core.helius import has_api_key

        # Mock _load_api_key to return None (no key found)
        with patch("core.helius._load_api_key", return_value=None):
            assert has_api_key() is False

    def test_get_api_status(self, monkeypatch):
        """Test get_api_status returns correct info."""
        monkeypatch.setenv("HELIUS_API_KEY", "test-key")
        import importlib
        import core.helius
        importlib.reload(core.helius)
        from core.helius import get_api_status

        status = get_api_status()

        assert "has_api_key" in status
        assert "rate_limit" in status
        assert status["has_api_key"] is True

    def test_format_helius_url(self, mock_api_key, monkeypatch):
        """Test URL formatting with API key."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import format_helius_url

        url = format_helius_url("https://api.helius.xyz/v0/test", mock_api_key)

        assert mock_api_key in url
        assert "api-key" in url.lower()


# =============================================================================
# Priority Fee Estimation Tests
# =============================================================================

class TestHeliusPriorityFees:
    """Tests for priority fee estimation."""

    @pytest.mark.asyncio
    async def test_get_priority_fee_estimate(self, mock_api_key, monkeypatch):
        """Test fetching priority fee estimates."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {
            "result": {
                "priorityFeeLevels": {
                    "low": 100,
                    "medium": 500,
                    "high": 2000,
                    "veryHigh": 10000,
                }
            }
        })
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        fees = await client.get_priority_fee_estimate()

        assert fees is not None
        assert fees["low"] == 100
        assert fees["high"] == 2000

    @pytest.mark.asyncio
    async def test_get_priority_fee_for_accounts(self, mock_api_key, monkeypatch):
        """Test priority fees for specific accounts."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {
            "result": {
                "priorityFeeLevels": {
                    "low": 200,
                    "medium": 1000,
                    "high": 5000,
                }
            }
        })
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        fees = await client.get_priority_fee_estimate(
            accounts=["ACCOUNT1", "ACCOUNT2"]
        )

        assert fees is not None
        assert fees["medium"] == 1000


# =============================================================================
# Additional RPC Method Tests
# =============================================================================

class TestHeliusRPCMethods:
    """Tests for standard RPC methods via Helius."""

    @pytest.mark.asyncio
    async def test_get_balance(self, mock_api_key, monkeypatch):
        """Test getting account balance."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"result": {"value": 1000000000}})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        balance = await client.get_balance("ADDRESS")

        assert balance == 1000000000

    @pytest.mark.asyncio
    async def test_get_token_accounts(self, mock_api_key, monkeypatch):
        """Test getting token accounts for an owner."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {
            "result": {
                "value": [
                    {
                        "pubkey": "TOKEN_ACCOUNT_1",
                        "account": {
                            "data": {"parsed": {"info": {"mint": "TOKEN_MINT"}}},
                        },
                    }
                ]
            }
        })
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        accounts = await client.get_token_accounts_by_owner("OWNER")

        assert len(accounts) >= 1

    @pytest.mark.asyncio
    async def test_get_slot(self, mock_api_key, monkeypatch):
        """Test getting current slot."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"result": 123456789})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        slot = await client.get_slot()

        assert slot == 123456789

    @pytest.mark.asyncio
    async def test_get_block_height(self, mock_api_key, monkeypatch):
        """Test getting current block height."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"result": 98765432})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        height = await client.get_block_height()

        assert height == 98765432

    @pytest.mark.asyncio
    async def test_send_transaction(self, mock_api_key, monkeypatch):
        """Test sending a transaction."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        sig = "5UfDuX7ZwNwLJw3yYe6C9ykPMwHx4MvnKq8qFJBvLG8DXYW9NFGepBMRzqGx3eVCjNQKEfMZJLxdVHJz8jGm3JVR"
        mock_response = create_mock_response(200, {"result": sig})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        result = await client.send_transaction("base64_encoded_tx")

        assert result == sig


# =============================================================================
# DAS API Tests (Digital Asset Standard)
# =============================================================================

class TestHeliusDAS:
    """Tests for DAS (Digital Asset Standard) API methods."""

    @pytest.mark.asyncio
    async def test_search_assets(self, mock_api_key, monkeypatch):
        """Test searching for assets."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {
            "result": {
                "items": [
                    {"id": "ASSET1", "content": {"metadata": {"name": "Asset 1"}}},
                    {"id": "ASSET2", "content": {"metadata": {"name": "Asset 2"}}},
                ],
                "total": 2,
            }
        })
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        results = await client.search_assets(owner="OWNER_ADDRESS")

        assert len(results["items"]) == 2

    @pytest.mark.asyncio
    async def test_get_assets_by_owner(self, mock_api_key, monkeypatch):
        """Test getting all assets owned by an address."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {
            "result": {
                "items": [
                    {"id": "NFT1", "interface": "V1_NFT"},
                ],
                "total": 1,
            }
        })
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        assets = await client.get_assets_by_owner("OWNER")

        assert len(assets["items"]) == 1


# =============================================================================
# Result Classes Tests
# =============================================================================

class TestHeliusResultClasses:
    """Tests for result wrapper classes."""

    def test_helius_result_success(self, monkeypatch):
        """Test HeliusResult for success case."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusResult

        result = HeliusResult(
            success=True,
            data={"key": "value"},
            cached=False,
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_helius_result_failure(self, monkeypatch):
        """Test HeliusResult for failure case."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusResult

        result = HeliusResult(
            success=False,
            error="Connection failed",
            retryable=True,
        )

        assert result.success is False
        assert result.error == "Connection failed"
        assert result.retryable is True

    def test_helius_result_cached(self, monkeypatch):
        """Test HeliusResult for cached response."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusResult

        result = HeliusResult(
            success=True,
            data={"cached": "data"},
            cached=True,
        )

        assert result.cached is True


# =============================================================================
# Integration-Style Tests (with mocked external calls)
# =============================================================================

class TestHeliusIntegration:
    """Integration-style tests that verify full workflows."""

    @pytest.mark.asyncio
    async def test_full_transaction_flow(self, mock_api_key, sample_transaction_data, monkeypatch):
        """Test complete transaction fetch and parse flow."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, [sample_transaction_data])
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        # Fetch transaction
        tx = await client.get_transaction(sample_transaction_data["signature"])

        # Verify parsing
        assert tx is not None
        assert tx["type"] == "SWAP"
        assert len(tx["tokenTransfers"]) > 0
        assert tx["feePayer"] == "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"

    @pytest.mark.asyncio
    async def test_token_discovery_flow(self, mock_api_key, sample_asset_data, monkeypatch):
        """Test token discovery and metadata fetch flow."""
        monkeypatch.delenv("HELIUS_API_KEY", raising=False)
        from core.helius import HeliusClient

        mock_response = create_mock_response(200, {"result": sample_asset_data})
        mock_cm = create_mock_context_manager(mock_response)

        client = HeliusClient(api_key=mock_api_key)
        client._session = MagicMock()
        client._session.closed = False
        client._session.post.return_value = mock_cm

        # Get asset
        asset = await client.get_asset(sample_asset_data["id"])

        # Get metadata
        metadata = await client.get_token_metadata(sample_asset_data["id"])

        assert asset is not None
        assert metadata is not None
        assert metadata["symbol"] == "TEST"
