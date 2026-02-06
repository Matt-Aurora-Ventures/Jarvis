#!/usr/bin/env python3
"""
Add a changelog entry to UNIFIED_GSD.md
"""

file_path = r"c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\.planning\milestones\v2-clawdbot-evolution\phases\09-team-orchestration\UNIFIED_GSD.md"

# Read the file
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the changelog section and insert the new entry
new_entry = "| 2026-02-02 | Documentation sprint: Created 28 config/ops docs (2.4MB total) | Claude Code |\n"
inserted = False

for i, line in enumerate(lines):
    # Find the last changelog entry before the separator
    if "| 2026-02-01 | Added DEBUGGING LESSONS LEARNED section | Claude |" in line:
        # Insert after this line
        lines.insert(i + 1, new_entry)
        inserted = True
        break

if inserted:
    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"✓ Successfully added changelog entry")
    print(f"  {new_entry.strip()}")
else:
    print("✗ Could not find the insertion point in CHANGELOG section")
