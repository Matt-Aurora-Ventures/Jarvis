# Agent TARS Quick Start Guide

## ✅ Installation Complete

**UI-TARS-desktop** (Agent TARS CLI v0.3.0) has been successfully installed and configured for Claude.

## What is Agent TARS?

Agent TARS is ByteDance's open-source multimodal AI agent that provides:
- 🖥️ **GUI Automation**: Control desktop applications using vision-language models
- 🌐 **Browser Control**: Hybrid mode (visual grounding + DOM manipulation)
- 🧠 **Task Planning**: Complex task decomposition and execution
- 🔌 **MCP Integration**: Model Context Protocol for external tools
- 🔍 **Web Search**: Built-in search capabilities

## Quick Start

### 1. Set Your API Key

**PowerShell:**
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

**CMD:**
```cmd
set ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 2. Launch Agent TARS

**Option A: Web UI Mode (Recommended)**
```bash
agent-tars --config "C:\Users\lucid\.agent-tars\agent.config.json" --open
```
This opens a web interface at http://localhost:8888

**Option B: Use the Launch Scripts**
```cmd
REM Windows CMD
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts\start_agent_tars.bat

REM Windows PowerShell
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts\start_agent_tars.ps1
```

**Option C: Headless Mode (CLI)**
```bash
agent-tars --headless --input "your task here" --config "C:\Users\lucid\.agent-tars\agent.config.json"
```

**Option D: Server Mode (API)**
```bash
agent-tars serve --port 8888 --config "C:\Users\lucid\.agent-tars\agent.config.json"
```

## Example Tasks

### Example 1: Simple Browser Task
```bash
agent-tars --headless --input "Open Chrome and navigate to github.com" \
  --config "C:\Users\lucid\.agent-tars\agent.config.json"
```

### Example 2: Jarvis Trading UI Check
```bash
# First start the trading UI
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\web
python trading_web.py &

# Then use Agent TARS to interact with it
agent-tars --headless \
  --input "Navigate to http://127.0.0.1:5001 and check the current SOL balance" \
  --config "C:\Users\lucid\.agent-tars\agent.config.json"
```

### Example 3: Token Research
```bash
agent-tars --headless \
  --input "Search Google for 'Solana token KR8TIV' and summarize the results" \
  --config "C:\Users\lucid\.agent-tars\agent.config.json" \
  --format json
```

### Example 4: Interactive Web UI Mode
```bash
agent-tars --open --config "C:\Users\lucid\.agent-tars\agent.config.json"
```
Then type your tasks in the web interface.

## Configuration

Your configuration is located at: `C:\Users\lucid\.agent-tars\agent.config.json`

**Current Settings:**
- **Model**: Claude 3.7 Sonnet (Anthropic)
- **Browser Control**: Hybrid mode (visual + DOM)
- **Planning**: Enabled
- **Search**: Browser-based
- **Streaming**: Enabled
- **Reasoning**: Enabled

## Integration with Jarvis

Agent TARS can enhance Jarvis automation:

### Use Case 1: Automated Trading UI Monitoring
```python
# In your Python code
import subprocess

def check_trading_ui():
    result = subprocess.run([
        "agent-tars", "--headless",
        "--input", "Check http://127.0.0.1:5001 for portfolio balance",
        "--config", r"C:\Users\lucid\.agent-tars\agent.config.json",
        "--format", "json"
    ], capture_output=True, text=True)
    return result.stdout
```

### Use Case 2: Token Research Automation
```python
def research_token(address: str):
    task = f"Search Birdeye for token {address} and extract 24h volume and price"
    result = subprocess.run([
        "agent-tars", "--headless",
        "--input", task,
        "--config", r"C:\Users\lucid\.agent-tars\agent.config.json"
    ], capture_output=True, text=True)
    return result.stdout
```

### Use Case 3: Desktop App Control
```python
def check_telegram_messages():
    result = subprocess.run([
        "agent-tars", "--headless",
        "--input", "Open Telegram Desktop and check for new messages",
        "--config", r"C:\Users\lucid\.agent-tars\agent.config.json"
    ], capture_output=True, text=True)
    return result.stdout
```

## Available Commands

```bash
# Run an agent task
agent-tars [run] [task]

# Start server mode
agent-tars serve --port 8888

# Send a direct request
agent-tars request --input "your query"

# Manage workspace
agent-tars workspace --init
agent-tars workspace --status

# Get help
agent-tars --help
agent-tars serve --help
```

## Advanced Options

### Browser Control Modes
```bash
# Hybrid (visual + DOM) - default
--browser.control hybrid

# DOM only
--browser.control dom

# Visual grounding only
--browser.control visual-grounding
```

### Debug Mode
```bash
agent-tars --debug --input "your task" --config "..."
```

### Custom Model
```bash
agent-tars --provider anthropic \
  --model claude-3-7-sonnet-latest \
  --apiKey $ANTHROPIC_API_KEY
```

### Include Logs in Output
```bash
agent-tars --headless --input "task" \
  --include-logs \
  --format json
```

## Troubleshooting

### Issue: API Key Not Found
**Solution:**
```powershell
# Set the environment variable
$env:ANTHROPIC_API_KEY = "your-key-here"

# Or add to your .env file
echo "ANTHROPIC_API_KEY=your-key-here" >> .env
```

### Issue: Port 8888 Already in Use
**Solution:**
```bash
# Use a different port
agent-tars --port 9999 --config "..." --open
```

### Issue: Browser Control Fails
**Solution:**
1. Close all Chrome/Chromium instances
2. Try visual-grounding only mode:
   ```bash
   agent-tars --browser.control visual-grounding
   ```
3. Check if Chrome is installed

### Issue: Command Not Found
**Solution:**
```bash
# Verify installation
npm list -g @agent-tars/cli

# Reinstall if needed
npm install @agent-tars/cli@latest -g
```

## Files Created

| File | Purpose |
|------|---------|
| `C:\Users\lucid\.agent-tars\agent.config.json` | Main configuration |
| `C:\Users\lucid\.agent-tars\README.md` | Documentation |
| `C:\Users\lucid\.agent-tars\workspace\` | Agent workspace |
| `scripts\start_agent_tars.bat` | Windows CMD launcher |
| `scripts\start_agent_tars.ps1` | PowerShell launcher |
| `docs\AGENT_TARS_INTEGRATION.md` | Jarvis integration guide |
| `docs\AGENT_TARS_QUICKSTART.md` | This file |

## Next Steps

1. **Test Basic Functionality**
   ```bash
   agent-tars --headless --input "What is 2+2?"
   ```

2. **Try Web UI Mode**
   ```bash
   agent-tars --open --config "C:\Users\lucid\.agent-tars\agent.config.json"
   ```

3. **Test Browser Control**
   ```bash
   agent-tars --headless --input "Open google.com and search for Anthropic Claude"
   ```

4. **Integrate with Jarvis**
   - See `docs/AGENT_TARS_INTEGRATION.md` for detailed examples
   - Create Python wrappers in `core/automation/agent_tars_client.py`
   - Add to supervisor orchestration

## Resources

- **Official Documentation**: https://agent-tars.com
- **GitHub Repository**: https://github.com/bytedance/UI-TARS-desktop
- **Quick Start Guide**: https://agent-tars.com/docs/quick-start
- **MCP Protocol**: https://modelcontextprotocol.io

## Support

For issues or questions:
1. Check the official docs: https://agent-tars.com
2. GitHub Issues: https://github.com/bytedance/UI-TARS-desktop/issues
3. Jarvis integration questions: See `docs/AGENT_TARS_INTEGRATION.md`

---

**Installation Date**: February 3, 2026
**Installed Version**: Agent TARS CLI v0.3.0
**Configured For**: Claude 3.7 Sonnet (Anthropic)
