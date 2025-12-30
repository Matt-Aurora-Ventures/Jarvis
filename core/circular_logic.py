"""Circular Logic Prevention for Autonomous Controller."""

import time
from typing import Any, Dict, List, Set, Optional
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CircularLogicDetector:
    """Detects and prevents circular logic in autonomous cycles."""
    
    def __init__(self):
        self.cycle_history: List[Dict[str, Any]] = []
        self.max_history = 100
        self.recent_actions: List[str] = []
        self.max_recent_actions = 20
        self.action_patterns: Dict[str, int] = {}
        self.suspicious_patterns = {
            "research_improvement_loop": 3,  # Research -> Improvement -> Research
            "self_evaluation_loop": 2,      # Self-eval -> Improvement -> Self-eval
            "restart_loop": 2,               # Multiple restarts in short time
            "error_recovery_loop": 3,        # Same error recovery pattern
        }
        
    def record_cycle_start(self, cycle_type: str, task: Optional[Dict] = None):
        """Record the start of a cycle."""
        entry = {
            "type": cycle_type,
            "timestamp": time.time(),
            "task_id": task.get("id") if task else None,
            "task_title": task.get("title") if task else None,
            "phase": "start"
        }
        self.cycle_history.append(entry)
        self._cleanup_history()
        
    def record_cycle_end(self, cycle_type: str, result: Dict = None, error: str = None):
        """Record the end of a cycle."""
        entry = {
            "type": cycle_type,
            "timestamp": time.time(),
            "result": result,
            "error": error,
            "phase": "end"
        }
        self.cycle_history.append(entry)
        self._cleanup_history()
        
    def record_action(self, action: str):
        """Record a specific action for pattern detection."""
        self.recent_actions.append(action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions.pop(0)
            
        # Track action frequency
        self.action_patterns[action] = self.action_patterns.get(action, 0) + 1
        
    def detect_circular_logic(self) -> Optional[Dict]:
        """Detect various types of circular logic."""
        # Check for repeated patterns
        if self._detect_research_improvement_loop():
            return {
                "type": "research_improvement_loop",
                "severity": "medium",
                "description": "Research and improvement cycles triggering each other",
                "suggestion": "Add cooldown period between research and improvement cycles"
            }
            
        if self._detect_self_evaluation_loop():
            return {
                "type": "self_evaluation_loop",
                "severity": "high",
                "description": "Self-evaluation triggering continuous improvements",
                "suggestion": "Limit self-evaluation frequency or add minimum improvement threshold"
            }
            
        if self._detect_restart_loop():
            return {
                "type": "restart_loop",
                "severity": "high",
                "description": "Frequent restarts detected",
                "suggestion": "Investigate restart causes and implement backoff strategy"
            }
            
        if self._detect_error_recovery_loop():
            return {
                "type": "error_recovery_loop",
                "severity": "medium",
                "description": "Repeated error recovery patterns",
                "suggestion": "Review error handling and implement different recovery strategies"
            }
            
        return None

    def _recent_cycles(self, count: int, phase: str = "end") -> List[Dict]:
        """Return the most recent cycles filtered by phase."""
        filtered = [cycle for cycle in self.cycle_history if cycle.get("phase") == phase]
        return filtered[-count:]
        
    def _detect_research_improvement_loop(self) -> bool:
        """Detect research -> improvement -> research loops."""
        recent = self._recent_cycles(6)
        if len(recent) < 4:
            return False
            
        research_count = sum(1 for c in recent if c["type"] == "research")
        improvement_count = sum(1 for c in recent if c["type"] == "improvement")
        
        return research_count >= 2 and improvement_count >= 2
        
    def _detect_self_evaluation_loop(self) -> bool:
        """Detect self-evaluation -> improvement loops."""
        recent = self._recent_cycles(4)
        if len(recent) < 3:
            return False
            
        eval_count = sum(1 for c in recent if c["type"] == "self_evaluation")
        improvement_count = sum(1 for c in recent if c["type"] == "iterative_improvement")
        
        return eval_count >= 2 and improvement_count >= 2
        
    def _detect_restart_loop(self) -> bool:
        """Detect frequent restarts."""
        recent_restarts = [
            c for c in self._recent_cycles(20)
            if c.get("result", {}).get("restart_triggered") or c.get("result", {}).get("restart_needed")
        ]
        
        if len(recent_restarts) >= 2:
            # Check if restarts are within 10 minutes
            for i in range(len(recent_restarts) - 1):
                if recent_restarts[i+1]["timestamp"] - recent_restarts[i]["timestamp"] < 600:
                    return True
                    
        return False
        
    def _detect_error_recovery_loop(self) -> bool:
        """Detect repeated error recovery patterns."""
        recent = self._recent_cycles(10)
        if len(recent) < 4:
            return False
            
        # Look for same error pattern repeating
        error_patterns = {}
        for cycle in recent:
            if cycle.get("error"):
                error_type = cycle["error"].split(":")[0]  # Get error type
                error_patterns[error_type] = error_patterns.get(error_type, 0) + 1
                
        return any(count >= 3 for count in error_patterns.values())
        
    def _cleanup_history(self):
        """Clean up old history entries."""
        if len(self.cycle_history) > self.max_history:
            self.cycle_history = self.cycle_history[-self.max_history:]
            
    def get_cycle_stats(self) -> Dict:
        """Get statistics about cycle patterns."""
        cycle_types = {}
        for cycle in self.cycle_history:
            cycle_type = cycle["type"]
            cycle_types[cycle_type] = cycle_types.get(cycle_type, 0) + 1
            
        return {
            "total_cycles": len(self.cycle_history),
            "cycle_types": cycle_types,
            "action_patterns": dict(sorted(self.action_patterns.items(), key=lambda x: x[1], reverse=True)[:10]),
            "recent_actions": self.recent_actions[-10:]
        }


class CycleGovernor:
    """Governor to prevent excessive cycle execution."""
    
    def __init__(self):
        self.cycle_cooldowns = {
            "research": 300,          # 5 minutes
            "improvement": 600,       # 10 minutes
            "self_evaluation": 1800,  # 30 minutes
            "restart": 1800,          # 30 minutes
            "ability_acquisition": 900, # 15 minutes
        }
        self.last_cycle_times: Dict[str, float] = {}
        self.cycle_counts: Dict[str, int] = {}
        self.cycle_history: Dict[str, List[float]] = {}
        self.max_cycles_per_hour = {
            "research": 3,
            "improvement": 2,
            "self_evaluation": 1,
            "ability_acquisition": 2,
        }
        
    def can_run_cycle(self, cycle_type: str) -> tuple[bool, str]:
        """Check if a cycle can run based on cooldown and frequency limits."""
        now = time.time()
        
        # Check cooldown
        last_run = self.last_cycle_times.get(cycle_type, 0)
        cooldown = self.cycle_cooldowns.get(cycle_type, 60)
        
        if now - last_run < cooldown:
            remaining = int(cooldown - (now - last_run))
            return False, f"Cooldown active: {remaining}s remaining"
            
        # Check hourly frequency
        hour_ago = now - 3600
        recent_cycles = sum(
            1 for timestamp in self.cycle_history.get(cycle_type, [])
            if timestamp > hour_ago
        )
        
        max_hourly = self.max_cycles_per_hour.get(cycle_type, 5)
        if recent_cycles >= max_hourly:
            return False, f"Hourly limit reached: {recent_cycles}/{max_hourly}"
            
        return True, "Cycle allowed"
        
    def record_cycle(self, cycle_type: str):
        """Record that a cycle was executed."""
        now = time.time()
        self.last_cycle_times[cycle_type] = now
        
        if cycle_type not in self.cycle_history:
            self.cycle_history[cycle_type] = []
        self.cycle_history[cycle_type].append(now)
        
        # Clean old entries
        hour_ago = now - 3600
        self.cycle_history[cycle_type] = [
            ts for ts in self.cycle_history[cycle_type] if ts > hour_ago
        ]
        
    def block_cycle(self, cycle_type: str, duration_seconds: int = 1800):
        """Explicitly block a cycle type for a duration (enforcement)."""
        now = time.time()
        # Set last_run to future time to simulate long cooldown
        self.last_cycle_times[cycle_type] = now + duration_seconds - self.cycle_cooldowns.get(cycle_type, 60)

    def enforce_circular_logic_block(self, detected_issue: Dict):
        """Enforce blocks based on detected circular logic issue."""
        issue_type = detected_issue.get("type", "")

        if issue_type == "research_improvement_loop":
            self.block_cycle("research", 600)  # 10 min block
            self.block_cycle("improvement", 600)
        elif issue_type == "self_evaluation_loop":
            self.block_cycle("self_evaluation", 3600)  # 1 hour block
        elif issue_type == "restart_loop":
            self.block_cycle("restart", 1800)  # 30 min block
        elif issue_type == "error_recovery_loop":
            # Block any improvement-related cycles
            self.block_cycle("improvement", 900)

    def get_governor_stats(self) -> Dict:
        """Get governor statistics."""
        now = time.time()
        stats = {}

        for cycle_type in self.cycle_cooldowns.keys():
            last_run = self.last_cycle_times.get(cycle_type, 0)
            cooldown = self.cycle_cooldowns[cycle_type]
            can_run, reason = self.can_run_cycle(cycle_type)

            stats[cycle_type] = {
                "last_run": last_run,
                "cooldown_remaining": max(0, cooldown - (now - last_run)),
                "can_run": can_run,
                "reason": reason,
                "hourly_count": len(self.cycle_history.get(cycle_type, []))
            }

        return stats
