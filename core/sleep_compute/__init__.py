"""
Sleep-Time Compute System for ClawdBot Team.

This module provides nightly analysis of bot activity logs to:
- Extract patterns from multi-agent interactions
- Create knowledge graph derives (Supermemory)
- Update SOUL files with actionable insights

Designed to run during low-activity hours (cron: 0 3 * * *)
"""

from .nightly_routine import (
    NightlyRoutine,
    Pattern,
    PatternCategory,
    DeriveChain,
    SleepComputeConfig,
)

__all__ = [
    "NightlyRoutine",
    "Pattern",
    "PatternCategory",
    "DeriveChain",
    "SleepComputeConfig",
]
