"""
Iterative Improver for Jarvis.
Continuously learns, validates, and improves functions.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, providers, evolution, guardian, learning_validator, ability_acquisition, error_recovery, safety

ROOT = Path(__file__).resolve().parents[1]
ITERATIVE_PATH = ROOT / "data" / "iterative_improvements"
ITERATION_LOG_PATH = ROOT / "data" / "iteration_log.json"


class IterativeImprover:
    """Manages iterative improvement cycles with enhanced validation."""
    
    def __init__(self):
        self.validator = learning_validator.get_learning_validator()
        self.ability_acquisition = ability_acquisition.get_ability_acquisition()
        self.error_manager = error_recovery.get_error_manager()
        self.iteration_db = ITERATIVE_PATH / "iterations.json"
        self._ensure_directories()
        self._load_iterations()
        
        # Validation thresholds
        self.min_success_rate = 0.8  # 80% success rate required
        self.min_test_coverage = 0.7  # 70% test coverage required
        self.max_regression_risk = 0.2  # 20% max regression risk

        # Circuit breaker for circular improvements
        self.cooldown_until = self.iterations.get("cooldown_until", 0)
        self.cooldown_duration_seconds = 300  # 5 minute cooldown after circular detection
        
    def _ensure_directories(self):
        """Ensure data directories exist."""
        ITERATIVE_PATH.mkdir(parents=True, exist_ok=True)
        
    def _load_iterations(self):
        """Load iteration history."""
        if self.iteration_db.exists():
            with open(self.iteration_db, "r") as f:
                self.iterations = json.load(f)
        else:
            self.iterations = {
                "cycles": [],
                "improvements_applied": [],
                "functions_improved": {},
                "learning_progress": [],
                "validation_failures": [],
                "regression_tests": []
            }
    
    def _save_iterations(self):
        """Save iteration data."""
        with open(self.iteration_db, "w") as f:
            json.dump(self.iterations, f, indent=2)
    
    def _log_iteration(self, cycle_type: str, details: Dict[str, Any]):
        """Log iteration activity."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "cycle_type": cycle_type,
            "details": details
        }
        
        with open(ITERATION_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def analyze_performance_gaps(self) -> List[Dict[str, Any]]:
        """Analyze current system for performance gaps with enhanced metrics."""
        gaps = []
        
        try:
            # Get validation summary
            validation_summary = self.validator.get_validation_summary()
            
            # Identify areas needing improvement
            if validation_summary["metrics"]["test_success_rate"] < self.min_success_rate:
                gaps.append({
                    "type": "test_coverage",
                    "severity": "high",
                    "description": "Low test success rate",
                    "current_rate": validation_summary["metrics"]["test_success_rate"],
                    "target_rate": self.min_success_rate
                })
            
            if validation_summary["metrics"]["backtest_success_rate"] < self.min_success_rate:
                gaps.append({
                    "type": "backtest_reliability",
                    "severity": "medium",
                    "description": "Backtest failures detected",
                    "current_rate": validation_summary["metrics"]["backtest_success_rate"],
                    "target_rate": self.min_success_rate
                })
            
            # Check ability acquisition
            ability_status = self.ability_acquisition.get_status()
            if ability_status["total_abilities"] < 10:
                gaps.append({
                    "type": "ability_acquisition",
                    "severity": "medium",
                    "description": "Need more acquired abilities",
                    "current_count": ability_status["total_abilities"],
                    "target_count": 20
                })
            
            # Analyze recent failures
            recent_failures = self.validator.validations["failed_validations"][-5:]
            if recent_failures:
                gaps.append({
                    "type": "recent_failures",
                    "severity": "high",
                    "description": "Recent validation failures",
                    "failures": recent_failures
                })
            
            # Check error patterns
            error_stats = self.error_manager.get_error_stats()
            if error_stats.get("resolution_rate", 1.0) < 0.8:
                gaps.append({
                    "type": "error_recovery",
                    "severity": "high",
                    "description": "Low error recovery rate",
                    "current_rate": error_stats.get("resolution_rate", 0),
                    "target_rate": 0.8
                })
            
            # Check for circular logic patterns
            if len(self.iterations.get("validation_failures", [])) > 5:
                gaps.append({
                    "type": "circular_improvement",
                    "severity": "medium",
                    "description": "Too many validation failures - possible circular logic",
                    "failure_count": len(self.iterations.get("validation_failures", []))
                })
                
        except Exception as e:
            self.error_manager.handle_error(e, {"function": "analyze_performance_gaps"})
            
        return gaps
    
    def validate_improvement_safety(self, proposal: evolution.ImprovementProposal) -> tuple[bool, str]:
        """Validate that an improvement is safe to apply."""
        try:
            # Check for risky patterns
            risky_keywords = ["import os", "subprocess", "exec(", "eval(", "rm -rf", "sudo"]
            code_snippet = (proposal.code_snippet or "").lower()

            if code_snippet:
                for keyword in risky_keywords:
                    if keyword in code_snippet:
                        return False, f"Risky keyword detected: {keyword}"
            
            # Check if modification targets critical files
            critical_files = ["core/autonomous_controller.py", "core/jarvis.py", "core/daemon.py"]
            for file_path in proposal.files_to_modify:
                if file_path in critical_files:
                    if proposal.confidence < 0.9:
                        return False, f"Low confidence for critical file: {file_path}"
            
            # Check regression risk
            if proposal.confidence < 0.7:
                return False, f"Low confidence score: {proposal.confidence}"
            
            # Check for circular improvement patterns
            if "improvement" in proposal.title.lower() and len(self.iterations.get("validation_failures", [])) > 3:
                return False, "Possible circular improvement pattern detected"
            
            return True, "Improvement appears safe"
            
        except Exception as e:
            self.error_manager.handle_error(e, {"function": "validate_improvement_safety"})
            return False, f"Validation error: {str(e)}"

    def generate_improvement_plan(self, gaps: List[Dict[str, Any]]) -> List[evolution.ImprovementProposal]:
        """Generate lightweight improvement proposals based on identified gaps."""
        proposals: List[evolution.ImprovementProposal] = []
        max_proposals_per_cycle = 3  # Hard limit to prevent runaway improvements

        for gap in gaps:
            # Hard limit on proposals per cycle
            if len(proposals) >= max_proposals_per_cycle:
                break

            severity = gap.get("severity", "medium")
            priority = 0.8 if severity == "high" else 0.6 if severity == "medium" else 0.4
            confidence = 0.8 if severity == "high" else 0.6 if severity == "medium" else 0.5
            gap_type = gap.get("type", "general")

            if gap_type == "test_coverage":
                proposals.append(evolution.ImprovementProposal(
                    category="behavior",
                    title="Increase test coverage",
                    description=(
                        f"Raise test success rate from {gap.get('current_rate', 0):.2f} "
                        f"toward {gap.get('target_rate', 0):.2f} by adding targeted tests."
                    ),
                    rationale="Validation metrics are below target.",
                    priority=priority,
                    confidence=confidence,
                    source="iterative_improver",
                ))
            elif gap_type == "backtest_reliability":
                proposals.append(evolution.ImprovementProposal(
                    category="behavior",
                    title="Stabilize backtests",
                    description="Reduce backtest flakiness with smaller test scopes and clearer success criteria.",
                    rationale="Backtest failures reduce confidence in improvements.",
                    priority=priority,
                    confidence=confidence,
                    source="iterative_improver",
                ))
            elif gap_type == "ability_acquisition":
                proposals.append(evolution.ImprovementProposal(
                    category="behavior",
                    title="Boost ability acquisition cadence",
                    description="Prioritize lightweight abilities and shorten acquisition cycles until targets are met.",
                    rationale="Ability count below target.",
                    priority=priority,
                    confidence=confidence,
                    source="iterative_improver",
                ))
            elif gap_type == "recent_failures":
                proposals.append(evolution.ImprovementProposal(
                    category="behavior",
                    title="Mitigate recent validation failures",
                    description="Address recurring validation failures with targeted checks and smaller changes.",
                    rationale="Recent validation failures indicate fragile improvements.",
                    priority=priority,
                    confidence=confidence,
                    source="iterative_improver",
                ))
            elif gap_type == "error_recovery":
                proposals.append(evolution.ImprovementProposal(
                    category="behavior",
                    title="Improve error recovery",
                    description="Add clearer error categorization and recovery playbooks for repeat failures.",
                    rationale="Low resolution rate in error recovery.",
                    priority=priority,
                    confidence=confidence,
                    source="iterative_improver",
                ))
            elif gap_type == "circular_improvement":
                # DO NOT generate an improvement proposal for circular improvement!
                # This would create a meta-circular loop. Instead, take corrective action:
                # 1. Clear old validation failures (keep only last 3)
                # 2. Set cooldown timer
                # 3. Skip generating a proposal
                old_failures = self.iterations.get("validation_failures", [])
                if len(old_failures) > 3:
                    self.iterations["validation_failures"] = old_failures[-3:]

                # Set cooldown to prevent rapid re-attempts
                self.cooldown_until = time.time() + self.cooldown_duration_seconds
                self.iterations["cooldown_until"] = self.cooldown_until
                self._save_iterations()

                self._log_iteration("circular_cooldown", {
                    "action": "Entered cooldown mode - blocking improvements for 5 minutes",
                    "cooldown_until": self.cooldown_until,
                    "failures_cleared": len(old_failures) - 3 if len(old_failures) > 3 else 0,
                })
                # Don't add any proposal - continue to next gap
                continue
            else:
                proposals.append(evolution.ImprovementProposal(
                    category="behavior",
                    title="General improvement hygiene",
                    description=f"Address gap type: {gap_type}",
                    rationale="Unknown gap type reported.",
                    priority=priority,
                    confidence=confidence,
                    source="iterative_improver",
                ))

        return proposals
    
    def run_improvement_cycle(self) -> Dict[str, Any]:
        """Run a complete improvement cycle with validation."""
        cycle_start = time.time()

        # Check cooldown - don't run if we recently hit circular improvement
        if time.time() < self.cooldown_until:
            remaining = int(self.cooldown_until - time.time())
            return {
                "success": False,
                "message": f"In cooldown mode - {remaining}s remaining (circular improvement detected)",
                "gaps_found": 0,
                "improvements_applied": [],
                "improvements_validated": 0,
                "improvements_failed": 0,
                "cooldown_remaining": remaining,
            }

        try:
            # Analyze performance gaps
            gaps = self.analyze_performance_gaps()
            
            if not gaps:
                return {
                    "success": True,
                    "message": "No performance gaps detected",
                    "gaps_found": 0,
                    "improvements_applied": [],
                    "improvements_validated": 0,
                    "improvements_failed": 0
                }
            
            # Generate improvement proposals
            proposals = self.generate_improvement_plan(gaps)
            
            # Validate proposals for safety
            safe_proposals = []
            for proposal in proposals:
                is_safe, reason = self.validate_improvement_safety(proposal)
                if is_safe:
                    safe_proposals.append(proposal)
                else:
                    self.iterations["validation_failures"].append({
                        "timestamp": time.time(),
                        "proposal": proposal.title,
                        "reason": reason
                    })
            
            # Apply safe improvements
            improvements_applied = []
            improvements_validated = 0
            improvements_failed = 0
            for proposal in safe_proposals:
                try:
                    code_present = bool(proposal.code_snippet)
                    if code_present:
                        backtest_result = self.validator.backtest_improvement(proposal)
                        if not backtest_result.get("validation_passed"):
                            improvements_failed += 1
                            self.iterations["validation_failures"].append({
                                "timestamp": time.time(),
                                "proposal": proposal.title,
                                "reason": f"Backtest failed: {backtest_result.get('error', 'Unknown')}"
                            })
                            continue
                        improvements_validated += 1

                    # Apply the improvement
                    result = evolution.apply_improvement(
                        proposal,
                        safety.SafetyContext(apply=True, dry_run=False),
                    )
                    status = result.get("status")
                    if status in ("applied", "saved"):
                        improvements_applied.append({
                            "title": proposal.title,
                            "category": proposal.category,
                            "status": status,
                            "files_to_modify": proposal.files_to_modify,
                            "source": proposal.source,
                        })
                        # Record successful application
                        self.iterations["improvements_applied"].append({
                            "timestamp": time.time(),
                            "proposal": proposal.title,
                            "confidence": proposal.confidence,
                            "status": status,
                        })
                    else:
                        improvements_failed += 1
                        self.iterations["validation_failures"].append({
                            "timestamp": time.time(),
                            "proposal": proposal.title,
                            "reason": result.get("message", "Apply failed"),
                        })
                        
                except Exception as e:
                    self.error_manager.handle_error(e, {"function": "run_improvement_cycle", "proposal": proposal.title})
                    improvements_failed += 1
                    self.iterations["validation_failures"].append({
                        "timestamp": time.time(),
                        "proposal": proposal.title,
                        "reason": f"Application error: {str(e)}"
                    })
            
            # Save iteration data
            self._save_iterations()
            
            # Log cycle completion
            cycle_duration = time.time() - cycle_start
            self._log_iteration("improvement_cycle", {
                "gaps_found": len(gaps),
                "proposals_generated": len(proposals),
                "safe_proposals": len(safe_proposals),
                "improvements_applied": len(improvements_applied),
                "improvements_validated": improvements_validated,
                "improvements_failed": improvements_failed,
                "duration": cycle_duration
            })
            
            return {
                "success": True,
                "gaps_found": len(gaps),
                "proposals_generated": len(proposals),
                "safe_proposals": len(safe_proposals),
                "improvements_applied": improvements_applied,
                "improvements_validated": improvements_validated,
                "improvements_failed": improvements_failed,
                "duration": cycle_duration
            }
            
        except Exception as e:
            self.error_manager.handle_error(e, {"function": "run_improvement_cycle"})
            return {
                "success": False,
                "error": str(e),
                "duration": time.time() - cycle_start
            }

    def run_learning_cycle(self) -> Dict[str, Any]:
        """Run a complete learning and improvement cycle."""
        cycle_start = datetime.now()
        cycle_id = len(self.iterations.get("cycles", [])) + 1

        self._log_iteration("cycle_started", {"cycle_id": cycle_id})

        improvement_result = self.run_improvement_cycle()
        insights = self._learn_from_cycle_results(improvement_result)

        cycle_result = {
            "cycle_id": cycle_id,
            "start_time": cycle_start.isoformat(),
            "end_time": datetime.now().isoformat(),
            "gaps_identified": improvement_result.get("gaps_found", 0),
            "proposals_generated": improvement_result.get("proposals_generated", 0),
            "improvements_applied": improvement_result.get("improvements_applied", []),
            "improvements_validated": improvement_result.get("improvements_validated", 0),
            "improvements_failed": improvement_result.get("improvements_failed", 0),
            "learning_insights": insights,
            "success": improvement_result.get("success", False),
        }

        self.iterations["cycles"].append(cycle_result)
        self._save_iterations()
        self._log_iteration("cycle_completed", cycle_result)

        return cycle_result

    def _learn_from_cycle_results(self, results: Dict[str, Any]) -> List[str]:
        """Extract lightweight insights from cycle results."""
        insights: List[str] = []
        validated = results.get("improvements_validated", 0)
        failed = results.get("improvements_failed", 0)
        applied = results.get("improvements_applied", [])

        if validated > failed:
            insights.append("Validation success rate is trending positive.")
        if failed > validated:
            insights.append("Validation failures outweigh successes; tighten proposal filters.")
        if not applied:
            insights.append("No improvements applied; revisit gap detection and proposal generation.")

        self.iterations["learning_progress"].append({
            "timestamp": datetime.now().isoformat(),
            "insights": insights,
            "success_rate": validated / max(len(applied), 1),
        })

        return insights
