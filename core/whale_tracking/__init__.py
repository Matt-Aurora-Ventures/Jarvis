"""
JARVIS Whale Tracking System

Monitor large wallet movements and on-chain whale activity.
Provides alerts and analytics on significant transactions.

Prompts #109-112: Whale Watching
"""

from .tracker import (
    WhaleTracker,
    WhaleWallet,
    WhaleTransaction,
    WhaleAlert,
    get_whale_tracker,
)
from .analyzer import (
    WhaleAnalyzer,
    WhalePattern,
    AccumulationSignal,
)

__all__ = [
    # Tracker
    "WhaleTracker",
    "WhaleWallet",
    "WhaleTransaction",
    "WhaleAlert",
    "get_whale_tracker",
    # Analyzer
    "WhaleAnalyzer",
    "WhalePattern",
    "AccumulationSignal",
]
