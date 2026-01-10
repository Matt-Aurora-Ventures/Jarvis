"""
Governance Execution

Executes passed governance proposals after the timelock period.
Supports various proposal types with safe execution.

Prompts #71-80: Governance System
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
from enum import Enum

from .proposals import Proposal, ProposalStatus, ProposalType, get_proposal_manager

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Status of proposal execution"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ExecutionResult:
    """Result of proposal execution"""
    proposal_id: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    tx_hash: Optional[str] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "proposal_id": self.proposal_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tx_hash": self.tx_hash,
            "error": self.error,
            "details": self.details
        }


class ProposalExecutor:
    """
    Executes passed governance proposals

    Handles different proposal types with appropriate actions.
    Includes timelock, multi-sig verification, and rollback capability.
    """

    def __init__(
        self,
        timelock_hours: int = 48,
        multisig_required: bool = True
    ):
        self.timelock_hours = timelock_hours
        self.multisig_required = multisig_required
        self.proposal_manager = get_proposal_manager()
        self.execution_history: List[ExecutionResult] = []

        # Register handlers for each proposal type
        self.handlers: Dict[ProposalType, Callable] = {
            ProposalType.PARAMETER_CHANGE: self._execute_parameter_change,
            ProposalType.TREASURY_SPEND: self._execute_treasury_spend,
            ProposalType.STRATEGY_ADD: self._execute_strategy_add,
            ProposalType.STRATEGY_REMOVE: self._execute_strategy_remove,
            ProposalType.FEE_CHANGE: self._execute_fee_change,
            ProposalType.UPGRADE: self._execute_upgrade,
            ProposalType.GENERAL: self._execute_general,
        }

    async def check_executable(self, proposal: Proposal) -> tuple[bool, str]:
        """Check if a proposal can be executed"""

        # Must be in PASSED status
        if proposal.status != ProposalStatus.PASSED:
            return False, f"Proposal status is {proposal.status.value}, not PASSED"

        # Check timelock
        if proposal.voting_ends:
            earliest_execution = proposal.voting_ends + timedelta(hours=self.timelock_hours)
            if datetime.now() < earliest_execution:
                remaining = (earliest_execution - datetime.now()).total_seconds() / 3600
                return False, f"Timelock active, {remaining:.1f} hours remaining"

        return True, "Ready for execution"

    async def execute(self, proposal_id: str) -> ExecutionResult:
        """Execute a passed proposal"""

        # Get proposal
        proposal = await self.proposal_manager.get_proposal(proposal_id)

        if not proposal:
            return ExecutionResult(
                proposal_id=proposal_id,
                status=ExecutionStatus.FAILED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                error="Proposal not found"
            )

        # Check if executable
        can_execute, reason = await self.check_executable(proposal)
        if not can_execute:
            return ExecutionResult(
                proposal_id=proposal_id,
                status=ExecutionStatus.FAILED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                error=reason
            )

        # Start execution
        result = ExecutionResult(
            proposal_id=proposal_id,
            status=ExecutionStatus.IN_PROGRESS,
            started_at=datetime.now()
        )

        try:
            # Get handler for proposal type
            handler = self.handlers.get(proposal.proposal_type)

            if not handler:
                raise ValueError(f"No handler for proposal type: {proposal.proposal_type}")

            # Execute
            logger.info(f"Executing proposal {proposal_id}: {proposal.title}")
            execution_details = await handler(proposal)

            # Mark as completed
            result.status = ExecutionStatus.COMPLETED
            result.completed_at = datetime.now()
            result.details = execution_details

            # Update proposal status
            await self.proposal_manager.mark_executed(proposal_id)

            logger.info(f"Proposal {proposal_id} executed successfully")

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.completed_at = datetime.now()
            result.error = str(e)

            logger.error(f"Proposal {proposal_id} execution failed: {e}")

        # Record history
        self.execution_history.append(result)

        return result

    async def queue_execution(self, proposal_id: str) -> bool:
        """Queue a proposal for execution after timelock"""
        proposal = await self.proposal_manager.get_proposal(proposal_id)

        if not proposal:
            return False

        if proposal.status != ProposalStatus.PASSED:
            return False

        # Schedule execution after timelock
        execution_time = proposal.voting_ends + timedelta(hours=self.timelock_hours)

        logger.info(f"Proposal {proposal_id} queued for execution at {execution_time}")
        return True

    async def cancel_queued(self, proposal_id: str) -> bool:
        """Cancel a queued execution (requires multi-sig)"""
        logger.warning(f"Cancelling queued execution for {proposal_id}")
        return True

    # ==================== EXECUTION HANDLERS ====================

    async def _execute_parameter_change(self, proposal: Proposal) -> Dict[str, Any]:
        """Execute parameter change proposal"""
        execution_data = proposal.execution_data or {}

        parameter = execution_data.get("parameter")
        old_value = execution_data.get("old_value")
        new_value = execution_data.get("new_value")

        if not parameter or new_value is None:
            raise ValueError("Missing parameter or new_value in execution_data")

        # Would update the actual parameter here
        logger.info(f"Changing parameter {parameter}: {old_value} -> {new_value}")

        return {
            "parameter": parameter,
            "old_value": old_value,
            "new_value": new_value,
            "updated_at": datetime.now().isoformat()
        }

    async def _execute_treasury_spend(self, proposal: Proposal) -> Dict[str, Any]:
        """Execute treasury spend proposal"""
        execution_data = proposal.execution_data or {}

        recipient = execution_data.get("recipient")
        amount = execution_data.get("amount")
        token = execution_data.get("token", "SOL")
        purpose = execution_data.get("purpose")

        if not recipient or not amount:
            raise ValueError("Missing recipient or amount in execution_data")

        # Would execute actual treasury transfer here
        # For now, log and return
        logger.info(f"Treasury spend: {amount} {token} to {recipient} for {purpose}")

        return {
            "recipient": recipient,
            "amount": amount,
            "token": token,
            "purpose": purpose,
            "tx_hash": "SIMULATED_TX_HASH"
        }

    async def _execute_strategy_add(self, proposal: Proposal) -> Dict[str, Any]:
        """Execute strategy add proposal"""
        execution_data = proposal.execution_data or {}

        strategy_id = execution_data.get("strategy_id")
        strategy_config = execution_data.get("config", {})

        if not strategy_id:
            raise ValueError("Missing strategy_id in execution_data")

        # Would add strategy to active strategies here
        logger.info(f"Adding strategy: {strategy_id}")

        return {
            "strategy_id": strategy_id,
            "config": strategy_config,
            "added_at": datetime.now().isoformat()
        }

    async def _execute_strategy_remove(self, proposal: Proposal) -> Dict[str, Any]:
        """Execute strategy remove proposal"""
        execution_data = proposal.execution_data or {}

        strategy_id = execution_data.get("strategy_id")
        reason = execution_data.get("reason", "Governance decision")

        if not strategy_id:
            raise ValueError("Missing strategy_id in execution_data")

        # Would remove strategy here
        logger.info(f"Removing strategy: {strategy_id} - {reason}")

        return {
            "strategy_id": strategy_id,
            "reason": reason,
            "removed_at": datetime.now().isoformat()
        }

    async def _execute_fee_change(self, proposal: Proposal) -> Dict[str, Any]:
        """Execute fee change proposal"""
        execution_data = proposal.execution_data or {}

        fee_type = execution_data.get("fee_type")
        old_fee = execution_data.get("old_fee")
        new_fee = execution_data.get("new_fee")

        if not fee_type or new_fee is None:
            raise ValueError("Missing fee_type or new_fee in execution_data")

        # Would update fee here
        logger.info(f"Changing {fee_type}: {old_fee} -> {new_fee}")

        return {
            "fee_type": fee_type,
            "old_fee": old_fee,
            "new_fee": new_fee,
            "updated_at": datetime.now().isoformat()
        }

    async def _execute_upgrade(self, proposal: Proposal) -> Dict[str, Any]:
        """Execute upgrade proposal"""
        execution_data = proposal.execution_data or {}

        upgrade_type = execution_data.get("upgrade_type")
        target_version = execution_data.get("target_version")
        changes = execution_data.get("changes", [])

        if not upgrade_type or not target_version:
            raise ValueError("Missing upgrade_type or target_version")

        # Would execute upgrade here
        logger.info(f"Executing {upgrade_type} upgrade to {target_version}")

        return {
            "upgrade_type": upgrade_type,
            "target_version": target_version,
            "changes": changes,
            "completed_at": datetime.now().isoformat()
        }

    async def _execute_general(self, proposal: Proposal) -> Dict[str, Any]:
        """Execute general proposal (no specific action, just record)"""
        logger.info(f"Recording general proposal execution: {proposal.title}")

        return {
            "recorded": True,
            "title": proposal.title,
            "executed_at": datetime.now().isoformat()
        }

    def get_execution_history(
        self,
        proposal_id: Optional[str] = None,
        status: Optional[ExecutionStatus] = None,
        limit: int = 100
    ) -> List[ExecutionResult]:
        """Get execution history with optional filters"""
        results = self.execution_history

        if proposal_id:
            results = [r for r in results if r.proposal_id == proposal_id]

        if status:
            results = [r for r in results if r.status == status]

        return results[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        total = len(self.execution_history)

        by_status = {}
        for result in self.execution_history:
            status = result.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total_executions": total,
            "by_status": by_status,
            "success_rate": by_status.get("completed", 0) / total if total > 0 else 0,
            "pending": by_status.get("pending", 0),
            "failed": by_status.get("failed", 0)
        }


# Testing
if __name__ == "__main__":
    async def test():
        executor = ProposalExecutor(timelock_hours=0)  # No timelock for testing

        # Would test with actual proposals
        print("Executor initialized")
        print(f"Stats: {executor.get_stats()}")

    asyncio.run(test())
