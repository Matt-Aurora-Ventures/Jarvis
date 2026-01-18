"""
Jarvis Auto-Moderation System

Autonomous content filtering and user management:
- Toxicity detection (OpenAI Moderation API)
- Spam detection
- Scam/phishing detection
- Auto-actions (warn, mute, ban)
- Appeal system for false positives
"""

from .toxicity_detector import ToxicityDetector, ToxicityLevel
from .auto_actions import AutoActions, ModerationAction

__all__ = ["ToxicityDetector", "ToxicityLevel", "AutoActions", "ModerationAction"]
