file_path = r"c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\.planning\milestones\v2-clawdbot-evolution\phases\09-team-orchestration\UNIFIED_GSD.md"

with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

old = "| 2026-02-01 | Added DEBUGGING LESSONS LEARNED section | Claude |"
new = old + "\n| 2026-02-02 | Documentation sprint: Created 28 config/ops docs (2.4MB total) | Claude Code |"

text = text.replace(old, new)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Done!")
