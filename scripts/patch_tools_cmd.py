"""Patch Matt's bot with /tools command."""
import sys

BOT_FILE = "/root/clawdbots/clawdmatt_telegram_bot.py"

with open(BOT_FILE, "r") as f:
    content = f.read()

if "/tools" in content and "handle_tools" in content:
    print("Already has /tools")
    sys.exit(0)

tools_code = '''
@bot.message_handler(commands=['tools'])
async def handle_tools(message):
    """List available tools across all bots."""
    try:
        from bots.shared.plugin_registry import PluginRegistry
        reg = PluginRegistry()
        tools = reg.discover()
        if not tools:
            await _safe_reply(message, "No tools registered. Run register_default_tools() first.")
            return
        lines = ["AVAILABLE TOOLS\\n"]
        current_provider = ""
        for t in sorted(tools, key=lambda x: x.provider):
            if t.provider != current_provider:
                current_provider = t.provider
                lines.append(f"\\n[{current_provider.upper()}]")
            auth = " (auth)" if t.requires_auth else ""
            lines.append(f"  /{t.name}{auth} - {t.description}")
        lines.append(f"\\nTotal: {len(tools)} tools from {len(set(t.provider for t in tools))} bots")
        await _safe_reply(message, "\\n".join(lines))
    except Exception as e:
        await _safe_reply(message, f"Error: {e}")

'''

marker = "@bot.message_handler(func=lambda message: True)"
if marker in content:
    content = content.replace(marker, tools_code + marker)
    with open(BOT_FILE, "w") as f:
        f.write(content)
    print("Added /tools command")
else:
    print("Could not find insertion point")
    sys.exit(1)
