"""
Governance Voting

Token-weighted voting system for $KR8TIV governance.
Voting power is based on token balance and staking tier.

Prompts #71-80: Governance System
"""

import asyncio
import logging
import os
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class VoteChoice(str, Enum):
    """Vote choices"""
    FOR = "for"
    AGAINST = "against"
    ABSTAIN = "abstain"


@dataclass
class VotingPower:
    """User's voting power"""
    wallet: str
    token_balance: float
    staked_balance: float
    staking_multiplier: float
    total_voting_power: float
    tier: str
    last_updated: datetime = field(default_factory=datetime.now)

    @classmethod
    def calculate(
        cls,
        wallet: str,
        token_balance: float,
        staked_balance: float,
        tier: str = "bronze"
    ) -> "VotingPower":
        """Calculate voting power for a wallet"""
        # Staking multipliers by tier
        tier_multipliers = {
            "bronze": 1.0,
            "silver": 1.25,
            "gold": 1.5,
            "platinum": 2.0,
            "diamond": 2.5
        }

        multiplier = tier_multipliers.get(tier.lower(), 1.0)

        # Staked tokens have higher voting power
        staked_power = staked_balance * multiplier
        unstaked_power = token_balance

        total_power = staked_power + unstaked_power

        return cls(
            wallet=wallet,
            token_balance=token_balance,
            staked_balance=staked_balance,
            staking_multiplier=multiplier,
            total_voting_power=total_power,
            tier=tier
        )


@dataclass
class Vote:
    """A single vote on a proposal"""
    vote_id: str
    proposal_id: str
    voter: str
    choice: VoteChoice
    voting_power: float
    timestamp: datetime = field(default_factory=datetime.now)
    tx_hash: Optional[str] = None  # On-chain transaction hash

    def __post_init__(self):
        if not self.vote_id:
            data = f"{self.proposal_id}{self.voter}{self.timestamp.isoformat()}"
            self.vote_id = f"VOTE-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "vote_id": self.vote_id,
            "proposal_id": self.proposal_id,
            "voter": self.voter,
            "choice": self.choice.value,
            "voting_power": self.voting_power,
            "timestamp": self.timestamp.isoformat(),
            "tx_hash": self.tx_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Vote":
        """Create from dictionary"""
        return cls(
            vote_id=data["vote_id"],
            proposal_id=data["proposal_id"],
            voter=data["voter"],
            choice=VoteChoice(data["choice"]),
            voting_power=data["voting_power"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            tx_hash=data.get("tx_hash")
        )


class VotingManager:
    """
    Manages governance voting

    Handles vote submission, tracking, and power calculation.
    """

    def __init__(
        self,
        storage_path: str = "data/governance/votes.json",
        staking_service: Any = None
    ):
        self.storage_path = Path(storage_path)
        self.staking_service = staking_service
        self.votes: Dict[str, Vote] = {}
        self.votes_by_proposal: Dict[str, List[str]] = {}
        self.votes_by_voter: Dict[str, List[str]] = {}
        self._load()

    def _load(self):
        """Load votes from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for vote_data in data.get("votes", []):
                vote = Vote.from_dict(vote_data)
                self.votes[vote.vote_id] = vote

                # Index by proposal
                if vote.proposal_id not in self.votes_by_proposal:
                    self.votes_by_proposal[vote.proposal_id] = []
                self.votes_by_proposal[vote.proposal_id].append(vote.vote_id)

                # Index by voter
                if vote.voter not in self.votes_by_voter:
                    self.votes_by_voter[vote.voter] = []
                self.votes_by_voter[vote.voter].append(vote.vote_id)

            logger.info(f"Loaded {len(self.votes)} votes")

        except Exception as e:
            logger.error(f"Failed to load votes: {e}")

    def _save(self):
        """Save votes to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "votes": [v.to_dict() for v in self.votes.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save votes: {e}")
            raise

    async def get_voting_power(self, wallet: str) -> VotingPower:
        """Get voting power for a wallet"""
        # Get token balances (would integrate with on-chain data)
        token_balance = 0.0
        staked_balance = 0.0
        tier = "bronze"

        if self.staking_service:
            try:
                stake_info = await self.staking_service.get_stake_info(wallet)
                if stake_info:
                    staked_balance = stake_info.get("staked_amount", 0.0)
                    tier = stake_info.get("tier", "bronze")
            except Exception as e:
                logger.warning(f"Failed to get staking info: {e}")

        # For now, use mock data
        # In production, would query on-chain
        return VotingPower.calculate(
            wallet=wallet,
            token_balance=token_balance,
            staked_balance=staked_balance,
            tier=tier
        )

    async def cast_vote(
        self,
        proposal_id: str,
        voter: str,
        choice: VoteChoice,
        voting_power: Optional[float] = None
    ) -> Optional[Vote]:
        """Cast a vote on a proposal"""

        # Check if already voted
        existing = await self.get_vote(proposal_id, voter)
        if existing:
            logger.warning(f"Voter {voter} already voted on {proposal_id}")
            return None

        # Get voting power if not provided
        if voting_power is None:
            power = await self.get_voting_power(voter)
            voting_power = power.total_voting_power

        if voting_power <= 0:
            logger.warning(f"Voter {voter} has no voting power")
            return None

        # Create vote
        vote = Vote(
            vote_id="",  # Will be generated
            proposal_id=proposal_id,
            voter=voter,
            choice=choice,
            voting_power=voting_power
        )

        # Store vote
        self.votes[vote.vote_id] = vote

        # Update indexes
        if proposal_id not in self.votes_by_proposal:
            self.votes_by_proposal[proposal_id] = []
        self.votes_by_proposal[proposal_id].append(vote.vote_id)

        if voter not in self.votes_by_voter:
            self.votes_by_voter[voter] = []
        self.votes_by_voter[voter].append(vote.vote_id)

        self._save()
        logger.info(f"Vote cast: {vote.vote_id} - {voter} voted {choice.value} on {proposal_id}")

        return vote

    async def get_vote(self, proposal_id: str, voter: str) -> Optional[Vote]:
        """Get a user's vote on a proposal"""
        voter_votes = self.votes_by_voter.get(voter, [])

        for vote_id in voter_votes:
            vote = self.votes.get(vote_id)
            if vote and vote.proposal_id == proposal_id:
                return vote

        return None

    async def get_proposal_votes(self, proposal_id: str) -> List[Vote]:
        """Get all votes for a proposal"""
        vote_ids = self.votes_by_proposal.get(proposal_id, [])
        return [self.votes[vid] for vid in vote_ids if vid in self.votes]

    async def get_voter_history(self, voter: str) -> List[Vote]:
        """Get all votes by a voter"""
        vote_ids = self.votes_by_voter.get(voter, [])
        return [self.votes[vid] for vid in vote_ids if vid in self.votes]

    async def get_vote_summary(self, proposal_id: str) -> Dict[str, Any]:
        """Get vote summary for a proposal"""
        votes = await self.get_proposal_votes(proposal_id)

        summary = {
            "proposal_id": proposal_id,
            "total_votes": len(votes),
            "total_voting_power": sum(v.voting_power for v in votes),
            "votes_for": 0.0,
            "votes_against": 0.0,
            "votes_abstain": 0.0,
            "unique_voters": len(set(v.voter for v in votes))
        }

        for vote in votes:
            if vote.choice == VoteChoice.FOR:
                summary["votes_for"] += vote.voting_power
            elif vote.choice == VoteChoice.AGAINST:
                summary["votes_against"] += vote.voting_power
            else:
                summary["votes_abstain"] += vote.voting_power

        return summary

    async def delegate_votes(
        self,
        delegator: str,
        delegatee: str,
        proposal_id: Optional[str] = None
    ) -> bool:
        """Delegate voting power to another user"""
        # Delegation feature - would store in database
        logger.info(f"Delegation from {delegator} to {delegatee}")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get voting statistics"""
        total_votes = len(self.votes)
        unique_voters = len(self.votes_by_voter)
        proposals_voted = len(self.votes_by_proposal)

        total_power_cast = sum(v.voting_power for v in self.votes.values())

        return {
            "total_votes": total_votes,
            "unique_voters": unique_voters,
            "proposals_with_votes": proposals_voted,
            "total_voting_power_cast": total_power_cast,
            "average_power_per_vote": total_power_cast / total_votes if total_votes > 0 else 0
        }


# Singleton instance
_voting_manager: Optional[VotingManager] = None


def get_voting_manager() -> VotingManager:
    """Get voting manager singleton"""
    global _voting_manager

    if _voting_manager is None:
        _voting_manager = VotingManager()

    return _voting_manager


# Testing
if __name__ == "__main__":
    async def test():
        manager = VotingManager("test_votes.json")

        # Calculate voting power
        power = await manager.get_voting_power("WALLET_123")
        print(f"Voting power: {power.total_voting_power}")

        # Cast votes
        vote1 = await manager.cast_vote(
            proposal_id="PROP-TEST1234",
            voter="VOTER_A",
            choice=VoteChoice.FOR,
            voting_power=1000.0
        )
        print(f"Cast vote: {vote1.vote_id}")

        vote2 = await manager.cast_vote(
            proposal_id="PROP-TEST1234",
            voter="VOTER_B",
            choice=VoteChoice.FOR,
            voting_power=500.0
        )
        print(f"Cast vote: {vote2.vote_id}")

        vote3 = await manager.cast_vote(
            proposal_id="PROP-TEST1234",
            voter="VOTER_C",
            choice=VoteChoice.AGAINST,
            voting_power=300.0
        )
        print(f"Cast vote: {vote3.vote_id}")

        # Get summary
        summary = await manager.get_vote_summary("PROP-TEST1234")
        print(f"\nVote summary: {summary}")

        # Stats
        print(f"\nStats: {manager.get_stats()}")

        # Clean up
        os.remove("test_votes.json")

    asyncio.run(test())
