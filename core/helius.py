"""
Helius RPC/API Integration for Solana.

Provides:
- Enhanced transaction data with human-readable parsing
- Asset metadata via DAS (Digital Asset Standard) API
- WebSocket subscriptions for real-time updates
- Webhook management for event notifications
- Token metadata fetching with local caching
- Priority fee estimation
- Standard RPC methods with automatic fallback

Usage:
    from core.helius import HeliusClient, has_api_key

    if has_api_key():
        async with HeliusClient() as client:
            tx = await client.get_transaction(signature)
            asset = await client.get_asset(mint_address)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

import aiohttp

logger = logging.getLogger(__name__)

# Constants
ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "helius_cache"
DEFAULT_RPC_URL = "https://mainnet.helius-rpc.com"
DEFAULT_API_URL = "https://api.helius.xyz"
DEFAULT_TIMEOUT = 30
DEFAULT_CACHE_TTL = 300  # 5 minutes

# Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE = 100
_request_timestamps: List[float] = []
_rate_limit_backoff: float = 0
_last_rate_limit_time: float = 0


# =============================================================================
# Custom Exceptions
# =============================================================================

class HeliusError(Exception):
    """Base exception for Helius errors."""
    pass


class HeliusRateLimitError(HeliusError):
    """Raised when rate limit (429) is hit."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = f"Rate limited. Retry after {retry_after}s" if retry_after else "Rate limited"
        super().__init__(message)


class HeliusAuthError(HeliusError):
    """Raised when authentication fails (401/403)."""
    pass


# =============================================================================
# Result Wrappers
# =============================================================================

@dataclass
class HeliusResult:
    """Result wrapper for Helius API calls."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    cached: bool = False
    retryable: bool = True


# =============================================================================
# Utility Functions
# =============================================================================

def _load_api_key() -> Optional[str]:
    """Load API key from secrets file or environment."""
    secrets_path = ROOT / "secrets" / "keys.json"
    if secrets_path.exists():
        try:
            data = json.loads(secrets_path.read_text())
            key = data.get("helius", {}).get("api_key")
            if key:
                return key
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load Helius key from secrets: {e}")

    env_key = os.getenv("HELIUS_API_KEY")
    if env_key:
        return env_key

    logger.debug("No Helius API key found")
    return None


def has_api_key() -> bool:
    """Return True if a Helius API key is configured."""
    return bool(_load_api_key())


def get_api_status() -> Dict[str, Any]:
    """Get current API status including rate limit info."""
    now = time.time()
    cutoff = now - 60
    recent_requests = len([t for t in _request_timestamps if t > cutoff])

    return {
        "has_api_key": has_api_key(),
        "requests_last_minute": recent_requests,
        "rate_limit": RATE_LIMIT_REQUESTS_PER_MINUTE,
        "rate_limit_backoff": _rate_limit_backoff if _rate_limit_backoff > 0 else None,
        "base_rpc_url": DEFAULT_RPC_URL,
        "base_api_url": DEFAULT_API_URL,
    }


def format_helius_url(base_url: str, api_key: str) -> str:
    """Format a URL with the Helius API key."""
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}api-key={api_key}"


# =============================================================================
# HeliusClient
# =============================================================================

class HeliusClient:
    """
    Async client for Helius RPC and API endpoints.

    Supports:
    - Enhanced transaction parsing
    - DAS (Digital Asset Standard) API
    - WebSocket subscriptions
    - Webhook management
    - Priority fee estimation
    - Automatic fallback to public RPC
    """

    # WebSocket reconnection settings
    INITIAL_BACKOFF_SECONDS = 1
    MAX_BACKOFF_SECONDS = 60
    BACKOFF_MULTIPLIER = 2

    def __init__(
        self,
        api_key: Optional[str] = None,
        rpc_url: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        fallback_rpc_url: Optional[str] = None,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ):
        """
        Initialize Helius client.

        Args:
            api_key: Helius API key. If not provided, loads from env.
            rpc_url: Custom RPC URL. Defaults to Helius mainnet.
            api_url: Custom API URL. Defaults to Helius API.
            timeout: Request timeout in seconds.
            fallback_rpc_url: Fallback RPC URL if Helius fails.
            cache_ttl: Cache TTL in seconds.
        """
        self.api_key = api_key or _load_api_key()
        if not self.api_key:
            raise ValueError(
                "Helius API key required. Set HELIUS_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.rpc_url = rpc_url or f"{DEFAULT_RPC_URL}/?api-key={self.api_key}"
        self.api_url = api_url or DEFAULT_API_URL
        self.timeout = timeout
        self.fallback_rpc_url = fallback_rpc_url
        self._cache_ttl = cache_ttl

        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None

        # WebSocket state
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._subscriptions: Dict[int, str] = {}

        # Caching
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}

        # Rate limiting
        self._rate_limit_backoff = 0
        self._last_rate_limit_time = 0

    # =========================================================================
    # Session Management
    # =========================================================================

    async def connect(self) -> None:
        """Create HTTP session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        """Close HTTP session and WebSocket."""
        if self._ws and not self._ws.closed:
            await self._ws.close()
            self._ws = None

        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "HeliusClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    def _record_rate_limit(self) -> None:
        """Record that we hit a rate limit."""
        self._last_rate_limit_time = time.time()
        if self._rate_limit_backoff == 0:
            self._rate_limit_backoff = 5
        else:
            self._rate_limit_backoff = min(self._rate_limit_backoff * 2, 60)
        logger.warning(f"Helius rate limit hit, backing off for {self._rate_limit_backoff:.1f}s")

    # =========================================================================
    # WebSocket Helpers
    # =========================================================================

    def _calculate_backoff(self) -> float:
        """Calculate exponential backoff delay."""
        delay = self.INITIAL_BACKOFF_SECONDS * (self.BACKOFF_MULTIPLIER ** self._reconnect_attempts)
        return min(delay, self.MAX_BACKOFF_SECONDS)

    def _parse_notification(self, notification: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a WebSocket notification."""
        if "params" not in notification:
            return None

        params = notification["params"]
        result = params.get("result", {})
        context = result.get("context", {})

        return {
            "subscription_id": params.get("subscription"),
            "slot": context.get("slot"),
            "value": result.get("value"),
        }

    # =========================================================================
    # HTTP Request Helpers
    # =========================================================================

    async def _ensure_session(self) -> None:
        """Ensure session is connected."""
        if self._session is None or self._session.closed:
            await self.connect()

    async def _make_rpc_request(
        self,
        method: str,
        params: List[Any],
        use_fallback: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Make a JSON-RPC request."""
        await self._ensure_session()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        try:
            async with self._session.post(self.rpc_url, json=payload) as resp:
                if resp.status == 429:
                    self._record_rate_limit()
                    raise HeliusRateLimitError(
                        retry_after=int(resp.headers.get("Retry-After", 5))
                    )

                if resp.status in (401, 403):
                    raise HeliusAuthError(await resp.text())

                if resp.status != 200:
                    if use_fallback and self.fallback_rpc_url:
                        return await self._make_fallback_request(method, params)
                    return None

                data = await resp.json()
                return data.get("result")

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Helius RPC error: {e}")
            if use_fallback and self.fallback_rpc_url:
                return await self._make_fallback_request(method, params)
            return None
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from Helius")
            return None

    async def _make_fallback_request(
        self,
        method: str,
        params: List[Any],
    ) -> Optional[Dict[str, Any]]:
        """Make request to fallback RPC."""
        if not self.fallback_rpc_url:
            return None

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        try:
            async with self._session.post(self.fallback_rpc_url, json=payload) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("result")
        except Exception as e:
            logger.error(f"Fallback RPC error: {e}")
            return None

    async def _make_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make a Helius API request."""
        await self._ensure_session()

        url = format_helius_url(f"{self.api_url}{endpoint}", self.api_key)

        try:
            if method == "GET":
                async with self._session.get(url, params=params) as resp:
                    return await self._handle_api_response(resp)
            elif method == "POST":
                async with self._session.post(url, json=json_body or params) as resp:
                    return await self._handle_api_response(resp)
            elif method == "PUT":
                async with self._session.put(url, json=json_body or params) as resp:
                    return await self._handle_api_response(resp)
            elif method == "DELETE":
                async with self._session.delete(url) as resp:
                    return await self._handle_api_response(resp)

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Helius API error: {e}")
            return None
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from Helius API")
            return None

        return None

    async def _handle_api_response(
        self,
        resp: aiohttp.ClientResponse,
    ) -> Optional[Dict[str, Any]]:
        """Handle API response with error checking."""
        if resp.status == 429:
            self._record_rate_limit()
            raise HeliusRateLimitError(
                retry_after=int(resp.headers.get("Retry-After", 5))
            )

        if resp.status in (401, 403):
            raise HeliusAuthError(await resp.text())

        if resp.status != 200:
            return None

        return await resp.json()

    # =========================================================================
    # Enhanced Transaction API
    # =========================================================================

    async def get_transaction(
        self,
        signature: str,
        commitment: str = "confirmed",
    ) -> Optional[Dict[str, Any]]:
        """
        Get enhanced transaction data.

        Args:
            signature: Transaction signature.
            commitment: Commitment level.

        Returns:
            Enhanced transaction data or None if not found.
        """
        await self._ensure_session()

        url = format_helius_url(f"{self.api_url}/v0/transactions/", self.api_key)
        payload = {"transactions": [signature]}

        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status == 429:
                    self._record_rate_limit()
                    raise HeliusRateLimitError()

                if resp.status in (401, 403):
                    raise HeliusAuthError(await resp.text())

                if resp.status != 200:
                    return None

                data = await resp.json()
                if data and len(data) > 0:
                    return data[0]
                return None

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Failed to get transaction {signature}: {e}")
            return None
        except json.JSONDecodeError:
            return None

    async def get_transactions_batch(
        self,
        signatures: List[str],
        commitment: str = "confirmed",
    ) -> List[Dict[str, Any]]:
        """
        Get enhanced transaction data for multiple signatures.

        Args:
            signatures: List of transaction signatures.
            commitment: Commitment level.

        Returns:
            List of enhanced transaction data.
        """
        await self._ensure_session()

        url = format_helius_url(f"{self.api_url}/v0/transactions/", self.api_key)
        payload = {"transactions": signatures}

        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                return data if data else []

        except Exception as e:
            logger.error(f"Failed to get transactions batch: {e}")
            return []

    # =========================================================================
    # DAS API - Digital Asset Standard
    # =========================================================================

    async def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """
        Get asset data using DAS API.

        Args:
            asset_id: Asset/token mint address.

        Returns:
            Asset data or None if not found.
        """
        await self._ensure_session()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAsset",
            "params": {"id": asset_id},
        }

        try:
            async with self._session.post(self.rpc_url, json=payload) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                return data.get("result")

        except Exception as e:
            logger.error(f"Failed to get asset {asset_id}: {e}")
            return None

    async def get_assets_batch(
        self,
        asset_ids: List[str],
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Get multiple assets using DAS API.

        Args:
            asset_ids: List of asset/token mint addresses.

        Returns:
            List of asset data (None for not found).
        """
        await self._ensure_session()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAssetBatch",
            "params": {"ids": asset_ids},
        }

        try:
            async with self._session.post(self.rpc_url, json=payload) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                result = data.get("result", [])
                return result if isinstance(result, list) else []

        except Exception as e:
            logger.error(f"Failed to get assets batch: {e}")
            return []

    async def get_assets_by_owner(
        self,
        owner: str,
        page: int = 1,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get all assets owned by an address.

        Args:
            owner: Owner wallet address.
            page: Page number.
            limit: Results per page.

        Returns:
            Dict with items and total count.
        """
        await self._ensure_session()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAssetsByOwner",
            "params": {
                "ownerAddress": owner,
                "page": page,
                "limit": limit,
            },
        }

        try:
            async with self._session.post(self.rpc_url, json=payload) as resp:
                if resp.status != 200:
                    return {"items": [], "total": 0}

                data = await resp.json()
                return data.get("result", {"items": [], "total": 0})

        except Exception as e:
            logger.error(f"Failed to get assets by owner {owner}: {e}")
            return {"items": [], "total": 0}

    async def search_assets(
        self,
        owner: Optional[str] = None,
        creator: Optional[str] = None,
        collection: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Search for assets with filters.

        Args:
            owner: Filter by owner address.
            creator: Filter by creator address.
            collection: Filter by collection address.
            page: Page number.
            limit: Results per page.

        Returns:
            Dict with items and total count.
        """
        await self._ensure_session()

        params: Dict[str, Any] = {
            "page": page,
            "limit": limit,
        }

        if owner:
            params["ownerAddress"] = owner
        if creator:
            params["creatorAddress"] = creator
        if collection:
            params["grouping"] = ["collection", collection]

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "searchAssets",
            "params": params,
        }

        try:
            async with self._session.post(self.rpc_url, json=payload) as resp:
                if resp.status != 200:
                    return {"items": [], "total": 0}

                data = await resp.json()
                return data.get("result", {"items": [], "total": 0})

        except Exception as e:
            logger.error(f"Failed to search assets: {e}")
            return {"items": [], "total": 0}

    # =========================================================================
    # Account History
    # =========================================================================

    async def get_account_transactions(
        self,
        address: str,
        limit: int = 100,
        before: Optional[str] = None,
        tx_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get transaction history for an account.

        Args:
            address: Account address.
            limit: Maximum transactions to return.
            before: Pagination cursor (signature to start before).
            tx_type: Filter by transaction type (e.g., "SWAP").

        Returns:
            List of enhanced transactions.
        """
        await self._ensure_session()

        params: Dict[str, Any] = {"limit": limit}
        if before:
            params["before"] = before
        if tx_type:
            params["type"] = tx_type

        url = format_helius_url(
            f"{self.api_url}/v0/addresses/{address}/transactions",
            self.api_key,
        )

        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                return data if isinstance(data, list) else []

        except Exception as e:
            logger.error(f"Failed to get account transactions: {e}")
            return []

    # =========================================================================
    # WebSocket Subscriptions
    # =========================================================================

    async def subscribe_account(
        self,
        address: str,
        encoding: str = "jsonParsed",
        commitment: str = "confirmed",
    ) -> Optional[int]:
        """
        Subscribe to account changes.

        Args:
            address: Account address to monitor.
            encoding: Data encoding.
            commitment: Commitment level.

        Returns:
            Subscription ID or None on failure.
        """
        if not self._ws:
            return None

        subscribe_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "accountSubscribe",
            "params": [
                address,
                {"encoding": encoding, "commitment": commitment}
            ],
        }

        await self._ws.send_json(subscribe_msg)

        msg = await self._ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            sub_id = data.get("result")
            if sub_id:
                self._subscriptions[sub_id] = "account"
            return sub_id

        return None

    async def subscribe_token_transfers(
        self,
        mint: str,
        commitment: str = "confirmed",
    ) -> Optional[int]:
        """
        Subscribe to token transfer events for a mint.

        Args:
            mint: Token mint address.
            commitment: Commitment level.

        Returns:
            Subscription ID or None on failure.
        """
        if not self._ws:
            return None

        subscribe_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "logsSubscribe",
            "params": [
                {"mentions": [mint]},
                {"commitment": commitment},
            ],
        }

        await self._ws.send_json(subscribe_msg)

        msg = await self._ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            sub_id = data.get("result")
            if sub_id:
                self._subscriptions[sub_id] = "logs"
            return sub_id

        return None

    async def unsubscribe(self, subscription_id: int) -> bool:
        """
        Unsubscribe from updates.

        Args:
            subscription_id: Subscription ID to cancel.

        Returns:
            True if successful.
        """
        if not self._ws:
            return False

        sub_type = self._subscriptions.get(subscription_id, "account")
        method = "accountUnsubscribe" if sub_type == "account" else "logsUnsubscribe"

        unsub_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": method,
            "params": [subscription_id],
        }

        await self._ws.send_json(unsub_msg)

        msg = await self._ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            success = data.get("result", False)
            if success:
                self._subscriptions.pop(subscription_id, None)
            return success

        return False

    # =========================================================================
    # Webhook Management
    # =========================================================================

    async def create_webhook(
        self,
        url: str,
        addresses: List[str],
        transaction_types: Optional[List[str]] = None,
        webhook_type: str = "enhanced",
        auth_header: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new webhook.

        Args:
            url: Webhook URL to receive events.
            addresses: Addresses to monitor.
            transaction_types: Transaction types to filter.
            webhook_type: "enhanced" or "raw".
            auth_header: Optional auth header for webhook calls.

        Returns:
            Webhook configuration or None on failure.
        """
        payload: Dict[str, Any] = {
            "webhookURL": url,
            "accountAddresses": addresses,
            "webhookType": webhook_type,
        }

        if transaction_types:
            payload["transactionTypes"] = transaction_types
        if auth_header:
            payload["authHeader"] = auth_header

        return await self._make_api_request(
            "/v0/webhooks",
            method="POST",
            json_body=payload,
        )

    async def update_webhook(
        self,
        webhook_id: str,
        url: Optional[str] = None,
        addresses: Optional[List[str]] = None,
        transaction_types: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing webhook.

        Args:
            webhook_id: Webhook ID to update.
            url: New webhook URL.
            addresses: New addresses to monitor.
            transaction_types: New transaction types to filter.

        Returns:
            Updated webhook configuration or None on failure.
        """
        payload: Dict[str, Any] = {}

        if url:
            payload["webhookURL"] = url
        if addresses:
            payload["accountAddresses"] = addresses
        if transaction_types:
            payload["transactionTypes"] = transaction_types

        return await self._make_api_request(
            f"/v0/webhooks/{webhook_id}",
            method="PUT",
            json_body=payload,
        )

    async def delete_webhook(self, webhook_id: str) -> bool:
        """
        Delete a webhook.

        Args:
            webhook_id: Webhook ID to delete.

        Returns:
            True if successful.
        """
        result = await self._make_api_request(
            f"/v0/webhooks/{webhook_id}",
            method="DELETE",
        )
        return result is not None

    async def list_webhooks(self) -> List[Dict[str, Any]]:
        """
        List all webhooks.

        Returns:
            List of webhook configurations.
        """
        result = await self._make_api_request("/v0/webhooks", method="GET")
        return result if isinstance(result, list) else []

    async def get_webhook(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific webhook.

        Args:
            webhook_id: Webhook ID.

        Returns:
            Webhook configuration or None if not found.
        """
        return await self._make_api_request(
            f"/v0/webhooks/{webhook_id}",
            method="GET",
        )

    # =========================================================================
    # Token Metadata
    # =========================================================================

    async def get_token_metadata(
        self,
        mint: str,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Get token metadata.

        Args:
            mint: Token mint address.
            use_cache: Whether to use cached data.

        Returns:
            Token metadata or None if not found.
        """
        # Check cache
        if use_cache and mint in self._metadata_cache:
            cached = self._metadata_cache[mint]
            age = datetime.now() - cached["timestamp"]
            if age.total_seconds() < self._cache_ttl:
                return cached["data"]

        # Fetch from API
        asset = await self.get_asset(mint)
        if not asset:
            return None

        content = asset.get("content", {})
        metadata = content.get("metadata", {})

        result = {
            "name": metadata.get("name"),
            "symbol": metadata.get("symbol"),
            "description": metadata.get("description"),
            "image": None,
            "decimals": asset.get("token_info", {}).get("decimals"),
        }

        # Get image from files
        files = content.get("files", [])
        if files:
            result["image"] = files[0].get("uri")

        # Cache result
        self._metadata_cache[mint] = {
            "data": result,
            "timestamp": datetime.now(),
        }

        return result

    async def fetch_external_metadata(self, uri: str) -> Optional[Dict[str, Any]]:
        """
        Fetch metadata from external URI (e.g., Arweave).

        Args:
            uri: External metadata URI.

        Returns:
            Metadata JSON or None on failure.
        """
        await self._ensure_session()

        try:
            async with self._session.get(uri) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch external metadata: {e}")
            return None

    # =========================================================================
    # Priority Fees
    # =========================================================================

    async def get_priority_fee_estimate(
        self,
        accounts: Optional[List[str]] = None,
    ) -> Optional[Dict[str, int]]:
        """
        Get priority fee estimates.

        Args:
            accounts: Optional list of accounts to consider.

        Returns:
            Dict with fee levels (low, medium, high, veryHigh).
        """
        await self._ensure_session()

        params: Dict[str, Any] = {}
        if accounts:
            params["accountKeys"] = accounts

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getPriorityFeeEstimate",
            "params": [params] if params else [{}],
        }

        try:
            async with self._session.post(self.rpc_url, json=payload) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                result = data.get("result", {})
                return result.get("priorityFeeLevels")

        except Exception as e:
            logger.error(f"Failed to get priority fee estimate: {e}")
            return None

    # =========================================================================
    # Standard RPC Methods
    # =========================================================================

    async def get_balance(self, address: str) -> Optional[int]:
        """
        Get account balance in lamports.

        Args:
            address: Account address.

        Returns:
            Balance in lamports or None on failure.
        """
        result = await self._make_rpc_request("getBalance", [address])
        if result and "value" in result:
            return result["value"]
        return result

    async def get_token_accounts_by_owner(
        self,
        owner: str,
        mint: Optional[str] = None,
        program_id: str = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    ) -> List[Dict[str, Any]]:
        """
        Get token accounts for an owner.

        Args:
            owner: Owner wallet address.
            mint: Optional mint to filter by.
            program_id: Token program ID.

        Returns:
            List of token accounts.
        """
        params: List[Any] = [owner]

        if mint:
            params.append({"mint": mint})
        else:
            params.append({"programId": program_id})

        params.append({"encoding": "jsonParsed"})

        result = await self._make_rpc_request("getTokenAccountsByOwner", params)
        if result and "value" in result:
            return result["value"]
        return []

    async def get_slot(self) -> Optional[int]:
        """
        Get current slot.

        Returns:
            Current slot or None on failure.
        """
        return await self._make_rpc_request("getSlot", [])

    async def get_block_height(self) -> Optional[int]:
        """
        Get current block height.

        Returns:
            Current block height or None on failure.
        """
        return await self._make_rpc_request("getBlockHeight", [])

    async def send_transaction(
        self,
        transaction: str,
        skip_preflight: bool = False,
        max_retries: int = 3,
    ) -> Optional[str]:
        """
        Send a transaction.

        Args:
            transaction: Base64-encoded transaction.
            skip_preflight: Skip preflight checks.
            max_retries: Maximum retry attempts.

        Returns:
            Transaction signature or None on failure.
        """
        params: List[Any] = [
            transaction,
            {
                "skipPreflight": skip_preflight,
                "maxRetries": max_retries,
                "encoding": "base64",
            },
        ]

        return await self._make_rpc_request("sendTransaction", params, use_fallback=False)
