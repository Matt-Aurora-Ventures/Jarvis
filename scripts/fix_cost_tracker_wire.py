"""Fix CostTracker wiring - it takes storage_path, not bot_name."""

BOTS = [
    "clawdmatt_telegram_bot.py",
    "clawdjarvis_telegram_bot.py",
    "clawdfriday_telegram_bot.py",
]

for filename in BOTS:
    path = f"/root/clawdbots/{filename}"
    with open(path, "r") as f:
        content = f.read()

    for bot_name in ["clawdmatt", "clawdjarvis", "clawdfriday"]:
        old = f'_cost_tracker = CostTracker("{bot_name}")'
        new = '_cost_tracker = CostTracker()'
        if old in content:
            content = content.replace(old, new)
            print(f"FIXED: {filename} CostTracker()")

    with open(path, "w") as f:
        f.write(content)
