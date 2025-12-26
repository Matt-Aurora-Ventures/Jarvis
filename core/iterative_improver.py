"""
Iterative Improver for Jarvis.
Continuously learns, validates, and improves functions.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, providers, evolution, guardian, learning_validator, ability_acquisition, error_recovery

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
            code_snippet = proposal.code_snippet.lower()
            
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
    
    def run_improvement_cycle(self) -> Dict[str, Any]:
        """Run a complete improvement cycle with validation."""
        cycle_start = time.time()
        
        try:
            # Analyze performance gaps
            gaps = self.analyze_performance_gaps()
            
            if not gaps:
                return {
                    "success": True,
                    "message": "No performance gaps detected",
                    "gaps_found": 0
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
            for proposal in safe_proposals:
                try:
                    # Backtest the improvement
                    backtest_result = self.validator.backtest_improvement(proposal)
                    
                    if backtest_result["success"]:
                        # Apply the improvement
                        evolution.apply_improvement(proposal)
                        improvements_applied.append(proposal.title)
                        
                        # Record successful application
                        self.iterations["improvements_applied"].append({
                            "timestamp": time.time(),
                            "proposal": proposal.title,
                            "confidence": proposal.confidence
                        })
                    else:
                        # Record failed backtest
                        self.iterations["validation_failures"].append({
                            "timestamp": time.time(),
                            "proposal": proposal.title,
                            "reason": f"Backtest failed: {backtest_result.get('error', 'Unknown')}"
                        })
                        
                except Exception as e:
                    self.error_manager.handle_error(e, {"function": "run_improvement_cycle", "proposal": proposal.title})
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
                "duration": cycle_duration
            })
            
            return {
                "success": True,
                "gaps_found": len(gaps),
                "proposals_generated": len(proposals),
                "safe_proposals": len(safe_proposals),
                "improvements_applied": improvements_applied,
                "duration": cycle_duration
            }
            
        except Exception as e:
            self.error_manager.handle_error(e, {"function": "run_improvement_cycle"})
            return {
                "success": False,
                "error": str(e),
                "duration": time.time() - cycle_start
            }
