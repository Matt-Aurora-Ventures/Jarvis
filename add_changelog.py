#!/usr/bin/env python3
import sys

file_path = r"c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\.planning\milestones\v2-clawdbot-evolution\phases\09-team-orchestration\UNIFIED_GSD.md"

try:
    # Read file
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find the line to insert after
    target_line = "| 2026-02-01 | Added DEBUGGING LESSONS LEARNED section | Claude |\n"
    new_line = "| 2026-02-02 | Documentation sprint: Created 28 config/ops docs (2.4MB total) | Claude Code |\n"

    # Find and insert
    for i, line in enumerate(lines):
        if line == target_line:
            lines.insert(i + 1, new_line)
            print(f"✓ Found target at line {i+1}, inserting new entry")
            break
    else:
        print("✗ Target line not found")
        sys.exit(1)

    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"✓ Successfully added changelog entry")
    print(f"  {new_line.strip()}")

except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
