"""Fix CostTracker and SelfHealing import names in all 3 bots."""

BOTS = [
    "clawdmatt_telegram_bot.py",
    "clawdjarvis_telegram_bot.py",
    "clawdfriday_telegram_bot.py",
]

FIXES = [
    ("from shared.cost_tracker import CostTracker", "from shared.cost_tracker import ClawdBotCostTracker as CostTracker"),
    ("from shared.self_healing import SelfHealing", "from shared.self_healing import LogErrorDetector as SelfHealing"),
]

for filename in BOTS:
    path = f"/root/clawdbots/{filename}"
    with open(path, "r") as f:
        content = f.read()

    changed = False
    for old, new in FIXES:
        if old in content:
            content = content.replace(old, new)
            changed = True

    if changed:
        with open(path, "w") as f:
            f.write(content)
        print(f"FIXED: {filename}")
    else:
        print(f"SKIP: {filename} (already fixed or not present)")
