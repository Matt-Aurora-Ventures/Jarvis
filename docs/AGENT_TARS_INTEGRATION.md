# Agent TARS Integration with Jarvis

Agent TARS provides GUI automation capabilities that can enhance Jarvis's automation features.

## What is Agent TARS?

UI-TARS-desktop is ByteDance's open-source multimodal AI agent that provides:
- Vision-language model powered GUI automation
- Browser control (hybrid DOM + visual grounding)
- Desktop application control
- Task planning and execution
- MCP (Model Context Protocol) integration

## Installation Status

✅ **Installed:** Agent TARS CLI v0.3.0
✅ **Configured:** Claude 3.7 Sonnet integration
✅ **Location:** `C:\Users\lucid\.agent-tars\`

## Quick Start

### Launch Agent TARS

**Option 1: Using scripts**
```cmd
REM Windows CMD
scripts\start_agent_tars.bat

REM Windows PowerShell
scripts\start_agent_tars.ps1
```

**Option 2: Direct command**
```bash
agent-tars --config "C:\Users\lucid\.agent-tars\agent.config.json" --open
```

### Environment Setup

Ensure `ANTHROPIC_API_KEY` is set:
```powershell
$env:ANTHROPIC_API_KEY = "your-api-key-here"
```

## Use Cases for Jarvis

### 1. Trading Web UI Automation

Automate interactions with the Jarvis trading interface (http://127.0.0.1:5001):

```bash
# Launch Agent TARS and give it a task
agent-tars --headless --input "Navigate to http://127.0.0.1:5001 and check the current portfolio balance"
```

**Example Tasks:**
- Monitor portfolio values
- Execute trades via the web UI
- Check position statuses
- Capture screenshots of charts

### 2. System Control Deck Automation

Automate the system control deck (http://127.0.0.1:5000):

```bash
agent-tars --headless --input "Open the system control deck and enable the debug toggle"
```

**Example Tasks:**
- Toggle configuration flags
- Monitor system health
- Execute mission control tasks
- Review security logs

### 3. Browser-Based Trading Research

Automate token research and analysis:

```bash
agent-tars --headless --input "Search for token $TOKEN_ADDRESS on Birdeye and extract the 24h volume"
```

**Example Tasks:**
- Token research on Birdeye/DEXScreener
- Social media sentiment gathering
- Price chart analysis
- Holder distribution checks

### 4. Desktop Application Control

Control desktop applications (Discord, Telegram Desktop, trading platforms):

```bash
agent-tars --headless --input "Open Discord and check the #trading channel for new messages"
```

**Example Tasks:**
- Monitor Discord channels
- Interact with Telegram Desktop
- Control browser windows
- Manage multiple trading platforms

## Integration Patterns

### Pattern 1: Agent TARS as a Python Subprocess

Call Agent TARS from Python code:

```python
import subprocess
import json

def run_agent_tars_task(task: str) -> dict:
    """Execute a task using Agent TARS and return the result."""
    cmd = [
        "agent-tars",
        "--headless",
        "--input", task,
        "--config", r"C:\Users\lucid\.agent-tars\agent.config.json",
        "--format", "json"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

# Example usage
result = run_agent_tars_task("Navigate to the trading UI and get the current SOL balance")
print(result)
```

### Pattern 2: Agent TARS Server Mode

Run Agent TARS as an API server:

```bash
# Start the server
agent-tars serve --port 8888 --config "C:\Users\lucid\.agent-tars\agent.config.json"
```

Then call it via HTTP from Python:

```python
import requests

def agent_tars_api_call(task: str) -> dict:
    """Call Agent TARS API with a task."""
    response = requests.post(
        "http://localhost:8888/api/run",
        json={"input": task}
    )
    return response.json()

# Example usage
result = agent_tars_api_call("Check the portfolio on the trading UI")
```

### Pattern 3: MCP Integration

Agent TARS supports MCP (Model Context Protocol) which can be integrated with Jarvis's existing MCP servers.

**Configure MCP servers in agent.config.json:**
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/workspace"]
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://..."]
    }
  }
}
```

## Jarvis Integration Examples

### Example 1: Automated Token Research

```python
# In bots/buy_tracker/sentiment_report.py

async def enhanced_token_research(token_address: str) -> dict:
    """Use Agent TARS to gather comprehensive token data."""

    task = f"""
    Research token {token_address}:
    1. Navigate to birdeye.so and search for the token
    2. Extract: price, 24h volume, liquidity, holder count
    3. Check Twitter/X for recent mentions
    4. Return data as JSON
    """

    result = run_agent_tars_task(task)
    return result
```

### Example 2: Web UI Monitoring

```python
# In bots/supervisor.py

async def monitor_trading_ui_health():
    """Use Agent TARS to monitor the trading web UI."""

    task = """
    Navigate to http://127.0.0.1:5001 and verify:
    1. Page loads successfully
    2. Portfolio balance is visible
    3. Position table is populated
    4. No error messages displayed
    Return health status as JSON
    """

    health = run_agent_tars_task(task)
    return health["status"] == "healthy"
```

### Example 3: Automated Screenshot Capture

```python
# In core/observability/metrics.py

async def capture_trading_ui_screenshot(filename: str):
    """Capture a screenshot of the trading UI using Agent TARS."""

    task = f"""
    1. Navigate to http://127.0.0.1:5001
    2. Wait for page to fully load
    3. Take a screenshot and save as {filename}
    """

    run_agent_tars_task(task)
    print(f"Screenshot saved: {filename}")
```

## Configuration for Jarvis

Add Agent TARS configuration to Jarvis environment:

```bash
# In .env or lifeos/config/bot.env

AGENT_TARS_ENABLED=true
AGENT_TARS_CONFIG_PATH=C:\Users\lucid\.agent-tars\agent.config.json
AGENT_TARS_PORT=8888
AGENT_TARS_MODE=server  # or "headless"
```

## Next Steps

1. **Test Basic Functionality**
   ```bash
   agent-tars --headless --input "Open Chrome and navigate to google.com"
   ```

2. **Test Trading UI Access**
   ```bash
   # Start trading UI first
   cd web && python trading_web.py &

   # Then test with Agent TARS
   agent-tars --headless --input "Navigate to http://127.0.0.1:5001 and describe what you see"
   ```

3. **Create Jarvis Integration Module**
   - Create `core/automation/agent_tars_client.py`
   - Implement subprocess/API wrappers
   - Add to supervisor orchestration

4. **Build Automation Workflows**
   - Token research automation
   - Portfolio monitoring
   - Trade execution verification
   - System health checks

## Troubleshooting

### Agent TARS Not Found
```bash
# Verify installation
agent-tars --version

# If not found, reinstall
npm install @agent-tars/cli@latest -g
```

### API Key Issues
```bash
# Check if key is set
echo $ANTHROPIC_API_KEY

# Set it if missing
export ANTHROPIC_API_KEY="your-key-here"
```

### Browser Control Issues
- Ensure Chrome/Chromium is installed
- Try `--browser.control visual-grounding` mode
- Check CDP endpoint availability

## Resources

- **Agent TARS Docs**: https://agent-tars.com
- **GitHub**: https://github.com/bytedance/UI-TARS-desktop
- **MCP Spec**: https://modelcontextprotocol.io
- **Jarvis Automation**: `core/automation/README.md`

## License

Agent TARS is licensed under Apache License 2.0 (compatible with Jarvis).
