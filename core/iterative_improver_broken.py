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
        def generate_improvement_plan(self, gaps: List[Dict[str, Any]]) -> List[evolution.ImprovementProposal]:
        """Generate improvement proposals based on identified gaps."""
        proposals = []
        
        for gap in gaps:
            if gap["type"] == "test_coverage":
                proposals.append(evolution.ImprovementProposal(
                    title="Improve test coverage",
                    description=f"Increase test success rate from {gap['current_rate']:.2f} to {gap['target_rate']:.2f}",
                    code_snippet="""
# Enhanced testing framework
def run_comprehensive_tests():
    \"\"\"Run comprehensive tests with better coverage.\"\"\"
    import unittest
    import sys
    
    # Discover and run all tests
    loader = unittest.TestLoader()
    suite = loader.discover('data/tests', pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()
""",
                    files_to_modify=["core/actions.py"],
                    rationale="Better test coverage improves reliability",
                    confidence=0.8
                ))
            
            elif gap["type"] == "backtest_reliability":
                proposals.append(evolution.ImprovementProposal(
                    title="Enhance backtesting",
                    description="Improve backtest success rate and reliability",
                    code_snippet="""
# Robust backtesting with error handling
def robust_backtest(improvement):
    \"\"\"Run backtest with comprehensive error handling.\"\"\"
    try:
        # Pre-flight checks
        if not improvement.code_snippet.strip():
            return False, "Empty code snippet"
        
        # Execute with timeout
        import signal
        def timeout_handler(signum, frame):
            raise TimeoutError("Backtest timeout")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)  # 30 second timeout
        
        try:
            # Run actual backtest
            result = execute_backtest(improvement)
            signal.alarm(0)  # Cancel timeout
            return result
        except TimeoutError:
            signal.alarm(0)
            return False, "Backtest timed out"
        except Exception as e:
            signal.alarm(0)
            return False, str(e)
            
    except Exception as e:
        return False, f"Backtest setup error: {str(e)}"
""",
                    files_to_modify=["core/evolution.py"],
                    rationale="More robust backtesting reduces failures",
                    confidence=0.75
                ))
            
            elif gap["type"] == "ability_acquisition":
                proposals.append(evolution.ImprovementProposal(
                    title="Enhance ability discovery",
                    description="Improve discovery and acquisition of new abilities",
                    code_snippet="""
# Enhanced ability discovery
def discover_more_abilities():
    \"\"\"Discover more open-source abilities.\"\"\"
    sources = [
        "github trending AI projects",
        "huggingface new models",
        "arxiv latest AI papers",
        "reddit machine learning",
        "hacker news AI"
    ]
    
    discovered = []
    for source in sources:
        try:
            results = search_source(source)
            discovered.extend(results)
        except Exception as e:
            log_error(f"Failed to search {source}: {e}")
    
    return discovered
""",
                    files_to_modify=["core/ability_acquisition.py"],
                    rationale="More sources increase ability discovery",
                    confidence=0.7
                ))
            
            elif gap["type"] == "error_recovery":
                proposals.append(evolution.ImprovementProposal(
                    title="Improve error recovery",
                    description="Enhance error handling and recovery mechanisms",
                    code_snippet="""
# Enhanced error recovery
def enhanced_error_recovery(error, context):
    \"\"\"Enhanced error recovery with multiple strategies.\"\"\"
    from core.error_recovery import get_error_manager
    
    manager = get_error_manager()
    
    # Try multiple recovery strategies
    strategies = [
        restart_mcp_servers,
        clear_cache,
        reset_config,
        retry_with_backoff
    ]
    
    for strategy in strategies:
        try:
            if strategy(error, context):
                return True
        except Exception:
            continue
    
    return False
""",
                    files_to_modify=["core/error_recovery.py"],
                    rationale="Better error recovery improves system stability",
                    confidence=0.85
                ))
        
        return proposals
    
    discoveries = []
    for source in sources:
        results = research_web(source, max_results=10)
        discoveries.extend(results)
    
    return discoveries
""",
                    files_to_modify=["core/ability_acquisition.py"],
                    rationale="More sources = more abilities",
                    confidence=0.7
                ))
        
        return proposals
    
    def apply_and_validate_improvements(self, proposals: List[evolution.ImprovementProposal]) -> Dict[str, Any]:
        """Apply improvements and validate them."""
        results = {
            "applied": 0,
            "validated": 0,
            "failed": 0,
            "details": []
        }
        
        for proposal in proposals:
            # Apply improvement
            apply_result = evolution.apply_improvement(proposal, dry_run=False)
            
            if apply_result["success"]:
                results["applied"] += 1
                
                # Validate the improvement
                if "function" in proposal.title.lower():
                    # Extract function name for validation
                    function_name = proposal.title.split()[-1].lower()
                    validation_result = self.validator.validate_new_function(
                        function_name, 
                        proposal.code_snippet
                    )
                    
                    if validation_result["overall_status"] == "passed":
                        results["validated"] += 1
                    else:
                        results["failed"] += 1
                    
                    results["details"].append({
                        "proposal": proposal.title,
                        "applied": True,
                        "validated": validation_result["overall_status"] == "passed",
                        "validation": validation_result
                    })
                else:
                    results["validated"] += 1
                    results["details"].append({
                        "proposal": proposal.title,
                        "applied": True,
                        "validated": True
                    })
            else:
                results["failed"] += 1
                results["details"].append({
                    "proposal": proposal.title,
                    "applied": False,
                    "error": apply_result.get("error", "Unknown error")
                })
        
        return results
    
    def run_learning_cycle(self) -> Dict[str, Any]:
        """Run a complete learning and improvement cycle."""
        cycle_start = datetime.now()
        
        self._log_iteration("cycle_started", {
            "cycle_id": len(self.iterations["cycles"]) + 1
        })
        
        # Step 1: Analyze performance gaps
        gaps = self.analyze_performance_gaps()
        
        # Step 2: Generate improvement plan
        proposals = self.generate_improvement_plan(gaps)
        
        # Step 3: Apply and validate improvements
        improvement_results = self.apply_and_validate_improvements(proposals)
        
        # Step 4: Learn from results
        learning_insights = self._learn_from_cycle_results(improvement_results)
        
        # Step 5: Update metrics
        metrics = self.validator.calculate_metrics()
        
        cycle_result = {
            "cycle_id": len(self.iterations["cycles"]) + 1,
            "start_time": cycle_start.isoformat(),
            "end_time": datetime.now().isoformat(),
            "gaps_identified": len(gaps),
            "proposals_generated": len(proposals),
            "improvements_applied": improvement_results["applied"],
            "improvements_validated": improvement_results["validated"],
            "improvements_failed": improvement_results["failed"],
            "learning_insights": learning_insights,
            "updated_metrics": metrics
        }
        
        # Store cycle results
        self.iterations["cycles"].append(cycle_result)
        self._save_iterations()
        
        self._log_iteration("cycle_completed", cycle_result)
        
        return cycle_result
    
    def _learn_from_cycle_results(self, results: Dict[str, Any]) -> List[str]:
        """Extract learning insights from cycle results."""
        insights = []
        
        if results["validated"] > results["failed"]:
            insights.append("Improvement validation success rate is good")
        
        if results["applied"] == 0:
            insights.append("No improvements were applied - check improvement generation")
        
        if results["failed"] > results["validated"]:
            insights.append("High failure rate - need better pre-validation")
        
        # Store learning progress
        self.iterations["learning_progress"].append({
            "timestamp": datetime.now().isoformat(),
            "insights": insights,
            "success_rate": results["validated"] / max(results["applied"], 1)
        })
        
        return insights
    
    def get_improvement_history(self) -> Dict[str, Any]:
        """Get history of improvements."""
        return {
            "total_cycles": len(self.iterations["cycles"]),
            "total_improvements": len(self.iterations["improvements_applied"]),
            "functions_improved": list(self.iterations["functions_improved"].keys()),
            "recent_cycles": self.iterations["cycles"][-5:],
            "learning_progress": self.iterations["learning_progress"][-10:]
        }


# Global iterative improver instance
_improver: Optional[IterativeImprover] = None


def get_iterative_improver() -> IterativeImprover:
    """Get the global iterative improver instance."""
    global _improver
    if not _improver:
        _improver = IterativeImprover()
    return _improver
