#!/usr/bin/env python3
"""
Insert a new changelog entry into UNIFIED_GSD.md
"""

file_path = r"c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\.planning\milestones\v2-clawdbot-evolution\phases\09-team-orchestration\UNIFIED_GSD.md"

# Read the file
print(f"Reading file: {file_path}")
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# The new entry to add
new_entry = "| 2026-02-02 | Documentation sprint: Created 28 config/ops docs (2.4MB total) | Claude Code |"

# Find the position to insert - after the last existing entry and before the blank line/separator
target = "| 2026-02-01 | Added DEBUGGING LESSONS LEARNED section | Claude |"

if target in content:
    # Insert the new entry on the next line
    content = content.replace(target, target + "\n" + new_entry)

    # Write back the file
    print(f"Writing updated content...")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✓ Successfully added changelog entry:")
    print(f"  {new_entry}")
else:
    print(f"✗ Could not find the target line in the file")
    print(f"  Looking for: {target}")
