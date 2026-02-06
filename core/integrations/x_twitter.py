"""
X/Twitter Integration for the Integration Hub.

Provides connection to X (Twitter) API with support for:
- Posting tweets
- Getting mentions
- OAuth authentication

NOTE: This is a stub implementation. Full OAuth flow and API calls
require additional setup and X Developer account credentials.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from .base import Integration

logger = logging.getLogger(__name__)

# X API base URL
X_API_BASE = "https://api.twitter.com/2"


class XTwitterIntegration(Integration):
    """
    X (Twitter) API integration.

    Provides methods for posting tweets and retrieving mentions.
    This is a stub implementation - full functionality requires
    proper OAuth credentials and API access.

    Example:
        integration = XTwitterIntegration(bearer_token="...")
        integration.connect()

        result = await integration.post_tweet("Hello from Jarvis!")
    """

    def __init__(
        self,
        bearer_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None,
    ):
        """
        Initialize X/Twitter integration.

        Args:
            bearer_token: App-only authentication token (for read operations)
            api_key: OAuth API key
            api_secret: OAuth API secret
            access_token: OAuth access token
            access_token_secret: OAuth access token secret
        """
        self._bearer_token = bearer_token or os.environ.get("TWITTER_BEARER_TOKEN")
        self._api_key = api_key or os.environ.get("TWITTER_API_KEY")
        self._api_secret = api_secret or os.environ.get("TWITTER_API_SECRET")
        self._access_token = access_token or os.environ.get("TWITTER_ACCESS_TOKEN")
        self._access_token_secret = access_token_secret or os.environ.get(
            "TWITTER_ACCESS_TOKEN_SECRET"
        )

        self._connected = False
        self._user_info: Optional[Dict] = None

    @property
    def name(self) -> str:
        """Integration name."""
        return "x_twitter"

    @property
    def description(self) -> str:
        """Integration description."""
        return "X (Twitter) API integration for posting and monitoring"

    @property
    def required_config(self) -> List[str]:
        """Required configuration keys."""
        return ["bearer_token"]

    def _validate_credentials(self) -> bool:
        """
        Validate credentials by checking if they're present.

        In a full implementation, this would make an API call to verify.

        Returns:
            bool: True if credentials appear valid
        """
        # At minimum, we need a bearer token
        if not self._bearer_token:
            return False

        # Stub: In production, we'd call /users/me or similar
        return True

    def connect(self) -> bool:
        """
        Connect to X API by validating credentials.

        Returns:
            bool: True if connection successful
        """
        if not self._bearer_token:
            logger.error("No bearer token provided")
            return False

        if self._validate_credentials():
            self._connected = True
            logger.info("Connected to X/Twitter API")
            return True

        return False

    def disconnect(self) -> None:
        """Disconnect from X API."""
        self._connected = False
        self._user_info = None
        logger.info("Disconnected from X/Twitter")

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def health_check(self) -> bool:
        """
        Check X API health.

        Returns:
            bool: True if healthy
        """
        if not self._connected:
            return False

        # Stub: In production, make a lightweight API call
        return True

    async def _send_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Send a request to X API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body for POST/PUT
            params: Query parameters

        Returns:
            API response as dict
        """
        if not self._connected:
            raise RuntimeError("Not connected to X API")

        url = f"{X_API_BASE}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self._bearer_token}",
            "Content-Type": "application/json",
        }

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params, timeout=30)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data, timeout=30)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                return response.json()
        except ImportError:
            # Fallback to requests (sync)
            import requests

            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            return response.json()

    async def post_tweet(
        self,
        text: str,
        reply_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Post a tweet.

        NOTE: This is a STUB implementation. Actual tweet posting requires
        OAuth 1.0a User Context authentication with proper scopes.

        Args:
            text: Tweet text (max 280 characters)
            reply_to: Tweet ID to reply to

        Returns:
            Dict with tweet info or stub response
        """
        if not self._connected:
            raise RuntimeError("Not connected to X API")

        # Stub implementation - return placeholder
        logger.warning("post_tweet is a stub - full OAuth required for real posting")

        stub_response = {
            "stub": True,
            "message": "This is a stub response. Full OAuth 1.0a required for real posting.",
            "data": {
                "id": "stub_tweet_id_123456",
                "text": text[:280],
            },
        }

        return stub_response

    async def get_mentions(
        self,
        user_id: Optional[str] = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get mentions for a user.

        NOTE: This is a STUB implementation.

        Args:
            user_id: User ID to get mentions for
            max_results: Maximum number of results

        Returns:
            List of mention objects or stub response
        """
        if not self._connected:
            raise RuntimeError("Not connected to X API")

        # Stub implementation
        logger.warning("get_mentions is a stub - returning placeholder data")

        stub_mentions = [
            {
                "stub": True,
                "id": f"stub_mention_{i}",
                "text": f"Stub mention {i} @user",
                "author_id": f"author_{i}",
            }
            for i in range(min(max_results, 3))
        ]

        return stub_mentions

    async def search_tweets(
        self,
        query: str,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for tweets.

        This can work with bearer token authentication.

        Args:
            query: Search query
            max_results: Maximum number of results (10-100)

        Returns:
            List of tweet objects
        """
        if not self._connected:
            raise RuntimeError("Not connected to X API")

        # Note: Search requires elevated API access
        logger.warning("search_tweets may require elevated API access")

        try:
            params = {
                "query": query,
                "max_results": min(max_results, 100),
                "tweet.fields": "created_at,author_id,public_metrics",
            }

            result = await self._send_request("GET", "/tweets/search/recent", params=params)

            if "data" in result:
                return result["data"]
            return []

        except Exception as e:
            logger.error(f"Search failed: {e}")
            # Return stub on failure
            return [
                {
                    "stub": True,
                    "id": "stub_search_1",
                    "text": f"Stub search result for: {query}",
                }
            ]

    def get_user_info(self) -> Optional[Dict]:
        """
        Get current user information.

        Returns:
            User info dict or None if not connected
        """
        return self._user_info
