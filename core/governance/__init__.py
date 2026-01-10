"""
JARVIS Governance System

Token-based governance for $KR8TIV holders.
Includes proposals, voting, and on-chain execution.
"""

from .proposals import (
    Proposal,
    ProposalStatus,
    ProposalType,
    ProposalManager,
    get_proposal_manager,
)
from .voting import (
    Vote,
    VoteChoice,
    VotingPower,
    VotingManager,
    get_voting_manager,
)
from .execution import (
    ProposalExecutor,
    ExecutionResult,
)

__all__ = [
    # Proposals
    "Proposal",
    "ProposalStatus",
    "ProposalType",
    "ProposalManager",
    "get_proposal_manager",
    # Voting
    "Vote",
    "VoteChoice",
    "VotingPower",
    "VotingManager",
    "get_voting_manager",
    # Execution
    "ProposalExecutor",
    "ExecutionResult",
]
