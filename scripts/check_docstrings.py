#!/usr/bin/env python3
"""
Module Docstring Checker

Scans Python modules for missing or incomplete docstrings.
Reports modules, classes, and functions lacking documentation.
"""
import ast
import sys
from pathlib import Path
from typing import List, Dict, Any, Set
from dataclasses import dataclass


@dataclass
class DocstringIssue:
    """Represents a missing or incomplete docstring."""
    file: str
    line: int
    item_type: str  # module, class, function
    name: str
    issue: str


class DocstringChecker(ast.NodeVisitor):
    """AST visitor to check for docstrings."""

    def __init__(self, filename: str):
        self.filename = filename
        self.issues: List[DocstringIssue] = []
        self._current_class: str = ""

    def visit_Module(self, node: ast.Module) -> None:
        """Check module-level docstring."""
        if not ast.get_docstring(node):
            self.issues.append(DocstringIssue(
                file=self.filename,
                line=1,
                item_type="module",
                name=Path(self.filename).stem,
                issue="Missing module docstring"
            ))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check class docstring."""
        if not ast.get_docstring(node):
            self.issues.append(DocstringIssue(
                file=self.filename,
                line=node.lineno,
                item_type="class",
                name=node.name,
                issue="Missing class docstring"
            ))

        old_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check function docstring."""
        self._check_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Check async function docstring."""
        self._check_function(node)

    def _check_function(self, node) -> None:
        """Check function/method docstring."""
        # Skip private and magic methods
        if node.name.startswith('_') and not node.name.startswith('__'):
            return

        # Skip common magic methods that don't need docs
        skip_magic = {'__init__', '__repr__', '__str__', '__eq__', '__hash__'}
        if node.name in skip_magic:
            self.generic_visit(node)
            return

        if not ast.get_docstring(node):
            name = f"{self._current_class}.{node.name}" if self._current_class else node.name
            self.issues.append(DocstringIssue(
                file=self.filename,
                line=node.lineno,
                item_type="function",
                name=name,
                issue="Missing function/method docstring"
            ))

        self.generic_visit(node)


def check_file(filepath: Path) -> List[DocstringIssue]:
    """Check a single Python file for docstring issues."""
    try:
        content = filepath.read_text(encoding='utf-8')
        tree = ast.parse(content)
        checker = DocstringChecker(str(filepath))
        checker.visit(tree)
        return checker.issues
    except SyntaxError as e:
        return [DocstringIssue(
            file=str(filepath),
            line=e.lineno or 0,
            item_type="file",
            name=filepath.name,
            issue=f"Syntax error: {e.msg}"
        )]
    except Exception as e:
        return [DocstringIssue(
            file=str(filepath),
            line=0,
            item_type="file",
            name=filepath.name,
            issue=f"Error parsing: {str(e)}"
        )]


def check_directory(
    directory: Path,
    exclude_patterns: Set[str] = None
) -> Dict[str, Any]:
    """
    Check all Python files in a directory.

    Returns:
        Dictionary with results and statistics
    """
    exclude = exclude_patterns or {
        '__pycache__', '.git', '.venv', 'venv', 'node_modules',
        'dist', 'build', '.eggs', '*.egg-info'
    }

    all_issues: List[DocstringIssue] = []
    files_checked = 0
    files_with_issues = 0

    for py_file in directory.rglob("*.py"):
        # Skip excluded directories
        if any(ex in str(py_file) for ex in exclude):
            continue

        issues = check_file(py_file)
        all_issues.extend(issues)
        files_checked += 1

        if issues:
            files_with_issues += 1

    # Group by type
    by_type = {
        "module": [],
        "class": [],
        "function": []
    }

    for issue in all_issues:
        if issue.item_type in by_type:
            by_type[issue.item_type].append(issue)

    return {
        "total_issues": len(all_issues),
        "files_checked": files_checked,
        "files_with_issues": files_with_issues,
        "issues_by_type": {
            "module": len(by_type["module"]),
            "class": len(by_type["class"]),
            "function": len(by_type["function"])
        },
        "issues": all_issues
    }


def generate_report(results: Dict[str, Any], verbose: bool = False) -> str:
    """Generate a human-readable report."""
    lines = [
        "=" * 60,
        "DOCSTRING ANALYSIS REPORT",
        "=" * 60,
        "",
        f"Files checked: {results['files_checked']}",
        f"Files with issues: {results['files_with_issues']}",
        f"Total issues: {results['total_issues']}",
        "",
        "Issues by type:",
        f"  - Missing module docstrings: {results['issues_by_type']['module']}",
        f"  - Missing class docstrings: {results['issues_by_type']['class']}",
        f"  - Missing function docstrings: {results['issues_by_type']['function']}",
        ""
    ]

    if verbose and results['issues']:
        lines.append("-" * 60)
        lines.append("DETAILED ISSUES:")
        lines.append("-" * 60)

        # Group by file
        by_file: Dict[str, List[DocstringIssue]] = {}
        for issue in results['issues']:
            by_file.setdefault(issue.file, []).append(issue)

        for filepath, issues in sorted(by_file.items()):
            lines.append(f"\n{filepath}:")
            for issue in sorted(issues, key=lambda x: x.line):
                lines.append(f"  L{issue.line}: [{issue.item_type}] {issue.name}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Check Python docstrings")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory or file to check"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed issues"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    args = parser.parse_args()
    path = Path(args.path)

    if path.is_file():
        issues = check_file(path)
        results = {
            "total_issues": len(issues),
            "files_checked": 1,
            "files_with_issues": 1 if issues else 0,
            "issues_by_type": {
                "module": sum(1 for i in issues if i.item_type == "module"),
                "class": sum(1 for i in issues if i.item_type == "class"),
                "function": sum(1 for i in issues if i.item_type == "function")
            },
            "issues": issues
        }
    else:
        results = check_directory(path)

    if args.json:
        import json
        # Convert issues to dicts
        output = {**results}
        output['issues'] = [
            {
                "file": i.file,
                "line": i.line,
                "type": i.item_type,
                "name": i.name,
                "issue": i.issue
            }
            for i in results['issues']
        ]
        print(json.dumps(output, indent=2))
    else:
        print(generate_report(results, verbose=args.verbose))

    # Exit with error code if issues found
    sys.exit(1 if results['total_issues'] > 0 else 0)


if __name__ == "__main__":
    main()
