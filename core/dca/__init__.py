"""
JARVIS DCA Automation System

Automated Dollar-Cost Averaging with customizable schedules,
smart entry timing, and portfolio rebalancing.

Prompts #113-116: DCA Automation
"""

from .scheduler import (
    DCAScheduler,
    DCASchedule,
    DCAExecution,
    ScheduleFrequency,
    get_dca_scheduler,
)
from .smart_dca import (
    SmartDCA,
    SmartDCAConfig,
    MarketCondition,
)

__all__ = [
    # Scheduler
    "DCAScheduler",
    "DCASchedule",
    "DCAExecution",
    "ScheduleFrequency",
    "get_dca_scheduler",
    # Smart DCA
    "SmartDCA",
    "SmartDCAConfig",
    "MarketCondition",
]

# Safety flag
DCA_AUTOMATION_ENABLED = False  # DISABLED until audited
