"""Fix ErrorHandler wiring - it takes error_log_path, not bot_name."""

BOTS = [
    "clawdmatt_telegram_bot.py",
    "clawdjarvis_telegram_bot.py",
    "clawdfriday_telegram_bot.py",
]

for filename in BOTS:
    path = f"/root/clawdbots/{filename}"
    with open(path, "r") as f:
        content = f.read()

    # Fix ErrorHandler - pass no args (uses default path)
    for bot_name in ["clawdmatt", "clawdjarvis", "clawdfriday"]:
        old = f'_error_handler = ErrorHandler("{bot_name}")'
        new = '_error_handler = ErrorHandler()'
        if old in content:
            content = content.replace(old, new)
            print(f"FIXED: {filename} ErrorHandler()")

    # Also fix SelfHealing if it has same issue - check its signature
    # SelfHealing might also not take bot_name as first arg

    with open(path, "w") as f:
        f.write(content)

# Also check SelfHealing signature
try:
    import inspect
    from bots.shared.self_healing import SelfHealing
    sig = inspect.signature(SelfHealing.__init__)
    params = list(sig.parameters.keys())
    print(f"SelfHealing.__init__ params: {params}")
except Exception as e:
    print(f"SelfHealing check: {e}")

# Check CostTracker signature
try:
    from bots.shared.cost_tracker import CostTracker
    sig = inspect.signature(CostTracker.__init__)
    params = list(sig.parameters.keys())
    print(f"CostTracker.__init__ params: {params}")
except Exception as e:
    print(f"CostTracker check: {e}")
