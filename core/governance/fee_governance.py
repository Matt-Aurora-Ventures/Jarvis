"""
Fee Governance System
Prompts #74-75: Community voting on fee parameters and transparency
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Voting periods
MIN_VOTING_PERIOD_HOURS = 24
DEFAULT_VOTING_PERIOD_HOURS = 72
MAX_VOTING_PERIOD_HOURS = 168  # 7 days

# Quorum requirements (basis points of total supply)
MIN_QUORUM_BPS = 100    # 1%
DEFAULT_QUORUM_BPS = 500  # 5%
MAX_QUORUM_BPS = 2000   # 20%

# Approval threshold (basis points of votes cast)
APPROVAL_THRESHOLD_BPS = 5000  # 50% + 1

# Timelock for execution
TIMELOCK_HOURS = 24

# Fee change limits per proposal
MAX_FEE_CHANGE_BPS = 100  # Can only change fees by 1% max per proposal


# =============================================================================
# MODELS
# =============================================================================

class FeeProposalType(str, Enum):
    BASE_FEE = "base_fee"
    TIER_DISCOUNT = "tier_discount"
    VOLUME_THRESHOLD = "volume_threshold"
    NEW_FEE_TYPE = "new_fee_type"
    FEE_DISTRIBUTION = "fee_distribution"
    EMERGENCY = "emergency"


class FeeProposalStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    DEFEATED = "defeated"
    QUEUED = "queued"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class VoteChoice(str, Enum):
    FOR = "for"
    AGAINST = "against"
    ABSTAIN = "abstain"


@dataclass
class FeeChange:
    """A proposed fee change"""
    parameter: str
    current_value: Any
    proposed_value: Any
    fee_type: Optional[str] = None
    justification: str = ""


@dataclass
class Vote:
    """A vote on a proposal"""
    voter: str
    choice: VoteChoice
    voting_power: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    delegate: Optional[str] = None


@dataclass
class FeeProposal:
    """A fee governance proposal"""
    id: str
    proposer: str
    title: str
    description: str
    proposal_type: FeeProposalType
    changes: List[FeeChange]

    status: FeeProposalStatus = FeeProposalStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    voting_starts: Optional[datetime] = None
    voting_ends: Optional[datetime] = None
    execution_time: Optional[datetime] = None
    executed_at: Optional[datetime] = None

    votes_for: int = 0
    votes_against: int = 0
    votes_abstain: int = 0
    voter_count: int = 0
    quorum_bps: int = DEFAULT_QUORUM_BPS

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeeParameters:
    """Current fee parameters"""
    base_swap_fee_bps: int = 30
    base_stake_fee_bps: int = 10
    base_unstake_fee_bps: int = 20

    tier_discounts: Dict[str, int] = field(default_factory=lambda: {
        "free": 0,
        "starter": 10,
        "pro": 20,
        "enterprise": 35,
        "whale": 50
    })

    volume_thresholds: Dict[int, int] = field(default_factory=lambda: {
        10_000: -5,
        100_000: -10,
        1_000_000: -15
    })

    fee_distribution: Dict[str, int] = field(default_factory=lambda: {
        "treasury": 5000,      # 50%
        "stakers": 3000,       # 30%
        "buyback": 1500,       # 15%
        "development": 500     # 5%
    })

    last_updated: datetime = field(default_factory=datetime.utcnow)
    version: int = 1


# =============================================================================
# FEE GOVERNANCE MANAGER
# =============================================================================

class FeeGovernanceManager:
    """Manages community governance of fee parameters"""

    def __init__(
        self,
        total_supply: int,
        get_voting_power: Callable[[str], int]
    ):
        self.total_supply = total_supply
        self.get_voting_power = get_voting_power

        self.proposals: Dict[str, FeeProposal] = {}
        self.votes: Dict[str, Dict[str, Vote]] = {}  # proposal_id -> voter -> vote
        self.current_params = FeeParameters()
        self.param_history: List[Tuple[datetime, FeeParameters]] = []

    # =========================================================================
    # PROPOSAL MANAGEMENT
    # =========================================================================

    async def create_proposal(
        self,
        proposer: str,
        title: str,
        description: str,
        proposal_type: FeeProposalType,
        changes: List[FeeChange],
        voting_period_hours: int = DEFAULT_VOTING_PERIOD_HOURS,
        quorum_bps: int = DEFAULT_QUORUM_BPS
    ) -> FeeProposal:
        """Create a new fee governance proposal"""
        import uuid

        # Validate proposer has enough voting power
        voting_power = self.get_voting_power(proposer)
        min_power = self.total_supply * 10 // 10000  # 0.1% to propose
        if voting_power < min_power:
            raise ValueError(f"Insufficient voting power to propose. Need {min_power}")

        # Validate changes
        await self._validate_changes(proposal_type, changes)

        # Validate voting period
        if voting_period_hours < MIN_VOTING_PERIOD_HOURS:
            voting_period_hours = MIN_VOTING_PERIOD_HOURS
        if voting_period_hours > MAX_VOTING_PERIOD_HOURS:
            voting_period_hours = MAX_VOTING_PERIOD_HOURS

        # Validate quorum
        if quorum_bps < MIN_QUORUM_BPS:
            quorum_bps = MIN_QUORUM_BPS
        if quorum_bps > MAX_QUORUM_BPS:
            quorum_bps = MAX_QUORUM_BPS

        proposal_id = str(uuid.uuid4())[:8]
        now = datetime.utcnow()

        proposal = FeeProposal(
            id=proposal_id,
            proposer=proposer,
            title=title,
            description=description,
            proposal_type=proposal_type,
            changes=changes,
            status=FeeProposalStatus.DRAFT,
            voting_starts=now,
            voting_ends=now + timedelta(hours=voting_period_hours),
            quorum_bps=quorum_bps
        )

        self.proposals[proposal_id] = proposal
        self.votes[proposal_id] = {}

        logger.info(f"Created fee proposal {proposal_id}: {title}")
        return proposal

    async def _validate_changes(
        self,
        proposal_type: FeeProposalType,
        changes: List[FeeChange]
    ):
        """Validate proposed changes"""
        for change in changes:
            # Check fee change limits
            if "fee" in change.parameter.lower() and "_bps" in change.parameter.lower():
                current = change.current_value
                proposed = change.proposed_value

                if isinstance(current, int) and isinstance(proposed, int):
                    diff = abs(proposed - current)
                    if diff > MAX_FEE_CHANGE_BPS:
                        raise ValueError(
                            f"Fee change of {diff}bps exceeds maximum {MAX_FEE_CHANGE_BPS}bps per proposal"
                        )

    async def activate_proposal(self, proposal_id: str) -> FeeProposal:
        """Activate a proposal for voting"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.status != FeeProposalStatus.DRAFT:
            raise ValueError("Proposal is not in draft status")

        proposal.status = FeeProposalStatus.ACTIVE
        proposal.voting_starts = datetime.utcnow()

        logger.info(f"Activated proposal {proposal_id}")
        return proposal

    async def cancel_proposal(self, proposal_id: str, canceller: str) -> FeeProposal:
        """Cancel a proposal"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        # Only proposer or admin can cancel
        if canceller != proposal.proposer:
            raise ValueError("Only proposer can cancel")

        if proposal.status not in [FeeProposalStatus.DRAFT, FeeProposalStatus.ACTIVE]:
            raise ValueError("Cannot cancel proposal in current status")

        proposal.status = FeeProposalStatus.CANCELLED
        logger.info(f"Cancelled proposal {proposal_id}")
        return proposal

    # =========================================================================
    # VOTING
    # =========================================================================

    async def cast_vote(
        self,
        proposal_id: str,
        voter: str,
        choice: VoteChoice,
        delegate: Optional[str] = None
    ) -> Vote:
        """Cast a vote on a proposal"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.status != FeeProposalStatus.ACTIVE:
            raise ValueError("Proposal is not active for voting")

        now = datetime.utcnow()
        if now > proposal.voting_ends:
            raise ValueError("Voting period has ended")

        # Get voting power
        voting_power = self.get_voting_power(voter)
        if voting_power <= 0:
            raise ValueError("No voting power")

        # Check if already voted
        if voter in self.votes.get(proposal_id, {}):
            raise ValueError("Already voted on this proposal")

        vote = Vote(
            voter=voter,
            choice=choice,
            voting_power=voting_power,
            delegate=delegate
        )

        # Record vote
        if proposal_id not in self.votes:
            self.votes[proposal_id] = {}
        self.votes[proposal_id][voter] = vote

        # Update tallies
        if choice == VoteChoice.FOR:
            proposal.votes_for += voting_power
        elif choice == VoteChoice.AGAINST:
            proposal.votes_against += voting_power
        else:
            proposal.votes_abstain += voting_power

        proposal.voter_count += 1

        logger.info(f"Vote cast on {proposal_id}: {choice.value} with {voting_power} power")
        return vote

    async def get_vote(self, proposal_id: str, voter: str) -> Optional[Vote]:
        """Get a voter's vote on a proposal"""
        return self.votes.get(proposal_id, {}).get(voter)

    # =========================================================================
    # PROPOSAL LIFECYCLE
    # =========================================================================

    async def finalize_proposal(self, proposal_id: str) -> FeeProposal:
        """Finalize a proposal after voting ends"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.status != FeeProposalStatus.ACTIVE:
            raise ValueError("Proposal is not active")

        now = datetime.utcnow()
        if now < proposal.voting_ends:
            raise ValueError("Voting period has not ended")

        # Check quorum
        total_votes = proposal.votes_for + proposal.votes_against + proposal.votes_abstain
        quorum_required = self.total_supply * proposal.quorum_bps // 10000

        if total_votes < quorum_required:
            proposal.status = FeeProposalStatus.DEFEATED
            proposal.metadata["defeat_reason"] = "quorum_not_met"
            logger.info(f"Proposal {proposal_id} defeated: quorum not met")
            return proposal

        # Check approval
        votes_cast = proposal.votes_for + proposal.votes_against
        if votes_cast == 0:
            proposal.status = FeeProposalStatus.DEFEATED
            proposal.metadata["defeat_reason"] = "no_votes"
            return proposal

        approval_bps = proposal.votes_for * 10000 // votes_cast

        if approval_bps >= APPROVAL_THRESHOLD_BPS:
            proposal.status = FeeProposalStatus.SUCCEEDED
            proposal.execution_time = now + timedelta(hours=TIMELOCK_HOURS)
            logger.info(f"Proposal {proposal_id} succeeded with {approval_bps/100}% approval")
        else:
            proposal.status = FeeProposalStatus.DEFEATED
            proposal.metadata["defeat_reason"] = "approval_threshold_not_met"
            proposal.metadata["approval_bps"] = approval_bps
            logger.info(f"Proposal {proposal_id} defeated: only {approval_bps/100}% approval")

        return proposal

    async def queue_proposal(self, proposal_id: str) -> FeeProposal:
        """Queue a successful proposal for execution"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.status != FeeProposalStatus.SUCCEEDED:
            raise ValueError("Proposal has not succeeded")

        proposal.status = FeeProposalStatus.QUEUED
        logger.info(f"Proposal {proposal_id} queued for execution")
        return proposal

    async def execute_proposal(self, proposal_id: str, executor: str) -> FeeProposal:
        """Execute a queued proposal"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.status != FeeProposalStatus.QUEUED:
            raise ValueError("Proposal is not queued")

        now = datetime.utcnow()
        if proposal.execution_time and now < proposal.execution_time:
            raise ValueError(f"Timelock not expired. Wait until {proposal.execution_time}")

        # Save current params to history
        self.param_history.append((now, FeeParameters(**vars(self.current_params))))

        # Apply changes
        for change in proposal.changes:
            await self._apply_change(change)

        self.current_params.last_updated = now
        self.current_params.version += 1

        proposal.status = FeeProposalStatus.EXECUTED
        proposal.executed_at = now

        logger.info(f"Proposal {proposal_id} executed by {executor[:8]}...")
        return proposal

    async def _apply_change(self, change: FeeChange):
        """Apply a single fee change"""
        param = change.parameter

        if param == "base_swap_fee_bps":
            self.current_params.base_swap_fee_bps = change.proposed_value
        elif param == "base_stake_fee_bps":
            self.current_params.base_stake_fee_bps = change.proposed_value
        elif param == "base_unstake_fee_bps":
            self.current_params.base_unstake_fee_bps = change.proposed_value
        elif param.startswith("tier_discount_"):
            tier = param.replace("tier_discount_", "")
            self.current_params.tier_discounts[tier] = change.proposed_value
        elif param.startswith("volume_threshold_"):
            threshold = int(param.replace("volume_threshold_", ""))
            self.current_params.volume_thresholds[threshold] = change.proposed_value
        elif param.startswith("fee_distribution_"):
            recipient = param.replace("fee_distribution_", "")
            self.current_params.fee_distribution[recipient] = change.proposed_value

        logger.info(f"Applied change: {param} = {change.proposed_value}")

    # =========================================================================
    # QUERIES
    # =========================================================================

    async def get_proposal(self, proposal_id: str) -> Optional[FeeProposal]:
        """Get a proposal by ID"""
        return self.proposals.get(proposal_id)

    async def get_proposals(
        self,
        status: Optional[FeeProposalStatus] = None,
        limit: int = 20
    ) -> List[FeeProposal]:
        """Get proposals filtered by status"""
        proposals = list(self.proposals.values())

        if status:
            proposals = [p for p in proposals if p.status == status]

        proposals.sort(key=lambda p: p.created_at, reverse=True)
        return proposals[:limit]

    async def get_active_proposals(self) -> List[FeeProposal]:
        """Get currently active proposals"""
        return await self.get_proposals(status=FeeProposalStatus.ACTIVE)

    async def get_current_params(self) -> FeeParameters:
        """Get current fee parameters"""
        return self.current_params

    async def get_param_history(
        self,
        limit: int = 10
    ) -> List[Tuple[datetime, FeeParameters]]:
        """Get parameter change history"""
        return self.param_history[-limit:]

    async def get_vote_summary(self, proposal_id: str) -> Dict[str, Any]:
        """Get vote summary for a proposal"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return {}

        total_votes = proposal.votes_for + proposal.votes_against + proposal.votes_abstain
        votes_cast = proposal.votes_for + proposal.votes_against

        return {
            "proposal_id": proposal_id,
            "votes_for": proposal.votes_for,
            "votes_against": proposal.votes_against,
            "votes_abstain": proposal.votes_abstain,
            "total_voting_power": total_votes,
            "voter_count": proposal.voter_count,
            "approval_percent": (
                proposal.votes_for * 100 / votes_cast if votes_cast > 0 else 0
            ),
            "quorum_percent": (
                total_votes * 100 / (self.total_supply * proposal.quorum_bps // 10000)
                if self.total_supply > 0 else 0
            ),
            "quorum_met": (
                total_votes >= self.total_supply * proposal.quorum_bps // 10000
            )
        }


# =============================================================================
# FEE TRANSPARENCY TRACKER
# =============================================================================

class FeeTransparencyTracker:
    """Tracks and reports on fee collection and distribution"""

    def __init__(self):
        self.fee_collections: List[Dict[str, Any]] = []
        self.distributions: List[Dict[str, Any]] = []
        self.daily_totals: Dict[str, Dict[str, int]] = {}

    async def record_fee_collection(
        self,
        fee_type: str,
        amount: int,
        user: str,
        user_tier: str,
        transaction_hash: str
    ):
        """Record a fee collection event"""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "fee_type": fee_type,
            "amount": amount,
            "user_tier": user_tier,
            "transaction_hash": transaction_hash
        }

        self.fee_collections.append(record)

        # Update daily totals
        date_key = datetime.utcnow().strftime("%Y-%m-%d")
        if date_key not in self.daily_totals:
            self.daily_totals[date_key] = {
                "total": 0,
                "by_type": {},
                "by_tier": {}
            }

        self.daily_totals[date_key]["total"] += amount
        self.daily_totals[date_key]["by_type"][fee_type] = (
            self.daily_totals[date_key]["by_type"].get(fee_type, 0) + amount
        )
        self.daily_totals[date_key]["by_tier"][user_tier] = (
            self.daily_totals[date_key]["by_tier"].get(user_tier, 0) + amount
        )

    async def record_distribution(
        self,
        recipient: str,
        amount: int,
        distribution_type: str,
        transaction_hash: str
    ):
        """Record a fee distribution event"""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "recipient": recipient,
            "amount": amount,
            "distribution_type": distribution_type,
            "transaction_hash": transaction_hash
        }

        self.distributions.append(record)

    async def get_transparency_report(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """Generate transparency report"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        # Aggregate collections
        total_collected = sum(
            data["total"]
            for date, data in self.daily_totals.items()
            if date >= cutoff_str
        )

        # Aggregate by type
        by_type = {}
        for date, data in self.daily_totals.items():
            if date >= cutoff_str:
                for fee_type, amount in data.get("by_type", {}).items():
                    by_type[fee_type] = by_type.get(fee_type, 0) + amount

        # Aggregate by tier
        by_tier = {}
        for date, data in self.daily_totals.items():
            if date >= cutoff_str:
                for tier, amount in data.get("by_tier", {}).items():
                    by_tier[tier] = by_tier.get(tier, 0) + amount

        # Recent distributions
        recent_distributions = [
            d for d in self.distributions
            if datetime.fromisoformat(d["timestamp"]) > cutoff
        ]

        return {
            "period_days": days,
            "generated_at": datetime.utcnow().isoformat(),
            "total_fees_collected": total_collected,
            "fees_by_type": by_type,
            "fees_by_tier": by_tier,
            "distribution_count": len(recent_distributions),
            "total_distributed": sum(d["amount"] for d in recent_distributions),
            "daily_average": total_collected // days if days > 0 else 0
        }


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_fee_governance_endpoints(
    governance: FeeGovernanceManager,
    transparency: FeeTransparencyTracker
):
    """Create fee governance API endpoints"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    from typing import List as TypeList

    router = APIRouter(prefix="/api/governance/fees", tags=["Fee Governance"])

    class FeeChangeRequest(BaseModel):
        parameter: str
        current_value: Any
        proposed_value: Any
        justification: str = ""

    class CreateProposalRequest(BaseModel):
        title: str
        description: str
        proposal_type: str
        changes: TypeList[FeeChangeRequest]
        voting_period_hours: int = 72

    class VoteRequest(BaseModel):
        choice: str
        delegate: Optional[str] = None

    @router.post("/proposals")
    async def create_proposal(wallet: str, request: CreateProposalRequest):
        """Create a new fee governance proposal"""
        try:
            changes = [
                FeeChange(
                    parameter=c.parameter,
                    current_value=c.current_value,
                    proposed_value=c.proposed_value,
                    justification=c.justification
                )
                for c in request.changes
            ]

            proposal = await governance.create_proposal(
                proposer=wallet,
                title=request.title,
                description=request.description,
                proposal_type=FeeProposalType(request.proposal_type),
                changes=changes,
                voting_period_hours=request.voting_period_hours
            )

            return {"proposal_id": proposal.id, "status": proposal.status.value}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/proposals")
    async def list_proposals(status: Optional[str] = None, limit: int = 20):
        """List fee governance proposals"""
        status_enum = FeeProposalStatus(status) if status else None
        proposals = await governance.get_proposals(status=status_enum, limit=limit)
        return [
            {
                "id": p.id,
                "title": p.title,
                "status": p.status.value,
                "votes_for": p.votes_for,
                "votes_against": p.votes_against,
                "voter_count": p.voter_count,
                "voting_ends": p.voting_ends.isoformat() if p.voting_ends else None
            }
            for p in proposals
        ]

    @router.get("/proposals/{proposal_id}")
    async def get_proposal(proposal_id: str):
        """Get proposal details"""
        proposal = await governance.get_proposal(proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        summary = await governance.get_vote_summary(proposal_id)

        return {
            "id": proposal.id,
            "title": proposal.title,
            "description": proposal.description,
            "proposal_type": proposal.proposal_type.value,
            "status": proposal.status.value,
            "proposer": proposal.proposer,
            "changes": [
                {
                    "parameter": c.parameter,
                    "current_value": c.current_value,
                    "proposed_value": c.proposed_value,
                    "justification": c.justification
                }
                for c in proposal.changes
            ],
            "voting_starts": proposal.voting_starts.isoformat() if proposal.voting_starts else None,
            "voting_ends": proposal.voting_ends.isoformat() if proposal.voting_ends else None,
            "vote_summary": summary
        }

    @router.post("/proposals/{proposal_id}/vote")
    async def vote_on_proposal(proposal_id: str, wallet: str, request: VoteRequest):
        """Vote on a proposal"""
        try:
            vote = await governance.cast_vote(
                proposal_id=proposal_id,
                voter=wallet,
                choice=VoteChoice(request.choice),
                delegate=request.delegate
            )
            return {
                "status": "voted",
                "choice": vote.choice.value,
                "voting_power": vote.voting_power
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/proposals/{proposal_id}/finalize")
    async def finalize_proposal(proposal_id: str):
        """Finalize a proposal after voting ends"""
        try:
            proposal = await governance.finalize_proposal(proposal_id)
            return {"status": proposal.status.value}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/proposals/{proposal_id}/execute")
    async def execute_proposal(proposal_id: str, wallet: str):
        """Execute a queued proposal"""
        try:
            proposal = await governance.execute_proposal(proposal_id, wallet)
            return {"status": proposal.status.value, "executed_at": proposal.executed_at.isoformat()}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/params")
    async def get_current_params():
        """Get current fee parameters"""
        params = await governance.get_current_params()
        return {
            "base_swap_fee_bps": params.base_swap_fee_bps,
            "base_stake_fee_bps": params.base_stake_fee_bps,
            "base_unstake_fee_bps": params.base_unstake_fee_bps,
            "tier_discounts": params.tier_discounts,
            "volume_thresholds": params.volume_thresholds,
            "fee_distribution": params.fee_distribution,
            "version": params.version,
            "last_updated": params.last_updated.isoformat()
        }

    @router.get("/transparency")
    async def get_transparency_report(days: int = 30):
        """Get fee transparency report"""
        return await transparency.get_transparency_report(days)

    return router
