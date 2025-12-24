"""
Comprehensive System Auditor for Jarvis.
Identifies errors, fixes issues, and improves error handling.
"""

import json
import traceback
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import storage_utils

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "data" / "system_audit"


class SystemAuditor:
    """Comprehensive system auditor and error fixer."""
    
    def __init__(self):
        self.storage = storage_utils.get_storage(AUDIT_PATH)
        self.issues_found = []
        self.issues_fixed = []
        self.audit_start = datetime.now()
    
    def audit_entire_system(self) -> Dict[str, Any]:
        """Perform comprehensive system audit."""
        audit_results = {
            "start_time": self.audit_start.isoformat(),
            "status": "in_progress",
            "issues_found": [],
            "issues_fixed": [],
            "recommendations": [],
            "health_score": 0
        }
        
        try:
            # 1. Audit core modules
            core_issues = self.audit_core_modules()
            audit_results["issues_found"].extend(core_issues)
            
            # 2. Audit storage system
            storage_issues = self.audit_storage_system()
            audit_results["issues_found"].extend(storage_issues)
            
            # 3. Audit error handling
            error_handling_issues = self.audit_error_handling()
            audit_results["issues_found"].extend(error_handling_issues)
            
            # 4. Audit imports and dependencies
            import_issues = self.audit_imports()
            audit_results["issues_found"].extend(import_issues)
            
            # 5. Fix identified issues
            fixed_count = self.fix_issues(audit_results["issues_found"])
            audit_results["issues_fixed"] = self.issues_fixed
            
            # 6. Calculate health score
            audit_results["health_score"] = self.calculate_health_score(audit_results)
            
            # 7. Generate recommendations
            audit_results["recommendations"] = self.generate_recommendations(audit_results)
            
            audit_results["status"] = "completed"
            
        except Exception as e:
            audit_results["status"] = "failed"
            audit_results["error"] = str(e)
            traceback.print_exc()
        
        audit_results["end_time"] = datetime.now().isoformat()
        
        # Save audit results
        self.storage.save_txt("system_audit", audit_results)
        
        return audit_results
    
    def audit_core_modules(self) -> List[Dict[str, Any]]:
        """Audit all core modules for issues."""
        issues = []
        core_dir = ROOT / "core"
        
        for py_file in core_dir.glob("*.py"):
            try:
                file_issues = self.analyze_python_file(py_file)
                issues.extend(file_issues)
            except Exception as e:
                issues.append({
                    "type": "file_analysis_error",
                    "file": str(py_file),
                    "severity": "medium",
                    "description": f"Failed to analyze file: {e}",
                    "fixable": False
                })
        
        return issues
    
    def analyze_python_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Analyze a Python file for common issues."""
        issues = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Check for common issues
            for i, line in enumerate(lines, 1):
                line_stripped = line.strip()
                
                # 1. Bare except clauses
                if "except:" in line and "except Exception" not in line:
                    issues.append({
                        "type": "bare_except",
                        "file": str(file_path),
                        "line": i,
                        "severity": "medium",
                        "description": "Bare except clause - should specify exception type",
                        "fixable": True,
                        "code": line_stripped
                    })
                
                # 2. Missing error messages
                if "except Exception" in line and "as e" not in line:
                    issues.append({
                        "type": "missing_error_variable",
                        "file": str(file_path),
                        "line": i,
                        "severity": "low",
                        "description": "Exception caught but not stored in variable",
                        "fixable": True,
                        "code": line_stripped
                    })
                
                # 3. Silent failures (return False/None without logging)
                if "return False" in line or "return None" in line:
                    # Check if this is in an except block
                    if i > 1 and "except" in lines[i-2:i]:
                        issues.append({
                            "type": "silent_failure",
                            "file": str(file_path),
                            "line": i,
                            "severity": "medium",
                            "description": "Silent failure - should log error before returning",
                            "fixable": True,
                            "code": line_stripped
                        })
                
                # 4. TODO comments (technical debt)
                if "# TODO" in line.upper() or "# FIXME" in line.upper():
                    issues.append({
                        "type": "technical_debt",
                        "file": str(file_path),
                        "line": i,
                        "severity": "low",
                        "description": "Technical debt marker found",
                        "fixable": False,
                        "code": line_stripped
                    })
        
        except Exception as e:
            issues.append({
                "type": "file_read_error",
                "file": str(file_path),
                "severity": "high",
                "description": f"Could not read file: {e}",
                "fixable": False
            })
        
        return issues
    
    def audit_storage_system(self) -> List[Dict[str, Any]]:
        """Audit storage system for issues."""
        issues = []
        
        try:
            # Test storage utilities
            storage_dir = ROOT / "data" / "test_storage"
            storage = storage_utils.get_storage(storage_dir)
            
            # Test save/load
            test_data = {"test": "data", "timestamp": time.time()}
            
            if not storage.save_txt("test_file", test_data):
                issues.append({
                    "type": "storage_save_error",
                    "severity": "high",
                    "description": "Storage save operation failed",
                    "fixable": True
                })
            
            loaded_data = storage.load_txt("test_file", "dict")
            if loaded_data is None:
                issues.append({
                    "type": "storage_load_error",
                    "severity": "high",
                    "description": "Storage load operation failed",
                    "fixable": True
                })
            
            # Clean up
            storage.clear_file("test_file")
            
        except Exception as e:
            issues.append({
                "type": "storage_audit_error",
                "severity": "medium",
                "description": f"Storage audit failed: {e}",
                "fixable": False
            })
        
        return issues
    
    def audit_error_handling(self) -> List[Dict[str, Any]]:
        """Audit error handling patterns."""
        issues = []
        
        # Check for modules that need better error handling
        modules_to_check = [
            "providers.py",
            "autonomous_agent.py", 
            "self_healing.py",
            "profile_analyzer.py"
        ]
        
        for module in modules_to_check:
            module_path = ROOT / "core" / module
            if module_path.exists():
                try:
                    content = module_path.read_text(encoding='utf-8')
                    
                    # Count error handling patterns
                    except_count = content.count("except")
                    error_var_count = content.count("as e")
                    silent_failures = content.count("return False") + content.count("return None")
                    
                    if except_count > error_var_count:
                        issues.append({
                            "type": "inconsistent_error_handling",
                            "file": str(module_path),
                            "severity": "medium",
                            "description": f"Module has {except_count} except blocks but only {error_var_count} store exceptions",
                            "fixable": True
                        })
                    
                    if silent_failures > 5:
                        issues.append({
                            "type": "excessive_silent_failures",
                            "file": str(module_path),
                            "severity": "medium", 
                            "description": f"Module has {silent_failures} silent failure patterns",
                            "fixable": True
                        })
                
                except Exception as e:
                    issues.append({
                        "type": "error_handling_audit_error",
                        "file": str(module_path),
                        "severity": "low",
                        "description": f"Could not audit error handling: {e}",
                        "fixable": False
                    })
        
        return issues
    
    def audit_imports(self) -> List[Dict[str, Any]]:
        """Audit import statements and dependencies."""
        issues = []
        
        try:
            core_dir = ROOT / "core"
            
            for py_file in core_dir.glob("*.py"):
                try:
                    content = py_file.read_text(encoding='utf-8')
                    lines = content.split('\n')
                    
                    for i, line in enumerate(lines, 1):
                        if line.strip().startswith("import ") or line.strip().startswith("from "):
                            # Check for relative imports that might fail
                            if "from core" in line and py_file.name != "__init__.py":
                                issues.append({
                                    "type": "relative_import",
                                    "file": str(py_file),
                                    "line": i,
                                    "severity": "low",
                                    "description": "Relative import might cause issues",
                                    "fixable": False,
                                    "code": line.strip()
                                })
                
                except Exception:
                    continue
        
        except Exception as e:
            issues.append({
                "type": "import_audit_error",
                "severity": "medium",
                "description": f"Import audit failed: {e}",
                "fixable": False
            })
        
        return issues
    
    def fix_issues(self, issues: List[Dict[str, Any]]) -> int:
        """Fix fixable issues."""
        fixed_count = 0
        
        for issue in issues:
            if not issue.get("fixable", False):
                continue
            
            try:
                if issue["type"] == "bare_except":
                    if self.fix_bare_except(issue):
                        fixed_count += 1
                        self.issues_fixed.append(issue)
                
                elif issue["type"] == "missing_error_variable":
                    if self.fix_missing_error_variable(issue):
                        fixed_count += 1
                        self.issues_fixed.append(issue)
                
                elif issue["type"] == "silent_failure":
                    if self.fix_silent_failure(issue):
                        fixed_count += 1
                        self.issues_fixed.append(issue)
                
                elif issue["type"] == "storage_save_error":
                    if self.fix_storage_issues():
                        fixed_count += 1
                        self.issues_fixed.append(issue)
                
            except Exception as e:
                print(f"Failed to fix issue {issue['type']}: {e}")
        
        return fixed_count
    
    def fix_bare_except(self, issue: Dict[str, Any]) -> bool:
        """Fix bare except clause."""
        try:
            file_path = Path(issue["file"])
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Find and fix the bare except
            for i, line in enumerate(lines):
                if "except:" in line and "except Exception" not in line:
                    lines[i] = line.replace("except:", "except Exception as e:")
                    break
            
            file_path.write_text('\n'.join(lines), encoding='utf-8')
            return True
        
        except Exception:
            return False
    
    def fix_missing_error_variable(self, issue: Dict[str, Any]) -> bool:
        """Fix missing error variable in except clause."""
        try:
            file_path = Path(issue["file"])
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Find and fix the except clause
            for i, line in enumerate(lines):
                if "except Exception" in line and "as e" not in line:
                    lines[i] = line.replace("except Exception:", "except Exception as e:")
                    break
            
            file_path.write_text('\n'.join(lines), encoding='utf-8')
            return True
        
        except Exception:
            return False
    
    def fix_silent_failure(self, issue: Dict[str, Any]) -> bool:
        """Fix silent failure by adding logging."""
        try:
            file_path = Path(issue["file"])
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Find the return False/None in except block and add logging before it
            for i, line in enumerate(lines):
                if ("return False" in line or "return None" in line) and i > 0:
                    # Check if previous lines indicate except block
                    prev_lines = '\n'.join(lines[max(0, i-3):i])
                    if "except" in prev_lines:
                        # Insert logging before return
                        indent = len(line) - len(line.lstrip())
                        log_line = " " * indent + f'print(f"Operation failed: {{e}}")'
                        lines.insert(i, log_line)
                        break
            
            file_path.write_text('\n'.join(lines), encoding='utf-8')
            return True
        
        except Exception:
            return False
    
    def fix_storage_issues(self) -> bool:
        """Fix storage system issues."""
        try:
            # Test and fix storage utilities
            test_dir = ROOT / "data" / "test_fix"
            test_dir.mkdir(exist_ok=True)
            
            storage = storage_utils.get_storage(test_dir)
            
            # Test basic operations
            test_data = {"test": "fix", "timestamp": time.time()}
            storage.save_txt("test_fix", test_data)
            
            loaded = storage.load_txt("test_fix", "dict")
            if loaded and loaded.get("test") == "fix":
                storage.clear_file("test_fix")
                return True
            
            return False
        
        except Exception:
            return False
    
    def calculate_health_score(self, audit_results: Dict[str, Any]) -> int:
        """Calculate system health score (0-100)."""
        total_issues = len(audit_results["issues_found"])
        fixed_issues = len(audit_results["issues_fixed"])
        
        if total_issues == 0:
            return 100
        
        # Base score from fixed issues
        base_score = (fixed_issues / total_issues) * 100
        
        # Deduct points for high severity issues
        high_severity = len([i for i in audit_results["issues_found"] if i.get("severity") == "high"])
        base_score -= high_severity * 10
        
        # Ensure score doesn't go below 0
        return max(0, min(100, int(base_score)))
    
    def generate_recommendations(self, audit_results: Dict[str, Any]) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        # Analyze issue types
        issue_types = {}
        for issue in audit_results["issues_found"]:
            issue_type = issue["type"]
            issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
        
        # Generate recommendations based on common issues
        if issue_types.get("bare_except", 0) > 0:
            recommendations.append("Add specific exception types to all except clauses")
        
        if issue_types.get("silent_failure", 0) > 3:
            recommendations.append("Implement proper error logging instead of silent failures")
        
        if issue_types.get("technical_debt", 0) > 5:
            recommendations.append("Address technical debt markers (TODO/FIXME comments)")
        
        if audit_results["health_score"] < 70:
            recommendations.append("Focus on improving error handling and logging practices")
        
        if len(audit_results["issues_fixed"]) < len(audit_results["issues_found"]) / 2:
            recommendations.append("Manual intervention needed for non-fixable issues")
        
        return recommendations


# Global auditor instance
_auditor: Optional[SystemAuditor] = None


def get_system_auditor() -> SystemAuditor:
    """Get the global system auditor instance."""
    global _auditor
    if not _auditor:
        _auditor = SystemAuditor()
    return _auditor
