"""
JARVIS Developer SDK

Python SDK for integrating with JARVIS APIs.

Prompts #61-64: Developer API SDK
"""

import asyncio
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
import aiohttp
import json

logger = logging.getLogger(__name__)


@dataclass
class SDKConfig:
    """SDK configuration"""
    base_url: str = "https://api.jarvis.ai/v1"
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_buffer: float = 0.9  # Use 90% of rate limit


@dataclass
class APICredentials:
    """API credentials for authentication"""
    api_key: str
    api_secret: Optional[str] = None
    environment: str = "production"

    def sign_request(self, body: str, timestamp: str) -> str:
        """Sign a request using HMAC-SHA256"""
        if not self.api_secret:
            return ""
        message = f"{timestamp}.{body}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature


@dataclass
class RateLimitInfo:
    """Rate limit status"""
    limit: int = 100
    remaining: int = 100
    reset_at: datetime = field(default_factory=datetime.utcnow)
    window_seconds: int = 60

    @property
    def is_exhausted(self) -> bool:
        return self.remaining <= 0

    @property
    def seconds_until_reset(self) -> float:
        return max(0, (self.reset_at - datetime.utcnow()).total_seconds())


@dataclass
class APIResponse:
    """Standardized API response"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    status_code: int = 200
    rate_limit: Optional[RateLimitInfo] = None
    request_id: Optional[str] = None


class JarvisSDK:
    """
    Official JARVIS Python SDK.

    Provides easy access to all JARVIS APIs with automatic:
    - Authentication and request signing
    - Rate limiting and retry logic
    - Error handling and response parsing
    - Webhook verification
    """

    def __init__(
        self,
        credentials: APICredentials,
        config: Optional[SDKConfig] = None
    ):
        self.credentials = credentials
        self.config = config or SDKConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limit = RateLimitInfo()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self):
        """Initialize the SDK"""
        self._session = aiohttp.ClientSession()
        logger.info("JARVIS SDK connected")

    async def close(self):
        """Close the SDK"""
        if self._session:
            await self._session.close()
        logger.info("JARVIS SDK closed")

    # =========================================================================
    # HTTP METHODS
    # =========================================================================

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> APIResponse:
        """Make an authenticated API request"""
        if not self._session:
            await self.connect()

        # Check rate limit
        if self._rate_limit.is_exhausted:
            wait_time = self._rate_limit.seconds_until_reset
            logger.warning(f"Rate limit exhausted, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)

        url = f"{self.config.base_url}{endpoint}"
        timestamp = str(int(time.time()))

        # Prepare headers
        req_headers = {
            "X-API-Key": self.credentials.api_key,
            "X-Timestamp": timestamp,
            "Content-Type": "application/json",
            **(headers or {})
        }

        # Sign request if secret is available
        body = json.dumps(data) if data else ""
        if self.credentials.api_secret:
            signature = self.credentials.sign_request(body, timestamp)
            req_headers["X-Signature"] = signature

        # Make request with retry
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                async with self._session.request(
                    method,
                    url,
                    params=params,
                    json=data,
                    headers=req_headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    # Parse rate limit headers
                    self._parse_rate_limit(response.headers)

                    # Parse response
                    try:
                        result = await response.json()
                    except Exception:
                        result = await response.text()

                    if response.status >= 400:
                        return APIResponse(
                            success=False,
                            error=str(result),
                            status_code=response.status,
                            rate_limit=self._rate_limit,
                            request_id=response.headers.get("X-Request-Id")
                        )

                    return APIResponse(
                        success=True,
                        data=result,
                        status_code=response.status,
                        rate_limit=self._rate_limit,
                        request_id=response.headers.get("X-Request-Id")
                    )

            except aiohttp.ClientError as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

        return APIResponse(
            success=False,
            error=str(last_error),
            status_code=0
        )

    def _parse_rate_limit(self, headers: Dict):
        """Parse rate limit headers"""
        if "X-RateLimit-Limit" in headers:
            self._rate_limit.limit = int(headers["X-RateLimit-Limit"])
        if "X-RateLimit-Remaining" in headers:
            self._rate_limit.remaining = int(headers["X-RateLimit-Remaining"])
        if "X-RateLimit-Reset" in headers:
            reset_ts = int(headers["X-RateLimit-Reset"])
            self._rate_limit.reset_at = datetime.fromtimestamp(reset_ts)

    async def get(self, endpoint: str, params: Optional[Dict] = None) -> APIResponse:
        """GET request"""
        return await self._request("GET", endpoint, params=params)

    async def post(self, endpoint: str, data: Optional[Dict] = None) -> APIResponse:
        """POST request"""
        return await self._request("POST", endpoint, data=data)

    async def put(self, endpoint: str, data: Optional[Dict] = None) -> APIResponse:
        """PUT request"""
        return await self._request("PUT", endpoint, data=data)

    async def delete(self, endpoint: str) -> APIResponse:
        """DELETE request"""
        return await self._request("DELETE", endpoint)

    # =========================================================================
    # PORTFOLIO API
    # =========================================================================

    async def get_portfolio(self, wallet: Optional[str] = None) -> APIResponse:
        """Get portfolio overview"""
        params = {"wallet": wallet} if wallet else None
        return await self.get("/portfolio", params)

    async def get_positions(self, wallet: Optional[str] = None) -> APIResponse:
        """Get all positions"""
        params = {"wallet": wallet} if wallet else None
        return await self.get("/portfolio/positions", params)

    async def get_position(self, token: str) -> APIResponse:
        """Get specific position"""
        return await self.get(f"/portfolio/positions/{token}")

    async def get_transactions(
        self,
        wallet: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> APIResponse:
        """Get transaction history"""
        params = {"limit": limit, "offset": offset}
        if wallet:
            params["wallet"] = wallet
        return await self.get("/portfolio/transactions", params)

    # =========================================================================
    # TRADING API
    # =========================================================================

    async def get_quote(
        self,
        token_in: str,
        token_out: str,
        amount: float,
        slippage_bps: int = 100
    ) -> APIResponse:
        """Get a swap quote"""
        return await self.post("/trade/quote", {
            "token_in": token_in,
            "token_out": token_out,
            "amount": amount,
            "slippage_bps": slippage_bps
        })

    async def execute_trade(
        self,
        quote_id: str,
        wallet: Optional[str] = None
    ) -> APIResponse:
        """Execute a trade from quote"""
        return await self.post("/trade/execute", {
            "quote_id": quote_id,
            "wallet": wallet
        })

    async def get_token_price(self, token: str) -> APIResponse:
        """Get current token price"""
        return await self.get(f"/tokens/{token}/price")

    async def get_token_info(self, token: str) -> APIResponse:
        """Get token information"""
        return await self.get(f"/tokens/{token}")

    # =========================================================================
    # SIGNALS API
    # =========================================================================

    async def get_signals(
        self,
        token: Optional[str] = None,
        limit: int = 20
    ) -> APIResponse:
        """Get trading signals"""
        params = {"limit": limit}
        if token:
            params["token"] = token
        return await self.get("/signals", params)

    async def subscribe_signals(
        self,
        tokens: List[str],
        webhook_url: str
    ) -> APIResponse:
        """Subscribe to signals via webhook"""
        return await self.post("/signals/subscribe", {
            "tokens": tokens,
            "webhook_url": webhook_url
        })

    # =========================================================================
    # ALERTS API
    # =========================================================================

    async def create_alert(
        self,
        alert_type: str,
        conditions: Dict,
        notification_channels: List[str]
    ) -> APIResponse:
        """Create a new alert"""
        return await self.post("/alerts", {
            "type": alert_type,
            "conditions": conditions,
            "channels": notification_channels
        })

    async def get_alerts(self, active_only: bool = True) -> APIResponse:
        """Get all alerts"""
        params = {"active": "true" if active_only else "false"}
        return await self.get("/alerts", params)

    async def delete_alert(self, alert_id: str) -> APIResponse:
        """Delete an alert"""
        return await self.delete(f"/alerts/{alert_id}")

    # =========================================================================
    # WHALE TRACKING API
    # =========================================================================

    async def get_whale_activity(
        self,
        token: str,
        hours: int = 24
    ) -> APIResponse:
        """Get whale activity for a token"""
        return await self.get(f"/whales/{token}", {"hours": hours})

    async def get_whale_signals(self) -> APIResponse:
        """Get current whale-based signals"""
        return await self.get("/whales/signals")

    # =========================================================================
    # STAKING API
    # =========================================================================

    async def get_stake_info(self, wallet: str) -> APIResponse:
        """Get staking info for wallet"""
        return await self.get(f"/staking/stake/{wallet}")

    async def get_staking_rewards(self, wallet: str) -> APIResponse:
        """Get pending staking rewards"""
        return await self.get(f"/staking/rewards/{wallet}")

    # =========================================================================
    # WEBHOOK VERIFICATION
    # =========================================================================

    def verify_webhook(
        self,
        payload: str,
        signature: str,
        timestamp: str
    ) -> bool:
        """Verify a webhook signature"""
        if not self.credentials.api_secret:
            return False

        expected = self.credentials.sign_request(payload, timestamp)
        return hmac.compare_digest(signature, expected)

    # =========================================================================
    # UTILITIES
    # =========================================================================

    @property
    def rate_limit(self) -> RateLimitInfo:
        """Get current rate limit info"""
        return self._rate_limit

    async def health_check(self) -> APIResponse:
        """Check API health"""
        return await self.get("/health")


# Convenience function to create SDK instance
def create_sdk(
    api_key: str,
    api_secret: Optional[str] = None,
    base_url: Optional[str] = None
) -> JarvisSDK:
    """Create a new SDK instance"""
    credentials = APICredentials(api_key=api_key, api_secret=api_secret)
    config = SDKConfig()
    if base_url:
        config.base_url = base_url
    return JarvisSDK(credentials, config)


# Testing
if __name__ == "__main__":
    async def test():
        # Create SDK
        sdk = create_sdk(
            api_key="test_key",
            base_url="http://localhost:8000/api/v1"
        )

        async with sdk:
            # Test health check
            result = await sdk.health_check()
            print(f"Health check: {result}")

            # Test portfolio
            result = await sdk.get_portfolio()
            print(f"Portfolio: {result}")

            # Test rate limit
            print(f"Rate limit: {sdk.rate_limit}")

    asyncio.run(test())
