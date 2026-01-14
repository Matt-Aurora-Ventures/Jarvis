#!/usr/bin/env python3
"""
JARVIS Coverage Runner

Script to run tests with coverage and generate reports.
"""

import subprocess
import sys
import argparse
from pathlib import Path
import json


def run_coverage(
    html: bool = True,
    xml: bool = False,
    json_report: bool = False,
    fail_under: int = 60,
    parallel: bool = False,
    test_path: str = "tests",
    verbose: bool = False
) -> int:
    """
    Run tests with coverage.

    Args:
        html: Generate HTML report
        xml: Generate XML report
        json_report: Generate JSON report
        fail_under: Minimum coverage percentage
        parallel: Run tests in parallel
        test_path: Path to tests
        verbose: Verbose output

    Returns:
        Exit code (0 for success)
    """
    # Build pytest command
    cmd = ["python", "-m", "pytest"]

    if verbose:
        cmd.append("-v")

    # Add coverage options
    cmd.extend([
        f"--cov=core",
        f"--cov=api",
        f"--cov=bots",
        f"--cov=integrations",
        f"--cov=tg_bot",
        f"--cov-branch",
        f"--cov-report=term-missing",
        f"--cov-fail-under={fail_under}",
    ])

    if html:
        cmd.append("--cov-report=html:htmlcov")

    if xml:
        cmd.append("--cov-report=xml:coverage.xml")

    if json_report:
        cmd.append("--cov-report=json:coverage.json")

    if parallel:
        cmd.extend(["-n", "auto"])

    cmd.append(test_path)

    print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd)
    return result.returncode


def show_coverage_summary(coverage_file: str = "coverage.json") -> None:
    """Show coverage summary from JSON report."""
    path = Path(coverage_file)
    if not path.exists():
        print(f"Coverage file not found: {coverage_file}")
        return

    with open(path) as f:
        data = json.load(f)

    totals = data.get("totals", {})

    print("\n" + "=" * 60)
    print("COVERAGE SUMMARY")
    print("=" * 60)
    print(f"Statements:   {totals.get('num_statements', 0):>6}")
    print(f"Covered:      {totals.get('covered_lines', 0):>6}")
    print(f"Missing:      {totals.get('missing_lines', 0):>6}")
    print(f"Branches:     {totals.get('num_branches', 0):>6}")
    print(f"Coverage:     {totals.get('percent_covered', 0):>5.1f}%")
    print("=" * 60)

    # Show files with lowest coverage
    files = data.get("files", {})
    if files:
        print("\nLOWEST COVERAGE FILES:")
        print("-" * 60)

        sorted_files = sorted(
            files.items(),
            key=lambda x: x[1].get("summary", {}).get("percent_covered", 100)
        )

        for filepath, info in sorted_files[:10]:
            summary = info.get("summary", {})
            pct = summary.get("percent_covered", 0)
            missing = summary.get("missing_lines", 0)
            print(f"  {pct:5.1f}% ({missing:3} missing) - {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Run JARVIS tests with coverage"
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Skip HTML report generation"
    )
    parser.add_argument(
        "--xml",
        action="store_true",
        help="Generate XML report for CI"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Generate JSON report"
    )
    parser.add_argument(
        "--fail-under",
        type=int,
        default=60,
        help="Minimum coverage percentage (default: 60)"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel"
    )
    parser.add_argument(
        "--path",
        default="tests",
        help="Test path (default: tests)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show coverage summary (requires --json)"
    )

    args = parser.parse_args()

    # Always generate JSON if summary requested
    json_report = args.json or args.summary

    exit_code = run_coverage(
        html=not args.no_html,
        xml=args.xml,
        json_report=json_report,
        fail_under=args.fail_under,
        parallel=args.parallel,
        test_path=args.path,
        verbose=args.verbose
    )

    if args.summary and exit_code == 0:
        show_coverage_summary()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
