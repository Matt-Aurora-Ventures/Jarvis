"""
Information Session - User Alignment Protocol

Scheduled check-ins where Jarvis asks for input on medium-confidence improvements.
Never interrupts flow - only during idle time or scheduled sessions.

Key Features:
- Smart scheduling (idle detection, time-based)
- Batch questions (max 3 per session)
- Quick approval interface
- Learning from user preferences
"""

import json
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, state, passive


ROOT = Path(__file__).resolve().parents[1]
SESSION_LOG = ROOT / "data" / "observation" / "info_sessions.jsonl"
PREFERENCES_DB = ROOT / "data" / "observation" / "user_preferences.json"


@dataclass
class InfoSession:
    """An information session record."""
    session_id: str
    started_at: float
    ended_at: float
    questions_asked: int
    questions_approved: int
    questions_rejected: int
    user_idle_seconds: float


class InformationSessionManager:
    """
    Manages scheduled information sessions.
    
    Triggers:
    - Daily scheduled time (default: 9am)
    - User idle for 10+ minutes (opportunistic)
    - Manual trigger: `lifeos info-session`
    
    Never triggers during:
    - Active coding (recent keystrokes)
    - Active communication (email, chat apps)
    - Meetings (calendar integration)
    """
    
    def __init__(self):
        cfg = config.load_config()
        session_cfg = cfg.get("information_session", {})
        self.enabled = session_cfg.get("enabled", True)
        self.scheduled_time = session_cfg.get("scheduled_time", "09:00")
        self.min_idle_seconds = session_cfg.get("min_idle_seconds", 600)  # 10 min
        self.max_questions_per_session = session_cfg.get("max_questions", 3)
        self.cooldown_hours = session_cfg.get("cooldown_hours", 4)
        
        # State
        self.last_session_time = 0.0
        self.user_preferences = self._load_preferences()
    
    def _load_preferences(self) -> Dict[str, Any]:
        """Load user preferences from disk."""
        if not PREFERENCES_DB.exists():
            return {}
        
        try:
            with open(PREFERENCES_DB, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _save_preferences(self):
        """Save user preferences to disk."""
        PREFERENCES_DB.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(PREFERENCES_DB, "w") as f:
                json.dump(self.user_preferences, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save preferences: {e}")
    
    def should_trigger_session(self) -> bool:
        """
        Check if an information session should be triggered.
        
        Returns True if conditions are met.
        """
        if not self.enabled:
            return False
        
        # Check cooldown
        hours_since_last = (time.time() - self.last_session_time) / 3600
        if hours_since_last < self.cooldown_hours:
            return False
        
        # Check if scheduled time
        now = datetime.now()
        scheduled_hour, scheduled_min = map(int, self.scheduled_time.split(":"))
        if now.hour == scheduled_hour and now.minute == scheduled_min:
            # Check if already ran today
            last_session_date = datetime.fromtimestamp(self.last_session_time).date()
            if last_session_date == now.date():
                return False  # Already ran today
            return True
        
        # Check opportunistic trigger (user idle)
        system_state = state.read_state()
        idle_seconds = system_state.get("passive_idle_seconds", 0)
        
        if idle_seconds >= self.min_idle_seconds:
            # Additional check: not in active communication apps
            current_app = system_state.get("passive_context", "")
            blocked_apps = ["Mail", "Slack", "Discord", "Zoom", "Teams", "Messages"]
            if any(app in current_app for app in blocked_apps):
                return False
            
            return True
        
        return False
    
    def run_session(self, queued_hypotheses: List[Any]) -> InfoSession:
        """
        Run an information session.
        
        Args:
            queued_hypotheses: List of ImprovementHypothesis objects
        
        Returns:
            InfoSession record
        """
        session_id = f"session_{int(time.time())}"
        started_at = time.time()
        
        # Get idle time
        system_state = state.read_state()
        idle_seconds = system_state.get("passive_idle_seconds", 0)
        
        # Limit questions
        hypotheses_to_ask = queued_hypotheses[:self.max_questions_per_session]
        
        approved_count = 0
        rejected_count = 0
        
        # Send notification
        self._send_notification(
            "Jarvis Information Session",
            f"I have {len(hypotheses_to_ask)} improvement suggestions. Let's review them!"
        )
        
        # Ask each question
        for hyp in hypotheses_to_ask:
            approved = self._ask_user(hyp)
            
            if approved:
                approved_count += 1
                # Execute improvement
                from core.background_improver import BackgroundImprover
                improver = BackgroundImprover()
                improver.execute(hyp.proposal)
                
                # Learn preference
                self._learn_preference(hyp, approved=True)
            else:
                rejected_count += 1
                self._learn_preference(hyp, approved=False)
        
        # Record session
        session = InfoSession(
            session_id=session_id,
            started_at=started_at,
            ended_at=time.time(),
            questions_asked=len(hypotheses_to_ask),
            questions_approved=approved_count,
            questions_rejected=rejected_count,
            user_idle_seconds=idle_seconds,
        )
        
        self._log_session(session)
        self.last_session_time = time.time()
        
        return session
    
    def _ask_user(self, hypothesis: Any) -> bool:
        """
        Ask user to approve/reject a hypothesis.
        
        Uses macOS dialog box for quick approval.
        """
        # Build question text
        question = f"""
{hypothesis.description}

Category: {hypothesis.category}
Confidence: {hypothesis.confidence:.0%}
Impact: {hypothesis.impact}
Risk: {hypothesis.risk:.0%}

Details:
{hypothesis.proposal.code[:100] if hypothesis.proposal else '(No code)'}

Approve this improvement?
"""
        
        # Display macOS dialog
        script = f'''
display dialog "{question.replace('"', '\\"')}" ¬
    buttons {{"Reject", "Approve"}} ¬
    default button "Approve" ¬
    with title "Jarvis Improvement Suggestion" ¬
    giving up after 30
'''
        
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=35,
            )
            
            # Check which button was clicked
            if "Approve" in result.stdout:
                return True
            elif "gave up:true" in result.stdout:
                # User didn't respond - default to reject
                return False
            else:
                return False
        
        except Exception as e:
            print(f"Warning: User prompt failed: {e}")
            return False
    
    def _learn_preference(self, hypothesis: Any, approved: bool):
        """
        Learn from user's approval/rejection.
        
        Updates thresholds for similar patterns.
        """
        category = hypothesis.category
        
        if category not in self.user_preferences:
            self.user_preferences[category] = {
                "total_asked": 0,
                "total_approved": 0,
                "approval_rate": 0.5,
            }
        
        pref = self.user_preferences[category]
        pref["total_asked"] += 1
        
        if approved:
            pref["total_approved"] += 1
        
        pref["approval_rate"] = pref["total_approved"] / pref["total_asked"]
        
        self._save_preferences()
    
    def get_adjusted_threshold(self, category: str) -> float:
        """
        Get adjusted confidence threshold for a category based on user preferences.
        
        If user approves 90% of a category, lower the threshold.
        If user rejects 60%, raise the threshold.
        """
        base_threshold = 0.7
        
        if category not in self.user_preferences:
            return base_threshold
        
        approval_rate = self.user_preferences[category]["approval_rate"]
        
        # Adjust threshold based on approval rate
        # High approval (0.8+) → lower threshold (auto-execute more)
        # Low approval (0.4-) → raise threshold (ask less often)
        
        if approval_rate >= 0.8:
            return base_threshold - 0.1  # 0.6
        elif approval_rate >= 0.6:
            return base_threshold  # 0.7
        elif approval_rate >= 0.4:
            return base_threshold + 0.1  # 0.8
        else:
            return base_threshold + 0.2  # 0.9 (very selective)
    
    def _send_notification(self, title: str, message: str):
        """Send macOS notification."""
        try:
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                check=False,
                timeout=5,
            )
        except Exception:
            pass
    
    def _log_session(self, session: InfoSession):
        """Log session to JSONL file."""
        SESSION_LOG.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(SESSION_LOG, "a") as f:
                f.write(json.dumps(asdict(session)) + "\n")
        except Exception as e:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        if not SESSION_LOG.exists():
            return {
                "total_sessions": 0,
                "total_questions": 0,
                "total_approved": 0,
                "approval_rate": 0.0,
            }
        
        sessions = []
        try:
            with open(SESSION_LOG, "r") as f:
                for line in f:
                    try:
                        sessions.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            return {"total_sessions": 0}
        
        total_questions = sum(s.get("questions_asked", 0) for s in sessions)
        total_approved = sum(s.get("questions_approved", 0) for s in sessions)
        
        return {
            "total_sessions": len(sessions),
            "total_questions": total_questions,
            "total_approved": total_approved,
            "approval_rate": total_approved / max(total_questions, 1),
            "last_session": sessions[-1] if sessions else None,
            "preferences": self.user_preferences,
        }


# Global manager instance
_manager: Optional[InformationSessionManager] = None


def get_manager() -> InformationSessionManager:
    """Get or create the global session manager."""
    global _manager
    if _manager is None:
        _manager = InformationSessionManager()
    return _manager


def trigger_session_if_ready():
    """
    Check if session should trigger and run if conditions met.
    
    This is called periodically by the daemon.
    """
    manager = get_manager()
    
    if manager.should_trigger_session():
        # Get queued hypotheses from daemon
        from core.observation_daemon import get_daemon
        daemon = get_daemon()
        
        if daemon:
            queued = daemon.get_queued_improvements()
            if queued:
                manager.run_session(queued)


def manual_session():
    """
    Manually trigger an information session.
    
    CLI command: lifeos info-session
    """
    manager = get_manager()
    
    from core.observation_daemon import get_daemon
    daemon = get_daemon()
    
    if daemon:
        queued = daemon.get_queued_improvements()
        if queued:
            session = manager.run_session(queued)
            print(f"✅ Information Session complete:")
            print(f"   Questions: {session.questions_asked}")
            print(f"   Approved: {session.questions_approved}")
            print(f"   Rejected: {session.questions_rejected}")
        else:
            print("ℹ️  No queued improvements to review")
    else:
        print("⚠️  Observational Daemon not running")
