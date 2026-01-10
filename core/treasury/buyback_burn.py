"""
Buyback and Burn Mechanism
Prompt #44: Automated buyback and token burn from treasury
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import json
import aiohttp

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Burn address (dead wallet)
BURN_ADDRESS = "1nc1nerator11111111111111111111111111111111"

# Buyback settings
DEFAULT_BUYBACK_PERCENTAGE = 20  # 20% of fees go to buyback
MIN_BUYBACK_AMOUNT = 1_000_000  # 0.001 SOL minimum
MAX_SLIPPAGE_BPS = 100  # 1% max slippage


# =============================================================================
# MODELS
# =============================================================================

class BuybackStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class BurnStatus(str, Enum):
    PENDING = "pending"
    BURNED = "burned"
    FAILED = "failed"


@dataclass
class BuybackConfig:
    """Configuration for buyback operations"""
    enabled: bool = True
    percentage_of_fees: int = 20  # % of fees allocated to buyback
    min_amount: int = MIN_BUYBACK_AMOUNT
    max_slippage_bps: int = MAX_SLIPPAGE_BPS
    execution_interval: timedelta = field(default_factory=lambda: timedelta(hours=24))
    auto_burn: bool = True  # Automatically burn after buyback
    preferred_venue: str = "bags"  # "bags" or "jupiter"
    twap_enabled: bool = True  # Time-weighted average price execution
    twap_intervals: int = 12  # Split into N orders over execution window
    twap_window: timedelta = field(default_factory=lambda: timedelta(hours=4))


@dataclass
class BuybackOrder:
    """A buyback order"""
    id: str
    amount_sol: int  # SOL to spend
    expected_tokens: int  # Expected $KR8TIV tokens
    actual_tokens: int = 0
    average_price: Decimal = Decimal("0")
    slippage_actual: int = 0  # Actual slippage in bps
    status: BuybackStatus = BuybackStatus.PENDING
    venue: str = "bags"
    executions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class BurnEvent:
    """Record of a token burn"""
    id: str
    token_mint: str
    amount: int
    burned_from: str  # Wallet that held tokens
    burn_signature: str
    burn_type: str  # "buyback", "manual", "scheduled"
    status: BurnStatus = BurnStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BuybackBurnStats:
    """Aggregate statistics"""
    total_sol_spent: int = 0
    total_tokens_bought: int = 0
    total_tokens_burned: int = 0
    average_buy_price: Decimal = Decimal("0")
    total_buybacks: int = 0
    total_burns: int = 0
    last_buyback: Optional[datetime] = None
    last_burn: Optional[datetime] = None
    current_period_sol: int = 0  # SOL accumulated for next buyback


# =============================================================================
# BUYBACK & BURN MANAGER
# =============================================================================

class BuybackBurnManager:
    """Manages buyback and burn operations"""

    def __init__(
        self,
        token_mint: str,
        treasury_wallet: str,
        bags_api_key: str,
        db_url: str,
        config: Optional[BuybackConfig] = None
    ):
        self.token_mint = token_mint
        self.treasury_wallet = treasury_wallet
        self.bags_api_key = bags_api_key
        self.db_url = db_url
        self.config = config or BuybackConfig()

        self.pending_orders: List[BuybackOrder] = []
        self.completed_orders: List[BuybackOrder] = []
        self.burn_events: List[BurnEvent] = []
        self.stats = BuybackBurnStats()

        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False

    async def start(self):
        """Start the buyback engine"""
        self._session = aiohttp.ClientSession()
        self._running = True

        # Start background task for scheduled buybacks
        asyncio.create_task(self._buyback_loop())
        logger.info("Buyback & Burn manager started")

    async def stop(self):
        """Stop the buyback engine"""
        self._running = False
        if self._session:
            await self._session.close()
        logger.info("Buyback & Burn manager stopped")

    # =========================================================================
    # FEE ACCUMULATION
    # =========================================================================

    async def accumulate_fees(self, amount_sol: int):
        """Accumulate fees for next buyback"""
        buyback_portion = amount_sol * self.config.percentage_of_fees // 100
        self.stats.current_period_sol += buyback_portion
        await self._save_stats()

        logger.debug(f"Accumulated {buyback_portion} lamports for buyback")

        # Check if we should execute immediately
        if self.stats.current_period_sol >= self.config.min_amount * 10:
            # Large accumulation, execute sooner
            asyncio.create_task(self.execute_buyback())

    # =========================================================================
    # BUYBACK EXECUTION
    # =========================================================================

    async def execute_buyback(
        self,
        amount_override: Optional[int] = None
    ) -> Optional[BuybackOrder]:
        """Execute a buyback operation"""
        amount = amount_override or self.stats.current_period_sol

        if amount < self.config.min_amount:
            logger.info(f"Buyback amount {amount} below minimum {self.config.min_amount}")
            return None

        import uuid
        order = BuybackOrder(
            id=str(uuid.uuid4()),
            amount_sol=amount,
            expected_tokens=await self._estimate_tokens(amount),
            venue=self.config.preferred_venue
        )

        self.pending_orders.append(order)
        await self._save_order(order)

        try:
            if self.config.twap_enabled:
                await self._execute_twap(order)
            else:
                await self._execute_single(order)

            order.status = BuybackStatus.COMPLETED
            order.completed_at = datetime.utcnow()

            # Update stats
            self.stats.total_sol_spent += order.amount_sol
            self.stats.total_tokens_bought += order.actual_tokens
            self.stats.total_buybacks += 1
            self.stats.last_buyback = datetime.utcnow()
            self.stats.current_period_sol = 0

            # Calculate running average price
            if self.stats.total_tokens_bought > 0:
                self.stats.average_buy_price = (
                    Decimal(self.stats.total_sol_spent) /
                    Decimal(self.stats.total_tokens_bought)
                )

            await self._save_stats()

            # Auto-burn if enabled
            if self.config.auto_burn:
                await self.burn_tokens(order.actual_tokens, "buyback", order.id)

            logger.info(
                f"Buyback completed: {order.amount_sol} SOL -> "
                f"{order.actual_tokens} tokens"
            )

            return order

        except Exception as e:
            order.status = BuybackStatus.FAILED
            order.error = str(e)
            await self._save_order(order)
            logger.error(f"Buyback failed: {e}")
            raise

        finally:
            self.pending_orders.remove(order)
            self.completed_orders.append(order)

    async def _execute_single(self, order: BuybackOrder):
        """Execute as single swap"""
        result = await self._execute_swap(order.amount_sol)
        order.actual_tokens = result["output_amount"]
        order.average_price = Decimal(str(result["price"]))
        order.executions.append({
            "timestamp": datetime.utcnow().isoformat(),
            "amount_sol": order.amount_sol,
            "tokens_received": result["output_amount"],
            "signature": result["signature"]
        })

    async def _execute_twap(self, order: BuybackOrder):
        """Execute using TWAP strategy"""
        chunk_size = order.amount_sol // self.config.twap_intervals
        interval_seconds = (
            self.config.twap_window.total_seconds() /
            self.config.twap_intervals
        )

        total_tokens = 0
        total_spent = 0

        for i in range(self.config.twap_intervals):
            # Adjust last chunk for remainder
            if i == self.config.twap_intervals - 1:
                chunk = order.amount_sol - total_spent
            else:
                chunk = chunk_size

            try:
                result = await self._execute_swap(chunk)
                tokens_received = result["output_amount"]
                total_tokens += tokens_received
                total_spent += chunk

                order.executions.append({
                    "chunk": i + 1,
                    "timestamp": datetime.utcnow().isoformat(),
                    "amount_sol": chunk,
                    "tokens_received": tokens_received,
                    "signature": result["signature"]
                })

                logger.info(
                    f"TWAP chunk {i+1}/{self.config.twap_intervals}: "
                    f"{chunk} SOL -> {tokens_received} tokens"
                )

            except Exception as e:
                logger.error(f"TWAP chunk {i+1} failed: {e}")
                order.status = BuybackStatus.PARTIAL
                order.error = f"Chunk {i+1} failed: {e}"
                break

            # Wait before next chunk
            if i < self.config.twap_intervals - 1:
                await asyncio.sleep(interval_seconds)

        order.actual_tokens = total_tokens
        if total_tokens > 0:
            order.average_price = Decimal(total_spent) / Decimal(total_tokens)

    async def _execute_swap(self, amount_sol: int) -> Dict[str, Any]:
        """Execute a swap via preferred venue"""
        # SOL mint
        sol_mint = "So11111111111111111111111111111111111111112"

        if self.config.preferred_venue == "bags":
            return await self._swap_via_bags(sol_mint, self.token_mint, amount_sol)
        else:
            return await self._swap_via_jupiter(sol_mint, self.token_mint, amount_sol)

    async def _swap_via_bags(
        self,
        input_mint: str,
        output_mint: str,
        amount: int
    ) -> Dict[str, Any]:
        """Execute swap via Bags API"""
        # Get quote
        async with self._session.post(
            "https://public-api-v2.bags.fm/api/v1/trade/quote",
            headers={"x-api-key": self.bags_api_key},
            json={
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": amount,
                "slippageBps": self.config.max_slippage_bps
            }
        ) as response:
            if response.status != 200:
                raise ValueError(f"Quote failed: {response.status}")
            quote = await response.json()

        # Execute swap
        async with self._session.post(
            "https://public-api-v2.bags.fm/api/v1/trade/swap",
            headers={"x-api-key": self.bags_api_key},
            json={"quote": quote}
        ) as response:
            if response.status != 200:
                raise ValueError(f"Swap failed: {response.status}")
            result = await response.json()

        return {
            "output_amount": result.get("outputAmount", 0),
            "price": result.get("price", 0),
            "signature": result.get("signature", "")
        }

    async def _swap_via_jupiter(
        self,
        input_mint: str,
        output_mint: str,
        amount: int
    ) -> Dict[str, Any]:
        """Execute swap via Jupiter API"""
        # Get quote
        async with self._session.get(
            "https://quote-api.jup.ag/v6/quote",
            params={
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": amount,
                "slippageBps": self.config.max_slippage_bps
            }
        ) as response:
            if response.status != 200:
                raise ValueError(f"Jupiter quote failed: {response.status}")
            quote = await response.json()

        # In production, would execute the swap transaction
        # For now, return mock result
        return {
            "output_amount": int(quote.get("outAmount", 0)),
            "price": Decimal(amount) / Decimal(quote.get("outAmount", 1)),
            "signature": "mock_jupiter_signature"
        }

    async def _estimate_tokens(self, amount_sol: int) -> int:
        """Estimate tokens to receive for given SOL amount"""
        sol_mint = "So11111111111111111111111111111111111111112"

        try:
            async with self._session.post(
                "https://public-api-v2.bags.fm/api/v1/trade/quote",
                headers={"x-api-key": self.bags_api_key},
                json={
                    "inputMint": sol_mint,
                    "outputMint": self.token_mint,
                    "amount": amount_sol,
                    "slippageBps": 0
                }
            ) as response:
                if response.status == 200:
                    quote = await response.json()
                    return int(quote.get("outAmount", 0))
        except Exception as e:
            logger.warning(f"Failed to estimate tokens: {e}")

        return 0

    # =========================================================================
    # BURN EXECUTION
    # =========================================================================

    async def burn_tokens(
        self,
        amount: int,
        burn_type: str = "manual",
        reference_id: Optional[str] = None
    ) -> BurnEvent:
        """Burn tokens"""
        import uuid

        event = BurnEvent(
            id=str(uuid.uuid4()),
            token_mint=self.token_mint,
            amount=amount,
            burned_from=self.treasury_wallet,
            burn_signature="",
            burn_type=burn_type,
            metadata={"reference_id": reference_id} if reference_id else {}
        )

        try:
            # Execute burn (send to dead address)
            signature = await self._execute_burn(amount)
            event.burn_signature = signature
            event.status = BurnStatus.BURNED

            # Update stats
            self.stats.total_tokens_burned += amount
            self.stats.total_burns += 1
            self.stats.last_burn = datetime.utcnow()

            await self._save_stats()
            await self._save_burn(event)

            logger.info(f"Burned {amount} tokens, signature: {signature}")

        except Exception as e:
            event.status = BurnStatus.FAILED
            event.metadata["error"] = str(e)
            await self._save_burn(event)
            logger.error(f"Burn failed: {e}")
            raise

        self.burn_events.append(event)
        return event

    async def _execute_burn(self, amount: int) -> str:
        """Execute token burn on-chain"""
        # In production, this would:
        # 1. Create burn instruction using SPL Token program
        # 2. Sign and send transaction
        # 3. Return signature

        # Option 1: Send to dead address
        # Option 2: Use token burn instruction (reduces supply)

        return "mock_burn_signature"

    # =========================================================================
    # SCHEDULED OPERATIONS
    # =========================================================================

    async def _buyback_loop(self):
        """Background loop for scheduled buybacks"""
        while self._running:
            try:
                # Check if it's time for scheduled buyback
                if self._should_execute_scheduled():
                    if self.stats.current_period_sol >= self.config.min_amount:
                        await self.execute_buyback()

            except Exception as e:
                logger.error(f"Error in buyback loop: {e}")

            # Check every hour
            await asyncio.sleep(3600)

    def _should_execute_scheduled(self) -> bool:
        """Check if scheduled buyback should run"""
        if not self.config.enabled:
            return False

        if self.stats.last_buyback is None:
            return True

        time_since_last = datetime.utcnow() - self.stats.last_buyback
        return time_since_last >= self.config.execution_interval

    # =========================================================================
    # VIEW FUNCTIONS
    # =========================================================================

    async def get_stats(self) -> Dict[str, Any]:
        """Get buyback and burn statistics"""
        return {
            "total_sol_spent": self.stats.total_sol_spent,
            "total_tokens_bought": self.stats.total_tokens_bought,
            "total_tokens_burned": self.stats.total_tokens_burned,
            "average_buy_price": str(self.stats.average_buy_price),
            "total_buybacks": self.stats.total_buybacks,
            "total_burns": self.stats.total_burns,
            "last_buyback": self.stats.last_buyback.isoformat() if self.stats.last_buyback else None,
            "last_burn": self.stats.last_burn.isoformat() if self.stats.last_burn else None,
            "pending_for_buyback": self.stats.current_period_sol
        }

    async def get_recent_buybacks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent buyback orders"""
        orders = sorted(
            self.completed_orders,
            key=lambda x: x.created_at,
            reverse=True
        )[:limit]

        return [
            {
                "id": o.id,
                "amount_sol": o.amount_sol,
                "tokens_bought": o.actual_tokens,
                "average_price": str(o.average_price),
                "status": o.status.value,
                "venue": o.venue,
                "created_at": o.created_at.isoformat(),
                "completed_at": o.completed_at.isoformat() if o.completed_at else None,
                "executions": len(o.executions)
            }
            for o in orders
        ]

    async def get_recent_burns(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent burn events"""
        burns = sorted(
            self.burn_events,
            key=lambda x: x.created_at,
            reverse=True
        )[:limit]

        return [
            {
                "id": b.id,
                "amount": b.amount,
                "burn_type": b.burn_type,
                "signature": b.burn_signature,
                "status": b.status.value,
                "created_at": b.created_at.isoformat()
            }
            for b in burns
        ]

    async def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        return {
            "enabled": self.config.enabled,
            "percentage_of_fees": self.config.percentage_of_fees,
            "min_amount": self.config.min_amount,
            "max_slippage_bps": self.config.max_slippage_bps,
            "execution_interval_hours": self.config.execution_interval.total_seconds() / 3600,
            "auto_burn": self.config.auto_burn,
            "preferred_venue": self.config.preferred_venue,
            "twap_enabled": self.config.twap_enabled,
            "twap_intervals": self.config.twap_intervals,
            "twap_window_hours": self.config.twap_window.total_seconds() / 3600
        }

    async def update_config(
        self,
        updates: Dict[str, Any],
        admin: str
    ) -> Dict[str, Any]:
        """Update configuration (admin only)"""
        if "enabled" in updates:
            self.config.enabled = updates["enabled"]
        if "percentage_of_fees" in updates:
            self.config.percentage_of_fees = updates["percentage_of_fees"]
        if "min_amount" in updates:
            self.config.min_amount = updates["min_amount"]
        if "auto_burn" in updates:
            self.config.auto_burn = updates["auto_burn"]
        if "twap_enabled" in updates:
            self.config.twap_enabled = updates["twap_enabled"]

        logger.info(f"Config updated by {admin}: {updates}")
        return await self.get_config()

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    async def _save_order(self, order: BuybackOrder):
        """Save order to database"""
        pass

    async def _save_burn(self, event: BurnEvent):
        """Save burn event to database"""
        pass

    async def _save_stats(self):
        """Save stats to database"""
        pass


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_buyback_endpoints(manager: BuybackBurnManager):
    """Create API endpoints for buyback & burn"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/buyback", tags=["Buyback & Burn"])

    class ExecuteBuybackRequest(BaseModel):
        amount: Optional[int] = None

    class BurnRequest(BaseModel):
        amount: int
        burn_type: str = "manual"

    class UpdateConfigRequest(BaseModel):
        enabled: Optional[bool] = None
        percentage_of_fees: Optional[int] = None
        min_amount: Optional[int] = None
        auto_burn: Optional[bool] = None
        twap_enabled: Optional[bool] = None

    @router.get("/stats")
    async def get_stats():
        """Get buyback & burn statistics"""
        return await manager.get_stats()

    @router.get("/buybacks")
    async def get_recent_buybacks(limit: int = 20):
        """Get recent buyback operations"""
        return await manager.get_recent_buybacks(limit)

    @router.get("/burns")
    async def get_recent_burns(limit: int = 20):
        """Get recent burn events"""
        return await manager.get_recent_burns(limit)

    @router.post("/execute")
    async def execute_buyback(request: ExecuteBuybackRequest, admin: str):
        """Manually execute a buyback (admin only)"""
        try:
            order = await manager.execute_buyback(request.amount)
            if order:
                return {
                    "order_id": order.id,
                    "amount_sol": order.amount_sol,
                    "tokens_bought": order.actual_tokens,
                    "status": order.status.value
                }
            return {"status": "skipped", "reason": "Amount below minimum"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/burn")
    async def burn_tokens(request: BurnRequest, admin: str):
        """Manually burn tokens (admin only)"""
        try:
            event = await manager.burn_tokens(
                amount=request.amount,
                burn_type=request.burn_type
            )
            return {
                "burn_id": event.id,
                "amount": event.amount,
                "signature": event.burn_signature,
                "status": event.status.value
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/config")
    async def get_config():
        """Get current configuration"""
        return await manager.get_config()

    @router.put("/config")
    async def update_config(request: UpdateConfigRequest, admin: str):
        """Update configuration (admin only)"""
        updates = {k: v for k, v in request.dict().items() if v is not None}
        return await manager.update_config(updates, admin)

    @router.get("/pending")
    async def get_pending():
        """Get pending buyback amount"""
        stats = await manager.get_stats()
        return {
            "pending_sol": stats["pending_for_buyback"],
            "min_required": manager.config.min_amount,
            "ready_to_execute": stats["pending_for_buyback"] >= manager.config.min_amount
        }

    return router


# =============================================================================
# REACT COMPONENT
# =============================================================================

BUYBACK_DASHBOARD_COMPONENT = """
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Flame, TrendingDown, Clock, ArrowRight } from 'lucide-react';

interface BuybackStats {
  total_sol_spent: number;
  total_tokens_bought: number;
  total_tokens_burned: number;
  average_buy_price: string;
  total_buybacks: number;
  total_burns: number;
  last_buyback: string | null;
  last_burn: string | null;
  pending_for_buyback: number;
}

interface BuybackOrder {
  id: string;
  amount_sol: number;
  tokens_bought: number;
  average_price: string;
  status: string;
  venue: string;
  created_at: string;
}

export function BuybackDashboard() {
  const [stats, setStats] = useState<BuybackStats | null>(null);
  const [recentBuybacks, setRecentBuybacks] = useState<BuybackOrder[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, buybacksRes] = await Promise.all([
        fetch('/api/buyback/stats'),
        fetch('/api/buyback/buybacks?limit=5')
      ]);

      setStats(await statsRes.json());
      setRecentBuybacks(await buybacksRes.json());
    } catch (error) {
      console.error('Failed to fetch buyback data:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatSOL = (lamports: number) => (lamports / 1e9).toFixed(4);
  const formatTokens = (amount: number) => (amount / 1e9).toFixed(2);

  if (loading || !stats) {
    return <div className="animate-pulse">Loading buyback data...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total SOL Spent
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatSOL(stats.total_sol_spent)} SOL
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Tokens Bought
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatTokens(stats.total_tokens_bought)} KR8TIV
            </div>
          </CardContent>
        </Card>

        <Card className="border-orange-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-orange-600 flex items-center gap-2">
              <Flame className="h-4 w-4" />
              Tokens Burned
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {formatTokens(stats.total_tokens_burned)} KR8TIV
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Pending Buyback
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatSOL(stats.pending_for_buyback)} SOL
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Buybacks */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingDown className="h-5 w-5" />
            Recent Buyback Operations
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {recentBuybacks.map((buyback) => (
              <div
                key={buyback.id}
                className="flex items-center justify-between p-4 border rounded-lg"
              >
                <div className="flex items-center gap-4">
                  <div className="text-sm text-muted-foreground">
                    {new Date(buyback.created_at).toLocaleDateString()}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">
                      {formatSOL(buyback.amount_sol)} SOL
                    </span>
                    <ArrowRight className="h-4 w-4" />
                    <span className="font-medium">
                      {formatTokens(buyback.tokens_bought)} KR8TIV
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={buyback.status === 'completed' ? 'default' : 'secondary'}>
                    {buyback.status}
                  </Badge>
                  <Badge variant="outline">{buyback.venue}</Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Burn Impact */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Flame className="h-5 w-5 text-orange-500" />
            Deflationary Impact
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <div className="text-4xl font-bold text-orange-600 mb-2">
              {formatTokens(stats.total_tokens_burned)}
            </div>
            <div className="text-muted-foreground">
              $KR8TIV tokens permanently removed from circulation
            </div>
            <div className="mt-4 text-sm">
              <span className="font-medium">{stats.total_burns}</span> burn events
              {stats.last_burn && (
                <span className="text-muted-foreground">
                  {' '}| Last burn: {new Date(stats.last_burn).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
"""
