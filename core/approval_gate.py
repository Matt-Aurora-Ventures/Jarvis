"""
Human Approval Gate for Live Trading
=====================================

Requires explicit human approval before executing live trades.
All proposed trades are queued until approved or rejected.

This is a CRITICAL safety component - no trade executes without approval.
"""

import json
import logging
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
APPROVALS_DIR = ROOT / "data" / "trading" / "approvals"


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    KILLED = "killed"


@dataclass
class TradeProposal:
    """A proposed trade awaiting human approval."""
    id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    size: float
    price: float
    strategy: str
    reason: str
    timestamp: float = field(default_factory=time.time)
    status: ApprovalStatus = ApprovalStatus.PENDING
    expiry_seconds: int = 300  # 5 minutes default
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    rejection_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "size": self.size,
            "price": self.price,
            "strategy": self.strategy,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "expiry_seconds": self.expiry_seconds,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rejection_reason": self.rejection_reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeProposal":
        status = data.get("status", "pending")
        if isinstance(status, str):
            status = ApprovalStatus(status)
        return cls(
            id=data.get("id", ""),
            symbol=data.get("symbol", ""),
            side=data.get("side", ""),
            size=float(data.get("size", 0)),
            price=float(data.get("price", 0)),
            strategy=data.get("strategy", ""),
            reason=data.get("reason", ""),
            timestamp=float(data.get("timestamp", time.time())),
            status=status,
            expiry_seconds=int(data.get("expiry_seconds", 300)),
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            rejection_reason=data.get("rejection_reason"),
        )
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.expiry_seconds


class ApprovalGate:
    """
    Gatekeeper for live trade execution.
    
    No trade executes without explicit human approval.
    This is a CRITICAL safety component.
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or APPROVALS_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pending_file = self.data_dir / "pending.json"
        self.history_file = self.data_dir / "history.jsonl"
        self._pending: Dict[str, TradeProposal] = {}
        self._load_pending()
        self._kill_switch_active = False
    
    def _load_pending(self):
        """Load pending proposals from disk."""
        if self.pending_file.exists():
            try:
                with open(self.pending_file) as f:
                    data = json.load(f)
                    for item in data:
                        prop = TradeProposal.from_dict(item)
                        if prop.status == ApprovalStatus.PENDING and not prop.is_expired():
                            self._pending[prop.id] = prop
            except Exception as e:
                log.warning(f"Failed to load pending proposals: {e}")
    
    def _save_pending(self):
        """Save pending proposals to disk."""
        try:
            data = [p.to_dict() for p in self._pending.values()]
            with open(self.pending_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save pending proposals: {e}")
    
    def submit_for_approval(self, proposal: TradeProposal) -> str:
        """
        Submit a trade proposal for human approval.
        
        Returns the proposal ID.
        """
        if self._kill_switch_active:
            proposal.status = ApprovalStatus.KILLED
            proposal.rejection_reason = "Kill switch active"
            self._log_history(proposal)
            return proposal.id
        
        # Generate ID if not provided
        if not proposal.id:
            proposal.id = f"trade_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        
        self._pending[proposal.id] = proposal
        self._save_pending()
        self._notify_user(proposal)
        
        log.info(f"Trade proposal submitted: {proposal.id} - {proposal.side} {proposal.size} {proposal.symbol}")
        return proposal.id
    
    def _notify_user(self, proposal: TradeProposal):
        """Send notification to user about pending approval."""
        msg = f"Trade Approval Needed: {proposal.side} {proposal.size:.4f} {proposal.symbol} @ ${proposal.price:.2f}"
        
        # macOS notification
        try:
            subprocess.run([
                'osascript', '-e',
                f'display notification "{msg}" with title "Jarvis Trading" sound name "Glass"'
            ], check=False, capture_output=True, timeout=5)
        except Exception as e:
            log.debug(f"Notification failed: {e}")
        
        # Also log prominently
        log.warning(f"[APPROVAL REQUIRED] {msg}")
    
    def approve(self, proposal_id: str, approved_by: str = "user") -> bool:
        """Approve a pending trade."""
        if proposal_id not in self._pending:
            log.warning(f"Proposal {proposal_id} not found in pending")
            return False
        
        if self._kill_switch_active:
            log.warning(f"Cannot approve - kill switch active")
            return False
        
        proposal = self._pending[proposal_id]
        
        if proposal.is_expired():
            proposal.status = ApprovalStatus.EXPIRED
            self._log_history(proposal)
            del self._pending[proposal_id]
            self._save_pending()
            return False
        
        proposal.status = ApprovalStatus.APPROVED
        proposal.approved_by = approved_by
        proposal.approved_at = time.time()
        
        # Move to history
        self._log_history(proposal)
        del self._pending[proposal_id]
        self._save_pending()
        
        log.info(f"Trade APPROVED: {proposal_id} by {approved_by}")
        return True
    
    def reject(self, proposal_id: str, reason: str = "") -> bool:
        """Reject a pending trade."""
        if proposal_id not in self._pending:
            log.warning(f"Proposal {proposal_id} not found in pending")
            return False
        
        proposal = self._pending[proposal_id]
        proposal.status = ApprovalStatus.REJECTED
        proposal.rejection_reason = reason or "Manually rejected"
        
        self._log_history(proposal)
        del self._pending[proposal_id]
        self._save_pending()
        
        log.info(f"Trade REJECTED: {proposal_id} - {reason}")
        return True
    
    def kill_switch(self) -> int:
        """
        EMERGENCY: Activate kill switch.
        
        - Rejects all pending trades
        - Prevents new trades from being approved
        
        Returns the number of trades killed.
        """
        self._kill_switch_active = True
        count = len(self._pending)
        
        for pid in list(self._pending.keys()):
            proposal = self._pending[pid]
            proposal.status = ApprovalStatus.KILLED
            proposal.rejection_reason = "KILL_SWITCH"
            self._log_history(proposal)
        
        self._pending.clear()
        self._save_pending()
        
        log.critical(f"KILL SWITCH ACTIVATED - {count} trades killed")
        
        # Send urgent notification
        try:
            subprocess.run([
                'osascript', '-e',
                f'display notification "Kill switch activated - {count} trades cancelled" with title "⚠️ JARVIS EMERGENCY" sound name "Sosumi"'
            ], check=False, capture_output=True, timeout=5)
        except Exception:
            pass
        
        return count
    
    def reset_kill_switch(self, confirm: str = "") -> bool:
        """Reset the kill switch. Requires confirmation."""
        if confirm != "I_UNDERSTAND_THE_RISK":
            log.warning("Kill switch reset requires confirmation: 'I_UNDERSTAND_THE_RISK'")
            return False
        
        self._kill_switch_active = False
        log.warning("Kill switch DEACTIVATED")
        return True
    
    def is_kill_switch_active(self) -> bool:
        """Check if kill switch is active."""
        return self._kill_switch_active
    
    def _log_history(self, proposal: TradeProposal):
        """Append proposal to history file."""
        try:
            with open(self.history_file, 'a') as f:
                f.write(json.dumps(proposal.to_dict()) + '\n')
        except Exception as e:
            log.error(f"Failed to log history: {e}")
    
    def get_pending(self) -> List[TradeProposal]:
        """Get all pending proposals, expire old ones."""
        now = time.time()
        expired = []
        
        for pid, prop in self._pending.items():
            if prop.is_expired():
                prop.status = ApprovalStatus.EXPIRED
                self._log_history(prop)
                expired.append(pid)
        
        for pid in expired:
            del self._pending[pid]
        
        if expired:
            self._save_pending()
        
        return list(self._pending.values())
    
    def get_pending_count(self) -> int:
        """Get count of pending proposals."""
        return len(self._pending)
    
    def get_history(self, limit: int = 50) -> List[TradeProposal]:
        """Get recent history of proposals."""
        if not self.history_file.exists():
            return []
        
        proposals = []
        try:
            with open(self.history_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            proposals.append(TradeProposal.from_dict(json.loads(line)))
                        except Exception:
                            pass
        except Exception as e:
            log.error(f"Failed to read history: {e}")
        
        # Return most recent
        return sorted(proposals, key=lambda p: p.timestamp, reverse=True)[:limit]
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the approval gate."""
        return {
            "kill_switch_active": self._kill_switch_active,
            "pending_count": len(self._pending),
            "pending_proposals": [p.to_dict() for p in self._pending.values()],
        }


# Global instance
_approval_gate: Optional[ApprovalGate] = None


def get_approval_gate() -> ApprovalGate:
    """Get the global approval gate instance."""
    global _approval_gate
    if _approval_gate is None:
        _approval_gate = ApprovalGate()
    return _approval_gate


def require_approval(
    symbol: str,
    side: str,
    size: float,
    price: float,
    strategy: str,
    reason: str = "",
    expiry_seconds: int = 300,
) -> TradeProposal:
    """
    Convenience function to submit a trade for approval.
    
    Returns the TradeProposal (check .status to see if approved).
    """
    gate = get_approval_gate()
    proposal = TradeProposal(
        id="",
        symbol=symbol,
        side=side,
        size=size,
        price=price,
        strategy=strategy,
        reason=reason,
        expiry_seconds=expiry_seconds,
    )
    gate.submit_for_approval(proposal)
    return proposal


if __name__ == "__main__":
    # Demo usage
    import sys
    
    gate = get_approval_gate()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "submit":
            prop = require_approval(
                symbol="BTC-USD",
                side="BUY",
                size=0.1,
                price=50000.0,
                strategy="manual_test",
                reason="Test trade proposal"
            )
            print(f"Submitted: {prop.id}")
        
        elif cmd == "list":
            pending = gate.get_pending()
            if pending:
                for p in pending:
                    print(f"  {p.id}: {p.side} {p.size} {p.symbol} @ {p.price}")
            else:
                print("No pending proposals")
        
        elif cmd == "approve" and len(sys.argv) > 2:
            result = gate.approve(sys.argv[2])
            print(f"Approve result: {result}")
        
        elif cmd == "reject" and len(sys.argv) > 2:
            result = gate.reject(sys.argv[2], reason="CLI rejection")
            print(f"Reject result: {result}")
        
        elif cmd == "kill":
            count = gate.kill_switch()
            print(f"Kill switch activated: {count} trades killed")
        
        elif cmd == "status":
            status = gate.get_status()
            print(json.dumps(status, indent=2))
        
        else:
            print("Usage: python approval_gate.py [submit|list|approve <id>|reject <id>|kill|status]")
    else:
        print("Approval Gate CLI")
        print("Usage: python approval_gate.py [submit|list|approve <id>|reject <id>|kill|status]")
