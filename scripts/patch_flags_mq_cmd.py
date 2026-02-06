"""Add /flags and /mq commands to Matt's bot."""

BOT_FILE = "/root/clawdbots/clawdmatt_telegram_bot.py"

with open(BOT_FILE, "r") as f:
    content = f.read()

if "handle_flags" in content:
    print("SKIP: /flags already exists")
else:
    flags_code = '''
@bot.message_handler(commands=['flags'])
async def handle_flags(message):
    """Manage feature flags."""
    if not _check_auth(message.from_user.id, AuthorizationLevel.ADMIN):
        await _safe_reply(message, "Admin only.")
        return
    try:
        from shared.feature_flags import FeatureFlags
        ff = FeatureFlags("clawdmatt")
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        if len(args) >= 2:
            flag_name = args[0]
            action = args[1].lower()
            if action in ("on", "true", "1"):
                scope = args[2] if len(args) > 2 else "global"
                ff.set_flag(flag_name, True, scope=scope)
                await _safe_reply(message, f"Flag '{flag_name}' ENABLED (scope={scope})")
            elif action in ("off", "false", "0"):
                scope = args[2] if len(args) > 2 else "global"
                ff.set_flag(flag_name, False, scope=scope)
                await _safe_reply(message, f"Flag '{flag_name}' DISABLED (scope={scope})")
            else:
                await _safe_reply(message, "Usage: /flags <name> <on|off> [scope]")
        else:
            flags = ff.list_flags()
            if not flags:
                await _safe_reply(message, "No flags set. Use: /flags <name> <on|off> [scope]")
            else:
                lines = ["FEATURE FLAGS\\n"]
                for f in flags:
                    status = "ON" if f["enabled"] else "OFF"
                    lines.append(f"  {f['name']} = {status} (scope={f['scope']}, rollout={f['rollout_pct']}%)")
                await _safe_reply(message, "\\n".join(lines))
    except Exception as e:
        await _safe_reply(message, f"Error: {e}")

'''

    marker = "@bot.message_handler(func=lambda message: True)"
    if marker in content:
        content = content.replace(marker, flags_code + marker)
        print("DONE: Added /flags command")
    else:
        print("WARN: Could not find insertion point for /flags")

if "handle_mq" in content:
    print("SKIP: /mq already exists")
else:
    mq_code = '''
@bot.message_handler(commands=['mq'])
async def handle_mq(message):
    """Message queue status and operations."""
    if not _check_auth(message.from_user.id, AuthorizationLevel.OPERATOR):
        await _safe_reply(message, "Operator+ only.")
        return
    try:
        from shared.message_queue import MessageQueue
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        if args and args[0] == "send" and len(args) >= 3:
            target = args[1]
            msg_text = " ".join(args[2:])
            mq = MessageQueue("matt")
            mid = mq.send(target, {"type": "command", "text": msg_text})
            await _safe_reply(message, f"Sent msg #{mid} to {target}")
        elif args and args[0] == "read":
            bot_name = args[1] if len(args) > 1 else "clawdmatt"
            mq = MessageQueue(bot_name)
            msgs = mq.receive(mark_read=False, limit=5)
            if not msgs:
                await _safe_reply(message, f"No unread messages for {bot_name}")
            else:
                lines = [f"MESSAGES FOR {bot_name}\\n"]
                for m in msgs:
                    lines.append(f"  #{m['id']} from {m['sender']}: {m['payload']}")
                await _safe_reply(message, "\\n".join(lines))
        else:
            lines = ["MESSAGE QUEUE STATUS\\n"]
            for bn in ["clawdmatt", "clawdjarvis", "clawdfriday"]:
                mq = MessageQueue(bn)
                s = mq.stats()
                lines.append(f"  {bn}: {s['unread']} unread, {s['total_received']} total, {s['total_sent']} sent")
            lines.append("\\nCommands:")
            lines.append("  /mq send <bot> <message>")
            lines.append("  /mq read [bot]")
            await _safe_reply(message, "\\n".join(lines))
    except Exception as e:
        await _safe_reply(message, f"Error: {e}")

'''

    marker = "@bot.message_handler(func=lambda message: True)"
    if marker in content:
        content = content.replace(marker, mq_code + marker)
        print("DONE: Added /mq command")
    else:
        print("WARN: Could not find insertion point for /mq")

with open(BOT_FILE, "w") as f:
    f.write(content)
