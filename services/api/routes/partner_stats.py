"""
Partner Stats Dashboard API
Prompt #40: API endpoints for partner fee analytics
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import json
import aiohttp
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
import redis.asyncio as redis

from api.pagination import PaginationParams, paginate

logger = logging.getLogger(__name__)


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class PartnerStats:
    """Aggregated partner statistics"""
    total_fees_earned: int  # In lamports
    fees_claimed: int
    fees_unclaimed: int
    total_volume: int
    trade_count: int
    unique_users: int
    avg_fee_per_trade: float
    updated_at: datetime


@dataclass
class PeriodStats:
    """Stats for a specific time period"""
    period: str  # "daily", "weekly", "monthly"
    start_time: datetime
    end_time: datetime
    fees_earned: int
    volume: int
    trade_count: int
    unique_users: int


@dataclass
class TokenStats:
    """Stats per token traded"""
    token_mint: str
    token_symbol: str
    total_volume: int
    fees_earned: int
    trade_count: int


# =============================================================================
# PARTNER STATS SERVICE
# =============================================================================

class PartnerStatsService:
    """Service for fetching and caching partner statistics"""

    CACHE_TTL = 300  # 5 minutes
    BAGS_API_URL = "https://public-api-v2.bags.fm"

    def __init__(
        self,
        bags_api_key: str,
        redis_url: str = "redis://localhost:6379"
    ):
        self.bags_api_key = bags_api_key
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self):
        """Initialize connections"""
        self._redis = await redis.from_url(self.redis_url)
        self._session = aiohttp.ClientSession()

    async def close(self):
        """Close connections"""
        if self._redis:
            await self._redis.close()
        if self._session:
            await self._session.close()

    # =========================================================================
    # CORE STATS
    # =========================================================================

    async def get_stats(self, force_refresh: bool = False) -> PartnerStats:
        """Get aggregated partner statistics"""
        cache_key = "partner:stats:aggregate"

        # Check cache
        if not force_refresh:
            cached = await self._redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return PartnerStats(**data)

        # Fetch from Bags API
        try:
            async with self._session.get(
                f"{self.BAGS_API_URL}/api/v1/partner/stats",
                headers={"x-api-key": self.bags_api_key},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    raise ValueError(f"API error: {response.status}")

                data = await response.json()

                stats = PartnerStats(
                    total_fees_earned=data.get("totalFeesEarned", 0),
                    fees_claimed=data.get("feesClaimed", 0),
                    fees_unclaimed=data.get("feesUnclaimed", 0),
                    total_volume=data.get("totalVolume", 0),
                    trade_count=data.get("tradeCount", 0),
                    unique_users=data.get("uniqueUsers", 0),
                    avg_fee_per_trade=data.get("avgFeePerTrade", 0),
                    updated_at=datetime.utcnow()
                )

                # Cache result
                await self._redis.setex(
                    cache_key,
                    self.CACHE_TTL,
                    json.dumps({
                        "total_fees_earned": stats.total_fees_earned,
                        "fees_claimed": stats.fees_claimed,
                        "fees_unclaimed": stats.fees_unclaimed,
                        "total_volume": stats.total_volume,
                        "trade_count": stats.trade_count,
                        "unique_users": stats.unique_users,
                        "avg_fee_per_trade": stats.avg_fee_per_trade,
                        "updated_at": stats.updated_at.isoformat()
                    })
                )

                return stats

        except Exception as e:
            logger.error(f"Failed to fetch partner stats: {e}")
            raise

    async def get_stats_history(
        self,
        period: str = "day",
        limit: int = 30
    ) -> List[PeriodStats]:
        """Get historical stats"""
        cache_key = f"partner:stats:history:{period}:{limit}"

        # Check cache
        cached = await self._redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            return [PeriodStats(**s) for s in data]

        # Fetch from Bags API
        try:
            async with self._session.get(
                f"{self.BAGS_API_URL}/api/v1/partner/stats/history",
                headers={"x-api-key": self.bags_api_key},
                params={"period": period, "limit": limit},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    raise ValueError(f"API error: {response.status}")

                data = await response.json()
                history = [
                    PeriodStats(
                        period=period,
                        start_time=datetime.fromisoformat(h.get("startTime")),
                        end_time=datetime.fromisoformat(h.get("endTime")),
                        fees_earned=h.get("feesEarned", 0),
                        volume=h.get("volume", 0),
                        trade_count=h.get("tradeCount", 0),
                        unique_users=h.get("uniqueUsers", 0)
                    )
                    for h in data.get("history", [])
                ]

                # Cache
                await self._redis.setex(
                    cache_key,
                    self.CACHE_TTL,
                    json.dumps([{
                        "period": s.period,
                        "start_time": s.start_time.isoformat(),
                        "end_time": s.end_time.isoformat(),
                        "fees_earned": s.fees_earned,
                        "volume": s.volume,
                        "trade_count": s.trade_count,
                        "unique_users": s.unique_users
                    } for s in history])
                )

                return history

        except Exception as e:
            logger.error(f"Failed to fetch stats history: {e}")
            raise

    async def get_token_stats(self, limit: int = 50) -> List[TokenStats]:
        """Get stats per token traded"""
        cache_key = f"partner:stats:tokens:{limit}"

        # Check cache
        cached = await self._redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            return [TokenStats(**t) for t in data]

        # Fetch from Bags API
        try:
            async with self._session.get(
                f"{self.BAGS_API_URL}/api/v1/partner/tokens",
                headers={"x-api-key": self.bags_api_key},
                params={"limit": limit},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    raise ValueError(f"API error: {response.status}")

                data = await response.json()
                tokens = [
                    TokenStats(
                        token_mint=t.get("tokenMint", ""),
                        token_symbol=t.get("tokenSymbol", "UNKNOWN"),
                        total_volume=t.get("totalVolume", 0),
                        fees_earned=t.get("feesEarned", 0),
                        trade_count=t.get("tradeCount", 0)
                    )
                    for t in data.get("tokens", [])
                ]

                # Cache
                await self._redis.setex(
                    cache_key,
                    self.CACHE_TTL,
                    json.dumps([{
                        "token_mint": t.token_mint,
                        "token_symbol": t.token_symbol,
                        "total_volume": t.total_volume,
                        "fees_earned": t.fees_earned,
                        "trade_count": t.trade_count
                    } for t in tokens])
                )

                return tokens

        except Exception as e:
            logger.error(f"Failed to fetch token stats: {e}")
            raise

    # =========================================================================
    # FEE CLAIMING
    # =========================================================================

    async def claim_fees(
        self,
        wallet_keypair: Any,
        amount: Optional[int] = None
    ) -> Dict[str, Any]:
        """Claim partner fees"""
        try:
            # Get claim transaction from Bags
            async with self._session.post(
                f"{self.BAGS_API_URL}/api/v1/partner/claim-transactions",
                headers={"x-api-key": self.bags_api_key},
                json={
                    "userPublicKey": str(wallet_keypair.pubkey()),
                    "amount": amount  # None = claim all
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise ValueError(f"Claim failed: {error}")

                data = await response.json()
                transaction = data.get("transaction")

                # Sign and send transaction
                # ... (actual signing logic)

                # Record claim
                await self._record_claim(
                    amount=data.get("amount", 0),
                    signature=data.get("signature", "")
                )

                return {
                    "success": True,
                    "amount": data.get("amount", 0),
                    "signature": data.get("signature", ""),
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to claim fees: {e}")
            raise

    async def _record_claim(self, amount: int, signature: str):
        """Record a claim in history"""
        claim_record = {
            "amount": amount,
            "signature": signature,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self._redis.lpush(
            "partner:claims:history",
            json.dumps(claim_record)
        )
        await self._redis.ltrim("partner:claims:history", 0, 999)

    async def get_claim_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get claim history"""
        claims = await self._redis.lrange(
            "partner:claims:history", 0, limit - 1
        )
        return [json.loads(c) for c in claims]

    # =========================================================================
    # TOP PERFORMERS
    # =========================================================================

    async def get_top_tokens(
        self,
        by: str = "fees",  # "fees", "volume", "trades"
        limit: int = 10
    ) -> List[TokenStats]:
        """Get top performing tokens"""
        all_tokens = await self.get_token_stats(limit=100)

        if by == "fees":
            sorted_tokens = sorted(
                all_tokens, key=lambda t: t.fees_earned, reverse=True
            )
        elif by == "volume":
            sorted_tokens = sorted(
                all_tokens, key=lambda t: t.total_volume, reverse=True
            )
        else:  # trades
            sorted_tokens = sorted(
                all_tokens, key=lambda t: t.trade_count, reverse=True
            )

        return sorted_tokens[:limit]


# =============================================================================
# API ROUTES
# =============================================================================

def create_partner_stats_routes(service: PartnerStatsService) -> APIRouter:
    """Create API router for partner stats"""
    router = APIRouter(prefix="/api/partner", tags=["Partner Stats"])

    @router.get("/stats")
    async def get_stats(force_refresh: bool = False):
        """
        Get aggregated partner statistics

        Returns:
        - total_fees_earned: Total fees earned all time (lamports)
        - fees_claimed: Fees already claimed
        - fees_unclaimed: Available to claim
        - total_volume: Trading volume routed through partner
        - trade_count: Number of trades
        - unique_users: Number of unique users
        - avg_fee_per_trade: Average fee per trade
        """
        stats = await service.get_stats(force_refresh)
        return {
            "total_fees_earned": stats.total_fees_earned,
            "total_fees_earned_sol": stats.total_fees_earned / 1e9,
            "fees_claimed": stats.fees_claimed,
            "fees_claimed_sol": stats.fees_claimed / 1e9,
            "fees_unclaimed": stats.fees_unclaimed,
            "fees_unclaimed_sol": stats.fees_unclaimed / 1e9,
            "total_volume": stats.total_volume,
            "total_volume_sol": stats.total_volume / 1e9,
            "trade_count": stats.trade_count,
            "unique_users": stats.unique_users,
            "avg_fee_per_trade": stats.avg_fee_per_trade,
            "updated_at": stats.updated_at.isoformat()
        }

    @router.get("/stats/history")
    async def get_stats_history(
        period: str = Query("day", description="Period: day, week, or month"),
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(30, ge=1, le=100, description="Items per page"),
    ):
        """
        Get historical stats time series with pagination.

        Args:
        - period: "day" | "week" | "month"
        - page: Page number (1-indexed)
        - page_size: Items per page
        """
        # Fetch more data than needed to support pagination
        history = await service.get_stats_history(period, limit=page_size * page)

        # Format the data
        formatted = [
            {
                "start_time": h.start_time.isoformat(),
                "end_time": h.end_time.isoformat(),
                "fees_earned": h.fees_earned,
                "fees_earned_sol": h.fees_earned / 1e9,
                "volume": h.volume,
                "volume_sol": h.volume / 1e9,
                "trade_count": h.trade_count,
                "unique_users": h.unique_users
            }
            for h in history
        ]

        # Apply pagination
        total = len(formatted)
        start = (page - 1) * page_size
        end = start + page_size
        page_data = formatted[start:end]

        total_pages = (total + page_size - 1) // page_size

        return {
            "period": period,
            "data": page_data,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            }
        }

    @router.get("/tokens")
    async def get_token_stats(
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    ):
        """
        Get stats per token traded with pagination.

        Returns list of tokens with:
        - token_mint: Mint address
        - token_symbol: Symbol
        - total_volume: Volume traded
        - fees_earned: Fees earned from this token
        - trade_count: Number of trades
        """
        # Fetch more tokens to support pagination
        tokens = await service.get_token_stats(limit=page_size * page)

        # Format tokens
        formatted = [
            {
                "token_mint": t.token_mint,
                "token_symbol": t.token_symbol,
                "total_volume": t.total_volume,
                "total_volume_sol": t.total_volume / 1e9,
                "fees_earned": t.fees_earned,
                "fees_earned_sol": t.fees_earned / 1e9,
                "trade_count": t.trade_count
            }
            for t in tokens
        ]

        # Apply pagination
        total = len(formatted)
        start = (page - 1) * page_size
        end = start + page_size
        page_tokens = formatted[start:end]

        total_pages = (total + page_size - 1) // page_size

        return {
            "tokens": page_tokens,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            }
        }

    @router.get("/tokens/top")
    async def get_top_tokens(
        by: str = "fees",
        limit: int = 10
    ):
        """Get top performing tokens by fees, volume, or trades"""
        tokens = await service.get_top_tokens(by, limit)
        return {
            "ranked_by": by,
            "tokens": [
                {
                    "rank": i + 1,
                    "token_mint": t.token_mint,
                    "token_symbol": t.token_symbol,
                    "total_volume": t.total_volume,
                    "fees_earned": t.fees_earned,
                    "trade_count": t.trade_count
                }
                for i, t in enumerate(tokens)
            ]
        }

    @router.post("/claim")
    async def claim_fees(
        amount: Optional[int] = None,
        background_tasks: BackgroundTasks = None
    ):
        """
        Trigger fee claim transaction

        Args:
        - amount: Amount in lamports (None = claim all available)

        Returns:
        - success: Whether claim was initiated
        - amount: Amount claimed
        - signature: Transaction signature
        """
        # In production, would require auth and use user's keypair
        # For now, return mock response
        return {
            "success": True,
            "message": "Fee claim initiated",
            "note": "In production, this would execute on-chain"
        }

    @router.get("/claims/history")
    async def get_claim_history(
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    ):
        """Get history of fee claims with pagination."""
        # Fetch more claims to support pagination
        claims = await service.get_claim_history(limit=page_size * page)

        # Apply pagination
        total = len(claims)
        start = (page - 1) * page_size
        end = start + page_size
        page_claims = claims[start:end]

        total_pages = (total + page_size - 1) // page_size

        return {
            "claims": page_claims,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            }
        }

    @router.get("/dashboard")
    async def get_dashboard():
        """Get complete dashboard data in one call"""
        stats, history, tokens = await asyncio.gather(
            service.get_stats(),
            service.get_stats_history("day", 7),
            service.get_top_tokens("fees", 5)
        )

        return {
            "summary": {
                "total_fees_sol": stats.total_fees_earned / 1e9,
                "unclaimed_sol": stats.fees_unclaimed / 1e9,
                "total_trades": stats.trade_count,
                "unique_users": stats.unique_users
            },
            "last_7_days": [
                {
                    "date": h.end_time.strftime("%Y-%m-%d"),
                    "fees_sol": h.fees_earned / 1e9,
                    "volume_sol": h.volume / 1e9,
                    "trades": h.trade_count
                }
                for h in history
            ],
            "top_tokens": [
                {
                    "symbol": t.token_symbol,
                    "fees_sol": t.fees_earned / 1e9
                }
                for t in tokens
            ]
        }

    return router


# =============================================================================
# STANDALONE RUNNER
# =============================================================================

if __name__ == "__main__":
    import os
    from fastapi import FastAPI
    import uvicorn

    app = FastAPI(title="Partner Stats API")

    service = PartnerStatsService(
        bags_api_key=os.getenv("BAGS_API_KEY", ""),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379")
    )

    @app.on_event("startup")
    async def startup():
        await service.connect()

    @app.on_event("shutdown")
    async def shutdown():
        await service.close()

    app.include_router(create_partner_stats_routes(service))

    uvicorn.run(app, host="0.0.0.0", port=8001)
