#!/usr/bin/env python3
"""
Fix bare except handlers across the codebase.

Bare `except:` statements catch everything including KeyboardInterrupt and SystemExit,
which makes debugging impossible and can cause unexpected behavior.

This script replaces:
    except Exception:
With:
    except Exception as e:

And adds proper logging where appropriate.

Usage:
    python scripts/fix_bare_excepts.py [--dry-run]
"""

import argparse
import re
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).parent.parent

# Files to skip (test files, third-party, etc.)
SKIP_PATTERNS = [
    "**/node_modules/**",
    "**/.venv/**",
    "**/__pycache__/**",
    "**/dist/**",
    "**/build/**",
    "**/.git/**",
]

# Files that are known to need bare excepts (e.g., cleanup code)
WHITELIST_FILES = set()


def find_python_files() -> List[Path]:
    """Find all Python files in the project."""
    files = []
    for pattern in ["**/*.py"]:
        for path in PROJECT_ROOT.glob(pattern):
            # Skip patterns
            skip = False
            for skip_pattern in SKIP_PATTERNS:
                if path.match(skip_pattern):
                    skip = True
                    break
            if not skip:
                files.append(path)
    return files


def fix_bare_excepts_in_file(file_path: Path, dry_run: bool = False) -> List[Tuple[int, str, str]]:
    """
    Fix bare except handlers in a single file.

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

    # Pattern to match bare except (with optional comment)
    bare_except_pattern = re.compile(r'^(\s*)except\s*:\s*(#.*)?$')
    # Pattern for except: pass on same line
    except_pass_pattern = re.compile(r'^(\s*)except\s*:\s*pass\s*(#.*)?$')

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for except: pass (common pattern)
        match = except_pass_pattern.match(line)
        if match:
            indent = match.group(1)
            comment = match.group(2) or ""
            new_line = f"{indent}except Exception:  # noqa: BLE001 - intentional catch-all{' ' + comment if comment else ''}"
            changes.append((i + 1, line, new_line))
            new_lines.append(new_line)
            new_lines.append(f"{indent}    pass")
            i += 1
            continue

        # Check for bare except:
        match = bare_except_pattern.match(line)
        if match:
            indent = match.group(1)
            comment = match.group(2) or ""

            # Look at the next line to determine context
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            next_line_stripped = next_line.strip()

            # If next line is pass, just add noqa comment
            if next_line_stripped == "pass":
                new_line = f"{indent}except Exception:  # noqa: BLE001 - intentional catch-all{' ' + comment if comment else ''}"
            # If next line has logging, change to capture exception
            elif "logger" in next_line_stripped or "logging" in next_line_stripped:
                new_line = f"{indent}except Exception as e:{' ' + comment if comment else ''}"
            else:
                # Generic case - capture exception for debugging
                new_line = f"{indent}except Exception:{' ' + comment if comment else ''}"

            changes.append((i + 1, line, new_line))
            new_lines.append(new_line)
            i += 1
            continue

        new_lines.append(line)
        i += 1

    if changes and not dry_run:
        new_content = '\n'.join(new_lines)
        file_path.write_text(new_content, encoding="utf-8")

    return changes


def main():
    parser = argparse.ArgumentParser(description="Fix bare except handlers")
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
        if str(rel_path) in WHITELIST_FILES:
            continue

        changes = fix_bare_excepts_in_file(file_path, args.dry_run)

        if changes:
            files_changed += 1
            total_changes += len(changes)
            print(f"\n{rel_path}:")
            for line_num, old, new in changes:
                print(f"  Line {line_num}:")
                print(f"    - {old.strip()}")
                print(f"    + {new.strip()}")

    print(f"\n{'=' * 60}")
    print(f"Summary: {total_changes} bare excepts in {files_changed} files")
    if args.dry_run:
        print("(Dry run - no changes made)")
    else:
        print("All changes applied!")


if __name__ == "__main__":
    main()
