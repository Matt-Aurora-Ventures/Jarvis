#!/usr/bin/env python3
"""
Module Dependency Graph Generator

Generates a visual dependency graph of Python modules.
Outputs in DOT format (Graphviz) and optionally renders to image.
"""
import ast
import sys
from pathlib import Path
from typing import Set, Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class ModuleInfo:
    """Information about a Python module."""
    name: str
    path: Path
    imports: List[str]
    size: int  # lines of code


class ImportExtractor(ast.NodeVisitor):
    """Extract imports from Python AST."""

    def __init__(self, local_prefix: str = ""):
        self.imports: Set[str] = set()
        self.local_prefix = local_prefix

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if self._is_local(alias.name):
                self.imports.add(self._normalize(alias.name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and self._is_local(node.module):
            self.imports.add(self._normalize(node.module))
        self.generic_visit(node)

    def _is_local(self, module: str) -> bool:
        """Check if module is local to project."""
        if self.local_prefix:
            return module.startswith(self.local_prefix)
        # Heuristic: assume non-stdlib, non-common packages are local
        stdlib = {
            'os', 'sys', 'json', 'typing', 'dataclasses', 'pathlib',
            'logging', 'asyncio', 'time', 'datetime', 'collections',
            'functools', 'itertools', 'hashlib', 'secrets', 're',
            'abc', 'enum', 'copy', 'math', 'random', 'uuid'
        }
        return module.split('.')[0] not in stdlib

    def _normalize(self, module: str) -> str:
        """Normalize module name."""
        return module.split('.')[0]


def get_module_name(filepath: Path, root: Path) -> str:
    """Convert file path to module name."""
    relative = filepath.relative_to(root)
    parts = list(relative.parts)

    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]

    return ".".join(parts) if parts else filepath.stem


def analyze_module(filepath: Path, root: Path, local_prefix: str) -> Optional[ModuleInfo]:
    """Analyze a Python module."""
    try:
        content = filepath.read_text(encoding='utf-8')
        lines = len(content.splitlines())

        tree = ast.parse(content)
        extractor = ImportExtractor(local_prefix)
        extractor.visit(tree)

        return ModuleInfo(
            name=get_module_name(filepath, root),
            path=filepath,
            imports=list(extractor.imports),
            size=lines
        )
    except Exception:
        return None


def build_dependency_graph(
    directory: Path,
    local_prefix: str = ""
) -> Dict[str, ModuleInfo]:
    """Build dependency graph for all modules."""
    modules: Dict[str, ModuleInfo] = {}

    for py_file in directory.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        info = analyze_module(py_file, directory, local_prefix)
        if info:
            modules[info.name] = info

    return modules


def generate_dot(
    modules: Dict[str, ModuleInfo],
    title: str = "Module Dependencies",
    group_by_package: bool = True
) -> str:
    """Generate DOT format graph."""
    lines = [
        'digraph G {',
        '    rankdir=LR;',
        '    node [shape=box, style=filled, fillcolor=lightblue];',
        f'    label="{title}";',
        '    labelloc=top;',
        ''
    ]

    # Group modules by top-level package
    packages: Dict[str, List[str]] = defaultdict(list)
    for name in modules:
        parts = name.split('.')
        pkg = parts[0] if len(parts) > 1 else "root"
        packages[pkg].append(name)

    # Create subgraphs for packages
    if group_by_package:
        colors = ['#E8F4FD', '#FDE8E8', '#E8FDE8', '#FDF8E8', '#F0E8FD']
        for i, (pkg, members) in enumerate(packages.items()):
            color = colors[i % len(colors)]
            lines.append(f'    subgraph cluster_{pkg} {{')
            lines.append(f'        label="{pkg}";')
            lines.append(f'        style=filled;')
            lines.append(f'        fillcolor="{color}";')

            for member in members:
                safe_name = member.replace('.', '_')
                size = modules[member].size
                # Size node by LOC
                width = max(1.0, min(3.0, size / 200))
                lines.append(f'        "{safe_name}" [label="{member}\\n({size} LOC)", width={width:.1f}];')

            lines.append('    }')
            lines.append('')

    # Add edges
    lines.append('    // Dependencies')
    for name, info in modules.items():
        safe_from = name.replace('.', '_')
        for imp in info.imports:
            if imp in modules or any(m.startswith(imp + '.') for m in modules):
                safe_to = imp.replace('.', '_')
                lines.append(f'    "{safe_from}" -> "{safe_to}";')

    lines.append('}')
    return '\n'.join(lines)


def generate_mermaid(modules: Dict[str, ModuleInfo]) -> str:
    """Generate Mermaid format graph."""
    lines = ['graph LR']

    # Add nodes
    for name, info in modules.items():
        safe_name = name.replace('.', '_').replace('-', '_')
        lines.append(f'    {safe_name}["{name}"]')

    lines.append('')

    # Add edges
    for name, info in modules.items():
        safe_from = name.replace('.', '_').replace('-', '_')
        for imp in info.imports:
            if imp in modules:
                safe_to = imp.replace('.', '_').replace('-', '_')
                lines.append(f'    {safe_from} --> {safe_to}')

    return '\n'.join(lines)


def get_statistics(modules: Dict[str, ModuleInfo]) -> Dict[str, any]:
    """Calculate graph statistics."""
    total_deps = sum(len(m.imports) for m in modules.values())
    total_loc = sum(m.size for m in modules.values())

    # Find most connected modules
    incoming: Dict[str, int] = defaultdict(int)
    for info in modules.values():
        for imp in info.imports:
            incoming[imp] += 1

    outgoing = {name: len(info.imports) for name, info in modules.items()}

    most_deps = sorted(outgoing.items(), key=lambda x: x[1], reverse=True)[:5]
    most_dependents = sorted(incoming.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_modules": len(modules),
        "total_dependencies": total_deps,
        "total_lines_of_code": total_loc,
        "average_deps_per_module": total_deps / len(modules) if modules else 0,
        "most_dependencies": most_deps,
        "most_dependents": most_dependents
    }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate module dependency graph")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to analyze"
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Local package prefix"
    )
    parser.add_argument(
        "--format",
        choices=["dot", "mermaid", "stats"],
        default="dot",
        help="Output format"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--title",
        default="Module Dependencies",
        help="Graph title"
    )

    args = parser.parse_args()
    path = Path(args.path)

    modules = build_dependency_graph(path, args.prefix)

    if args.format == "dot":
        output = generate_dot(modules, args.title)
    elif args.format == "mermaid":
        output = generate_mermaid(modules)
    else:  # stats
        import json
        stats = get_statistics(modules)
        output = json.dumps(stats, indent=2)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
