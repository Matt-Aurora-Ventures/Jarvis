#!/usr/bin/env python3
"""
Test script for self-healing functionality.
Demonstrates automatic error detection, research, and recovery.
"""

import sys
import os
from pathlib import Path

# Add the project root to the path
ROOT = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(ROOT))

from core import autonomous_agent, self_healing


def test_permission_denied_healing():
    """Test healing for permission denied errors."""
    print("=== Testing Permission Denied Healing ===")
    
    agent = autonomous_agent.get_autonomous_agent()
    
    # Simulate a permission denied scenario
    test_goal = "Try to access a protected system file"
    context = {"simulate_error": "permission_denied"}
    
    result = agent.execute_autonomous_task(test_goal, context)
    
    print(f"Task status: {result['status']}")
    if result.get('results'):
        for i, step_result in enumerate(result['results']):
            print(f"Step {i}: {step_result['status']}")
            if 'healing_applied' in step_result:
                print(f"  Healing applied: {step_result['healing_applied']['description']}")
    
    return result


def test_module_not_found_healing():
    """Test healing for module not found errors."""
    print("\n=== Testing Module Not Found Healing ===")
    
    healing = self_healing.get_self_healing()
    
    # Simulate module not found error
    error = "ModuleNotFoundError: No module named 'nonexistent_module'"
    context = {
        "tool": "terminal",
        "command": "python -c 'import nonexistent_module'",
        "module_name": "nonexistent_module"
    }
    
    healing_result = healing.heal_failure(error, context)
    
    print(f"Healing successful: {healing_result['healed']}")
    if healing_result['healed']:
        print(f"Solution applied: {healing_result['final_solution']['description']}")
    
    return healing_result


def test_file_not_found_healing():
    """Test healing for file not found errors."""
    print("\n=== Testing File Not Found Healing ===")
    
    healing = self_healing.get_self_healing()
    
    # Simulate file not found error
    error = "FileNotFoundError: [Errno 2] No such file or directory: '/nonexistent/path/file.txt'"
    context = {
        "tool": "file_ops",
        "operation": "read",
        "file_path": "/nonexistent/path/file.txt"
    }
    
    healing_result = healing.heal_failure(error, context)
    
    print(f"Healing successful: {healing_result['healed']}")
    if healing_result['healed']:
        print(f"Solution applied: {healing_result['final_solution']['description']}")
    
    return healing_result


def test_autonomous_task_with_healing():
    """Test a complete autonomous task that will trigger healing."""
    print("\n=== Testing Autonomous Task with Healing ===")
    
    agent = autonomous_agent.get_autonomous_agent()
    
    # This goal will likely fail and trigger healing
    test_goal = "Create a directory in /protected/path and write a file"
    
    result = agent.execute_autonomous_task(test_goal)
    
    print(f"Task status: {result['status']}")
    print(f"Steps completed: {len(result.get('results', []))}")
    
    # Check for healing events
    healing_events = []
    for step_result in result.get('results', []):
        if step_result.get('status') in ['healed_success', 'healed_failed']:
            healing_events.append(step_result)
    
    print(f"Healing events: {len(healing_events)}")
    for event in healing_events:
        print(f"  - {event['status']}: {event.get('tool', 'unknown')} tool")
    
    return result


def test_healing_statistics():
    """Test healing statistics and learning."""
    print("\n=== Testing Healing Statistics ===")
    
    healing = self_healing.get_self_healing()
    stats = healing.get_healing_stats()
    
    print(f"Learned solutions: {stats['learned_solutions']}")
    print(f"Recent sessions: {stats['recent_sessions']}")
    print(f"Success rate: {stats['success_rate']:.2%}")
    print(f"Common error types: {stats['common_error_types']}")
    
    return stats


def test_agent_status_with_healing():
    """Test agent status including healing information."""
    print("\n=== Testing Agent Status with Healing ===")
    
    agent = autonomous_agent.get_autonomous_agent()
    status = agent.get_agent_status()
    
    print(f"Self-healing capability: {status['capabilities']['self_healing']}")
    print(f"Tasks healed: {status['tasks_healed']}")
    print(f"Healing success rate: {status['healing_stats']['success_rate']:.2%}")
    
    return status


def main():
    """Run all self-healing tests."""
    print("Starting Self-Healing Tests\n")
    
    try:
        # Run individual healing tests
        test_permission_denied_healing()
        test_module_not_found_healing()
        test_file_not_found_healing()
        
        # Run comprehensive tests
        test_autonomous_task_with_healing()
        test_healing_statistics()
        test_agent_status_with_healing()
        
        print("\n=== All Tests Completed ===")
        print("Self-healing system is operational!")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
