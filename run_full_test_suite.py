#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Full test suite for Jarvis Dexter integration
Runs all tests and generates a comprehensive report
"""

import subprocess
import json
import sys
import time
from datetime import datetime
from pathlib import Path

class TestRunner:
    def __init__(self):
        self.results = {}
        self.start_time = datetime.now()

    def run_test(self, name, script_path, description=""):
        """Run a test script and capture results."""
        print(f"\n{'='*70}")
        print(f"[TEST] {name}")
        if description:
            print(f"[DESC] {description}")
        print(f"{'='*70}")

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=60
            )

            passed = result.returncode == 0
            self.results[name] = {
                "passed": passed,
                "returncode": result.returncode,
                "output": result.stdout,
                "errors": result.stderr,
                "timestamp": datetime.now().isoformat()
            }

            # Display output
            print(result.stdout)
            if result.stderr:
                print("[STDERR]", result.stderr)

            status = "[PASS]" if passed else "[FAIL]"
            print(f"{status} {name}")

            return passed
        except subprocess.TimeoutExpired:
            self.results[name] = {
                "passed": False,
                "error": "Test timed out (60s)"
            }
            print(f"[TIMEOUT] {name}")
            return False
        except Exception as e:
            self.results[name] = {
                "passed": False,
                "error": str(e)
            }
            print(f"[ERROR] {e}")
            return False

    def generate_report(self):
        """Generate test report."""
        print("\n" + "="*70)
        print("[REPORT] FULL TEST SUITE RESULTS")
        print("="*70)

        passed_count = sum(1 for r in self.results.values() if r.get("passed"))
        total_count = len(self.results)

        print()
        print(f"Tests Passed: {passed_count}/{total_count}")
        print(f"Pass Rate: {(passed_count/total_count*100):.0f}%")
        print()

        print("Test Results:")
        for test_name, result in self.results.items():
            status = "[PASS]" if result.get("passed") else "[FAIL]"
            print(f"  {status} {test_name}")

        duration = (datetime.now() - self.start_time).total_seconds()
        print()
        print(f"Duration: {duration:.1f}s")
        print("="*70)

        # Save report to file
        report_file = Path("test_results.json")
        with open(report_file, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"[SAVED] Report saved to {report_file}")

        return passed_count == total_count

def main():
    """Run full test suite."""
    runner = TestRunner()

    print("="*70)
    print("[START] JARVIS DEXTER FULL TEST SUITE")
    print("="*70)
    print(f"Started: {runner.start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Test 1: Local Dexter testing
    runner.run_test(
        "Local Dexter Testing",
        "test_dexter_locally.py",
        "Keyword detection and response simulation (no VPS required)"
    )

    # Test 2: Health check
    runner.run_test(
        "Bot Health Check",
        "health_check_bot.py",
        "Verify token validity and messaging capability"
    )

    # Generate final report
    print()
    all_passed = runner.generate_report()

    # Summary
    print()
    if all_passed:
        print("[SUCCESS] All tests PASSED! System is ready.")
        return 0
    else:
        print("[WARNING] Some tests FAILED. Review results above.")
        return 1

if __name__ == "__main__":
    exit(main())
