"""
DCA Scheduler

Manages automated DCA schedules and executions.
Supports various frequencies and intelligent execution timing.

Prompts #113-116: DCA Automation
"""

import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

# Safety flag
DCA_AUTOMATION_ENABLED = False


class ScheduleFrequency(str, Enum):
    """DCA schedule frequencies"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class ExecutionStatus(str, Enum):
    """Status of a DCA execution"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class DCASchedule:
    """A DCA schedule configuration"""
    schedule_id: str
    user_id: str
    token: str
    amount_per_execution: float  # USD
    frequency: ScheduleFrequency
    is_active: bool = True

    # Schedule details
    next_execution: Optional[datetime] = None
    last_execution: Optional[datetime] = None
    custom_interval_hours: int = 24  # For CUSTOM frequency

    # Execution settings
    max_slippage_pct: float = 1.0
    skip_if_price_above: Optional[float] = None  # Skip if price > this
    skip_if_volatility_above: Optional[float] = None  # Skip if vol > X%
    buy_extra_on_dip_pct: float = 0.0  # Buy X% more if price dipped

    # Funding source
    funding_wallet: str = ""
    funding_token: str = "USDC"

    # Limits
    total_budget: Optional[float] = None  # Total budget limit
    total_spent: float = 0.0
    execution_count: int = 0
    max_executions: Optional[int] = None  # Max number of buys

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    paused_at: Optional[datetime] = None
    notes: str = ""

    def __post_init__(self):
        if not self.schedule_id:
            data = f"{self.user_id}{self.token}{self.created_at.isoformat()}"
            self.schedule_id = f"DCA-{hashlib.sha256(data.encode()).hexdigest()[:8].upper()}"

        if not self.next_execution:
            self.next_execution = self._calculate_next_execution()

    def _calculate_next_execution(self) -> datetime:
        """Calculate next execution time based on frequency"""
        now = datetime.now()

        intervals = {
            ScheduleFrequency.HOURLY: timedelta(hours=1),
            ScheduleFrequency.DAILY: timedelta(days=1),
            ScheduleFrequency.WEEKLY: timedelta(weeks=1),
            ScheduleFrequency.BIWEEKLY: timedelta(weeks=2),
            ScheduleFrequency.MONTHLY: timedelta(days=30),
            ScheduleFrequency.CUSTOM: timedelta(hours=self.custom_interval_hours)
        }

        return now + intervals.get(self.frequency, timedelta(days=1))

    def is_budget_exhausted(self) -> bool:
        """Check if budget is exhausted"""
        if self.total_budget and self.total_spent >= self.total_budget:
            return True
        if self.max_executions and self.execution_count >= self.max_executions:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "schedule_id": self.schedule_id,
            "user_id": self.user_id,
            "token": self.token,
            "amount_per_execution": self.amount_per_execution,
            "frequency": self.frequency.value,
            "is_active": self.is_active,
            "next_execution": self.next_execution.isoformat() if self.next_execution else None,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
            "custom_interval_hours": self.custom_interval_hours,
            "max_slippage_pct": self.max_slippage_pct,
            "skip_if_price_above": self.skip_if_price_above,
            "skip_if_volatility_above": self.skip_if_volatility_above,
            "buy_extra_on_dip_pct": self.buy_extra_on_dip_pct,
            "funding_wallet": self.funding_wallet,
            "funding_token": self.funding_token,
            "total_budget": self.total_budget,
            "total_spent": self.total_spent,
            "execution_count": self.execution_count,
            "max_executions": self.max_executions,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
            "notes": self.notes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DCASchedule":
        """Create from dictionary"""
        def parse_dt(val):
            return datetime.fromisoformat(val) if val else None

        return cls(
            schedule_id=data["schedule_id"],
            user_id=data["user_id"],
            token=data["token"],
            amount_per_execution=data["amount_per_execution"],
            frequency=ScheduleFrequency(data["frequency"]),
            is_active=data.get("is_active", True),
            next_execution=parse_dt(data.get("next_execution")),
            last_execution=parse_dt(data.get("last_execution")),
            custom_interval_hours=data.get("custom_interval_hours", 24),
            max_slippage_pct=data.get("max_slippage_pct", 1.0),
            skip_if_price_above=data.get("skip_if_price_above"),
            skip_if_volatility_above=data.get("skip_if_volatility_above"),
            buy_extra_on_dip_pct=data.get("buy_extra_on_dip_pct", 0.0),
            funding_wallet=data.get("funding_wallet", ""),
            funding_token=data.get("funding_token", "USDC"),
            total_budget=data.get("total_budget"),
            total_spent=data.get("total_spent", 0.0),
            execution_count=data.get("execution_count", 0),
            max_executions=data.get("max_executions"),
            created_at=parse_dt(data.get("created_at")) or datetime.now(),
            updated_at=parse_dt(data.get("updated_at")) or datetime.now(),
            paused_at=parse_dt(data.get("paused_at")),
            notes=data.get("notes", "")
        )


@dataclass
class DCAExecution:
    """A single DCA execution record"""
    execution_id: str
    schedule_id: str
    user_id: str
    token: str
    status: ExecutionStatus = ExecutionStatus.PENDING

    # Amounts
    intended_amount: float = 0.0
    executed_amount: float = 0.0
    tokens_received: float = 0.0
    price_at_execution: float = 0.0
    fees_paid: float = 0.0

    # Timing
    scheduled_at: datetime = field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None

    # Result
    tx_hash: Optional[str] = None
    error_message: Optional[str] = None
    skip_reason: Optional[str] = None

    def __post_init__(self):
        if not self.execution_id:
            data = f"{self.schedule_id}{self.scheduled_at.isoformat()}"
            self.execution_id = f"DCAX-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "execution_id": self.execution_id,
            "schedule_id": self.schedule_id,
            "user_id": self.user_id,
            "token": self.token,
            "status": self.status.value,
            "intended_amount": self.intended_amount,
            "executed_amount": self.executed_amount,
            "tokens_received": self.tokens_received,
            "price_at_execution": self.price_at_execution,
            "fees_paid": self.fees_paid,
            "scheduled_at": self.scheduled_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "tx_hash": self.tx_hash,
            "error_message": self.error_message,
            "skip_reason": self.skip_reason
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DCAExecution":
        """Create from dictionary"""
        return cls(
            execution_id=data["execution_id"],
            schedule_id=data["schedule_id"],
            user_id=data["user_id"],
            token=data["token"],
            status=ExecutionStatus(data.get("status", "pending")),
            intended_amount=data.get("intended_amount", 0.0),
            executed_amount=data.get("executed_amount", 0.0),
            tokens_received=data.get("tokens_received", 0.0),
            price_at_execution=data.get("price_at_execution", 0.0),
            fees_paid=data.get("fees_paid", 0.0),
            scheduled_at=datetime.fromisoformat(data["scheduled_at"]) if data.get("scheduled_at") else datetime.now(),
            executed_at=datetime.fromisoformat(data["executed_at"]) if data.get("executed_at") else None,
            tx_hash=data.get("tx_hash"),
            error_message=data.get("error_message"),
            skip_reason=data.get("skip_reason")
        )


class DCAScheduler:
    """
    Manages DCA schedules and executions

    WARNING: Actual execution is DISABLED until security audit.
    """

    def __init__(
        self,
        storage_path: str = "data/dca/schedules.json",
        swap_executor: Optional[Callable] = None,
        price_fetcher: Optional[Callable] = None
    ):
        self.storage_path = Path(storage_path)
        self.swap_executor = swap_executor
        self.price_fetcher = price_fetcher
        self.schedules: Dict[str, DCASchedule] = {}
        self.executions: Dict[str, DCAExecution] = {}
        self.user_schedules: Dict[str, List[str]] = {}  # user_id -> schedule_ids
        self._running = False
        self._load()

    def _load(self):
        """Load schedules from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for sched_data in data.get("schedules", []):
                schedule = DCASchedule.from_dict(sched_data)
                self.schedules[schedule.schedule_id] = schedule

                if schedule.user_id not in self.user_schedules:
                    self.user_schedules[schedule.user_id] = []
                self.user_schedules[schedule.user_id].append(schedule.schedule_id)

            for exec_data in data.get("executions", [])[-1000:]:  # Keep last 1000
                execution = DCAExecution.from_dict(exec_data)
                self.executions[execution.execution_id] = execution

            logger.info(f"Loaded {len(self.schedules)} DCA schedules")

        except Exception as e:
            logger.error(f"Failed to load DCA schedules: {e}")

    def _save(self):
        """Save schedules to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "schedules": [s.to_dict() for s in self.schedules.values()],
                "executions": [e.to_dict() for e in list(self.executions.values())[-1000:]],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save DCA schedules: {e}")
            raise

    async def create_schedule(
        self,
        user_id: str,
        token: str,
        amount: float,
        frequency: ScheduleFrequency,
        funding_wallet: str = "",
        total_budget: Optional[float] = None,
        max_executions: Optional[int] = None,
        **kwargs
    ) -> DCASchedule:
        """Create a new DCA schedule"""
        schedule = DCASchedule(
            schedule_id="",
            user_id=user_id,
            token=token,
            amount_per_execution=amount,
            frequency=frequency,
            funding_wallet=funding_wallet,
            total_budget=total_budget,
            max_executions=max_executions,
            **{k: v for k, v in kwargs.items() if hasattr(DCASchedule, k)}
        )

        self.schedules[schedule.schedule_id] = schedule

        if user_id not in self.user_schedules:
            self.user_schedules[user_id] = []
        self.user_schedules[user_id].append(schedule.schedule_id)

        self._save()
        logger.info(f"Created DCA schedule {schedule.schedule_id} for {user_id}")
        return schedule

    async def get_schedule(self, schedule_id: str) -> Optional[DCASchedule]:
        """Get a schedule by ID"""
        return self.schedules.get(schedule_id)

    async def get_user_schedules(self, user_id: str) -> List[DCASchedule]:
        """Get all schedules for a user"""
        schedule_ids = self.user_schedules.get(user_id, [])
        return [self.schedules[sid] for sid in schedule_ids if sid in self.schedules]

    async def pause_schedule(self, schedule_id: str) -> bool:
        """Pause a schedule"""
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            return False

        schedule.is_active = False
        schedule.paused_at = datetime.now()
        schedule.updated_at = datetime.now()
        self._save()

        logger.info(f"Paused DCA schedule {schedule_id}")
        return True

    async def resume_schedule(self, schedule_id: str) -> bool:
        """Resume a paused schedule"""
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            return False

        schedule.is_active = True
        schedule.paused_at = None
        schedule.next_execution = schedule._calculate_next_execution()
        schedule.updated_at = datetime.now()
        self._save()

        logger.info(f"Resumed DCA schedule {schedule_id}")
        return True

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule"""
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            return False

        del self.schedules[schedule_id]

        if schedule.user_id in self.user_schedules:
            if schedule_id in self.user_schedules[schedule.user_id]:
                self.user_schedules[schedule.user_id].remove(schedule_id)

        self._save()
        logger.info(f"Deleted DCA schedule {schedule_id}")
        return True

    async def check_and_execute_due(self):
        """Check for due schedules and execute them"""
        if not DCA_AUTOMATION_ENABLED:
            logger.debug("DCA automation is disabled")
            return

        now = datetime.now()
        due_schedules = [
            s for s in self.schedules.values()
            if s.is_active and s.next_execution and now >= s.next_execution
        ]

        for schedule in due_schedules:
            if schedule.is_budget_exhausted():
                schedule.is_active = False
                continue

            await self._execute_dca(schedule)

        if due_schedules:
            self._save()

    async def _execute_dca(self, schedule: DCASchedule):
        """Execute a single DCA purchase"""
        execution = DCAExecution(
            execution_id="",
            schedule_id=schedule.schedule_id,
            user_id=schedule.user_id,
            token=schedule.token,
            intended_amount=schedule.amount_per_execution
        )

        try:
            # Check conditions
            if schedule.skip_if_price_above and self.price_fetcher:
                current_price = await self.price_fetcher(schedule.token)
                if current_price > schedule.skip_if_price_above:
                    execution.status = ExecutionStatus.SKIPPED
                    execution.skip_reason = f"Price ${current_price} above threshold ${schedule.skip_if_price_above}"
                    self.executions[execution.execution_id] = execution
                    schedule.next_execution = schedule._calculate_next_execution()
                    return

            # Calculate amount with dip adjustment
            amount = schedule.amount_per_execution

            # Execute swap
            if self.swap_executor:
                execution.status = ExecutionStatus.EXECUTING

                result = await self.swap_executor(
                    token_in=schedule.funding_token,
                    token_out=schedule.token,
                    amount=amount,
                    max_slippage=schedule.max_slippage_pct / 100
                )

                if result.get("success"):
                    execution.status = ExecutionStatus.COMPLETED
                    execution.executed_amount = amount
                    execution.tokens_received = result.get("amount_out", 0)
                    execution.price_at_execution = result.get("price", 0)
                    execution.fees_paid = result.get("fees", 0)
                    execution.tx_hash = result.get("tx_hash")
                    execution.executed_at = datetime.now()

                    # Update schedule stats
                    schedule.total_spent += amount
                    schedule.execution_count += 1
                    schedule.last_execution = datetime.now()

                else:
                    execution.status = ExecutionStatus.FAILED
                    execution.error_message = result.get("error", "Unknown error")

            else:
                execution.status = ExecutionStatus.FAILED
                execution.error_message = "No swap executor configured"

        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(e)
            logger.error(f"DCA execution failed: {e}")

        # Update next execution
        schedule.next_execution = schedule._calculate_next_execution()
        schedule.updated_at = datetime.now()

        self.executions[execution.execution_id] = execution

    async def get_execution_history(
        self,
        schedule_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[DCAExecution]:
        """Get execution history"""
        executions = list(self.executions.values())

        if schedule_id:
            executions = [e for e in executions if e.schedule_id == schedule_id]

        if user_id:
            executions = [e for e in executions if e.user_id == user_id]

        executions.sort(key=lambda e: e.scheduled_at, reverse=True)
        return executions[:limit]

    async def get_schedule_summary(self, schedule_id: str) -> Dict[str, Any]:
        """Get summary for a schedule"""
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            return {"error": "Schedule not found"}

        executions = await self.get_execution_history(schedule_id=schedule_id)

        completed = [e for e in executions if e.status == ExecutionStatus.COMPLETED]
        total_tokens = sum(e.tokens_received for e in completed)
        total_spent = sum(e.executed_amount for e in completed)
        avg_price = total_spent / total_tokens if total_tokens > 0 else 0

        return {
            "schedule_id": schedule_id,
            "token": schedule.token,
            "frequency": schedule.frequency.value,
            "is_active": schedule.is_active,
            "amount_per_execution": schedule.amount_per_execution,
            "total_executions": len(executions),
            "successful_executions": len(completed),
            "total_spent": total_spent,
            "total_tokens_acquired": total_tokens,
            "average_price": avg_price,
            "next_execution": schedule.next_execution.isoformat() if schedule.next_execution else None,
            "remaining_budget": schedule.total_budget - schedule.total_spent if schedule.total_budget else None
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get DCA statistics"""
        active_schedules = sum(1 for s in self.schedules.values() if s.is_active)
        total_volume = sum(
            e.executed_amount for e in self.executions.values()
            if e.status == ExecutionStatus.COMPLETED
        )

        return {
            "enabled": DCA_AUTOMATION_ENABLED,
            "total_schedules": len(self.schedules),
            "active_schedules": active_schedules,
            "total_executions": len(self.executions),
            "total_volume_usd": total_volume
        }


# Singleton instance
_dca_scheduler: Optional[DCAScheduler] = None


def get_dca_scheduler() -> DCAScheduler:
    """Get DCA scheduler singleton"""
    global _dca_scheduler

    if _dca_scheduler is None:
        _dca_scheduler = DCAScheduler()

    return _dca_scheduler


# Testing
if __name__ == "__main__":
    async def test():
        scheduler = DCAScheduler("test_dca.json")

        # Create a schedule
        schedule = await scheduler.create_schedule(
            user_id="TEST_USER",
            token="SOL",
            amount=100.0,
            frequency=ScheduleFrequency.WEEKLY,
            total_budget=1000.0
        )
        print(f"Created: {schedule.schedule_id}")
        print(f"  Next execution: {schedule.next_execution}")

        # Get summary
        summary = await scheduler.get_schedule_summary(schedule.schedule_id)
        print(f"\nSummary: {summary}")

        # Stats
        print(f"\nStats: {scheduler.get_stats()}")

        # Clean up
        import os
        os.remove("test_dca.json")

    asyncio.run(test())
