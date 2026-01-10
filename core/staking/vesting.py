"""
Vesting Schedule System
Prompt #42: Linear vesting with cliff for team/investor tokens
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
import json

logger = logging.getLogger(__name__)


# =============================================================================
# MODELS
# =============================================================================

class VestingStatus(str, Enum):
    PENDING = "pending"      # Before cliff
    ACTIVE = "active"        # Vesting in progress
    COMPLETED = "completed"  # Fully vested
    REVOKED = "revoked"      # Revoked by admin


@dataclass
class VestingSchedule:
    """A vesting schedule for a beneficiary"""
    id: str
    beneficiary: str  # Wallet address
    total_amount: int  # Total tokens to vest
    claimed_amount: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    cliff_duration: timedelta = field(default_factory=lambda: timedelta(days=180))  # 6 months
    vesting_duration: timedelta = field(default_factory=lambda: timedelta(days=730))  # 24 months
    status: VestingStatus = VestingStatus.PENDING
    revoked_at: Optional[datetime] = None
    revoked_amount: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def cliff_end(self) -> datetime:
        return self.start_time + self.cliff_duration

    @property
    def vesting_end(self) -> datetime:
        return self.start_time + self.vesting_duration

    def vested_amount(self, as_of: Optional[datetime] = None) -> int:
        """Calculate currently vested amount"""
        now = as_of or datetime.utcnow()

        # Not yet started
        if now < self.start_time:
            return 0

        # Revoked
        if self.status == VestingStatus.REVOKED:
            return self.claimed_amount

        # Before cliff
        if now < self.cliff_end:
            return 0

        # After full vesting
        if now >= self.vesting_end:
            return self.total_amount

        # Linear vesting after cliff
        elapsed = (now - self.start_time).total_seconds()
        total_duration = self.vesting_duration.total_seconds()

        vested = int(self.total_amount * elapsed / total_duration)
        return min(vested, self.total_amount)

    def claimable_amount(self, as_of: Optional[datetime] = None) -> int:
        """Calculate amount available to claim"""
        return self.vested_amount(as_of) - self.claimed_amount

    def update_status(self):
        """Update status based on current state"""
        now = datetime.utcnow()

        if self.status == VestingStatus.REVOKED:
            return

        if now < self.cliff_end:
            self.status = VestingStatus.PENDING
        elif self.vested_amount() >= self.total_amount:
            self.status = VestingStatus.COMPLETED
        else:
            self.status = VestingStatus.ACTIVE


# =============================================================================
# VESTING MANAGER
# =============================================================================

class VestingManager:
    """Manages vesting schedules"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.schedules: Dict[str, VestingSchedule] = {}

    async def create_vesting(
        self,
        beneficiary: str,
        total_amount: int,
        cliff_months: int = 6,
        vesting_months: int = 24,
        start_time: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VestingSchedule:
        """Create a new vesting schedule"""
        import uuid

        schedule = VestingSchedule(
            id=str(uuid.uuid4()),
            beneficiary=beneficiary,
            total_amount=total_amount,
            start_time=start_time or datetime.utcnow(),
            cliff_duration=timedelta(days=cliff_months * 30),
            vesting_duration=timedelta(days=vesting_months * 30),
            metadata=metadata or {}
        )

        self.schedules[schedule.id] = schedule
        await self._save_schedule(schedule)

        logger.info(
            f"Created vesting schedule {schedule.id} for {beneficiary}: "
            f"{total_amount} tokens over {vesting_months} months"
        )

        return schedule

    async def claim_vested(
        self,
        schedule_id: str,
        beneficiary: str,
        amount: Optional[int] = None
    ) -> Dict[str, Any]:
        """Claim vested tokens"""
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            raise ValueError("Schedule not found")

        if schedule.beneficiary != beneficiary:
            raise ValueError("Not the beneficiary")

        if schedule.status == VestingStatus.REVOKED:
            raise ValueError("Schedule has been revoked")

        claimable = schedule.claimable_amount()
        if claimable <= 0:
            raise ValueError("No tokens available to claim")

        claim_amount = min(amount or claimable, claimable)
        schedule.claimed_amount += claim_amount
        schedule.update_status()

        await self._save_schedule(schedule)

        # Execute on-chain transfer
        signature = await self._transfer_tokens(beneficiary, claim_amount)

        logger.info(
            f"Claimed {claim_amount} tokens from schedule {schedule_id}"
        )

        return {
            "schedule_id": schedule_id,
            "claimed_amount": claim_amount,
            "remaining_claimable": schedule.claimable_amount(),
            "total_claimed": schedule.claimed_amount,
            "signature": signature
        }

    async def revoke_vesting(
        self,
        schedule_id: str,
        admin: str
    ) -> Dict[str, Any]:
        """Revoke a vesting schedule (for team members who leave)"""
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            raise ValueError("Schedule not found")

        if schedule.status == VestingStatus.REVOKED:
            raise ValueError("Already revoked")

        # Calculate what was vested at revocation
        vested = schedule.vested_amount()
        unvested = schedule.total_amount - vested

        schedule.status = VestingStatus.REVOKED
        schedule.revoked_at = datetime.utcnow()
        schedule.revoked_amount = unvested
        schedule.metadata["revoked_by"] = admin

        await self._save_schedule(schedule)

        logger.info(
            f"Revoked vesting schedule {schedule_id}: "
            f"{unvested} tokens returned"
        )

        return {
            "schedule_id": schedule_id,
            "vested_at_revocation": vested,
            "revoked_amount": unvested,
            "revoked_by": admin,
            "revoked_at": schedule.revoked_at.isoformat()
        }

    async def get_schedule(self, schedule_id: str) -> Optional[VestingSchedule]:
        """Get a vesting schedule"""
        return self.schedules.get(schedule_id)

    async def get_beneficiary_schedules(
        self,
        beneficiary: str
    ) -> List[VestingSchedule]:
        """Get all schedules for a beneficiary"""
        return [
            s for s in self.schedules.values()
            if s.beneficiary == beneficiary
        ]

    async def get_global_stats(self) -> Dict[str, Any]:
        """Get global vesting statistics"""
        total_vesting = sum(s.total_amount for s in self.schedules.values())
        total_claimed = sum(s.claimed_amount for s in self.schedules.values())
        total_revoked = sum(s.revoked_amount for s in self.schedules.values())

        return {
            "total_schedules": len(self.schedules),
            "total_vesting": total_vesting,
            "total_claimed": total_claimed,
            "total_revoked": total_revoked,
            "total_pending": total_vesting - total_claimed - total_revoked,
            "by_status": {
                status.value: len([
                    s for s in self.schedules.values()
                    if s.status == status
                ])
                for status in VestingStatus
            }
        }

    async def _save_schedule(self, schedule: VestingSchedule):
        """Save schedule to database"""
        # In production, save to PostgreSQL
        pass

    async def _transfer_tokens(self, beneficiary: str, amount: int) -> str:
        """Transfer tokens on-chain"""
        # In production, execute Solana transfer
        return "mock_signature"


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_vesting_endpoints(manager: VestingManager):
    """Create API endpoints for vesting"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/vesting", tags=["Vesting"])

    class CreateVestingRequest(BaseModel):
        beneficiary: str
        total_amount: int
        cliff_months: int = 6
        vesting_months: int = 24

    @router.post("/create")
    async def create_vesting(request: CreateVestingRequest, admin: str):
        """Create a new vesting schedule (admin only)"""
        schedule = await manager.create_vesting(
            beneficiary=request.beneficiary,
            total_amount=request.total_amount,
            cliff_months=request.cliff_months,
            vesting_months=request.vesting_months
        )
        return {
            "schedule_id": schedule.id,
            "beneficiary": schedule.beneficiary,
            "total_amount": schedule.total_amount,
            "cliff_end": schedule.cliff_end.isoformat(),
            "vesting_end": schedule.vesting_end.isoformat()
        }

    @router.get("/schedule/{schedule_id}")
    async def get_schedule(schedule_id: str):
        """Get vesting schedule details"""
        schedule = await manager.get_schedule(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        return {
            "id": schedule.id,
            "beneficiary": schedule.beneficiary,
            "total_amount": schedule.total_amount,
            "claimed_amount": schedule.claimed_amount,
            "vested_amount": schedule.vested_amount(),
            "claimable_amount": schedule.claimable_amount(),
            "status": schedule.status.value,
            "start_time": schedule.start_time.isoformat(),
            "cliff_end": schedule.cliff_end.isoformat(),
            "vesting_end": schedule.vesting_end.isoformat(),
            "progress_pct": (
                schedule.vested_amount() / schedule.total_amount * 100
                if schedule.total_amount > 0 else 0
            )
        }

    @router.post("/claim/{schedule_id}")
    async def claim_vested(schedule_id: str, beneficiary: str, amount: Optional[int] = None):
        """Claim vested tokens"""
        try:
            result = await manager.claim_vested(schedule_id, beneficiary, amount)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/revoke/{schedule_id}")
    async def revoke_vesting(schedule_id: str, admin: str):
        """Revoke a vesting schedule (admin only)"""
        try:
            result = await manager.revoke_vesting(schedule_id, admin)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/beneficiary/{beneficiary}")
    async def get_beneficiary_schedules(beneficiary: str):
        """Get all schedules for a beneficiary"""
        schedules = await manager.get_beneficiary_schedules(beneficiary)
        return {
            "beneficiary": beneficiary,
            "schedules": [
                {
                    "id": s.id,
                    "total_amount": s.total_amount,
                    "vested_amount": s.vested_amount(),
                    "claimable_amount": s.claimable_amount(),
                    "status": s.status.value
                }
                for s in schedules
            ]
        }

    @router.get("/stats")
    async def get_global_stats():
        """Get global vesting statistics"""
        return await manager.get_global_stats()

    return router
