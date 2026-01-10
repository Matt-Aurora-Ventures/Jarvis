"""
Governance Proposals

Proposal creation and management for JARVIS governance.
$KR8TIV holders can create and vote on proposals.

Prompts #71-80: Governance System
"""

import asyncio
import logging
import os
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ProposalStatus(str, Enum):
    """Status of a governance proposal"""
    DRAFT = "draft"
    PENDING = "pending"       # Waiting for voting period
    ACTIVE = "active"         # Voting in progress
    PASSED = "passed"         # Quorum met, majority for
    REJECTED = "rejected"     # Quorum met, majority against
    EXPIRED = "expired"       # Voting period ended without quorum
    EXECUTED = "executed"     # Passed and executed
    CANCELLED = "cancelled"   # Cancelled by proposer


class ProposalType(str, Enum):
    """Types of governance proposals"""
    PARAMETER_CHANGE = "parameter_change"      # Change protocol parameters
    TREASURY_SPEND = "treasury_spend"          # Spend from treasury
    STRATEGY_ADD = "strategy_add"              # Add new trading strategy
    STRATEGY_REMOVE = "strategy_remove"        # Remove trading strategy
    FEE_CHANGE = "fee_change"                  # Change fee structure
    UPGRADE = "upgrade"                        # Protocol upgrade
    GENERAL = "general"                        # General proposal


@dataclass
class ProposalConfig:
    """Configuration for proposal creation"""
    min_proposer_balance: float = 1000.0      # Min $KR8TIV to create proposal
    proposal_deposit: float = 100.0            # Deposit required (returned if passed)
    voting_period_days: int = 7                # Default voting period
    execution_delay_days: int = 2              # Delay after passing
    quorum_percentage: float = 10.0            # Min % of total supply to vote
    pass_threshold: float = 51.0               # % of votes needed to pass
    min_voting_period_days: int = 3            # Minimum voting period
    max_voting_period_days: int = 30           # Maximum voting period


@dataclass
class Proposal:
    """A governance proposal"""
    proposal_id: str
    title: str
    description: str
    proposal_type: ProposalType
    proposer: str  # Wallet address
    status: ProposalStatus = ProposalStatus.DRAFT

    # Voting
    votes_for: float = 0.0
    votes_against: float = 0.0
    votes_abstain: float = 0.0
    total_votes: float = 0.0
    unique_voters: int = 0

    # Timeline
    created_at: datetime = field(default_factory=datetime.now)
    voting_starts: Optional[datetime] = None
    voting_ends: Optional[datetime] = None
    executed_at: Optional[datetime] = None

    # Metadata
    discussion_url: Optional[str] = None
    execution_data: Optional[Dict[str, Any]] = None
    deposit_amount: float = 0.0
    deposit_returned: bool = False

    def __post_init__(self):
        if not self.proposal_id:
            data = f"{self.title}{self.proposer}{self.created_at.isoformat()}"
            self.proposal_id = f"PROP-{hashlib.sha256(data.encode()).hexdigest()[:8].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "description": self.description,
            "proposal_type": self.proposal_type.value,
            "proposer": self.proposer,
            "status": self.status.value,
            "votes_for": self.votes_for,
            "votes_against": self.votes_against,
            "votes_abstain": self.votes_abstain,
            "total_votes": self.total_votes,
            "unique_voters": self.unique_voters,
            "created_at": self.created_at.isoformat(),
            "voting_starts": self.voting_starts.isoformat() if self.voting_starts else None,
            "voting_ends": self.voting_ends.isoformat() if self.voting_ends else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "discussion_url": self.discussion_url,
            "execution_data": self.execution_data,
            "deposit_amount": self.deposit_amount,
            "deposit_returned": self.deposit_returned
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Proposal":
        """Create from dictionary"""
        return cls(
            proposal_id=data["proposal_id"],
            title=data["title"],
            description=data["description"],
            proposal_type=ProposalType(data["proposal_type"]),
            proposer=data["proposer"],
            status=ProposalStatus(data["status"]),
            votes_for=data.get("votes_for", 0.0),
            votes_against=data.get("votes_against", 0.0),
            votes_abstain=data.get("votes_abstain", 0.0),
            total_votes=data.get("total_votes", 0.0),
            unique_voters=data.get("unique_voters", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
            voting_starts=datetime.fromisoformat(data["voting_starts"]) if data.get("voting_starts") else None,
            voting_ends=datetime.fromisoformat(data["voting_ends"]) if data.get("voting_ends") else None,
            executed_at=datetime.fromisoformat(data["executed_at"]) if data.get("executed_at") else None,
            discussion_url=data.get("discussion_url"),
            execution_data=data.get("execution_data"),
            deposit_amount=data.get("deposit_amount", 0.0),
            deposit_returned=data.get("deposit_returned", False)
        )

    def get_vote_percentage(self) -> Dict[str, float]:
        """Get vote percentages"""
        if self.total_votes == 0:
            return {"for": 0.0, "against": 0.0, "abstain": 0.0}

        return {
            "for": (self.votes_for / self.total_votes) * 100,
            "against": (self.votes_against / self.total_votes) * 100,
            "abstain": (self.votes_abstain / self.total_votes) * 100
        }

    def is_voting_active(self) -> bool:
        """Check if voting is currently active"""
        if self.status != ProposalStatus.ACTIVE:
            return False

        now = datetime.now()
        if self.voting_starts and now < self.voting_starts:
            return False
        if self.voting_ends and now > self.voting_ends:
            return False

        return True


class ProposalManager:
    """
    Manages governance proposals

    Handles creation, storage, and lifecycle of proposals.
    """

    def __init__(
        self,
        storage_path: str = "data/governance/proposals.json",
        config: Optional[ProposalConfig] = None
    ):
        self.storage_path = Path(storage_path)
        self.config = config or ProposalConfig()
        self.proposals: Dict[str, Proposal] = {}
        self._load()

    def _load(self):
        """Load proposals from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for prop_data in data.get("proposals", []):
                proposal = Proposal.from_dict(prop_data)
                self.proposals[proposal.proposal_id] = proposal

            logger.info(f"Loaded {len(self.proposals)} proposals")

        except Exception as e:
            logger.error(f"Failed to load proposals: {e}")

    def _save(self):
        """Save proposals to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "proposals": [p.to_dict() for p in self.proposals.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save proposals: {e}")
            raise

    async def create_proposal(
        self,
        title: str,
        description: str,
        proposal_type: ProposalType,
        proposer: str,
        voting_period_days: Optional[int] = None,
        execution_data: Optional[Dict[str, Any]] = None,
        discussion_url: Optional[str] = None
    ) -> Proposal:
        """Create a new proposal"""

        # Validate voting period
        voting_days = voting_period_days or self.config.voting_period_days
        voting_days = max(self.config.min_voting_period_days, min(voting_days, self.config.max_voting_period_days))

        # Create proposal
        proposal = Proposal(
            proposal_id="",  # Will be generated
            title=title,
            description=description,
            proposal_type=proposal_type,
            proposer=proposer,
            status=ProposalStatus.PENDING,
            voting_starts=datetime.now(),
            voting_ends=datetime.now() + timedelta(days=voting_days),
            execution_data=execution_data,
            discussion_url=discussion_url,
            deposit_amount=self.config.proposal_deposit
        )

        self.proposals[proposal.proposal_id] = proposal
        self._save()

        logger.info(f"Created proposal {proposal.proposal_id}: {title}")
        return proposal

    async def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """Get a proposal by ID"""
        return self.proposals.get(proposal_id)

    async def list_proposals(
        self,
        status: Optional[ProposalStatus] = None,
        proposal_type: Optional[ProposalType] = None,
        proposer: Optional[str] = None,
        limit: int = 100
    ) -> List[Proposal]:
        """List proposals with optional filters"""
        proposals = list(self.proposals.values())

        if status:
            proposals = [p for p in proposals if p.status == status]

        if proposal_type:
            proposals = [p for p in proposals if p.proposal_type == proposal_type]

        if proposer:
            proposals = [p for p in proposals if p.proposer == proposer]

        # Sort by created_at descending
        proposals.sort(key=lambda p: p.created_at, reverse=True)

        return proposals[:limit]

    async def activate_proposal(self, proposal_id: str) -> bool:
        """Activate a pending proposal for voting"""
        proposal = self.proposals.get(proposal_id)

        if not proposal:
            return False

        if proposal.status != ProposalStatus.PENDING:
            return False

        proposal.status = ProposalStatus.ACTIVE
        proposal.voting_starts = datetime.now()

        self._save()
        logger.info(f"Activated proposal {proposal_id}")
        return True

    async def record_vote(
        self,
        proposal_id: str,
        vote_power: float,
        choice: str  # "for", "against", "abstain"
    ) -> bool:
        """Record a vote on a proposal"""
        proposal = self.proposals.get(proposal_id)

        if not proposal:
            return False

        if not proposal.is_voting_active():
            return False

        if choice == "for":
            proposal.votes_for += vote_power
        elif choice == "against":
            proposal.votes_against += vote_power
        elif choice == "abstain":
            proposal.votes_abstain += vote_power
        else:
            return False

        proposal.total_votes += vote_power
        proposal.unique_voters += 1

        self._save()
        return True

    async def finalize_proposal(
        self,
        proposal_id: str,
        total_supply: float
    ) -> ProposalStatus:
        """Finalize voting and determine outcome"""
        proposal = self.proposals.get(proposal_id)

        if not proposal:
            return ProposalStatus.CANCELLED

        if proposal.status != ProposalStatus.ACTIVE:
            return proposal.status

        # Check if voting period ended
        if proposal.voting_ends and datetime.now() < proposal.voting_ends:
            return proposal.status

        # Check quorum
        quorum_votes = (self.config.quorum_percentage / 100) * total_supply
        if proposal.total_votes < quorum_votes:
            proposal.status = ProposalStatus.EXPIRED
            self._save()
            logger.info(f"Proposal {proposal_id} expired (no quorum)")
            return proposal.status

        # Check if passed
        if proposal.total_votes > 0:
            for_percentage = (proposal.votes_for / proposal.total_votes) * 100

            if for_percentage >= self.config.pass_threshold:
                proposal.status = ProposalStatus.PASSED
                logger.info(f"Proposal {proposal_id} passed with {for_percentage:.1f}% for")
            else:
                proposal.status = ProposalStatus.REJECTED
                logger.info(f"Proposal {proposal_id} rejected with {for_percentage:.1f}% for")

        self._save()
        return proposal.status

    async def cancel_proposal(self, proposal_id: str, canceller: str) -> bool:
        """Cancel a proposal (only proposer can cancel)"""
        proposal = self.proposals.get(proposal_id)

        if not proposal:
            return False

        if proposal.proposer != canceller:
            return False

        if proposal.status in [ProposalStatus.EXECUTED, ProposalStatus.CANCELLED]:
            return False

        proposal.status = ProposalStatus.CANCELLED
        self._save()

        logger.info(f"Proposal {proposal_id} cancelled by {canceller}")
        return True

    async def mark_executed(self, proposal_id: str) -> bool:
        """Mark a proposal as executed"""
        proposal = self.proposals.get(proposal_id)

        if not proposal:
            return False

        if proposal.status != ProposalStatus.PASSED:
            return False

        proposal.status = ProposalStatus.EXECUTED
        proposal.executed_at = datetime.now()
        proposal.deposit_returned = True

        self._save()
        logger.info(f"Proposal {proposal_id} executed")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get governance statistics"""
        total = len(self.proposals)
        by_status = {}
        by_type = {}

        for proposal in self.proposals.values():
            status = proposal.status.value
            by_status[status] = by_status.get(status, 0) + 1

            ptype = proposal.proposal_type.value
            by_type[ptype] = by_type.get(ptype, 0) + 1

        return {
            "total_proposals": total,
            "by_status": by_status,
            "by_type": by_type,
            "active_proposals": by_status.get("active", 0),
            "passed_proposals": by_status.get("passed", 0) + by_status.get("executed", 0),
            "rejected_proposals": by_status.get("rejected", 0) + by_status.get("expired", 0)
        }


# Singleton instance
_proposal_manager: Optional[ProposalManager] = None


def get_proposal_manager() -> ProposalManager:
    """Get proposal manager singleton"""
    global _proposal_manager

    if _proposal_manager is None:
        _proposal_manager = ProposalManager()

    return _proposal_manager


# Testing
if __name__ == "__main__":
    async def test():
        manager = ProposalManager("test_proposals.json")

        # Create a proposal
        proposal = await manager.create_proposal(
            title="Add New DCA Strategy",
            description="This proposal adds a new dollar-cost averaging strategy to the trading bot.",
            proposal_type=ProposalType.STRATEGY_ADD,
            proposer="JARVIS_TREASURY_WALLET",
            voting_period_days=7,
            execution_data={"strategy_id": "dca_v2", "parameters": {"interval": "1h"}}
        )

        print(f"Created proposal: {proposal.proposal_id}")

        # Activate
        await manager.activate_proposal(proposal.proposal_id)
        print("Proposal activated")

        # Record votes
        await manager.record_vote(proposal.proposal_id, 1000.0, "for")
        await manager.record_vote(proposal.proposal_id, 500.0, "for")
        await manager.record_vote(proposal.proposal_id, 300.0, "against")

        # Get proposal
        updated = await manager.get_proposal(proposal.proposal_id)
        print(f"Votes: {updated.votes_for} for, {updated.votes_against} against")
        print(f"Percentages: {updated.get_vote_percentage()}")

        # Stats
        print(f"\nStats: {manager.get_stats()}")

        # Clean up
        os.remove("test_proposals.json")

    asyncio.run(test())
