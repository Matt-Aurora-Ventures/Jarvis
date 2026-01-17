#!/usr/bin/env python3
"""
Fix blocking time.sleep() calls in async contexts.

Using time.sleep() in async code blocks the entire event loop, preventing
other coroutines from running. This script identifies and fixes these issues.

This script:
1. Finds async functions that use time.sleep()
2. Replaces them with await asyncio.sleep()

Usage:
    python scripts/fix_blocking_sleep.py [--dry-run]
"""

import argparse
import re
from pathlib import Path
from typing import List, Tuple, Set

PROJECT_ROOT = Path(__file__).parent.parent

# Files to skip
SKIP_PATTERNS = [
    "**/node_modules/**",
    "**/.venv/**",
    "**/__pycache__/**",
    "**/dist/**",
    "**/build/**",
    "**/.git/**",
]

# Files that legitimately need blocking sleep (non-async contexts, tests, etc.)
WHITELIST_FILES = {
    "core/daemon.py",  # Synchronous daemon
    "core/command_watchdog.py",  # Synchronous watchdog thread
    "core/config_hot_reload.py",  # Synchronous file watcher
    "core/hotkeys.py",  # Synchronous keyboard handler
    "examples/",  # Example files
}


def find_python_files() -> List[Path]:
    """Find all Python files in the project."""
    files = []
    for path in PROJECT_ROOT.glob("**/*.py"):
        skip = False
        for skip_pattern in SKIP_PATTERNS:
            if path.match(skip_pattern):
                skip = True
                break
        if not skip:
            files.append(path)
    return files


def is_in_async_context(lines: List[str], line_idx: int) -> bool:
    """
    Check if the given line is inside an async function.

    Walks backward to find the function definition.
    """
    indent_at_line = len(lines[line_idx]) - len(lines[line_idx].lstrip())

    for i in range(line_idx - 1, -1, -1):
        line = lines[i]
        if not line.strip():
            continue

        current_indent = len(line) - len(line.lstrip())

        # Found a less-indented line - check if it's a function def
        if current_indent < indent_at_line:
            stripped = line.strip()
            if stripped.startswith("async def "):
                return True
            if stripped.startswith("def "):
                return False
            # Could be in a class or other block, keep searching
            indent_at_line = current_indent

    return False


def fix_blocking_sleep_in_file(file_path: Path, dry_run: bool = False) -> List[Tuple[int, str, str]]:
    """
    Fix time.sleep() calls in async contexts.

    Returns list of (line_number, old_line, new_line) tuples.
    """
    changes = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  Error reading {file_path}: {e}")
        return changes

    lines = content.split('\n')
    new_lines = []

    # Track if asyncio is imported
    has_asyncio_import = "import asyncio" in content

    # Pattern to match time.sleep()
    sleep_pattern = re.compile(r'(\s*)(.*)time\.sleep\(([^)]+)\)(.*)')

    needs_asyncio_import = False

    for i, line in enumerate(lines):
        match = sleep_pattern.search(line)

        if match and is_in_async_context(lines, i):
            indent = match.group(1)
            prefix = match.group(2)
            sleep_arg = match.group(3)
            suffix = match.group(4)

            # Replace time.sleep with await asyncio.sleep
            new_line = f"{indent}{prefix}await asyncio.sleep({sleep_arg}){suffix}"
            changes.append((i + 1, line, new_line))
            new_lines.append(new_line)
            needs_asyncio_import = True
        else:
            new_lines.append(line)

    # Add asyncio import if needed
    if needs_asyncio_import and not has_asyncio_import:
        # Find where to insert the import
        import_idx = 0
        for i, line in enumerate(new_lines):
            if line.startswith("import ") or line.startswith("from "):
                import_idx = i + 1
            elif line.strip() and not line.startswith("#") and not line.startswith('"""') and not line.startswith("'''"):
                break

        new_lines.insert(import_idx, "import asyncio")
        changes.insert(0, (import_idx + 1, "", "import asyncio  # Added for asyncio.sleep"))

    if changes and not dry_run:
        new_content = '\n'.join(new_lines)
        file_path.write_text(new_content, encoding="utf-8")

    return changes


def main():
    parser = argparse.ArgumentParser(description="Fix blocking sleep in async contexts")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    args = parser.parse_args()

    print(f"Scanning Python files in {PROJECT_ROOT}...")
    files = find_python_files()
    print(f"Found {len(files)} Python files\n")

    total_changes = 0
    files_changed = 0

    for file_path in sorted(files):
        rel_path = file_path.relative_to(PROJECT_ROOT)

        # Skip whitelisted files
        skip = False
        for whitelist in WHITELIST_FILES:
            if str(rel_path).startswith(whitelist):
                skip = True
                break
        if skip:
            continue

        changes = fix_blocking_sleep_in_file(file_path, args.dry_run)

        if changes:
            files_changed += 1
            total_changes += len(changes)
            print(f"\n{rel_path}:")
            for line_num, old, new in changes:
                print(f"  Line {line_num}:")
                if old:
                    print(f"    - {old.strip()}")
                print(f"    + {new.strip()}")

    print(f"\n{'=' * 60}")
    print(f"Summary: {total_changes} blocking sleeps fixed in {files_changed} files")
    if args.dry_run:
        print("(Dry run - no changes made)")
    else:
        print("All changes applied!")


if __name__ == "__main__":
    main()
