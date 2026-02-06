"""Wire cost_tracker, self_healing, error_handler, and message_queue into all 3 bots."""
import sys

BOTS = {
    "clawdmatt_telegram_bot.py": "clawdmatt",
    "clawdjarvis_telegram_bot.py": "clawdjarvis",
    "clawdfriday_telegram_bot.py": "clawdfriday",
}

WIRE_BLOCK = '''
# === Shared Module Wiring (auto-injected) ===
try:
    from shared.cost_tracker import CostTracker
    _cost_tracker = CostTracker("{bot_name}")
    HAS_COST_TRACKER = True
except ImportError:
    HAS_COST_TRACKER = False
    _cost_tracker = None

try:
    from shared.self_healing import SelfHealing
    _self_healing = SelfHealing("{bot_name}")
    HAS_SELF_HEALING = True
except ImportError:
    HAS_SELF_HEALING = False
    _self_healing = None

try:
    from shared.error_handler import ErrorHandler
    _error_handler = ErrorHandler("{bot_name}")
    HAS_ERROR_HANDLER = True
except ImportError:
    HAS_ERROR_HANDLER = False
    _error_handler = None

try:
    from shared.message_queue import MessageQueue
    _message_queue = MessageQueue("{bot_name}")
    HAS_MESSAGE_QUEUE = True
except ImportError:
    HAS_MESSAGE_QUEUE = False
    _message_queue = None
# === End Shared Module Wiring ===
'''

MARKER = "# === Shared Module Wiring"

for filename, bot_name in BOTS.items():
    path = f"/root/clawdbots/{filename}"
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"SKIP: {filename} not found")
        continue

    if MARKER in content:
        print(f"SKIP: {filename} already has shared module wiring")
        continue

    block = WIRE_BLOCK.replace("{bot_name}", bot_name)

    # Insert after KaizenEngine block or after logger line
    if "KaizenEngine" in content and "HAS_KAIZEN" in content:
        # Find end of kaizen block
        idx = content.index("HAS_KAIZEN")
        # Find the next blank line after that
        newline_idx = content.find("\n\n", idx)
        if newline_idx == -1:
            newline_idx = content.find("\n", idx + 10) + 1
        else:
            newline_idx += 1
        content = content[:newline_idx] + block + content[newline_idx:]
    elif "logger = logging.getLogger" in content:
        marker_line = "logger = logging.getLogger(__name__)"
        idx = content.index(marker_line)
        end = content.index("\n", idx) + 1
        content = content[:end] + block + content[end:]
    else:
        content = block + content

    with open(path, "w") as f:
        f.write(content)
    print(f"DONE: {filename} wired with cost_tracker, self_healing, error_handler, message_queue")
