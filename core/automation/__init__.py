"""
Automation System - Multi-step action chains and scheduled tasks.

Provides:
- ActionChain: Sequential and parallel action execution with rollback
- ActionScheduler: Cron-like scheduled task execution
- ActionRecorder: Record and playback action sequences
"""

from core.automation.chains import (
    ActionChain,
    ChainStep,
    ChainResult,
    ChainExecutor,
    StepStatus,
    ExecutionMode,
    get_chain_executor,
)
from core.automation.scheduler import (
    ActionScheduler,
    ScheduledJob,
    JobExecution,
    ScheduleType,
    JobStatus,
    CronParser,
    get_scheduler,
)
from core.automation.recorder import (
    ActionRecorder,
    RecordedAction,
    ActionRecording,
    PlaybackResult,
    ActionType,
    RecordingStatus,
    get_recorder,
)

__all__ = [
    # Chains
    "ActionChain",
    "ChainStep",
    "ChainResult",
    "ChainExecutor",
    "StepStatus",
    "ExecutionMode",
    "get_chain_executor",
    # Scheduler
    "ActionScheduler",
    "ScheduledJob",
    "JobExecution",
    "ScheduleType",
    "JobStatus",
    "CronParser",
    "get_scheduler",
    # Recorder
    "ActionRecorder",
    "RecordedAction",
    "ActionRecording",
    "PlaybackResult",
    "ActionType",
    "RecordingStatus",
    "get_recorder",
]
