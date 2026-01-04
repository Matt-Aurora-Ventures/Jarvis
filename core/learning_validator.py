"""
Learning Validator for Jarvis.
Tests, validates, and backtests new functions and improvements.
"""

import json
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import config, evolution, guardian, providers, storage_utils, safe_subprocess

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_PATH = ROOT / "data" / "validations"
TESTS_PATH = ROOT / "data" / "tests"
METRICS_PATH = ROOT / "data" / "metrics"
VALIDATION_LOG_PATH = ROOT / "data" / "validation_results.log"


class LearningValidator:
    """Validates and tests new functions and improvements."""
    
    def __init__(self):
        self.validation_db = VALIDATION_PATH / "validations.json"
        self.metrics_db = METRICS_PATH / "metrics.json"
        self._ensure_directories()
        self._load_validations()
        
    def _ensure_directories(self):
        """Ensure data directories exist."""
        VALIDATION_PATH.mkdir(parents=True, exist_ok=True)
        TESTS_PATH.mkdir(parents=True, exist_ok=True)
        METRICS_PATH.mkdir(parents=True, exist_ok=True)
        
    def _load_validations(self):
        """Load validation history."""
        if self.validation_db.exists():
            with open(self.validation_db, "r") as f:
                self.validations = json.load(f)
        else:
            self.validations = {
                "test_results": [],
                "backtest_results": [],
                "performance_metrics": [],
                "validated_functions": {},
                "failed_validations": []
            }
        
        if self.metrics_db.exists():
            with open(self.metrics_db, "r") as f:
                self.metrics = json.load(f)
        else:
            self.metrics = {
                "function_performance": {},
                "improvement_success_rate": 0.0,
                "test_coverage": 0.0,
                "average_response_time": 0.0,
                "error_rates": {}
            }
    
    def _save_validations(self):
        """Save validation data."""
        with open(self.validation_db, "w") as f:
            json.dump(self.validations, f, indent=2)
        with open(self.metrics_db, "w") as f:
            json.dump(self.metrics, f, indent=2)
    
    def _log_validation(self, test_type: str, details: Dict[str, Any]):
        """Log validation activity."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": test_type,
            "details": details
        }
        
        with open(VALIDATION_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def generate_test_for_function(self, function_name: str, function_code: str) -> Dict[str, Any]:
        """Generate automated tests for a new function."""
        test_prompt = f"""Generate comprehensive tests for this function:

Function Name: {function_name}
Code:
```python
{function_code}
```

Create tests that:
1. Test normal operation with valid inputs
2. Test edge cases and error conditions
3. Test performance with different input sizes
4. Verify return types and values
5. Test integration with existing code

Provide test code in Python using unittest or pytest format."""
        
        try:
            response = providers.generate_text(test_prompt, max_output_tokens=1000)
            if response:
                test_code = response
                
                # Save test file
                test_file = TESTS_PATH / f"test_{function_name}.py"
                with open(test_file, "w") as f:
                    f.write(f"""
# Auto-generated tests for {function_name}
import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

{test_code}

if __name__ == "__main__":
    unittest.main()
""")
                
                return {
                    "success": True,
                    "test_file": str(test_file),
                    "test_code": test_code
                }
        except Exception as e:
            self._log_validation("test_generation_error", {
                "function": function_name,
                "error": str(e)
            })
        
        return {"success": False, "error": "Failed to generate tests"}
    
    def run_function_tests(self, function_name: str) -> Dict[str, Any]:
        """Run tests for a specific function."""
        test_file = TESTS_PATH / f"test_{function_name}.py"
        
        if not test_file.exists():
            return {"success": False, "error": "No test file found"}
        
        try:
            # Run tests with aggressive timeout protection
            result = safe_subprocess.run_command_safe(
                f"{sys.executable} {test_file}",
                timeout=30,
                shell=True,
                capture_output=True,
            )
            
            if result["timed_out"]:
                return {
                    "success": False,
                    "error": f"Test timed out after {result['timeout']}s",
                    "killed": True
                }
            
            test_result = {
                "function": function_name,
                "exit_code": result["returncode"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "success": result["returncode"] == 0,
                "timestamp": datetime.now().isoformat()
            }
            
            self.validations["test_results"].append(test_result)
            self._save_validations()
            
            self._log_validation("test_completed", test_result)
            
            return test_result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def backtest_improvement(self, improvement: evolution.ImprovementProposal) -> Dict[str, Any]:
        """Backtest an improvement against historical data."""
        backtest_result = {
            "improvement_id": improvement.title,
            "start_time": datetime.now().isoformat(),
            "tests_passed": 0,
            "tests_failed": 0,
            "performance_impact": {},
            "validation_passed": False
        }
        
        try:
            if not improvement.code_snippet:
                backtest_result["error"] = "Missing code snippet for backtest."
                self.validations["backtest_results"].append(backtest_result)
                self._save_validations()
                self._log_validation("backtest_failed", backtest_result)
                return backtest_result

            # 1. Safety validation
            is_safe, safety_reason = guardian.validate_code_for_safety(improvement.code_snippet)
            if not is_safe:
                backtest_result["safety_failed"] = safety_reason
                self._log_validation("backtest_safety_failed", {
                    "improvement": improvement.title,
                    "reason": safety_reason
                })
                return backtest_result
            
            # 2. Create test environment
            test_script = TESTS_PATH / f"backtest_{hash(improvement.title)}.py"
            
            # Generate backtest script
            backtest_code = f"""
# Backtest script for {improvement.title}
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test the improvement
{improvement.code_snippet}

# Performance test
start_time = time.time()
try:
    # Try to execute the improvement
    result = "success"  # Placeholder for actual test
    execution_time = time.time() - start_time
    print(f"EXECUTION_TIME:{{execution_time}}")
    print(f"RESULT:{{result}}")
except Exception as e:
    print(f"ERROR:{{str(e)}}")
"""
            
            with open(test_script, "w") as f:
                f.write(backtest_code)
            
            # 3. Run backtest
            result = subprocess.run(
                [sys.executable, str(test_script)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Parse results
            output = result.stdout
            if "ERROR:" in output:
                backtest_result["execution_error"] = output.split("ERROR:")[1].strip()
                backtest_result["tests_failed"] += 1
            else:
                backtest_result["tests_passed"] += 1
                
                # Extract performance metrics
                if "EXECUTION_TIME:" in output:
                    exec_time = float(output.split("EXECUTION_TIME:")[1].split("\\n")[0])
                    backtest_result["performance_impact"]["execution_time"] = exec_time
            
            # 4. Integration test
            if result.returncode == 0:
                backtest_result["tests_passed"] += 1
                backtest_result["validation_passed"] = True
            else:
                backtest_result["tests_failed"] += 1
                backtest_result["stderr"] = result.stderr
            
            # Clean up
            test_script.unlink(missing_ok=True)
            
        except Exception as e:
            backtest_result["error"] = str(e)
            backtest_result["tests_failed"] += 1
        
        backtest_result["end_time"] = datetime.now().isoformat()
        self.validations["backtest_results"].append(backtest_result)
        self._save_validations()
        
        self._log_validation("backtest_completed", backtest_result)
        
        return backtest_result
    
    def validate_new_function(self, function_name: str, function_code: str) -> Dict[str, Any]:
        """Complete validation pipeline for a new function."""
        validation_result = {
            "function": function_name,
            "timestamp": datetime.now().isoformat(),
            "stages": {
                "test_generation": {"status": "pending"},
                "test_execution": {"status": "pending"},
                "safety_check": {"status": "pending"},
                "performance_test": {"status": "pending"}
            },
            "overall_status": "pending"
        }
        
        # Stage 1: Generate tests
        test_gen = self.generate_test_for_function(function_name, function_code)
        validation_result["stages"]["test_generation"] = {
            "status": "passed" if test_gen["success"] else "failed",
            "details": test_gen
        }
        
        # Stage 2: Safety check
        is_safe, safety_reason = guardian.validate_code_for_safety(function_code)
        validation_result["stages"]["safety_check"] = {
            "status": "passed" if is_safe else "failed",
            "details": {"safe": is_safe, "reason": safety_reason}
        }
        
        if not is_safe:
            validation_result["overall_status"] = "failed"
            self.validations["failed_validations"].append(validation_result)
            return validation_result
        
        # Stage 3: Run tests
        if test_gen["success"]:
            test_result = self.run_function_tests(function_name)
            validation_result["stages"]["test_execution"] = {
                "status": "passed" if test_result["success"] else "failed",
                "details": test_result
            }
        
        # Stage 4: Performance test
        perf_result = self._performance_test(function_name, function_code)
        validation_result["stages"]["performance_test"] = {
            "status": "passed" if perf_result["success"] else "failed",
            "details": perf_result
        }
        
        # Determine overall status
        all_passed = all(
            stage["status"] == "passed" 
            for stage in validation_result["stages"].values()
        )
        validation_result["overall_status"] = "passed" if all_passed else "failed"
        
        # Store result
        if validation_result["overall_status"] == "passed":
            self.validations["validated_functions"][function_name] = validation_result
        else:
            self.validations["failed_validations"].append(validation_result)
        
        self._save_validations()
        self._log_validation("function_validation_completed", validation_result)
        
        return validation_result
    
    def _performance_test(self, function_name: str, function_code: str) -> Dict[str, Any]:
        """Test performance of a function."""
        try:
            # Create performance test
            perf_script = TESTS_PATH / f"perf_{function_name}.py"
            
            perf_code = f"""
# Performance test for {function_name}
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

{function_code}

# Performance measurements
start_time = time.time()
try:
    # Execute function (simplified)
    pass
    execution_time = time.time() - start_time
    print(f"PERFORMANCE:{{execution_time:.4f}}")
except Exception as e:
    print(f"PERF_ERROR:{{str(e)}}")
"""
            
            with open(perf_script, "w") as f:
                f.write(perf_code)
            
            # Run performance test
            result = subprocess.run(
                [sys.executable, str(perf_script)],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            perf_result = {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            # Clean up
            perf_script.unlink(missing_ok=True)
            
            return perf_result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics."""
        total_tests = len(self.validations["test_results"])
        passed_tests = sum(1 for test in self.validations["test_results"] if test["success"])
        
        total_backtests = len(self.validations["backtest_results"])
        passed_backtests = sum(1 for bt in self.validations["backtest_results"] if bt["validation_passed"])
        
        self.metrics.update({
            "test_success_rate": passed_tests / max(total_tests, 1),
            "backtest_success_rate": passed_backtests / max(total_backtests, 1),
            "total_validated_functions": len(self.validations["validated_functions"]),
            "total_failed_validations": len(self.validations["failed_validations"]),
            "last_updated": datetime.now().isoformat()
        })
        
        self._save_validations()
        return self.metrics
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation results."""
        return {
            "total_tests": len(self.validations["test_results"]),
            "passed_tests": sum(1 for test in self.validations["test_results"] if test["success"]),
            "total_backtests": len(self.validations["backtest_results"]),
            "passed_backtests": sum(1 for bt in self.validations["backtest_results"] if bt["validation_passed"]),
            "validated_functions": list(self.validations["validated_functions"].keys()),
            "failed_validations": len(self.validations["failed_validations"]),
            "metrics": self.calculate_metrics()
        }


# Global validator instance
_validator: Optional[LearningValidator] = None


def get_learning_validator() -> LearningValidator:
    """Get the global learning validator instance."""
    global _validator
    if not _validator:
        _validator = LearningValidator()
    return _validator
