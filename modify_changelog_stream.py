#!/usr/bin/env python3
"""
Stream-based modification to add changelog entry without loading entire file
"""
import sys
import tempfile
import shutil

file_path = r"c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\.planning\milestones\v2-clawdbot-evolution\phases\09-team-orchestration\UNIFIED_GSD.md"
new_entry = "| 2026-02-02 | Documentation sprint: Created 28 config/ops docs (2.4MB total) | Claude Code |\n"
target_line = "| 2026-02-01 | Added DEBUGGING LESSONS LEARNED section | Claude |\n"

try:
    # Create temp file
    temp_fd, temp_path = tempfile.mkstemp(mode='w', encoding='utf-8', delete=False)

    with open(file_path, 'r', encoding='utf-8') as infile:
        with open(temp_fd, 'w', encoding='utf-8', closefd=False) as outfile:
            found = False
            for line in infile:
                outfile.write(line)
                if line == target_line and not found:
                    outfile.write(new_entry)
                    found = True
                    print(f"✓ Inserted new entry after line: {target_line.strip()}")

    if not found:
        print(f"✗ Target line not found")
        sys.exit(1)

    # Replace original file
    shutil.move(temp_path, file_path)
    print(f"✓ File updated successfully")
    print(f"  Added: {new_entry.strip()}")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
