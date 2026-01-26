"""
Batch Trade Processor
Prompt #38: DCA and scheduled order processor
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import json
from decimal import Decimal
import aiohttp
from aiohttp import ClientTimeout
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from core.feature_manager import is_enabled_default
from core.security.emergency_shutdown import is_emergency_shutdown

logger = logging.getLogger(__name__)

_KILL_SWITCH_VALUES = ("1", "true", "yes", "on")


def _kill_switch_active() -> bool:
    """Check if the global kill switch is active via environment flags."""
    return (
        os.getenv("LIFEOS_KILL_SWITCH", "").lower() in _KILL_SWITCH_VALUES
        or os.getenv("KILL_SWITCH", "").lower() in _KILL_SWITCH_VALUES
    )


# =============================================================================
# MODELS
# =============================================================================

class OrderFrequency(str, Enum):
    """Frequency for recurring orders"""
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class OrderType(str, Enum):
    """Type of scheduled order"""
    DCA = "dca"  # Dollar cost averaging
    LIMIT = "limit"  # Execute when price reaches target
    PERCENTAGE = "percentage"  # Sell X% when price > Y


class OrderStatus(str, Enum):
    """Order status"""
    PENDING = "pending"
    ACTIVE = "active"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledOrder:
    """A scheduled/recurring trade order"""
    id: str
    user_id: str
    order_type: OrderType
    input_token: str
    output_token: str
    amount: Decimal  # Fixed amount or percentage
    is_percentage: bool = False
    frequency: OrderFrequency = OrderFrequency.ONCE
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    status: OrderStatus = OrderStatus.PENDING
    trigger_condition: Optional[Dict[str, Any]] = None  # For limit orders
    max_executions: Optional[int] = None
    execution_count: int = 0
    slippage_bps: int = 100
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderExecution:
    """Record of an order execution"""
    id: str
    order_id: str
    user_id: str
    input_token: str
    output_token: str
    input_amount: int
    output_amount: int
    price: Decimal
    fees: int
    partner_fee_earned: int
    signature: str
    venue: str
    status: str
    executed_at: datetime
    error: Optional[str] = None


# =============================================================================
# DATABASE INTERFACE
# =============================================================================

class OrderDatabase:
    """Database interface for scheduled orders"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        # In production, use SQLAlchemy or similar

    async def create_order(self, order: ScheduledOrder) -> str:
        """Create a new scheduled order"""
        # INSERT INTO scheduled_orders ...
        logger.info(f"Created order {order.id}")
        return order.id

    async def get_order(self, order_id: str) -> Optional[ScheduledOrder]:
        """Get order by ID"""
        # SELECT * FROM scheduled_orders WHERE id = ?
        pass

    async def get_user_orders(self, user_id: str) -> List[ScheduledOrder]:
        """Get all orders for a user"""
        # SELECT * FROM scheduled_orders WHERE user_id = ?
        return []

    async def get_pending_orders(self) -> List[ScheduledOrder]:
        """Get all orders due for execution"""
        # SELECT * FROM scheduled_orders
        # WHERE status = 'active' AND next_run <= NOW()
        return []

    async def update_order(self, order: ScheduledOrder):
        """Update an order"""
        # UPDATE scheduled_orders SET ... WHERE id = ?
        pass

    async def record_execution(self, execution: OrderExecution):
        """Record an execution"""
        # INSERT INTO order_executions ...
        pass

    async def get_executions(
        self,
        order_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[OrderExecution]:
        """Get execution history"""
        # SELECT * FROM order_executions WHERE ...
        return []


# =============================================================================
# BATCH PROCESSOR
# =============================================================================

class BatchTradeProcessor:
    """Processes scheduled and recurring trade orders"""

    def __init__(
        self,
        bags_api_key: str,
        db_url: str,
        notification_callback: Optional[Callable] = None
    ):
        self.bags_api_key = bags_api_key
        self.db = OrderDatabase(db_url)
        self.notify = notification_callback
        self.scheduler = AsyncIOScheduler()
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False

    async def start(self):
        """Start the processor"""
        # Configure timeouts: 60s total, 30s connect (for bags.fm API calls)
        timeout = ClientTimeout(total=60, connect=30)
        self._session = aiohttp.ClientSession(timeout=timeout)
        self.scheduler.start()

        # Add recurring job to process pending orders
        self.scheduler.add_job(
            self._process_pending_orders,
            IntervalTrigger(minutes=1),
            id="process_pending",
            replace_existing=True
        )

        self._running = True
        logger.info("Batch trade processor started")

    async def stop(self):
        """Stop the processor"""
        self._running = False
        self.scheduler.shutdown()
        if self._session:
            await self._session.close()
        logger.info("Batch trade processor stopped")

    # =========================================================================
    # ORDER MANAGEMENT
    # =========================================================================

    async def create_dca_order(
        self,
        user_id: str,
        input_token: str,
        output_token: str,
        amount_per_execution: Decimal,
        frequency: OrderFrequency,
        total_executions: Optional[int] = None,
        start_time: Optional[datetime] = None
    ) -> ScheduledOrder:
        """Create a DCA order"""
        import uuid

        order = ScheduledOrder(
            id=str(uuid.uuid4()),
            user_id=user_id,
            order_type=OrderType.DCA,
            input_token=input_token,
            output_token=output_token,
            amount=amount_per_execution,
            frequency=frequency,
            next_run=start_time or datetime.utcnow(),
            max_executions=total_executions,
            status=OrderStatus.ACTIVE
        )

        await self.db.create_order(order)
        return order

    async def create_limit_order(
        self,
        user_id: str,
        input_token: str,
        output_token: str,
        amount: Decimal,
        target_price: Decimal,
        above_or_below: str = "above"  # "above" or "below"
    ) -> ScheduledOrder:
        """Create a limit order"""
        import uuid

        order = ScheduledOrder(
            id=str(uuid.uuid4()),
            user_id=user_id,
            order_type=OrderType.LIMIT,
            input_token=input_token,
            output_token=output_token,
            amount=amount,
            trigger_condition={
                "type": "price",
                "target": str(target_price),
                "direction": above_or_below
            },
            status=OrderStatus.ACTIVE
        )

        await self.db.create_order(order)
        return order

    async def create_percentage_sell(
        self,
        user_id: str,
        token: str,
        percentage: Decimal,
        output_token: str,
        target_price: Decimal
    ) -> ScheduledOrder:
        """Create a percentage sell order"""
        import uuid

        order = ScheduledOrder(
            id=str(uuid.uuid4()),
            user_id=user_id,
            order_type=OrderType.PERCENTAGE,
            input_token=token,
            output_token=output_token,
            amount=percentage,
            is_percentage=True,
            trigger_condition={
                "type": "price",
                "target": str(target_price),
                "direction": "above"
            },
            status=OrderStatus.ACTIVE
        )

        await self.db.create_order(order)
        return order

    async def cancel_order(self, order_id: str, user_id: str) -> bool:
        """Cancel an order"""
        order = await self.db.get_order(order_id)
        if not order or order.user_id != user_id:
            return False

        order.status = OrderStatus.CANCELLED
        await self.db.update_order(order)

        if self.notify:
            await self.notify(
                user_id,
                "order_cancelled",
                {"order_id": order_id}
            )

        return True

    # =========================================================================
    # ORDER PROCESSING
    # =========================================================================

    async def _process_pending_orders(self):
        """Process all pending orders"""
        if not self._running:
            return

        try:
            orders = await self.db.get_pending_orders()
            logger.info(f"Processing {len(orders)} pending orders")

            for order in orders:
                try:
                    await self._execute_order(order)
                except Exception as e:
                    logger.error(f"Error executing order {order.id}: {e}")
                    order.status = OrderStatus.FAILED
                    order.metadata["last_error"] = str(e)
                    await self.db.update_order(order)

        except Exception as e:
            logger.error(f"Error in order processing loop: {e}")

    async def _execute_order(self, order: ScheduledOrder):
        """Execute a single order"""
        # Check trigger conditions for limit orders
        if order.order_type in [OrderType.LIMIT, OrderType.PERCENTAGE]:
            if not await self._check_trigger_condition(order):
                return

        # Mark as executing
        order.status = OrderStatus.EXECUTING
        await self.db.update_order(order)

        # Calculate amount
        amount = await self._calculate_amount(order)

        # Execute via Bags API (earn partner fees!)
        try:
            result = await self._execute_trade(
                order.input_token,
                order.output_token,
                amount,
                order.slippage_bps
            )

            # Record execution
            execution = OrderExecution(
                id=result.get("id", ""),
                order_id=order.id,
                user_id=order.user_id,
                input_token=order.input_token,
                output_token=order.output_token,
                input_amount=amount,
                output_amount=result.get("output_amount", 0),
                price=Decimal(str(result.get("price", 0))),
                fees=result.get("fees", 0),
                partner_fee_earned=result.get("partner_fee", 0),
                signature=result.get("signature", ""),
                venue=result.get("venue", "bags"),
                status="success",
                executed_at=datetime.utcnow()
            )

            await self.db.record_execution(execution)

            # Update order
            order.execution_count += 1
            order.last_run = datetime.utcnow()

            # Check if completed
            if order.max_executions and order.execution_count >= order.max_executions:
                order.status = OrderStatus.COMPLETED
            elif order.order_type in [OrderType.LIMIT, OrderType.PERCENTAGE]:
                order.status = OrderStatus.COMPLETED  # One-time orders
            else:
                order.status = OrderStatus.ACTIVE
                order.next_run = self._calculate_next_run(order)

            await self.db.update_order(order)

            # Notify user
            if self.notify:
                await self.notify(
                    order.user_id,
                    "order_executed",
                    {
                        "order_id": order.id,
                        "input_amount": amount,
                        "output_amount": result.get("output_amount", 0),
                        "signature": result.get("signature", "")
                    }
                )

        except Exception as e:
            order.status = OrderStatus.FAILED
            order.metadata["last_error"] = str(e)
            await self.db.update_order(order)

            if self.notify:
                await self.notify(
                    order.user_id,
                    "order_failed",
                    {"order_id": order.id, "error": str(e)}
                )

            raise

    async def _check_trigger_condition(self, order: ScheduledOrder) -> bool:
        """Check if trigger condition is met"""
        if not order.trigger_condition:
            return True

        if order.trigger_condition.get("type") == "price":
            current_price = await self._get_current_price(
                order.input_token,
                order.output_token
            )

            target = Decimal(order.trigger_condition.get("target", "0"))
            direction = order.trigger_condition.get("direction", "above")

            if direction == "above":
                return current_price >= target
            else:
                return current_price <= target

        return True

    async def _calculate_amount(self, order: ScheduledOrder) -> int:
        """Calculate trade amount"""
        if order.is_percentage:
            # Get user's token balance
            balance = await self._get_token_balance(
                order.user_id,
                order.input_token
            )
            return int(balance * order.amount / 100)
        else:
            return int(order.amount)

    def _calculate_next_run(self, order: ScheduledOrder) -> datetime:
        """Calculate next run time based on frequency"""
        now = datetime.utcnow()

        if order.frequency == OrderFrequency.HOURLY:
            return now + timedelta(hours=1)
        elif order.frequency == OrderFrequency.DAILY:
            return now + timedelta(days=1)
        elif order.frequency == OrderFrequency.WEEKLY:
            return now + timedelta(weeks=1)
        elif order.frequency == OrderFrequency.MONTHLY:
            return now + timedelta(days=30)
        else:
            return now

    async def _execute_trade(
        self,
        input_token: str,
        output_token: str,
        amount: int,
        slippage_bps: int
    ) -> Dict[str, Any]:
        """Execute trade via Bags API"""
        if _kill_switch_active():
            logger.warning("Batch trade blocked: kill switch active")
            raise ValueError("Kill switch active")

        if is_emergency_shutdown():
            logger.error("Batch trade blocked: emergency shutdown active")
            raise ValueError("Emergency shutdown active")

        if not is_enabled_default("LIVE_TRADING_ENABLED", default=True):
            logger.warning("Batch trade blocked: LIVE_TRADING_ENABLED=false")
            raise ValueError("Live trading disabled by feature flag")

        # Get quote
        async with self._session.post(
            "https://public-api-v2.bags.fm/api/v1/trade/quote",
            headers={"x-api-key": self.bags_api_key},
            json={
                "inputMint": input_token,
                "outputMint": output_token,
                "amount": amount,
                "slippageBps": slippage_bps
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

        return result

    async def _get_current_price(
        self,
        input_token: str,
        output_token: str
    ) -> Decimal:
        """Get current token price"""
        # Would call price API
        return Decimal("1.0")

    async def _get_token_balance(
        self,
        user_id: str,
        token: str
    ) -> int:
        """Get user's token balance"""
        # Would query Solana
        return 0


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_batch_endpoints(processor: BatchTradeProcessor):
    """Create API endpoints for batch trading"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/batch", tags=["Batch Trading"])

    class CreateDCARequest(BaseModel):
        input_token: str
        output_token: str
        amount_per_execution: str
        frequency: str
        total_executions: Optional[int] = None

    class CreateLimitRequest(BaseModel):
        input_token: str
        output_token: str
        amount: str
        target_price: str
        direction: str = "above"

    @router.post("/dca")
    async def create_dca(user_id: str, request: CreateDCARequest):
        """Create a DCA order"""
        order = await processor.create_dca_order(
            user_id=user_id,
            input_token=request.input_token,
            output_token=request.output_token,
            amount_per_execution=Decimal(request.amount_per_execution),
            frequency=OrderFrequency(request.frequency),
            total_executions=request.total_executions
        )
        return {"order_id": order.id, "status": order.status.value}

    @router.post("/limit")
    async def create_limit(user_id: str, request: CreateLimitRequest):
        """Create a limit order"""
        order = await processor.create_limit_order(
            user_id=user_id,
            input_token=request.input_token,
            output_token=request.output_token,
            amount=Decimal(request.amount),
            target_price=Decimal(request.target_price),
            above_or_below=request.direction
        )
        return {"order_id": order.id, "status": order.status.value}

    @router.get("/orders")
    async def get_orders(user_id: str):
        """Get user's orders"""
        orders = await processor.db.get_user_orders(user_id)
        return [
            {
                "id": o.id,
                "type": o.order_type.value,
                "status": o.status.value,
                "amount": str(o.amount),
                "frequency": o.frequency.value,
                "next_run": o.next_run.isoformat() if o.next_run else None,
                "execution_count": o.execution_count
            }
            for o in orders
        ]

    @router.delete("/orders/{order_id}")
    async def cancel_order(order_id: str, user_id: str):
        """Cancel an order"""
        success = await processor.cancel_order(order_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Order not found")
        return {"status": "cancelled"}

    @router.get("/executions")
    async def get_executions(user_id: str, order_id: Optional[str] = None):
        """Get execution history"""
        executions = await processor.db.get_executions(
            order_id=order_id,
            user_id=user_id
        )
        return executions

    return router
