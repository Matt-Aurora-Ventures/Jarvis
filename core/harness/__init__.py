"""NPC harness utilities for action journaling and approvals."""

from core.harness.action_schema import ActionDecision, ActionEvent, ActionProposal
from core.harness.aggregate import UnifiedAction, aggregate_actions, read_journal_tail
from core.harness.budgets import Budget
from core.harness.decision_gate import DecisionGate
from core.harness.identity import canonicalize, content_hash, new_id
from core.harness.journal import ActionJournal
from core.harness.loss_accounting import LossRecord, record_loss
from core.harness.validators import (
    ValidationResult,
    get_kill_switch_status,
    set_kill_switch_status,
    validate_budget,
    validate_kill_switch,
    validate_proposal_schema,
)

__all__ = [
    "ActionDecision",
    "ActionEvent",
    "ActionProposal",
    "ActionJournal",
    "Budget",
    "DecisionGate",
    "LossRecord",
    "ValidationResult",
    "UnifiedAction",
    "aggregate_actions",
    "canonicalize",
    "content_hash",
    "get_kill_switch_status",
    "new_id",
    "read_journal_tail",
    "record_loss",
    "set_kill_switch_status",
    "validate_budget",
    "validate_kill_switch",
    "validate_proposal_schema",
]
