"""Patch Matt's bot with /spawn command."""
import sys

BOT_FILE = "/root/clawdbots/clawdmatt_telegram_bot.py"

with open(BOT_FILE, "r") as f:
    content = f.read()

if "/spawn" in content:
    print("Already has /spawn")
    sys.exit(0)

spawn_code = '''
@bot.message_handler(commands=['spawn'])
async def handle_spawn(message):
    """Spawn parallel tasks across bots."""
    if not _check_auth(message, AuthorizationLevel.ADMIN):
        await _safe_reply(message, "Unauthorized. Admin access required for spawn.")
        return
    text = (message.text or "").replace("/spawn", "", 1).strip()
    if not text:
        await _safe_reply(message, "Usage: /spawn <complex request>\\n\\nI will detect which bots to involve and run tasks in parallel.")
        return

    try:
        from bots.shared.task_spawner import TaskSpawner, Task, detect_parallel_needs
        bots_needed = detect_parallel_needs(text)
        if not bots_needed:
            await _safe_reply(message, "Could not determine which specialists to involve.")
            return

        bot_names = ", ".join(b.upper() for b in bots_needed)
        await _safe_reply(message, f"Spawning tasks to: {bot_names}...")

        spawner = TaskSpawner()
        tasks = [Task(target_bot=b, instruction=text) for b in bots_needed]
        for t in tasks:
            spawner._log_task(t, 0)

        response = f"Tasks created for {len(tasks)} specialist(s):\\n"
        for t in tasks:
            response += f"  -> {t.target_bot.upper()}: {t.task_id}\\n"
        response += "\\nNote: Full async execution coming in Phase 9.17"
        await _safe_reply(message, response)
    except Exception as e:
        logger.error(f"Spawn error: {e}")
        await _safe_reply(message, f"Spawn failed: {e}")

'''

marker = "@bot.message_handler(func=lambda message: True)"
if marker in content:
    content = content.replace(marker, spawn_code + marker)
    with open(BOT_FILE, "w") as f:
        f.write(content)
    print("Added /spawn command to Matt")
else:
    print("Could not find insertion point")
    sys.exit(1)
