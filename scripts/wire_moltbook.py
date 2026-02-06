"""Wire moltbook learning journal into all 3 bots + add /learn command to Matt."""

BOTS = {
    "clawdmatt_telegram_bot.py": "clawdmatt",
    "clawdjarvis_telegram_bot.py": "clawdjarvis",
    "clawdfriday_telegram_bot.py": "clawdfriday",
}

MOLTBOOK_IMPORT = '''
# === Moltbook Wiring ===
try:
    from shared.moltbook import store_learning, search_learnings, get_relevant_context
    HAS_MOLTBOOK = True
except ImportError:
    HAS_MOLTBOOK = False
# === End Moltbook ===
'''

MOLTBOOK_MARKER = "# === Moltbook Wiring ==="

for filename, bot_name in BOTS.items():
    path = f"/root/clawdbots/{filename}"
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"SKIP: {filename} not found")
        continue

    if MOLTBOOK_MARKER in content:
        print(f"SKIP: {filename} already has moltbook")
        continue

    # Insert after sleep compute block or shared module wiring
    for end_mark in ["# === End Sleep Compute ===", "# === End Shared Module Wiring ==="]:
        if end_mark in content:
            idx = content.index(end_mark) + len(end_mark)
            next_nl = content.index("\n", idx) + 1
            content = content[:next_nl] + MOLTBOOK_IMPORT + content[next_nl:]
            break
    else:
        content = MOLTBOOK_IMPORT + content

    with open(path, "w") as f:
        f.write(content)
    print(f"DONE: {filename} wired with moltbook")

# Add /learn command to Matt
matt_path = "/root/clawdbots/clawdmatt_telegram_bot.py"
with open(matt_path, "r") as f:
    content = f.read()

if "handle_learn" in content:
    print("SKIP: /learn already exists")
else:
    learn_cmd = '''
@bot.message_handler(commands=['learn'])
async def handle_learn(message):
    """Store or search learnings in the moltbook."""
    if not _check_auth(message.from_user.id, AuthorizationLevel.OPERATOR):
        await _safe_reply(message, "Operator+ only.")
        return
    try:
        if not HAS_MOLTBOOK:
            await _safe_reply(message, "Moltbook not available.")
            return
        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            await _safe_reply(message, "Usage:\\n  /learn store <text> - Store a learning\\n  /learn search <query> - Search learnings\\n  /learn context <topic> - Get relevant context")
            return
        action = args[1].lower()
        text = args[2] if len(args) > 2 else ""
        if action == "store" and text:
            result = await store_learning(topic="telegram_learning", content=text, source="telegram")
            await _safe_reply(message, f"Stored learning: {result.get('id', 'ok')}")
        elif action == "search" and text:
            results = await search_learnings(text, limit=5)
            if not results:
                await _safe_reply(message, f"No learnings found for: {text}")
            else:
                lines = [f"LEARNINGS ({len(results)} results)\\n"]
                for r in results[:5]:
                    content_preview = str(r.get("content", r.get("text", "")))[:100]
                    lines.append(f"  - {content_preview}")
                await _safe_reply(message, "\\n".join(lines))
        elif action == "context" and text:
            ctx = await get_relevant_context(text)
            import json as _json
            ctx_str = _json.dumps(ctx, indent=2, default=str)[:2000] if ctx else "No context found"
            await _safe_reply(message, f"Context for '{text}':\\n{ctx_str}")
        else:
            await _safe_reply(message, "Usage: /learn store|search|context <text>")
    except Exception as e:
        await _safe_reply(message, f"Error: {e}")

'''
    marker = "@bot.message_handler(func=lambda message: True)"
    if marker in content:
        content = content.replace(marker, learn_cmd + marker)
        with open(matt_path, "w") as f:
            f.write(content)
        print("DONE: Added /learn command to Matt")
    else:
        print("WARN: Could not find insertion point for /learn")
