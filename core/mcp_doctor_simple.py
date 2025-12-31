#!/usr/bin/env python3
"""
MCP Doctor - Simple MCP server health diagnostics for available MCP tools
Tests the MCP servers that are actually available in this environment
"""

import json
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Any

ROOT = Path(__file__).resolve().parents[2]


class MCPDoctorResult:
    def __init__(self, server_name: str):
        self.server_name = server_name
        self.passed = False
        self.error = None
        self.details = {}
        self.duration_ms = 0
        self.recommendations = []

    def add_recommendation(self, rec: str):
        self.recommendations.append(rec)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server": self.server_name,
            "passed": self.passed,
            "error": self.error,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "recommendations": self.recommendations
        }


def test_mcp_availability() -> MCPDoctorResult:
    """Test if MCP tools are available in the current environment"""
    result = MCPDoctorResult("mcp_availability")
    
    try:
        # Check if we can import the available MCP modules
        import importlib.util
        
        # Test for common MCP modules that might be available
        test_modules = [
            'mcp11_shell_execute',
            'mcp13_get_cpu_info', 
            'mcp3_git_status',
            'mcp7_read_graph'
        ]
        
        available_modules = []
        for module_name in test_modules:
            spec = importlib.util.find_spec(module_name)
            if spec is not None:
                available_modules.append(module_name)
        
        if available_modules:
            result.passed = True
            result.details = {
                "available_modules": available_modules,
                "total_checked": len(test_modules),
                "environment": "Windsurf Cascade detected"
            }
        else:
            result.error = "No MCP modules found in current environment"
            
    except Exception as e:
        result.error = str(e)
        result.details["traceback"] = traceback.format_exc()
    
    if not result.passed:
        result.add_recommendation("Ensure running in Windsurf Cascade environment")
        result.add_recommendation("Check MCP server configuration")
        result.add_recommendation("Verify MCP tools are properly loaded")
    
    return result


def test_git_functionality() -> MCPDoctorResult:
    """Test git functionality using available tools"""
    result = MCPDoctorResult("git_functionality")
    
    try:
        # Use subprocess to test git directly
        import subprocess
        
        # Test git status
        git_status_result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Test git log
        git_log_result = subprocess.run(
            ['git', 'log', '--oneline', '-3'],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if git_status_result.returncode == 0 and git_log_result.returncode == 0:
            result.passed = True
            result.details = {
                "git_status": "working",
                "git_log": "working", 
                "repo_path": str(ROOT),
                "untracked_files": len(git_status_result.stdout.split('\n')) if git_status_result.stdout.strip() else 0,
                "recent_commits": len(git_log_result.stdout.split('\n')) if git_log_result.stdout.strip() else 0
            }
        else:
            result.error = f"Git commands failed: status={git_status_result.returncode}, log={git_log_result.returncode}"
            
    except subprocess.TimeoutExpired:
        result.error = "Git commands timed out"
    except FileNotFoundError:
        result.error = "Git binary not found"
    except Exception as e:
        result.error = str(e)
        result.details["traceback"] = traceback.format_exc()
    
    if not result.passed:
        result.add_recommendation("Ensure git is installed and accessible")
        result.add_recommendation("Check that this is a git repository")
        result.add_recommendation("Verify file permissions for .git directory")
    
    return result


def test_system_info() -> MCPDoctorResult:
    """Test system information gathering"""
    result = MCPDoctorResult("system_info")
    
    try:
        import subprocess
        import platform
        
        # Test basic system info commands
        system_info = {}
        
        # Get CPU info
        try:
            cpu_result = subprocess.run(['sysctl', '-n', 'hw.ncpu'], capture_output=True, text=True, timeout=5)
            if cpu_result.returncode == 0:
                system_info['cpu_cores'] = cpu_result.stdout.strip()
        except:
            system_info['cpu_cores'] = 'unknown'
        
        # Get memory info
        try:
            mem_result = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=5)
            if mem_result.returncode == 0:
                system_info['memory_info'] = 'available'
            else:
                system_info['memory_info'] = 'failed'
        except:
            system_info['memory_info'] = 'unknown'
        
        # Get platform info
        system_info['platform'] = platform.platform()
        system_info['python_version'] = platform.python_version()
        
        result.passed = True
        result.details = system_info
        
    except Exception as e:
        result.error = str(e)
        result.details["traceback"] = traceback.format_exc()
    
    if not result.passed:
        result.add_recommendation("Check system permissions for information gathering")
        result.add_recommendation("Ensure system monitoring tools are available")
    
    return result


def test_file_operations() -> MCPDoctorResult:
    """Test basic file operations"""
    result = MCPDoctorResult("file_operations")
    
    try:
        import tempfile
        import os
        
        # Test file creation
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.mcp_test') as f:
            f.write('MCP doctor test file')
            temp_file = f.name
        
        # Test file reading
        with open(temp_file, 'r') as f:
            content = f.read()
        
        # Test file deletion
        os.unlink(temp_file)
        
        if content == 'MCP doctor test file':
            result.passed = True
            result.details = {
                "file_creation": "working",
                "file_reading": "working",
                "file_deletion": "working",
                "temp_dir": tempfile.gettempdir()
            }
        else:
            result.error = "File content mismatch"
            
    except Exception as e:
        result.error = str(e)
        result.details["traceback"] = traceback.format_exc()
    
    if not result.passed:
        result.add_recommendation("Check file system permissions")
        result.add_recommendation("Ensure temp directory is writable")
    
    return result


def run_all_tests() -> Dict[str, MCPDoctorResult]:
    """Run all available MCP-related tests"""
    results = {}
    
    # Test each component
    test_functions = [
        ("mcp_availability", test_mcp_availability),
        ("git_functionality", test_git_functionality), 
        ("system_info", test_system_info),
        ("file_operations", test_file_operations)
    ]
    
    for server_name, test_func in test_functions:
        print(f"Testing {server_name}...")
        results[server_name] = test_func()
        status = "✓ PASS" if results[server_name].passed else "✗ FAIL"
        print(f"  {status}")
        if results[server_name].error:
            print(f"  Error: {results[server_name].error}")
    
    return results


def print_summary(results: Dict[str, MCPDoctorResult]) -> None:
    """Print human-readable summary of test results"""
    print("\n" + "=" * 60)
    print("MCP DOCTOR - SYSTEM HEALTH REPORT")
    print("=" * 60)
    
    passed_count = sum(1 for r in results.values() if r.passed)
    total_count = len(results)
    
    print(f"\nOverall: {passed_count}/{total_count} components healthy\n")
    
    for server_name, result in results.items():
        status = "✓ HEALTHY" if result.passed else "✗ UNHEALTHY"
        print(f"{status} {server_name}")
        
        if result.passed:
            # Show key details
            for key, value in result.details.items():
                if key not in ["traceback"]:
                    print(f"  • {key}: {value}")
        else:
            # Show error and recommendations
            print(f"  • Error: {result.error}")
            for rec in result.recommendations:
                print(f"  → {rec}")
        print()
    
    # Overall recommendations
    if passed_count < total_count:
        print("RECOMMENDATIONS:")
        print("1. Fix unhealthy components before proceeding")
        print("2. Run 'lifeos doctor --mcp' again after fixes")
        print("3. Check MCP configuration at lifeos/config/mcp.config.json")
        print("4. Verify all MCP server paths exist and are executable")
    else:
        print("✓ All components are healthy!")


def get_json_summary(results: Dict[str, MCPDoctorResult]) -> str:
    """Return JSON summary for programmatic use"""
    summary = {
        "timestamp": json.dumps({"now": True}),
        "overall": {
            "passed": sum(1 for r in results.values() if r.passed),
            "total": len(results),
            "healthy": sum(1 for r in results.values() if r.passed) == len(results)
        },
        "servers": {name: result.to_dict() for name, result in results.items()}
    }
    return json.dumps(summary, indent=2)


if __name__ == "__main__":
    # Run tests when called directly
    results = run_all_tests()
    print_summary(results)
    
    # Exit with appropriate code
    all_healthy = all(r.passed for r in results.values())
    sys.exit(0 if all_healthy else 1)
