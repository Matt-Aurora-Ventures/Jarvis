#!/usr/bin/env python3
"""
Circular Dependency Checker

Detects circular import dependencies in Python modules.
Uses AST analysis to find import statements and builds a dependency graph.
"""
import ast
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class ImportInfo:
    """Information about an import statement."""
    module: str
    from_module: Optional[str]
    line: int
    is_relative: bool


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to extract import statements."""

    def __init__(self, module_path: Path, package_root: Path):
        self.module_path = module_path
        self.package_root = package_root
        self.imports: List[ImportInfo] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(ImportInfo(
                module=alias.name,
                from_module=None,
                line=node.lineno,
                is_relative=False
            ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            module = node.module
            is_relative = node.level > 0

            if is_relative:
                # Resolve relative import
                module = self._resolve_relative(node.level, node.module)

            self.imports.append(ImportInfo(
                module=module,
                from_module=node.module,
                line=node.lineno,
                is_relative=is_relative
            ))
        self.generic_visit(node)

    def _resolve_relative(self, level: int, module: Optional[str]) -> str:
        """Resolve relative import to absolute module path."""
        parts = self.module_path.relative_to(self.package_root).parts

        # Go up 'level' directories
        if level > len(parts):
            return module or ""

        base_parts = parts[:-(level)]
        if module:
            return ".".join(base_parts) + "." + module
        return ".".join(base_parts)


class DependencyGraph:
    """Graph of module dependencies."""

    def __init__(self):
        self.edges: Dict[str, Set[str]] = defaultdict(set)
        self.nodes: Set[str] = set()

    def add_dependency(self, from_module: str, to_module: str) -> None:
        """Add a dependency edge."""
        self.nodes.add(from_module)
        self.nodes.add(to_module)
        self.edges[from_module].add(to_module)

    def find_cycles(self) -> List[List[str]]:
        """Find all cycles in the graph using DFS."""
        cycles = []
        visited = set()
        rec_stack = []
        rec_stack_set = set()

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)
            rec_stack_set.add(node)

            for neighbor in self.edges.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack_set:
                    # Found a cycle
                    cycle_start = rec_stack.index(neighbor)
                    cycle = rec_stack[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            rec_stack.pop()
            rec_stack_set.remove(node)

        for node in self.nodes:
            if node not in visited:
                dfs(node)

        return cycles

    def find_strongly_connected(self) -> List[Set[str]]:
        """Find strongly connected components (Tarjan's algorithm)."""
        index_counter = [0]
        stack = []
        lowlinks = {}
        index = {}
        on_stack = {}
        sccs = []

        def strongconnect(v: str) -> None:
            index[v] = index_counter[0]
            lowlinks[v] = index_counter[0]
            index_counter[0] += 1
            stack.append(v)
            on_stack[v] = True

            for w in self.edges.get(v, []):
                if w not in index:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif on_stack.get(w, False):
                    lowlinks[v] = min(lowlinks[v], index[w])

            if lowlinks[v] == index[v]:
                scc = set()
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.add(w)
                    if w == v:
                        break
                if len(scc) > 1:
                    sccs.append(scc)

        for v in self.nodes:
            if v not in index:
                strongconnect(v)

        return sccs


def get_module_name(filepath: Path, root: Path) -> str:
    """Convert file path to module name."""
    relative = filepath.relative_to(root)
    parts = list(relative.parts)

    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]  # Remove .py

    return ".".join(parts)


def analyze_imports(filepath: Path, root: Path) -> List[ImportInfo]:
    """Analyze imports in a Python file."""
    try:
        content = filepath.read_text(encoding='utf-8')
        tree = ast.parse(content)
        visitor = ImportVisitor(filepath, root)
        visitor.visit(tree)
        return visitor.imports
    except Exception:
        return []


def check_circular_dependencies(
    directory: Path,
    package_prefix: str = ""
) -> Dict[str, any]:
    """
    Check for circular dependencies in a Python package.

    Returns:
        Dictionary with analysis results
    """
    graph = DependencyGraph()

    # Find all Python files
    for py_file in directory.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        module_name = get_module_name(py_file, directory)
        if package_prefix:
            module_name = f"{package_prefix}.{module_name}"

        imports = analyze_imports(py_file, directory)

        for imp in imports:
            # Only track internal imports
            if package_prefix:
                if imp.module.startswith(package_prefix):
                    graph.add_dependency(module_name, imp.module)
            else:
                # Check if it's a local import
                potential_path = directory / imp.module.replace(".", "/")
                if potential_path.exists() or (potential_path.with_suffix(".py")).exists():
                    graph.add_dependency(module_name, imp.module)

    cycles = graph.find_cycles()
    sccs = graph.find_strongly_connected()

    return {
        "has_cycles": len(cycles) > 0,
        "cycle_count": len(cycles),
        "cycles": cycles,
        "strongly_connected_components": [list(scc) for scc in sccs],
        "total_modules": len(graph.nodes),
        "total_dependencies": sum(len(deps) for deps in graph.edges.values())
    }


def generate_report(results: Dict[str, any]) -> str:
    """Generate a human-readable report."""
    lines = [
        "=" * 60,
        "CIRCULAR DEPENDENCY ANALYSIS",
        "=" * 60,
        "",
        f"Total modules analyzed: {results['total_modules']}",
        f"Total dependencies: {results['total_dependencies']}",
        ""
    ]

    if results['has_cycles']:
        lines.append(f"CIRCULAR DEPENDENCIES DETECTED: {results['cycle_count']}")
        lines.append("")
        lines.append("-" * 60)

        for i, cycle in enumerate(results['cycles'], 1):
            lines.append(f"\nCycle {i}:")
            lines.append("  " + " -> ".join(cycle))

        if results['strongly_connected_components']:
            lines.append("")
            lines.append("-" * 60)
            lines.append("Strongly Connected Components:")

            for i, scc in enumerate(results['strongly_connected_components'], 1):
                lines.append(f"\n  Component {i}: {len(scc)} modules")
                for module in sorted(scc):
                    lines.append(f"    - {module}")
    else:
        lines.append("No circular dependencies detected!")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Check for circular dependencies")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to check"
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Package prefix to filter imports"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    args = parser.parse_args()
    path = Path(args.path)

    results = check_circular_dependencies(path, args.prefix)

    if args.json:
        import json
        print(json.dumps(results, indent=2))
    else:
        print(generate_report(results))

    sys.exit(1 if results['has_cycles'] else 0)


if __name__ == "__main__":
    main()
