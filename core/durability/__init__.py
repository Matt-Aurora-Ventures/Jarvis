"""
JARVIS Durability Layer - Resume after crash.

Bots should not "forget" mid-action. This module provides:
1. Run Ledger - Track operation state across restarts
2. Checkpointing - Save progress within long operations
3. Recovery - Resume or cleanly abort on restart

Usage:
    from core.durability import RunLedger, RunState

    ledger = RunLedger()

    # Start a run
    run = await ledger.start_run(
        platform="telegram",
        intent="send_broadcast",
        steps=["prepare", "send", "confirm"],
        metadata={"recipients": 100}
    )

    # Mark steps complete
    await ledger.complete_step(run.id, "prepare")
    await ledger.complete_step(run.id, "send")

    # On restart - check for incomplete runs
    incomplete = await ledger.get_incomplete_runs()
    for run in incomplete:
        if run.current_step == "confirm":
            await resume_confirmation(run)
        else:
            await ledger.abort_run(run.id, "Aborted on restart")
"""

from .ledger import (
    RunLedger,
    get_run_ledger,
)
from .models import (
    Run,
    RunState,
    RunStep,
    StepState,
)

__all__ = [
    "RunLedger",
    "get_run_ledger",
    "Run",
    "RunState",
    "RunStep",
    "StepState",
]
