"""Wire KaizenEngine into all 3 bot error handlers."""
import sys

BOTS = {
    "clawdmatt_telegram_bot.py": "clawdmatt",
    "clawdjarvis_telegram_bot.py": "clawdjarvis",
    "clawdfriday_telegram_bot.py": "clawdfriday",
}

for filename, bot_name in BOTS.items():
    path = f"/root/clawdbots/{filename}"
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"SKIP: {filename} not found")
        continue

    if "KaizenEngine" in content:
        print(f"SKIP: {filename} already has KaizenEngine")
        continue

    # Add kaizen import after existing auth import block
    kaizen_import = """
# Kaizen self-improvement
try:
    from bots.shared.kaizen import KaizenEngine
    _kaizen_engine = KaizenEngine('%s')
    HAS_KAIZEN = True
except ImportError:
    HAS_KAIZEN = False
    _kaizen_engine = None
""" % bot_name

    # Insert after logger line
    marker = "logger = logging.getLogger(__name__)"
    if marker in content:
        idx = content.index(marker)
        end = content.index("\n", idx) + 1
        # Check if kaizen import already exists nearby
        content = content[:end] + kaizen_import + content[end:]
    else:
        print(f"WARN: No logger marker in {filename}, appending import at top")
        content = kaizen_import + content

    with open(path, "w") as f:
        f.write(content)
    print(f"DONE: {filename} wired with KaizenEngine")
