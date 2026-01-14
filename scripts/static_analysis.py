#!/usr/bin/env python3
"""
JARVIS Static Analysis Runner

Runs multiple static analysis tools and aggregates results.
"""

import subprocess
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any
import json


@dataclass
class AnalysisResult:
    """Result from a single analysis tool."""
    tool: str
    passed: bool
    issues: int = 0
    warnings: int = 0
    errors: int = 0
    output: str = ""


@dataclass
class AnalysisSummary:
    """Summary of all analysis results."""
    results: List[AnalysisResult] = field(default_factory=list)
    total_issues: int = 0
    total_errors: int = 0
    all_passed: bool = True

    def add_result(self, result: AnalysisResult) -> None:
        self.results.append(result)
        self.total_issues += result.issues
        self.total_errors += result.errors
        if not result.passed:
            self.all_passed = False


def run_command(cmd: List[str], check: bool = False) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )
    except subprocess.CalledProcessError as e:
        return e


def run_ruff(paths: List[str]) -> AnalysisResult:
    """Run Ruff linter."""
    print("Running Ruff...")
    cmd = ["ruff", "check", "--output-format=json"] + paths

    result = run_command(cmd)
    output = result.stdout

    try:
        issues = json.loads(output) if output else []
        issue_count = len(issues)
        errors = len([i for i in issues if i.get("type") == "error"])
    except json.JSONDecodeError:
        issue_count = 0
        errors = 0

    passed = result.returncode == 0

    return AnalysisResult(
        tool="ruff",
        passed=passed,
        issues=issue_count,
        errors=errors,
        output=output if not passed else ""
    )


def run_mypy(paths: List[str]) -> AnalysisResult:
    """Run MyPy type checker."""
    print("Running MyPy...")
    cmd = ["mypy", "--ignore-missing-imports", "--no-error-summary"] + paths

    result = run_command(cmd)

    # Count issues from output
    lines = result.stdout.strip().split('\n') if result.stdout else []
    errors = len([l for l in lines if ': error:' in l])
    warnings = len([l for l in lines if ': warning:' in l or ': note:' in l])

    return AnalysisResult(
        tool="mypy",
        passed=result.returncode == 0,
        issues=errors + warnings,
        errors=errors,
        warnings=warnings,
        output=result.stdout if result.returncode != 0 else ""
    )


def run_bandit(paths: List[str]) -> AnalysisResult:
    """Run Bandit security scanner."""
    print("Running Bandit...")
    cmd = ["bandit", "-r", "-f", "json", "-q"] + paths

    result = run_command(cmd)

    try:
        data = json.loads(result.stdout) if result.stdout else {}
        metrics = data.get("metrics", {}).get("_totals", {})
        high = metrics.get("SEVERITY.HIGH", 0)
        medium = metrics.get("SEVERITY.MEDIUM", 0)
        low = metrics.get("SEVERITY.LOW", 0)
        total = high + medium + low
    except (json.JSONDecodeError, KeyError):
        total = 0
        high = 0

    return AnalysisResult(
        tool="bandit",
        passed=high == 0,  # Fail only on high severity
        issues=total,
        errors=high,
        warnings=medium,
        output=result.stdout if high > 0 else ""
    )


def run_black_check(paths: List[str]) -> AnalysisResult:
    """Run Black in check mode."""
    print("Running Black check...")
    cmd = ["black", "--check", "--quiet"] + paths

    result = run_command(cmd)

    # Count files that would be reformatted
    if result.returncode != 0:
        lines = result.stderr.strip().split('\n') if result.stderr else []
        issues = len([l for l in lines if 'would reformat' in l])
    else:
        issues = 0

    return AnalysisResult(
        tool="black",
        passed=result.returncode == 0,
        issues=issues,
        output=result.stderr if result.returncode != 0 else ""
    )


def run_vulture(paths: List[str]) -> AnalysisResult:
    """Run Vulture dead code finder."""
    print("Running Vulture...")
    cmd = ["vulture", "--min-confidence=80"] + paths

    result = run_command(cmd)

    lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
    issues = len(lines)

    return AnalysisResult(
        tool="vulture",
        passed=issues == 0,
        issues=issues,
        warnings=issues,
        output=result.stdout if issues > 0 else ""
    )


def run_all_analyses(paths: List[str], skip: List[str] = None) -> AnalysisSummary:
    """Run all analysis tools."""
    skip = skip or []
    summary = AnalysisSummary()

    analyses = [
        ("ruff", run_ruff),
        ("mypy", run_mypy),
        ("bandit", run_bandit),
        ("black", run_black_check),
        ("vulture", run_vulture),
    ]

    for name, func in analyses:
        if name not in skip:
            try:
                result = func(paths)
                summary.add_result(result)
                status = "✓" if result.passed else "✗"
                print(f"  {status} {name}: {result.issues} issues")
            except FileNotFoundError:
                print(f"  - {name}: not installed, skipping")

    return summary


def print_summary(summary: AnalysisSummary) -> None:
    """Print analysis summary."""
    print("\n" + "=" * 60)
    print("STATIC ANALYSIS SUMMARY")
    print("=" * 60)

    for result in summary.results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{result.tool:12} {status:6} Issues: {result.issues:4} Errors: {result.errors}")

    print("-" * 60)
    print(f"{'TOTAL':12} {'PASS' if summary.all_passed else 'FAIL':6} Issues: {summary.total_issues:4} Errors: {summary.total_errors}")
    print("=" * 60)

    if not summary.all_passed:
        print("\nFailed tools output:")
        for result in summary.results:
            if not result.passed and result.output:
                print(f"\n--- {result.tool} ---")
                # Truncate long output
                lines = result.output.split('\n')
                if len(lines) > 20:
                    print('\n'.join(lines[:20]))
                    print(f"... ({len(lines) - 20} more lines)")
                else:
                    print(result.output)


def main():
    parser = argparse.ArgumentParser(
        description="Run static analysis on JARVIS codebase"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["core", "api", "bots", "integrations", "tg_bot"],
        help="Paths to analyze"
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        default=[],
        help="Tools to skip (ruff, mypy, bandit, black, vulture)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Fail if any warnings are found"
    )

    args = parser.parse_args()

    # Filter to existing paths
    paths = [p for p in args.paths if Path(p).exists()]

    if not paths:
        print("No valid paths to analyze")
        sys.exit(1)

    print(f"Analyzing: {', '.join(paths)}\n")

    summary = run_all_analyses(paths, skip=args.skip)

    if args.json:
        output = {
            "passed": summary.all_passed,
            "total_issues": summary.total_issues,
            "total_errors": summary.total_errors,
            "results": [
                {
                    "tool": r.tool,
                    "passed": r.passed,
                    "issues": r.issues,
                    "errors": r.errors,
                    "warnings": r.warnings,
                }
                for r in summary.results
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print_summary(summary)

    # Exit code
    if not summary.all_passed:
        sys.exit(1)
    if args.fail_on_warning and summary.total_issues > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
