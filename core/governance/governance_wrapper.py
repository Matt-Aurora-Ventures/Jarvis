"""
Governance Token Wrapper
Prompt #45: Stake-to-vote governance integration
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import json
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Voting power multipliers based on stake duration
TIME_MULTIPLIERS = {
    0: 100,      # 0-30 days: 1.0x
    30: 120,     # 30-90 days: 1.2x
    90: 150,     # 90-180 days: 1.5x
    180: 200,    # 180-365 days: 2.0x
    365: 250,    # 365+ days: 2.5x (max)
}

# Quorum requirements
DEFAULT_QUORUM_BPS = 400  # 4% of total voting power
MIN_PROPOSAL_THRESHOLD = 100_000 * 10**9  # 100k tokens to create proposal

# Voting periods
DEFAULT_VOTING_PERIOD = timedelta(days=7)
DEFAULT_TIMELOCK = timedelta(days=2)


# =============================================================================
# MODELS
# =============================================================================

class ProposalStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    DEFEATED = "defeated"
    QUEUED = "queued"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class VoteType(str, Enum):
    FOR = "for"
    AGAINST = "against"
    ABSTAIN = "abstain"


class ProposalType(str, Enum):
    PARAMETER = "parameter"      # Change protocol parameters
    UPGRADE = "upgrade"          # Contract upgrade
    TREASURY = "treasury"        # Treasury spending
    GOVERNANCE = "governance"    # Governance rule changes
    GENERAL = "general"          # General signaling


@dataclass
class VotingPower:
    """User's voting power snapshot"""
    wallet: str
    base_power: int  # From staked tokens
    time_multiplier: int  # In basis points (100 = 1x)
    delegation_power: int  # Received from delegators
    delegated_away: int  # Delegated to others
    effective_power: int  # Final voting power
    snapshot_time: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Delegation:
    """Voting power delegation"""
    id: str
    from_wallet: str
    to_wallet: str
    amount: int  # Voting power delegated
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    is_active: bool = True


@dataclass
class Vote:
    """A vote on a proposal"""
    id: str
    proposal_id: str
    voter: str
    vote_type: VoteType
    voting_power: int
    reason: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    signature: str = ""


@dataclass
class Proposal:
    """A governance proposal"""
    id: str
    proposer: str
    title: str
    description: str
    proposal_type: ProposalType
    actions: List[Dict[str, Any]] = field(default_factory=list)  # On-chain actions
    status: ProposalStatus = ProposalStatus.DRAFT
    voting_starts: Optional[datetime] = None
    voting_ends: Optional[datetime] = None
    execution_time: Optional[datetime] = None
    for_votes: int = 0
    against_votes: int = 0
    abstain_votes: int = 0
    quorum_required: int = 0
    snapshot_block: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    votes: List[Vote] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_votes(self) -> int:
        return self.for_votes + self.against_votes + self.abstain_votes

    @property
    def quorum_reached(self) -> bool:
        return self.total_votes >= self.quorum_required

    @property
    def is_passing(self) -> bool:
        return self.for_votes > self.against_votes

    @property
    def for_percentage(self) -> Decimal:
        if self.total_votes == 0:
            return Decimal("0")
        return Decimal(self.for_votes) / Decimal(self.total_votes) * 100


@dataclass
class GovernanceConfig:
    """Governance configuration"""
    quorum_bps: int = DEFAULT_QUORUM_BPS
    proposal_threshold: int = MIN_PROPOSAL_THRESHOLD
    voting_period: timedelta = field(default_factory=lambda: DEFAULT_VOTING_PERIOD)
    timelock: timedelta = field(default_factory=lambda: DEFAULT_TIMELOCK)
    min_voting_delay: timedelta = field(default_factory=lambda: timedelta(hours=24))
    emergency_quorum_bps: int = 1000  # 10% for emergency proposals


# =============================================================================
# GOVERNANCE WRAPPER
# =============================================================================

class GovernanceWrapper:
    """Manages governance with stake-weighted voting"""

    def __init__(
        self,
        staking_program_id: str,
        governance_realm: str,
        token_mint: str,
        db_url: str,
        config: Optional[GovernanceConfig] = None
    ):
        self.staking_program_id = staking_program_id
        self.governance_realm = governance_realm
        self.token_mint = token_mint
        self.db_url = db_url
        self.config = config or GovernanceConfig()

        self.proposals: Dict[str, Proposal] = {}
        self.delegations: Dict[str, List[Delegation]] = {}  # wallet -> delegations
        self.voting_power_cache: Dict[str, VotingPower] = {}
        self.total_voting_power: int = 0

    # =========================================================================
    # VOTING POWER
    # =========================================================================

    async def get_voting_power(
        self,
        wallet: str,
        snapshot_time: Optional[datetime] = None
    ) -> VotingPower:
        """Calculate voting power for a wallet"""
        # Get staking info
        stake_info = await self._get_stake_info(wallet)

        if not stake_info:
            return VotingPower(
                wallet=wallet,
                base_power=0,
                time_multiplier=100,
                delegation_power=0,
                delegated_away=0,
                effective_power=0
            )

        # Calculate time multiplier
        stake_duration = (datetime.utcnow() - stake_info["staked_at"]).days
        time_multiplier = self._get_time_multiplier(stake_duration)

        # Calculate base power with multiplier
        base_power = stake_info["amount"]
        adjusted_power = base_power * time_multiplier // 100

        # Get delegation info
        received = await self._get_delegated_to(wallet)
        delegated = await self._get_delegated_from(wallet)

        # Final power = adjusted base + received - delegated
        effective = adjusted_power + received - delegated

        power = VotingPower(
            wallet=wallet,
            base_power=base_power,
            time_multiplier=time_multiplier,
            delegation_power=received,
            delegated_away=delegated,
            effective_power=max(0, effective),
            snapshot_time=snapshot_time or datetime.utcnow()
        )

        self.voting_power_cache[wallet] = power
        return power

    def _get_time_multiplier(self, days_staked: int) -> int:
        """Get time multiplier for stake duration"""
        multiplier = 100
        for days, mult in sorted(TIME_MULTIPLIERS.items()):
            if days_staked >= days:
                multiplier = mult
        return multiplier

    async def get_total_voting_power(self) -> int:
        """Get total voting power across all stakers"""
        # In production, query from staking program
        return self.total_voting_power

    # =========================================================================
    # DELEGATION
    # =========================================================================

    async def delegate(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: Optional[int] = None
    ) -> Delegation:
        """Delegate voting power to another wallet"""
        import uuid

        if from_wallet == to_wallet:
            raise ValueError("Cannot delegate to self")

        # Get current voting power
        power = await self.get_voting_power(from_wallet)
        available = power.effective_power

        if amount and amount > available:
            raise ValueError("Insufficient voting power to delegate")

        delegate_amount = amount or available

        # Check for existing delegation
        existing = await self._get_delegation(from_wallet, to_wallet)
        if existing:
            # Update existing
            existing.amount = delegate_amount
            return existing

        # Create new delegation
        delegation = Delegation(
            id=str(uuid.uuid4()),
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            amount=delegate_amount
        )

        if from_wallet not in self.delegations:
            self.delegations[from_wallet] = []
        self.delegations[from_wallet].append(delegation)

        await self._save_delegation(delegation)

        logger.info(f"Delegated {delegate_amount} voting power from {from_wallet} to {to_wallet}")
        return delegation

    async def undelegate(
        self,
        from_wallet: str,
        to_wallet: str
    ) -> bool:
        """Remove a delegation"""
        if from_wallet not in self.delegations:
            return False

        delegation = await self._get_delegation(from_wallet, to_wallet)
        if not delegation:
            return False

        delegation.is_active = False
        await self._save_delegation(delegation)

        logger.info(f"Removed delegation from {from_wallet} to {to_wallet}")
        return True

    async def get_delegations(self, wallet: str) -> Dict[str, List[Delegation]]:
        """Get all delegations for a wallet"""
        outgoing = self.delegations.get(wallet, [])
        incoming = []

        for delegator, delegations in self.delegations.items():
            for d in delegations:
                if d.to_wallet == wallet and d.is_active:
                    incoming.append(d)

        return {
            "outgoing": [d for d in outgoing if d.is_active],
            "incoming": incoming
        }

    async def _get_delegation(
        self,
        from_wallet: str,
        to_wallet: str
    ) -> Optional[Delegation]:
        """Get specific delegation if exists"""
        if from_wallet not in self.delegations:
            return None

        for d in self.delegations[from_wallet]:
            if d.to_wallet == to_wallet and d.is_active:
                return d
        return None

    async def _get_delegated_to(self, wallet: str) -> int:
        """Get total voting power delegated TO this wallet"""
        total = 0
        for delegator, delegations in self.delegations.items():
            for d in delegations:
                if d.to_wallet == wallet and d.is_active:
                    total += d.amount
        return total

    async def _get_delegated_from(self, wallet: str) -> int:
        """Get total voting power delegated FROM this wallet"""
        if wallet not in self.delegations:
            return 0
        return sum(d.amount for d in self.delegations[wallet] if d.is_active)

    # =========================================================================
    # PROPOSALS
    # =========================================================================

    async def create_proposal(
        self,
        proposer: str,
        title: str,
        description: str,
        proposal_type: ProposalType,
        actions: List[Dict[str, Any]] = None
    ) -> Proposal:
        """Create a new proposal"""
        import uuid

        # Check proposer has enough voting power
        power = await self.get_voting_power(proposer)
        if power.effective_power < self.config.proposal_threshold:
            raise ValueError(
                f"Insufficient voting power. Required: {self.config.proposal_threshold}, "
                f"Have: {power.effective_power}"
            )

        # Calculate quorum
        total_power = await self.get_total_voting_power()
        quorum = total_power * self.config.quorum_bps // 10000

        proposal = Proposal(
            id=str(uuid.uuid4()),
            proposer=proposer,
            title=title,
            description=description,
            proposal_type=proposal_type,
            actions=actions or [],
            quorum_required=quorum
        )

        self.proposals[proposal.id] = proposal
        await self._save_proposal(proposal)

        logger.info(f"Created proposal {proposal.id}: {title}")
        return proposal

    async def submit_proposal(
        self,
        proposal_id: str,
        proposer: str
    ) -> Proposal:
        """Submit a draft proposal for voting"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.proposer != proposer:
            raise ValueError("Only proposer can submit")

        if proposal.status != ProposalStatus.DRAFT:
            raise ValueError("Proposal already submitted")

        # Set voting period
        now = datetime.utcnow()
        proposal.voting_starts = now + self.config.min_voting_delay
        proposal.voting_ends = proposal.voting_starts + self.config.voting_period
        proposal.status = ProposalStatus.ACTIVE

        # Take snapshot
        proposal.snapshot_block = await self._get_current_slot()

        await self._save_proposal(proposal)

        logger.info(f"Proposal {proposal_id} submitted for voting")
        return proposal

    async def cancel_proposal(
        self,
        proposal_id: str,
        canceller: str
    ) -> Proposal:
        """Cancel a proposal"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.proposer != canceller:
            raise ValueError("Only proposer can cancel")

        if proposal.status not in [ProposalStatus.DRAFT, ProposalStatus.ACTIVE]:
            raise ValueError("Cannot cancel proposal in current state")

        proposal.status = ProposalStatus.CANCELLED
        await self._save_proposal(proposal)

        logger.info(f"Proposal {proposal_id} cancelled")
        return proposal

    # =========================================================================
    # VOTING
    # =========================================================================

    async def cast_vote(
        self,
        proposal_id: str,
        voter: str,
        vote_type: VoteType,
        reason: Optional[str] = None
    ) -> Vote:
        """Cast a vote on a proposal"""
        import uuid

        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.status != ProposalStatus.ACTIVE:
            raise ValueError("Proposal not active")

        now = datetime.utcnow()
        if now < proposal.voting_starts:
            raise ValueError("Voting has not started")
        if now > proposal.voting_ends:
            raise ValueError("Voting has ended")

        # Check if already voted
        existing = next((v for v in proposal.votes if v.voter == voter), None)
        if existing:
            raise ValueError("Already voted on this proposal")

        # Get voting power at snapshot
        power = await self.get_voting_power(voter, proposal.voting_starts)
        if power.effective_power == 0:
            raise ValueError("No voting power")

        vote = Vote(
            id=str(uuid.uuid4()),
            proposal_id=proposal_id,
            voter=voter,
            vote_type=vote_type,
            voting_power=power.effective_power,
            reason=reason
        )

        # Update vote counts
        if vote_type == VoteType.FOR:
            proposal.for_votes += power.effective_power
        elif vote_type == VoteType.AGAINST:
            proposal.against_votes += power.effective_power
        else:
            proposal.abstain_votes += power.effective_power

        proposal.votes.append(vote)
        await self._save_proposal(proposal)
        await self._save_vote(vote)

        logger.info(
            f"Vote cast on proposal {proposal_id}: {vote_type.value} "
            f"with {power.effective_power} power"
        )

        return vote

    async def finalize_proposal(self, proposal_id: str) -> Proposal:
        """Finalize voting and determine outcome"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.status != ProposalStatus.ACTIVE:
            raise ValueError("Proposal not active")

        now = datetime.utcnow()
        if now < proposal.voting_ends:
            raise ValueError("Voting period not ended")

        # Determine outcome
        if not proposal.quorum_reached:
            proposal.status = ProposalStatus.DEFEATED
            proposal.metadata["defeat_reason"] = "quorum_not_reached"
        elif proposal.is_passing:
            proposal.status = ProposalStatus.SUCCEEDED
            proposal.execution_time = now + self.config.timelock
        else:
            proposal.status = ProposalStatus.DEFEATED
            proposal.metadata["defeat_reason"] = "votes_against"

        await self._save_proposal(proposal)

        logger.info(f"Proposal {proposal_id} finalized: {proposal.status.value}")
        return proposal

    async def queue_proposal(self, proposal_id: str) -> Proposal:
        """Queue a passed proposal for execution"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.status != ProposalStatus.SUCCEEDED:
            raise ValueError("Proposal has not succeeded")

        proposal.status = ProposalStatus.QUEUED
        await self._save_proposal(proposal)

        logger.info(f"Proposal {proposal_id} queued for execution")
        return proposal

    async def execute_proposal(
        self,
        proposal_id: str,
        executor: str
    ) -> Proposal:
        """Execute a queued proposal"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.status != ProposalStatus.QUEUED:
            raise ValueError("Proposal not queued")

        now = datetime.utcnow()
        if now < proposal.execution_time:
            raise ValueError(
                f"Timelock not expired. Executable at: {proposal.execution_time}"
            )

        # Execute actions
        try:
            for action in proposal.actions:
                await self._execute_action(action, executor)

            proposal.status = ProposalStatus.EXECUTED
            proposal.executed_at = now

        except Exception as e:
            proposal.metadata["execution_error"] = str(e)
            logger.error(f"Failed to execute proposal {proposal_id}: {e}")
            raise

        await self._save_proposal(proposal)

        logger.info(f"Proposal {proposal_id} executed")
        return proposal

    async def _execute_action(self, action: Dict[str, Any], executor: str):
        """Execute a single proposal action"""
        action_type = action.get("type")

        if action_type == "parameter_change":
            # Change protocol parameter
            param = action.get("parameter")
            value = action.get("value")
            await self._change_parameter(param, value)

        elif action_type == "treasury_transfer":
            # Transfer from treasury
            recipient = action.get("recipient")
            amount = action.get("amount")
            await self._treasury_transfer(recipient, amount)

        elif action_type == "upgrade":
            # Queue upgrade
            new_program_id = action.get("program_id")
            await self._queue_upgrade(new_program_id)

        else:
            logger.warning(f"Unknown action type: {action_type}")

    # =========================================================================
    # VIEW FUNCTIONS
    # =========================================================================

    async def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """Get proposal by ID"""
        return self.proposals.get(proposal_id)

    async def get_proposals(
        self,
        status: Optional[ProposalStatus] = None,
        proposer: Optional[str] = None,
        limit: int = 20
    ) -> List[Proposal]:
        """Get proposals with filters"""
        proposals = list(self.proposals.values())

        if status:
            proposals = [p for p in proposals if p.status == status]

        if proposer:
            proposals = [p for p in proposals if p.proposer == proposer]

        # Sort by creation date, newest first
        proposals.sort(key=lambda x: x.created_at, reverse=True)

        return proposals[:limit]

    async def get_active_proposals(self) -> List[Proposal]:
        """Get all active proposals"""
        return await self.get_proposals(status=ProposalStatus.ACTIVE)

    async def get_user_votes(
        self,
        voter: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get user's voting history"""
        votes = []
        for proposal in self.proposals.values():
            for vote in proposal.votes:
                if vote.voter == voter:
                    votes.append({
                        "proposal_id": proposal.id,
                        "proposal_title": proposal.title,
                        "vote_type": vote.vote_type.value,
                        "voting_power": vote.voting_power,
                        "created_at": vote.created_at.isoformat()
                    })

        votes.sort(key=lambda x: x["created_at"], reverse=True)
        return votes[:limit]

    async def get_governance_stats(self) -> Dict[str, Any]:
        """Get governance statistics"""
        total_proposals = len(self.proposals)
        by_status = {}
        for status in ProposalStatus:
            by_status[status.value] = len([
                p for p in self.proposals.values() if p.status == status
            ])

        total_votes = sum(len(p.votes) for p in self.proposals.values())
        unique_voters = len(set(
            v.voter for p in self.proposals.values() for v in p.votes
        ))

        return {
            "total_proposals": total_proposals,
            "by_status": by_status,
            "total_votes": total_votes,
            "unique_voters": unique_voters,
            "total_voting_power": await self.get_total_voting_power(),
            "quorum_bps": self.config.quorum_bps,
            "proposal_threshold": self.config.proposal_threshold,
            "voting_period_days": self.config.voting_period.days,
            "timelock_days": self.config.timelock.days
        }

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    async def _get_stake_info(self, wallet: str) -> Optional[Dict[str, Any]]:
        """Get staking info for a wallet"""
        # In production, query from staking program
        return {
            "amount": 1_000_000 * 10**9,
            "staked_at": datetime.utcnow() - timedelta(days=100)
        }

    async def _get_current_slot(self) -> int:
        """Get current Solana slot"""
        return 0

    async def _save_proposal(self, proposal: Proposal):
        """Save proposal to database"""
        pass

    async def _save_vote(self, vote: Vote):
        """Save vote to database"""
        pass

    async def _save_delegation(self, delegation: Delegation):
        """Save delegation to database"""
        pass

    async def _change_parameter(self, param: str, value: Any):
        """Execute parameter change"""
        logger.info(f"Changing parameter {param} to {value}")

    async def _treasury_transfer(self, recipient: str, amount: int):
        """Execute treasury transfer"""
        logger.info(f"Transferring {amount} to {recipient}")

    async def _queue_upgrade(self, program_id: str):
        """Queue program upgrade"""
        logger.info(f"Queuing upgrade to {program_id}")


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_governance_endpoints(wrapper: GovernanceWrapper):
    """Create API endpoints for governance"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    from typing import Optional

    router = APIRouter(prefix="/api/governance", tags=["Governance"])

    class CreateProposalRequest(BaseModel):
        title: str
        description: str
        proposal_type: str
        actions: Optional[List[Dict[str, Any]]] = None

    class CastVoteRequest(BaseModel):
        vote_type: str
        reason: Optional[str] = None

    class DelegateRequest(BaseModel):
        to_wallet: str
        amount: Optional[int] = None

    @router.get("/power/{wallet}")
    async def get_voting_power(wallet: str):
        """Get voting power for a wallet"""
        power = await wrapper.get_voting_power(wallet)
        return {
            "wallet": wallet,
            "base_power": power.base_power,
            "time_multiplier": power.time_multiplier,
            "delegation_received": power.delegation_power,
            "delegated_away": power.delegated_away,
            "effective_power": power.effective_power
        }

    @router.post("/delegate")
    async def delegate(wallet: str, request: DelegateRequest):
        """Delegate voting power"""
        try:
            delegation = await wrapper.delegate(
                from_wallet=wallet,
                to_wallet=request.to_wallet,
                amount=request.amount
            )
            return {
                "delegation_id": delegation.id,
                "from": delegation.from_wallet,
                "to": delegation.to_wallet,
                "amount": delegation.amount
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.delete("/delegate/{to_wallet}")
    async def undelegate(wallet: str, to_wallet: str):
        """Remove delegation"""
        success = await wrapper.undelegate(wallet, to_wallet)
        if not success:
            raise HTTPException(status_code=404, detail="Delegation not found")
        return {"status": "ok"}

    @router.get("/delegations/{wallet}")
    async def get_delegations(wallet: str):
        """Get delegations for a wallet"""
        return await wrapper.get_delegations(wallet)

    @router.post("/proposals")
    async def create_proposal(wallet: str, request: CreateProposalRequest):
        """Create a new proposal"""
        try:
            proposal = await wrapper.create_proposal(
                proposer=wallet,
                title=request.title,
                description=request.description,
                proposal_type=ProposalType(request.proposal_type),
                actions=request.actions
            )
            return {
                "proposal_id": proposal.id,
                "status": proposal.status.value
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/proposals/{proposal_id}/submit")
    async def submit_proposal(proposal_id: str, wallet: str):
        """Submit proposal for voting"""
        try:
            proposal = await wrapper.submit_proposal(proposal_id, wallet)
            return {
                "proposal_id": proposal.id,
                "status": proposal.status.value,
                "voting_starts": proposal.voting_starts.isoformat(),
                "voting_ends": proposal.voting_ends.isoformat()
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/proposals")
    async def get_proposals(
        status: Optional[str] = None,
        limit: int = 20
    ):
        """Get proposals"""
        proposals = await wrapper.get_proposals(
            status=ProposalStatus(status) if status else None,
            limit=limit
        )
        return [
            {
                "id": p.id,
                "title": p.title,
                "proposer": p.proposer,
                "status": p.status.value,
                "proposal_type": p.proposal_type.value,
                "for_votes": p.for_votes,
                "against_votes": p.against_votes,
                "abstain_votes": p.abstain_votes,
                "quorum_required": p.quorum_required,
                "quorum_reached": p.quorum_reached,
                "for_percentage": str(p.for_percentage),
                "voting_ends": p.voting_ends.isoformat() if p.voting_ends else None,
                "created_at": p.created_at.isoformat()
            }
            for p in proposals
        ]

    @router.get("/proposals/{proposal_id}")
    async def get_proposal(proposal_id: str):
        """Get proposal details"""
        proposal = await wrapper.get_proposal(proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        return {
            "id": proposal.id,
            "proposer": proposal.proposer,
            "title": proposal.title,
            "description": proposal.description,
            "proposal_type": proposal.proposal_type.value,
            "actions": proposal.actions,
            "status": proposal.status.value,
            "for_votes": proposal.for_votes,
            "against_votes": proposal.against_votes,
            "abstain_votes": proposal.abstain_votes,
            "total_votes": proposal.total_votes,
            "quorum_required": proposal.quorum_required,
            "quorum_reached": proposal.quorum_reached,
            "is_passing": proposal.is_passing,
            "for_percentage": str(proposal.for_percentage),
            "voting_starts": proposal.voting_starts.isoformat() if proposal.voting_starts else None,
            "voting_ends": proposal.voting_ends.isoformat() if proposal.voting_ends else None,
            "execution_time": proposal.execution_time.isoformat() if proposal.execution_time else None,
            "created_at": proposal.created_at.isoformat(),
            "votes": [
                {
                    "voter": v.voter,
                    "vote_type": v.vote_type.value,
                    "voting_power": v.voting_power,
                    "reason": v.reason
                }
                for v in proposal.votes
            ]
        }

    @router.post("/proposals/{proposal_id}/vote")
    async def cast_vote(proposal_id: str, wallet: str, request: CastVoteRequest):
        """Cast a vote"""
        try:
            vote = await wrapper.cast_vote(
                proposal_id=proposal_id,
                voter=wallet,
                vote_type=VoteType(request.vote_type),
                reason=request.reason
            )
            return {
                "vote_id": vote.id,
                "proposal_id": vote.proposal_id,
                "vote_type": vote.vote_type.value,
                "voting_power": vote.voting_power
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/proposals/{proposal_id}/finalize")
    async def finalize_proposal(proposal_id: str):
        """Finalize voting on a proposal"""
        try:
            proposal = await wrapper.finalize_proposal(proposal_id)
            return {
                "proposal_id": proposal.id,
                "status": proposal.status.value,
                "execution_time": proposal.execution_time.isoformat() if proposal.execution_time else None
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/proposals/{proposal_id}/execute")
    async def execute_proposal(proposal_id: str, wallet: str):
        """Execute a passed proposal"""
        try:
            proposal = await wrapper.execute_proposal(proposal_id, wallet)
            return {
                "proposal_id": proposal.id,
                "status": proposal.status.value,
                "executed_at": proposal.executed_at.isoformat()
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/stats")
    async def get_stats():
        """Get governance statistics"""
        return await wrapper.get_governance_stats()

    @router.get("/votes/{wallet}")
    async def get_user_votes(wallet: str, limit: int = 20):
        """Get user's voting history"""
        return await wrapper.get_user_votes(wallet, limit)

    return router
