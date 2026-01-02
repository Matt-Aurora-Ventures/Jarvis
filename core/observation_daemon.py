"""
Observational Daemon - Continuous Learning Loop

Runs 24/7 in the background, detecting patterns in user behavior and
generating improvement hypotheses using lightweight Groq/Minimax models.

Key Features:
- Lightweight (< 2% CPU, < 50MB RAM)
- Real-time pattern detection
- Confidence-based auto-execution (>= 0.7)
- Silent except during scheduled Information Sessions
- Self-improving via feedback loop
"""

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple
import re

from core import config, observer, passive, providers, guardian
from core.background_improver import BackgroundImprover, ImprovementProposal


ROOT = Path(__file__).resolve().parents[1]
PATTERNS_DB = ROOT / "data" / "observation" / "patterns.json"
HYPOTHESIS_LOG = ROOT / "data" / "observation" / "hypotheses.jsonl"


@dataclass
class ObservedPattern:
    """A detected behavioral pattern."""
    pattern_id: str
    category: str  # command_alias, code_snippet, error_fix, workflow, etc.
    description: str
    occurrences: int
    first_seen: float
    last_seen: float
    confidence: float  # 0.0-1.0
    context: Dict[str, Any] = field(default_factory=dict)
    
    def age_hours(self) -> float:
        """Hours since first observation."""
        return (time.time() - self.first_seen) / 3600
    
    def frequency_per_hour(self) -> float:
        """Occurrence rate per hour."""
        age_h = max(self.age_hours(), 0.1)
        return self.occurrences / age_h


@dataclass
class ImprovementHypothesis:
    """A proposed improvement generated from observed patterns."""
    hypothesis_id: str
    pattern_id: str
    category: str
    description: str
    confidence: float
    impact: str  # low, medium, high
    risk: float  # 0.0-1.0
    proposal: Optional[ImprovementProposal]
    created_at: float
    status: str  # pending, executed, queued, discarded


class ObservationalDaemon(threading.Thread):
    """
    Always-on pattern detection and hypothesis generation.
    
    Workflow:
    1. Observe (via DeepObserver + PassiveObserver)
    2. Detect patterns (every 60s)
    3. Generate hypotheses (Groq LLM)
    4. Score confidence
    5. Route to BackgroundImprover or Information Session queue
    """
    
    def __init__(self):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
        # Configuration
        cfg = config.load_config()
        obs_cfg = cfg.get("observational_daemon", {})
        self.enabled = obs_cfg.get("enabled", True)
        self.analysis_interval = obs_cfg.get("analysis_interval_seconds", 60)
        self.auto_execute_threshold = obs_cfg.get("auto_execute_threshold", 0.7)
        self.info_session_threshold = obs_cfg.get("info_session_threshold", 0.5)
        self.max_hypotheses_per_cycle = obs_cfg.get("max_hypotheses_per_cycle", 3)
        
        # Pattern database (in-memory + disk)
        self.patterns: Dict[str, ObservedPattern] = {}
        self.hypotheses: Deque[ImprovementHypothesis] = deque(maxlen=100)
        
        # Components
        self.deep_observer = None
        self.passive_observer = None
        self.improver = BackgroundImprover()
        
        # Stats
        self.cycles_run = 0
        self.patterns_detected = 0
        self.hypotheses_generated = 0
        self.auto_executed = 0
        self.queued_for_review = 0
        
        # Load existing patterns
        self._load_patterns()
    
    def _load_patterns(self):
        """Load pattern database from disk."""
        if not PATTERNS_DB.exists():
            return
        
        try:
            with open(PATTERNS_DB, "r") as f:
                data = json.load(f)
            
            for p in data.get("patterns", []):
                pattern = ObservedPattern(**p)
                self.patterns[pattern.pattern_id] = pattern
        except Exception as e:
            print(f"Warning: Failed to load patterns: {e}")
    
    def _save_patterns(self):
        """Save pattern database to disk."""
        PATTERNS_DB.parent.mkdir(parents=True, exist_ok=True)
        
        with self._lock:
            data = {
                "updated_at": datetime.now().isoformat(),
                "patterns": [asdict(p) for p in self.patterns.values()],
            }
        
        try:
            with open(PATTERNS_DB, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save patterns: {e}")
    
    def _log_hypothesis(self, hypothesis: ImprovementHypothesis):
        """Log hypothesis to JSONL file."""
        HYPOTHESIS_LOG.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(HYPOTHESIS_LOG, "a") as f:
                f.write(json.dumps({
                    "id": hypothesis.hypothesis_id,
                    "pattern_id": hypothesis.pattern_id,
                    "category": hypothesis.category,
                    "confidence": hypothesis.confidence,
                    "status": hypothesis.status,
                    "timestamp": datetime.now().isoformat(),
                }) + "\n")
        except Exception as e:
            pass
    
    def _detect_command_patterns(self) -> List[ObservedPattern]:
        """
        Detect repeated command sequences from DeepObserver.
        
        Example: "git status && git pull" typed 5x → Create alias
        """
        if not self.deep_observer:
            return []
        
        patterns = []
        recent_text = self.deep_observer.get_recent_text(seconds=1800)  # Last 30min
        
        # Extract lines (simplified - looks for Enter keypresses)
        lines = [l.strip() for l in recent_text.split("\n") if l.strip()]
        
        # Count command occurrences
        command_freq = {}
        for line in lines:
            # Filter for shell-like commands (heuristic)
            if len(line) < 5 or len(line) > 100:
                continue
            if not re.match(r'^[a-z_\-/]+', line):
                continue
            
            command_freq[line] = command_freq.get(line, 0) + 1
        
        # Detect repeated commands (3+ occurrences)
        for cmd, count in command_freq.items():
            if count >= 3:
                pattern_id = f"cmd_{hash(cmd) % 10000:04d}"
                
                if pattern_id in self.patterns:
                    # Update existing
                    self.patterns[pattern_id].occurrences += count
                    self.patterns[pattern_id].last_seen = time.time()
                else:
                    # New pattern
                    patterns.append(ObservedPattern(
                        pattern_id=pattern_id,
                        category="command_alias",
                        description=f"Repeated command: {cmd}",
                        occurrences=count,
                        first_seen=time.time(),
                        last_seen=time.time(),
                        confidence=min(0.5 + (count * 0.1), 0.95),
                        context={"command": cmd},
                    ))
        
        return patterns
    
    def _detect_error_patterns(self) -> List[ObservedPattern]:
        """
        Detect error messages and subsequent fixes.
        
        Example: "ModuleNotFoundError" → "pip install requests"
        """
        if not self.deep_observer:
            return []
        
        patterns = []
        recent_text = self.deep_observer.get_recent_text(seconds=300)  # Last 5min
        
        # Common Python error patterns
        error_patterns = [
            (r"ModuleNotFoundError: No module named '(\w+)'", "missing_module"),
            (r"ImportError: cannot import name '(\w+)'", "import_error"),
            (r"SyntaxError:", "syntax_error"),
            (r"IndentationError:", "indentation_error"),
        ]
        
        for regex, error_type in error_patterns:
            matches = re.findall(regex, recent_text)
            if matches:
                for match in matches:
                    pattern_id = f"err_{error_type}_{hash(match if isinstance(match, str) else str(match)) % 10000:04d}"
                    
                    patterns.append(ObservedPattern(
                        pattern_id=pattern_id,
                        category="error_fix",
                        description=f"Error detected: {error_type}",
                        occurrences=1,
                        first_seen=time.time(),
                        last_seen=time.time(),
                        confidence=0.85,  # High confidence for known errors
                        context={
                            "error_type": error_type,
                            "match": match if isinstance(match, str) else str(match),
                        },
                    ))
        
        return patterns
    
    def _detect_workflow_patterns(self) -> List[ObservedPattern]:
        """
        Detect app switching patterns.
        
        Example: Terminal → Browser → VS Code (10x in 1 hour)
        """
        if not self.passive_observer:
            return []
        
        patterns = []
        
        # Get recent activity
        recent_activity = passive.load_recent_activity(hours=1)
        if len(recent_activity) < 5:
            return patterns
        
        # Extract app sequence
        app_sequence = [entry.get("app", "") for entry in recent_activity]
        
        # Detect repeated sequences
        # (Simplified: look for common 3-app sequences)
        for i in range(len(app_sequence) - 2):
            sequence = tuple(app_sequence[i:i+3])
            
            # Count occurrences of this sequence
            count = sum(1 for j in range(len(app_sequence) - 2) 
                       if tuple(app_sequence[j:j+3]) == sequence)
            
            if count >= 5:  # Repeated 5+ times in 1 hour
                pattern_id = f"wflow_{hash(sequence) % 10000:04d}"
                
                if pattern_id not in self.patterns:
                    patterns.append(ObservedPattern(
                        pattern_id=pattern_id,
                        category="workflow",
                        description=f"Frequent app sequence: {' → '.join(sequence)}",
                        occurrences=count,
                        first_seen=time.time(),
                        last_seen=time.time(),
                        confidence=0.6,  # Medium confidence
                        context={"sequence": list(sequence)},
                    ))
        
        return patterns
    
    def _generate_hypothesis(self, pattern: ObservedPattern) -> Optional[ImprovementHypothesis]:
        """
        Use Groq LLM to generate improvement hypothesis from pattern.
        
        Returns hypothesis or None if confidence too low.
        """
        # Build prompt
        prompt = f"""You are an AI assistant analyzing user behavior patterns.

Pattern detected:
- Category: {pattern.category}
- Description: {pattern.description}
- Occurrences: {pattern.occurrences}
- Frequency: {pattern.frequency_per_hour():.1f} times per hour
- Context: {json.dumps(pattern.context)}

Generate a SINGLE, SPECIFIC improvement suggestion.

Respond in JSON format:
{{
  "improvement": "Brief description of what to do",
  "category": "{pattern.category}",
  "confidence": 0.0-1.0 (how certain this is helpful),
  "impact": "low|medium|high",
  "risk": 0.0-1.0 (how risky this change is),
  "action": {{
    "type": "shell_alias|vscode_snippet|auto_install|workflow_template",
    "target_file": "/path/to/file",
    "code": "actual code to insert"
  }}
}}

Only suggest if confidence >= 0.5. Otherwise respond with {{"confidence": 0.0}}.
"""
        
        try:
            # Use Groq (free, fast) for hypothesis generation
            response = providers.generate_text(
                prompt=prompt,
                max_output_tokens=512,
                provider_override="groq",  # Force Groq for speed + cost
            )
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return None
            
            data = json.loads(json_match.group(0))
            
            # Check confidence threshold
            if data.get("confidence", 0) < self.info_session_threshold:
                return None
            
            # Create improvement proposal
            action = data.get("action", {})
            proposal = ImprovementProposal(
                proposal_id=f"prop_{int(time.time())}_{hash(pattern.pattern_id) % 1000:03d}",
                category=data.get("category", pattern.category),
                description=data.get("improvement", ""),
                action_type=action.get("type", "unknown"),
                target_file=action.get("target_file", ""),
                code=action.get("code", ""),
                confidence=data.get("confidence", 0.5),
                risk=data.get("risk", 0.5),
                created_at=time.time(),
            )
            
            # Create hypothesis
            hypothesis = ImprovementHypothesis(
                hypothesis_id=f"hyp_{int(time.time())}_{hash(pattern.pattern_id) % 1000:03d}",
                pattern_id=pattern.pattern_id,
                category=data.get("category", pattern.category),
                description=data.get("improvement", ""),
                confidence=data.get("confidence", 0.5),
                impact=data.get("impact", "low"),
                risk=data.get("risk", 0.5),
                proposal=proposal,
                created_at=time.time(),
                status="pending",
            )
            
            return hypothesis
            
        except Exception as e:
            print(f"Warning: Hypothesis generation failed: {e}")
            return None
    
    def _analyze_patterns(self):
        """
        Main analysis loop: detect patterns and generate hypotheses.
        """
        self.cycles_run += 1
        
        # 1. Detect patterns from all sources
        new_patterns = []
        new_patterns.extend(self._detect_command_patterns())
        new_patterns.extend(self._detect_error_patterns())
        new_patterns.extend(self._detect_workflow_patterns())
        
        # 2. Update pattern database
        with self._lock:
            for pattern in new_patterns:
                if pattern.pattern_id in self.patterns:
                   # Already exists, was updated in detection
                    self.patterns_detected += 1
                else:
                    # New pattern
                    self.patterns[pattern.pattern_id] = pattern
                    self.patterns_detected += 1
        
        # 3. Generate hypotheses for high-confidence patterns
        hypotheses_this_cycle = 0
        
        for pattern in sorted(
            self.patterns.values(),
            key=lambda p: p.confidence * p.frequency_per_hour(),
            reverse=True
        ):
            if hypotheses_this_cycle >= self.max_hypotheses_per_cycle:
                break
            
            # Skip if already have hypothesis for this pattern
            if any(h.pattern_id == pattern.pattern_id for h in self.hypotheses):
                continue
            
            # Generate hypothesis
            hypothesis = self._generate_hypothesis(pattern)
            if hypothesis:
                self.hypotheses.append(hypothesis)
                self._log_hypothesis(hypothesis)
                self.hypotheses_generated += 1
                hypotheses_this_cycle += 1
                
                # 4. Route based on confidence
                if hypothesis.confidence >= self.auto_execute_threshold:
                    # High confidence → Auto-execute via BackgroundImprover
                    success = self.improver.execute(hypothesis.proposal)
                    hypothesis.status = "executed" if success else "failed"
                    self.auto_executed += 1
                    self._log_hypothesis(hypothesis)
                    
                elif hypothesis.confidence >= self.info_session_threshold:
                    # Medium confidence → Queue for Information Session
                    hypothesis.status = "queued"
                    self.queued_for_review += 1
                    self._log_hypothesis(hypothesis)
                    
                else:
                    # Low confidence → Discard
                    hypothesis.status = "discarded"
                    self._log_hypothesis(hypothesis)
        
        # 5. Save patterns to disk
        self._save_patterns()
    
    def run(self):
        """Main daemon loop."""
        if not self.enabled:
            return
        
        # Get observer references
        self.deep_observer = observer.get_observer()
        # passive_observer is started by daemon.py, we just read its logs
        
        print(f"🔍 Observational Daemon started (analysis every {self.analysis_interval}s)")
        
        last_analysis = time.time()
        
        while not self._stop_event.is_set():
            try:
                now = time.time()
                
                # Run analysis every N seconds
                if now - last_analysis >= self.analysis_interval:
                    self._analyze_patterns()
                    last_analysis = now
                
                time.sleep(5)
                
            except Exception as e:
                print(f"Warning: Observational Daemon error: {e}")
                time.sleep(30)
        
        print("🔍 Observational Daemon stopped")
    
    def stop(self):
        """Stop the daemon."""
        self._stop_event.set()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get daemon statistics."""
        with self._lock:
            return {
                "cycles_run": self.cycles_run,
                "patterns_detected": self.patterns_detected,
                "active_patterns": len(self.patterns),
                "hypotheses_generated": self.hypotheses_generated,
                "auto_executed": self.auto_executed,
                "queued_for_review": self.queued_for_review,
                "recent_hypotheses": [
                    {
                        "id": h.hypothesis_id,
                        "category": h.category,
                        "confidence": h.confidence,
                        "status": h.status,
                    }
                    for h in list(self.hypotheses)[-10:]
                ],
            }
    
    def get_queued_improvements(self) -> List[ImprovementHypothesis]:
        """Get hypotheses queued for Information Session review."""
        with self._lock:
            return [h for h in self.hypotheses if h.status == "queued"]


# Global daemon instance
_daemon: Optional[ObservationalDaemon] = None


def start_daemon() -> ObservationalDaemon:
    """Start the global observational daemon."""
    global _daemon
    if _daemon is None or not _daemon.is_alive():
        _daemon = ObservationalDaemon()
        _daemon.start()
    return _daemon


def get_daemon() -> Optional[ObservationalDaemon]:
    """Get the global daemon instance."""
    return _daemon


def stop_daemon():
    """Stop the global daemon."""
    global _daemon
    if _daemon:
        _daemon.stop()
        _daemon = None
