"""
OpenRouter API Proxy with Credit Billing
Prompts #61-64: API proxy infrastructure with usage tracking and billing
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import json
import hashlib
import aiohttp
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Credit pricing (in smallest unit, e.g., micro-credits)
CREDIT_DECIMALS = 6
CREDITS_PER_DOLLAR = 100  # 100 credits = $1

# Model pricing (credits per 1K tokens)
MODEL_PRICING = {
    "openai/gpt-4o": {"input": 0.5, "output": 1.5},
    "openai/gpt-4-turbo": {"input": 1.0, "output": 3.0},
    "anthropic/claude-3.5-sonnet": {"input": 0.3, "output": 1.5},
    "anthropic/claude-3-opus": {"input": 1.5, "output": 7.5},
    "meta-llama/llama-3.1-405b": {"input": 0.3, "output": 0.9},
    "google/gemini-pro-1.5": {"input": 0.125, "output": 0.375}
}


# =============================================================================
# MODELS
# =============================================================================

class UserTier(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    STAKER = "staker"  # Special tier for token stakers


@dataclass
class TierConfig:
    """Configuration for a user tier"""
    tier: UserTier
    monthly_credits: int
    rate_limit_per_minute: int
    rate_limit_per_day: int
    max_tokens_per_request: int
    allowed_models: List[str]
    discount_percent: int = 0
    priority: int = 0  # Higher = higher priority in queue


TIER_CONFIGS: Dict[UserTier, TierConfig] = {
    UserTier.FREE: TierConfig(
        tier=UserTier.FREE,
        monthly_credits=100,
        rate_limit_per_minute=10,
        rate_limit_per_day=100,
        max_tokens_per_request=4096,
        allowed_models=["meta-llama/llama-3.1-405b"],
        discount_percent=0,
        priority=0
    ),
    UserTier.BASIC: TierConfig(
        tier=UserTier.BASIC,
        monthly_credits=1000,
        rate_limit_per_minute=30,
        rate_limit_per_day=500,
        max_tokens_per_request=8192,
        allowed_models=["*"],  # All models
        discount_percent=0,
        priority=1
    ),
    UserTier.PRO: TierConfig(
        tier=UserTier.PRO,
        monthly_credits=5000,
        rate_limit_per_minute=100,
        rate_limit_per_day=2000,
        max_tokens_per_request=16384,
        allowed_models=["*"],
        discount_percent=10,
        priority=2
    ),
    UserTier.ENTERPRISE: TierConfig(
        tier=UserTier.ENTERPRISE,
        monthly_credits=50000,
        rate_limit_per_minute=500,
        rate_limit_per_day=10000,
        max_tokens_per_request=32768,
        allowed_models=["*"],
        discount_percent=20,
        priority=3
    ),
    UserTier.STAKER: TierConfig(
        tier=UserTier.STAKER,
        monthly_credits=0,  # Dynamic based on stake
        rate_limit_per_minute=200,
        rate_limit_per_day=5000,
        max_tokens_per_request=16384,
        allowed_models=["*"],
        discount_percent=30,  # Stakers get 30% discount
        priority=4  # Highest priority
    )
}


@dataclass
class UserCredits:
    """User credit balance and usage"""
    user_id: str
    tier: UserTier
    balance: int = 0  # Current credit balance
    monthly_allocation: int = 0  # Monthly free credits
    used_this_month: int = 0
    total_spent: int = 0
    stake_credits: int = 0  # Bonus credits from staking
    last_reset: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageRecord:
    """Record of API usage"""
    id: str
    user_id: str
    model: str
    input_tokens: int
    output_tokens: int
    credits_charged: int
    latency_ms: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitState:
    """Rate limit tracking for a user"""
    user_id: str
    requests_this_minute: int = 0
    requests_today: int = 0
    minute_reset: datetime = field(default_factory=datetime.utcnow)
    day_reset: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# API PROXY
# =============================================================================

class OpenRouterProxy:
    """Proxies requests to OpenRouter with billing and rate limiting"""

    def __init__(
        self,
        openrouter_api_key: str,
        db_url: str,
        staking_service: Optional[Any] = None
    ):
        self.openrouter_api_key = openrouter_api_key
        self.db_url = db_url
        self.staking_service = staking_service

        self.users: Dict[str, UserCredits] = {}
        self.rate_limits: Dict[str, RateLimitState] = {}
        self.usage_records: List[UsageRecord] = []

        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Initialize the proxy"""
        # Configure timeouts: 60s total, 30s connect (for OpenRouter API calls)
        timeout = ClientTimeout(total=60, connect=30)
        self._session = aiohttp.ClientSession(timeout=timeout)
        logger.info("OpenRouter proxy started")

    async def stop(self):
        """Shutdown the proxy"""
        if self._session:
            await self._session.close()

    # =========================================================================
    # CREDIT MANAGEMENT
    # =========================================================================

    async def get_user_credits(self, user_id: str) -> UserCredits:
        """Get user credit balance"""
        if user_id not in self.users:
            await self._init_user(user_id)
        return self.users[user_id]

    async def add_credits(
        self,
        user_id: str,
        amount: int,
        source: str = "purchase"
    ) -> int:
        """Add credits to user balance"""
        user = await self.get_user_credits(user_id)
        user.balance += amount

        logger.info(f"Added {amount} credits to {user_id} from {source}")
        return user.balance

    async def deduct_credits(
        self,
        user_id: str,
        amount: int,
        source: str = "api_usage"
    ) -> bool:
        """Deduct credits from user balance"""
        user = await self.get_user_credits(user_id)

        if user.balance < amount:
            return False

        user.balance -= amount
        user.used_this_month += amount
        user.total_spent += amount

        return True

    async def sync_staking_credits(self, user_id: str):
        """Sync credits based on user's staking position"""
        if not self.staking_service:
            return

        user = await self.get_user_credits(user_id)

        # Get staking info
        stake_info = await self.staking_service.get_stake(user_id)
        if not stake_info:
            return

        # Calculate bonus credits based on stake amount
        # 1 credit per 1000 tokens staked, up to 10000 bonus
        stake_amount = stake_info.get("amount", 0) / 10**9
        bonus_credits = min(10000, int(stake_amount / 1000))

        user.stake_credits = bonus_credits
        user.tier = UserTier.STAKER

    async def _init_user(self, user_id: str):
        """Initialize a new user"""
        # Check if user is a staker
        tier = UserTier.FREE
        if self.staking_service:
            stake = await self.staking_service.get_stake(user_id)
            if stake and stake.get("amount", 0) > 0:
                tier = UserTier.STAKER

        config = TIER_CONFIGS[tier]

        self.users[user_id] = UserCredits(
            user_id=user_id,
            tier=tier,
            balance=config.monthly_credits,
            monthly_allocation=config.monthly_credits
        )

    # =========================================================================
    # RATE LIMITING
    # =========================================================================

    async def check_rate_limit(self, user_id: str) -> Tuple[bool, str]:
        """Check if user is within rate limits"""
        user = await self.get_user_credits(user_id)
        config = TIER_CONFIGS[user.tier]

        if user_id not in self.rate_limits:
            self.rate_limits[user_id] = RateLimitState(user_id=user_id)

        state = self.rate_limits[user_id]
        now = datetime.utcnow()

        # Reset minute counter
        if (now - state.minute_reset).total_seconds() >= 60:
            state.requests_this_minute = 0
            state.minute_reset = now

        # Reset day counter
        if (now - state.day_reset).total_seconds() >= 86400:
            state.requests_today = 0
            state.day_reset = now

        # Check limits
        if state.requests_this_minute >= config.rate_limit_per_minute:
            return False, "Rate limit exceeded (per minute)"

        if state.requests_today >= config.rate_limit_per_day:
            return False, "Rate limit exceeded (per day)"

        return True, ""

    async def increment_rate_limit(self, user_id: str):
        """Increment rate limit counters"""
        if user_id not in self.rate_limits:
            self.rate_limits[user_id] = RateLimitState(user_id=user_id)

        state = self.rate_limits[user_id]
        state.requests_this_minute += 1
        state.requests_today += 1

    # =========================================================================
    # API PROXY
    # =========================================================================

    async def chat_completion(
        self,
        user_id: str,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Proxy a chat completion request"""
        import uuid

        # Get user and config
        user = await self.get_user_credits(user_id)
        config = TIER_CONFIGS[user.tier]

        # Check model access
        if config.allowed_models != ["*"]:
            if model not in config.allowed_models:
                raise ValueError(f"Model {model} not available for tier {user.tier.value}")

        # Check max tokens
        if max_tokens > config.max_tokens_per_request:
            max_tokens = config.max_tokens_per_request

        # Check rate limits
        allowed, reason = await self.check_rate_limit(user_id)
        if not allowed:
            raise ValueError(reason)

        # Estimate cost
        input_tokens = self._estimate_tokens(messages)
        estimated_output = max_tokens // 2  # Conservative estimate
        estimated_cost = self._calculate_cost(
            model, input_tokens, estimated_output, config.discount_percent
        )

        # Check balance
        total_available = user.balance + user.stake_credits
        if total_available < estimated_cost:
            raise ValueError(
                f"Insufficient credits. Estimated cost: {estimated_cost}, "
                f"Available: {total_available}"
            )

        # Make request
        start_time = time.time()
        request_id = str(uuid.uuid4())

        try:
            async with self._session.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "HTTP-Referer": "https://jarvis.ai",
                    "X-Title": "JARVIS AI",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **kwargs
                }
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"OpenRouter error: {error_text}")

                result = await response.json()

        except Exception as e:
            logger.error(f"OpenRouter request failed: {e}")
            raise

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract usage
        usage = result.get("usage", {})
        actual_input = usage.get("prompt_tokens", input_tokens)
        actual_output = usage.get("completion_tokens", 0)

        # Calculate actual cost
        actual_cost = self._calculate_cost(
            model, actual_input, actual_output, config.discount_percent
        )

        # Deduct credits (prefer stake credits first)
        if user.stake_credits >= actual_cost:
            user.stake_credits -= actual_cost
        else:
            remaining = actual_cost - user.stake_credits
            user.stake_credits = 0
            await self.deduct_credits(user_id, remaining)

        # Record usage
        await self.increment_rate_limit(user_id)
        await self._record_usage(UsageRecord(
            id=request_id,
            user_id=user_id,
            model=model,
            input_tokens=actual_input,
            output_tokens=actual_output,
            credits_charged=actual_cost,
            latency_ms=latency_ms,
            request_id=request_id
        ))

        logger.info(
            f"Request {request_id}: {model}, "
            f"{actual_input}+{actual_output} tokens, "
            f"{actual_cost} credits"
        )

        return {
            **result,
            "jarvis_usage": {
                "credits_charged": actual_cost,
                "remaining_balance": user.balance,
                "stake_credits": user.stake_credits
            }
        }

    def _estimate_tokens(self, messages: List[Dict]) -> int:
        """Estimate token count for messages"""
        # Rough estimate: 4 chars = 1 token
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return total_chars // 4 + 50  # Add overhead for message formatting

    def _calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        discount_percent: int
    ) -> int:
        """Calculate credit cost for usage"""
        pricing = MODEL_PRICING.get(model, {"input": 1.0, "output": 3.0})

        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        total_cost = input_cost + output_cost

        # Apply discount
        if discount_percent > 0:
            total_cost = total_cost * (1 - discount_percent / 100)

        # Convert to credits (minimum 1)
        return max(1, int(total_cost * CREDITS_PER_DOLLAR))

    async def _record_usage(self, record: UsageRecord):
        """Record API usage"""
        self.usage_records.append(record)

        # Keep only last 10000 records in memory
        if len(self.usage_records) > 10000:
            self.usage_records = self.usage_records[-10000:]

    # =========================================================================
    # USAGE ANALYTICS
    # =========================================================================

    async def get_user_usage(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get usage statistics for a user"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        records = [
            r for r in self.usage_records
            if r.user_id == user_id and r.timestamp >= cutoff
        ]

        total_requests = len(records)
        total_tokens = sum(r.input_tokens + r.output_tokens for r in records)
        total_credits = sum(r.credits_charged for r in records)
        avg_latency = (
            sum(r.latency_ms for r in records) / total_requests
            if total_requests > 0 else 0
        )

        # Group by model
        by_model = {}
        for r in records:
            if r.model not in by_model:
                by_model[r.model] = {"requests": 0, "tokens": 0, "credits": 0}
            by_model[r.model]["requests"] += 1
            by_model[r.model]["tokens"] += r.input_tokens + r.output_tokens
            by_model[r.model]["credits"] += r.credits_charged

        return {
            "user_id": user_id,
            "period_days": days,
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_credits": total_credits,
            "avg_latency_ms": round(avg_latency, 2),
            "by_model": by_model
        }

    async def get_global_usage(self, hours: int = 24) -> Dict[str, Any]:
        """Get global usage statistics"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        records = [r for r in self.usage_records if r.timestamp >= cutoff]

        return {
            "period_hours": hours,
            "total_requests": len(records),
            "total_tokens": sum(r.input_tokens + r.output_tokens for r in records),
            "total_credits": sum(r.credits_charged for r in records),
            "unique_users": len(set(r.user_id for r in records)),
            "requests_per_hour": len(records) / hours
        }


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_proxy_endpoints(proxy: OpenRouterProxy):
    """Create API endpoints for the proxy"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/v1", tags=["AI Proxy"])

    class ChatRequest(BaseModel):
        model: str
        messages: List[Dict[str, str]]
        max_tokens: int = 1024
        temperature: float = 0.7

    class AddCreditsRequest(BaseModel):
        amount: int
        source: str = "purchase"

    @router.post("/chat/completions")
    async def chat_completions(user_id: str, request: ChatRequest):
        """Proxy chat completion request"""
        try:
            result = await proxy.chat_completion(
                user_id=user_id,
                model=request.model,
                messages=request.messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/credits")
    async def get_credits(user_id: str):
        """Get user credit balance"""
        credits = await proxy.get_user_credits(user_id)
        config = TIER_CONFIGS[credits.tier]

        return {
            "balance": credits.balance,
            "stake_credits": credits.stake_credits,
            "total_available": credits.balance + credits.stake_credits,
            "tier": credits.tier.value,
            "monthly_allocation": config.monthly_credits,
            "used_this_month": credits.used_this_month,
            "discount_percent": config.discount_percent
        }

    @router.post("/credits/add")
    async def add_credits(user_id: str, request: AddCreditsRequest):
        """Add credits to user balance"""
        new_balance = await proxy.add_credits(
            user_id, request.amount, request.source
        )
        return {"balance": new_balance}

    @router.get("/usage")
    async def get_usage(user_id: str, days: int = 30):
        """Get user usage statistics"""
        return await proxy.get_user_usage(user_id, days)

    @router.get("/models")
    async def get_models(user_id: str):
        """Get available models for user"""
        credits = await proxy.get_user_credits(user_id)
        config = TIER_CONFIGS[credits.tier]

        if config.allowed_models == ["*"]:
            models = list(MODEL_PRICING.keys())
        else:
            models = config.allowed_models

        return {
            "models": [
                {
                    "id": model,
                    "pricing": MODEL_PRICING.get(model, {}),
                    "available": True
                }
                for model in models
            ]
        }

    @router.get("/rate-limits")
    async def get_rate_limits(user_id: str):
        """Get user rate limit status"""
        credits = await proxy.get_user_credits(user_id)
        config = TIER_CONFIGS[credits.tier]

        state = proxy.rate_limits.get(user_id, RateLimitState(user_id=user_id))

        return {
            "tier": credits.tier.value,
            "limits": {
                "per_minute": config.rate_limit_per_minute,
                "per_day": config.rate_limit_per_day,
                "max_tokens": config.max_tokens_per_request
            },
            "current": {
                "requests_this_minute": state.requests_this_minute,
                "requests_today": state.requests_today
            }
        }

    return router


# Type alias for tuple return
from typing import Tuple
