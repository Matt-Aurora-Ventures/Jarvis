"""Wire sleep_compute into all 3 bots and add /sleep command to Matt."""
import sys

BOTS = {
    "clawdmatt_telegram_bot.py": "clawdmatt",
    "clawdjarvis_telegram_bot.py": "clawdjarvis",
    "clawdfriday_telegram_bot.py": "clawdfriday",
}

SLEEP_IMPORT = '''
# === Sleep Compute Wiring ===
try:
    from shared.sleep_compute import SleepComputeManager
    _sleep_compute = SleepComputeManager()
    HAS_SLEEP_COMPUTE = True
except ImportError:
    HAS_SLEEP_COMPUTE = False
    _sleep_compute = None
# === End Sleep Compute ===
'''

SLEEP_MARKER = "# === Sleep Compute Wiring ==="

for filename, bot_name in BOTS.items():
    path = f"/root/clawdbots/{filename}"
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"SKIP: {filename} not found")
        continue

    if SLEEP_MARKER in content:
        print(f"SKIP: {filename} already has sleep_compute")
        continue

    # Insert after the shared module wiring block
    end_marker = "# === End Shared Module Wiring ==="
    if end_marker in content:
        idx = content.index(end_marker) + len(end_marker)
        next_newline = content.index("\n", idx) + 1
        content = content[:next_newline] + SLEEP_IMPORT + content[next_newline:]
    else:
        # Fallback: insert after logger
        marker = "logger = logging.getLogger(__name__)"
        if marker in content:
            idx = content.index(marker)
            end = content.index("\n", idx) + 1
            content = content[:end] + SLEEP_IMPORT + content[end:]
        else:
            content = SLEEP_IMPORT + content

    with open(path, "w") as f:
        f.write(content)
    print(f"DONE: {filename} wired with sleep_compute")

# Now add /sleep command to Matt
matt_path = "/root/clawdbots/clawdmatt_telegram_bot.py"
with open(matt_path, "r") as f:
    content = f.read()

if "handle_sleep" in content:
    print("SKIP: /sleep command already exists")
else:
    sleep_cmd = '''
@bot.message_handler(commands=['sleep'])
async def handle_sleep(message):
    """Manage sleep-time compute tasks."""
    if not _check_auth(message.from_user.id, AuthorizationLevel.OPERATOR):
        await _safe_reply(message, "Operator+ only.")
        return
    try:
        if not HAS_SLEEP_COMPUTE or not _sleep_compute:
            await _safe_reply(message, "Sleep compute not available.")
            return
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        if args and args[0] == "queue":
            task_desc = " ".join(args[1:]) if len(args) > 1 else None
            if not task_desc:
                await _safe_reply(message, "Usage: /sleep queue <task description>")
                return
            from shared.sleep_compute import TaskType
            _sleep_compute.queue_task(
                task_type=TaskType.ANALYSIS,
                params={"description": task_desc, "source": "telegram", "user": message.from_user.id},
            )
            await _safe_reply(message, f"Queued sleep task: {task_desc}")
        elif args and args[0] == "run":
            processed = await _sleep_compute.check_and_execute_idle_tasks()
            await _safe_reply(message, f"Processed {processed} sleep tasks.")
        else:
            pending = len(_sleep_compute.get_pending_tasks())
            completed = len(_sleep_compute._completed)
            lines = [
                "SLEEP COMPUTE STATUS",
                f"  Pending: {pending}",
                f"  Completed: {completed}",
                "",
                "Commands:",
                "  /sleep queue <task> - Queue a task",
                "  /sleep run - Process pending tasks",
            ]
            await _safe_reply(message, "\\n".join(lines))
    except Exception as e:
        await _safe_reply(message, f"Error: {e}")

'''
    marker = "@bot.message_handler(func=lambda message: True)"
    if marker in content:
        content = content.replace(marker, sleep_cmd + marker)
        with open(matt_path, "w") as f:
            f.write(content)
        print("DONE: Added /sleep command to Matt")
    else:
        print("WARN: Could not find insertion point for /sleep")
