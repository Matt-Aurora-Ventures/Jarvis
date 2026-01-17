#!/usr/bin/env python3
"""
MCP Doctor - Comprehensive MCP server health diagnostics
Tests shell, git, system-monitor, and obsidian-memory MCP servers
"""

import json
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Try to detect if we're running in Windsurf with MCP available
MCP_AVAILABLE = False
MCP_IMPORT_ERROR = ""

# Test individual MCP imports
try:
    # These should be available in Windsurf environment
    import subprocess
    result = subprocess.run(['python3', '-c', 'import mcp11_shell_execute; print("shell ok")'], 
                          capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        MCP_AVAILABLE = True
    else:
        MCP_IMPORT_ERROR = "MCP modules not available in subprocess"
except Exception:
    MCP_IMPORT_ERROR = "Could not test MCP availability"

# Alternative: try direct imports (may work in some contexts)
if not MCP_AVAILABLE:
    try:
        from mcp11_shell_execute import mcp11_shell_execute
        from mcp13_get_cpu_info import mcp13_get_cpu_info
        from mcp13_get_memory_info import mcp13_get_memory_info
        from mcp13_get_network_info import mcp13_get_network_info
        from mcp3_git_status import mcp3_git_status
        from mcp3_git_log import mcp3_git_log
        from mcp7_read_graph import mcp7_read_graph
        from mcp7_create_entities import mcp7_create_entities
        from mcp7_search_nodes import mcp7_search_nodes
        MCP_AVAILABLE = True
    except ImportError as e:
        MCP_IMPORT_ERROR = str(e)

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


def test_shell_server() -> MCPDoctorResult:
    """Test shell MCP server functionality"""
    result = MCPDoctorResult("shell")
    
    try:
        # Test 1: Simple echo command
        response = mcp11_shell_execute(
            command="echo 'MCP shell test successful'",
            comment="MCP Doctor shell test"
        )
        
        if response and "stdout" in response:
            stdout = response.get("stdout", "")
            if "MCP shell test successful" in stdout:
                result.passed = True
                result.details = {
                    "command": "echo test",
                    "stdout": stdout.strip(),
                    "execution_id": response.get("execution_id")
                }
            else:
                result.error = f"Unexpected output: {stdout}"
        else:
            result.error = "No valid response from shell server"
            
    except Exception as e:
        result.error = str(e)
        result.details["traceback"] = traceback.format_exc()
    
    if not result.passed:
        result.add_recommendation("Check if shell MCP server is running")
        result.add_recommendation("Verify MCP configuration paths")
        result.add_recommendation("Check permissions for shell execution")
    
    return result


def test_git_server() -> MCPDoctorResult:
    """Test git MCP server functionality"""
    result = MCPDoctorResult("git")
    
    try:
        # Test 1: Get git status
        repo_path = str(ROOT)
        status_response = mcp3_git_status(repo_path=repo_path)
        
        if status_response and "Repository status:" in status_response:
            result.passed = True
            result.details = {
                "status_check": "passed",
                "repo_path": repo_path,
                "status_preview": status_response[:200] + "..." if len(status_response) > 200 else status_response
            }
            
            # Test 2: Get recent log
            try:
                log_response = mcp3_git_log(repo_path=repo_path, max_count=3)
                if log_response:
                    result.details["log_check"] = "passed"
                    result.details["recent_commits"] = len(log_response.split('\n')) if log_response else 0
            except Exception as log_error:
                result.details["log_check"] = f"failed: {log_error}"
                
        else:
            result.error = "Git status command failed"
            
    except Exception as e:
        result.error = str(e)
        result.details["traceback"] = traceback.format_exc()
    
    if not result.passed:
        result.add_recommendation("Verify this is a git repository")
        result.add_recommendation("Check git MCP server configuration")
        result.add_recommendation("Ensure git binary is accessible")
    
    return result


def test_system_monitor_server() -> MCPDoctorResult:
    """Test system-monitor MCP server functionality"""
    result = MCPDoctorResult("system-monitor")
    
    try:
        # Test 1: CPU info
        cpu_response = mcp13_get_cpu_info(per_cpu=False)
        
        # Test 2: Memory info  
        mem_response = mcp13_get_memory_info()
        
        # Test 3: Network info
        net_response = mcp13_get_network_info()
        
        if cpu_response and mem_response and net_response:
            result.passed = True
            result.details = {
                "cpu_cores": cpu_response.get("core_count", "unknown"),
                "cpu_usage": f"{cpu_response.get('usage_percent', [0])[0]:.1f}%" if cpu_response.get("usage_percent") else "unknown",
                "memory_total": f"{mem_response.get('total', 0) / (1024**3):.1f} GB" if mem_response.get("total") else "unknown",
                "memory_available": f"{mem_response.get('available', 0) / (1024**3):.1f} GB" if mem_response.get("available") else "unknown",
                "network_interfaces": len(net_response.get("interfaces", [])) if net_response.get("interfaces") else 0
            }
        else:
            result.error = "Incomplete system monitor response"
            
    except Exception as e:
        result.error = str(e)
        result.details["traceback"] = traceback.format_exc()
    
    if not result.passed:
        result.add_recommendation("Check system-monitor MCP server installation")
        result.add_recommendation("Verify system permissions for monitoring")
        result.add_recommendation("Ensure psutil dependencies are met")
    
    return result


def test_obsidian_memory_server() -> MCPDoctorResult:
    """Test obsidian-memory MCP server functionality"""
    result = MCPDoctorResult("obsidian-memory")
    
    try:
        # Test 1: Read current graph
        graph_response = mcp7_read_graph()
        
        # Test 2: Create test entity
        test_entity_name = "MCP Doctor Test Entity"
        create_response = mcp7_create_entities(
            entities=[{
                "name": test_entity_name,
                "entityType": "test",
                "observations": [f"Created by MCP doctor at {json.dumps({'timestamp': 'now'})}"]
            }]
        )
        
        # Test 3: Search for the test entity
        search_response = mcp7_search_nodes(query=test_entity_name)
        
        if graph_response is not None and create_response and search_response:
            result.passed = True
            result.details = {
                "graph_read": "passed",
                "entity_creation": "passed", 
                "entity_search": "passed",
                "total_entities": len(graph_response.get("entities", [])),
                "total_relations": len(graph_response.get("relations", [])),
                "test_entity_created": len(create_response) > 0,
                "search_results": len(search_response) if search_response else 0
            }
        else:
            result.error = "Obsidian memory operations failed"
            
    except Exception as e:
        result.error = str(e)
        result.details["traceback"] = traceback.format_exc()
    
    if not result.passed:
        result.add_recommendation("Check obsidian-memory MCP server paths")
        result.add_recommendation("Verify Obsidian vault directory exists")
        result.add_recommendation("Check file permissions for memory directory")
        result.add_recommendation("Ensure obsidian-memory server is running")
    
    return result


def run_all_tests() -> Dict[str, MCPDoctorResult]:
    """Run all MCP server tests"""
    if not MCP_AVAILABLE:
        # Return a single failed result for import error
        result = MCPDoctorResult("mcp_import")
        result.passed = False
        result.error = MCP_IMPORT_ERROR
        result.add_recommendation("Install MCP server dependencies")
        result.add_recommendation("Check Python path configuration")
        return {"mcp_import": result}
    
    results = {}
    
    # Test each server
    test_functions = [
        ("shell", test_shell_server),
        ("git", test_git_server), 
        ("system-monitor", test_system_monitor_server),
        ("obsidian-memory", test_obsidian_memory_server)
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
    print("MCP DOCTOR - SERVER HEALTH REPORT")
    print("=" * 60)
    
    passed_count = sum(1 for r in results.values() if r.passed)
    total_count = len(results)
    
    print(f"\nOverall: {passed_count}/{total_count} servers healthy\n")
    
    for server_name, result in results.items():
        status = "✓ HEALTHY" if result.passed else "✗ UNHEALTHY"
        print(f"{status} {server_name}")
        
        if result.passed:
            # Show key details
            for key, value in result.details.items():
                if key not in ["traceback", "status_preview"]:
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
        print("1. Fix unhealthy servers before proceeding")
        print("2. Run 'lifeos doctor' again after fixes")
        print("3. Check MCP configuration at lifeos/config/mcp.config.json")
        print("4. Verify all MCP server paths exist and are executable")
    else:
        print("✓ All MCP servers are healthy!")


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
