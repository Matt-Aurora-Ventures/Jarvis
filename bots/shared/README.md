# ClawdBots Shared Module Library

> Common capabilities for autonomous ClawdBot agents (Jarvis CTO, Matt COO, Friday CMO)

## Overview

The `bots/shared/` module provides reusable infrastructure for all ClawdBots running on VPS. These modules enable coordination, self-healing, remote control, cost tracking, and inter-bot communication.

**Three ClawdBots:**
- **Jarvis (CTO)** - Technical orchestration, trading, system control
- **Matt (COO)** - Operations, PR filtering, task coordination
- **Friday (CMO)** - Marketing, communications, content creation

All bots share these capabilities through the unified module library.

---

## Quick Start

### Installation

The shared modules are already included in the ClawdBots deployment. No additional installation required.

### Basic Usage

```python
# Import shared capabilities
from bots.shared import (
    # Computer control
    browse_web,
    control_computer,
    check_remote_status,

    # Inter-bot coordination
    BotCoordinator,
    BotRole,
    TaskPriority,
    get_coordinator,

    # Self-healing
    create_watchdog,
    ProcessWatchdog,

    # Cost tracking
    track_api_call,
    check_budget,
    get_cost_report,
)

# Example: Browse web from VPS
result = await browse_web("Go to coingecko.com and get SOL price")

# Example: Delegate task to another bot
coord = BotCoordinator(BotRole.JARVIS)
task_id = coord.delegate_task(
    to_bot=BotRole.FRIDAY,
    description="Research competitor marketing strategy",
    priority=TaskPriority.HIGH,
)

# Example: Track API costs
cost = track_api_call("clawdjarvis", "openai", input_tokens=1500, output_tokens=800)
if not check_budget("clawdjarvis"):
    print("Budget exceeded!")
```

---

## Module Reference

### 1. Computer Control (`computer_capabilities.py`)

Control Daryl's Windows computer remotely from VPS via Tailscale.

#### Features

- **Browser Automation** - LLM navigates web pages like a human
- **Full Computer Control** - Execute any task on the Windows machine
- **Telegram Web Access** - Send messages from Daryl's personal account
- **Remote Status Monitoring** - Check if Windows machine is available

#### API

```python
from bots.shared import browse_web, control_computer, send_telegram_web

# Browser automation
result = await browse_web("Go to twitter.com and check notifications")
result = await browse_web("Search google for 'solana ecosystem news'")
result = await browse_web("Go to pump.fun and find trending tokens")

# Computer control
result = await control_computer("What files are in Downloads?")
result = await control_computer("Open calculator and compute 123 * 456")
result = await control_computer("Take a screenshot and save it")

# Telegram Web (from Daryl's account)
result = await send_telegram_web("Saved Messages", "Reminder: check portfolio")
result = await send_telegram_web("Trading Group", "SOL update...")

# Check availability
status = await check_remote_status()
if status["available"]:
    print(f"Windows machine online at {status['host']}")
```

#### Configuration

Set these environment variables on VPS:

```bash
JARVIS_LOCAL_IP=100.102.41.120        # Tailscale IP of Windows machine
JARVIS_REMOTE_PORT=8765                # Remote control server port
JARVIS_REMOTE_API_KEY=<secret-key>     # API authentication key
```

#### How It Works

1. ClawdBot on VPS calls `browse_web()` or `control_computer()`
2. HTTP request sent to Windows machine via Tailscale
3. `remote_control_server.py` running on Windows receives request
4. Claude Computer Use API executes task on Windows
5. Result returned to VPS bot

#### Use Cases

- Research via browser automation
- Send emails/messages from Daryl's accounts
- Check calendar/drive/cloud dashboards
- Deploy websites via SSH from Windows
- Monitor system status
- Take screenshots for debugging

---

### 2. Inter-Bot Coordination (`coordination.py`)

Coordinate tasks and messages between the three ClawdBots.

#### Features

- **Task Delegation** - Assign work between bots
- **Shared State** - File-based coordination at `/root/clawdbots/shared_state.json`
- **Bot Messaging** - Send messages between bots
- **Task Ownership** - Prevent duplicate work via claiming
- **Status Reporting** - Aggregate health of all bots

#### API

```python
from bots.shared import (
    BotCoordinator,
    BotRole,
    TaskPriority,
    TaskStatus,
    get_coordinator,
)

# Initialize coordinator for your bot
coord = BotCoordinator(BotRole.JARVIS)  # or MATT, FRIDAY

# Delegate a task
task_id = coord.delegate_task(
    to_bot=BotRole.FRIDAY,
    description="Create Twitter thread about new feature",
    priority=TaskPriority.HIGH,
    context={"feature": "AI trading", "tone": "excited"},
)

# Check for pending tasks (as Friday)
friday_coord = BotCoordinator(BotRole.FRIDAY)
pending = friday_coord.get_pending_tasks()
for task in pending:
    print(f"Task: {task.description}")
    friday_coord.claim_task(task.id)
    # ... do the work ...
    friday_coord.complete_task(task.id, result="Thread posted")

# Send message to another bot
coord.send_message(
    to_bot=BotRole.MATT,
    content="Campaign ready for review",
    related_task_id=task_id,
)

# Check messages
messages = coord.get_unread_messages()
for msg in messages:
    print(f"From {msg.from_bot.value}: {msg.content}")
    coord.mark_message_read(msg.id)

# Update status
coord.update_status(
    current_task="Monitoring trading positions",
    tasks_completed=42,
    tasks_pending=3,
)

# Heartbeat (call periodically)
coord.heartbeat()

# Generate status report
report = coord.generate_status_report()
print(report)
```

#### Bot Roles

| Role | Title | Responsibility |
|------|-------|----------------|
| `JARVIS` | CTO | Technical lead, trading, orchestration |
| `MATT` | COO | Operations, PR filtering, coordination |
| `FRIDAY` | CMO | Marketing, communications, content |

#### Task Priority Levels

- `CRITICAL` (1) - Immediate action required
- `HIGH` (2) - Important, handle soon
- `MEDIUM` (3) - Normal priority (default)
- `LOW` (4) - Can wait

#### Task Lifecycle

```
PENDING → CLAIMED → IN_PROGRESS → COMPLETED
                                 ↘ FAILED
```

#### Shared State File

Location: `/root/clawdbots/shared_state.json`

Structure:
```json
{
  "version": "1.0",
  "last_updated": "2026-02-02T10:30:00Z",
  "tasks": [...],
  "completed_tasks": [...],
  "messages": [...],
  "bot_statuses": {
    "jarvis": {...},
    "matt": {...},
    "friday": {...}
  }
}
```

Thread-safe with file locking (requires `filelock` package).

---

### 3. Self-Healing (`self_healing.py`)

Automatic process monitoring, health checks, and restart coordination.

#### Features

- **Health Monitoring** - Track memory, CPU, disk usage
- **Heartbeat System** - Periodic liveness signals
- **Error Detection** - Pattern matching in logs
- **Alert System** - Trigger callbacks when thresholds exceeded
- **Restart Policy** - Exponential backoff for crash recovery

#### API

```python
from bots.shared import (
    create_watchdog,
    ProcessWatchdog,
    SelfHealingConfig,
    HealthStatus,
)

# Quick setup with defaults
def my_alert_callback(alert_type, details):
    print(f"ALERT: {alert_type} - {details}")
    # Send Telegram notification, etc.

watchdog = create_watchdog(
    bot_name="clawdjarvis",
    memory_threshold_mb=256,
    cpu_threshold_percent=80,
    heartbeat_interval=30,
    alert_callback=my_alert_callback,
)

# Start monitoring
watchdog.start()

# Get status
status = watchdog.get_status()
print(status["health"])  # HEALTHY, DEGRADED, UNHEALTHY, CRITICAL

# Check log lines for errors
for line in log_output:
    errors = watchdog.check_log_line(line)
    for error in errors:
        print(f"Error detected: {error.name} ({error.severity})")

# Stop watchdog
watchdog.stop()
```

#### Advanced Configuration

```python
from bots.shared import SelfHealingConfig, ProcessWatchdog

config = SelfHealingConfig(
    bot_name="clawdjarvis",
    heartbeat_interval=30,          # Seconds between heartbeats
    health_check_interval=60,       # Seconds between health checks
    max_restart_attempts=3,         # Max restart attempts before giving up
    restart_cooldown=300,           # Seconds between restart attempts
    memory_threshold_mb=512,        # Memory alert threshold
    cpu_threshold_percent=80,       # CPU alert threshold
    heartbeat_dir=Path("/root/clawdbots/.heartbeats"),
)

watchdog = ProcessWatchdog(config)

# Register callbacks
watchdog.on_alert(lambda alert_type, details: send_telegram_alert(alert_type, details))
watchdog.on_restart(lambda: restart_bot())

watchdog.start()
```

#### Error Patterns

Built-in error detection patterns:

- `critical_error` - CRITICAL level logs
- `error_log` - ERROR level logs
- `exception` - Python tracebacks
- `memory_error` - Memory allocation failures
- `connection_error` - Network failures
- `timeout_error` - Operation timeouts
- `rate_limit` - API rate limiting
- `auth_error` - Authentication failures
- `telegram_conflict` - Polling conflicts (duplicate instance)

#### Custom Patterns

```python
from bots.shared import ErrorPattern

watchdog.error_detector.add_pattern(
    ErrorPattern(
        name="wallet_error",
        regex=r"WalletError|InsufficientFunds",
        severity="high",
        description="Solana wallet error",
    )
)
```

#### Heartbeat Files

Written to `/root/clawdbots/.heartbeats/<bot_name>.heartbeat`:

```json
{
  "bot_name": "clawdjarvis",
  "timestamp": "2026-02-02T10:30:45Z",
  "pid": 12345
}
```

External systems (systemd, cron) can monitor these files to detect dead processes.

---

### 4. Cost Tracking (`cost_tracker.py`)

Track API costs across OpenAI, Anthropic, X.AI, and enforce budget limits.

#### Features

- **Multi-Provider Tracking** - OpenAI, Anthropic, X.AI/Grok, Groq
- **Daily/Monthly Budgets** - Set limits per bot
- **Alert System** - Warn at 80% of daily limit
- **Cost Reports** - Generate detailed usage reports
- **Persistent Storage** - `/root/clawdbots/api_costs.json`

#### API

```python
from bots.shared import (
    track_api_call,
    get_daily_cost,
    get_monthly_cost,
    check_budget,
    get_cost_report,
    set_daily_limit,
)

# Track an API call
cost = track_api_call(
    bot_name="clawdmatt",
    api="openai",
    input_tokens=1500,
    output_tokens=800,
    model="gpt-4o",  # Optional, for specific pricing
)
print(f"Call cost: ${cost:.4f}")

# Set daily limit
set_daily_limit("clawdmatt", 10.0)  # $10/day

# Check budget before making expensive call
if check_budget("clawdmatt"):
    # Safe to make API call
    response = await openai_client.chat.completions.create(...)
    track_api_call("clawdmatt", "openai", ...)
else:
    print("Budget exceeded for today")

# Get costs
daily = get_daily_cost("clawdmatt")
monthly = get_monthly_cost("clawdmatt")
print(f"Today: ${daily:.2f} | Month: ${monthly:.2f}")

# Generate report
print(get_cost_report())
```

#### Cost Report Example

```
ClawdBots API Cost Report
==============================

Date: 2026-02-02
Daily Total: $3.4500

Per-Bot Breakdown:
--------------------
  clawdjarvis: $1.2000 / $10.00 (12.0%)
  clawdmatt: $1.8500 / $10.00 (18.5%)
  clawdfriday: $0.4000 / $10.00 (4.0%)

Monthly Total: $142.3400

Per-API Breakdown (today):
--------------------
  openai: $2.1000 (15 calls, 45000 tokens)
  anthropic: $0.9500 (8 calls, 28000 tokens)
  xai: $0.4000 (3 calls, 12000 tokens)
```

#### Pricing (Per 1K Tokens)

| Provider | Model | Input | Output |
|----------|-------|-------|--------|
| OpenAI | GPT-4 | $0.03 | $0.06 |
| OpenAI | GPT-4o | $0.015 | $0.06 |
| OpenAI | GPT-4o-mini | $0.00015 | $0.0006 |
| Anthropic | Claude Opus | $0.015 | $0.075 |
| Anthropic | Claude Sonnet | $0.003 | $0.015 |
| Anthropic | Claude Haiku | $0.00025 | $0.00125 |
| X.AI | Grok-2 | $0.03 | $0.06 |
| X.AI | Grok-3 | $0.001 | $0.001 |
| Groq | Llama | $0.00059 | $0.00079 |

#### Alert Callback

```python
from bots.shared.cost_tracker import get_tracker

def budget_alert(bot_name, current_cost, limit, percentage):
    message = f"⚠️ {bot_name} at {percentage*100:.1f}% of daily budget (${current_cost:.2f} / ${limit:.2f})"
    send_telegram_notification(message)

tracker = get_tracker()
tracker.set_alert_callback(budget_alert)
```

Default alert threshold: 80% of daily limit

---

### 5. Life Control Commands (`life_control_commands.py`)

Full autonomous control via Telegram commands for ClawdJarvis.

#### Features

- Universal `/do` command for natural language requests
- Google Suite integration (Gmail, Calendar, Drive)
- Server/website deployment
- Firebase/Google Cloud management
- Android phone control
- Solana wallet operations

#### Registration

```python
from bots.shared.life_control_commands import register_life_commands

# In your ClawdJarvis bot initialization
bot = TeleBot(token)
register_life_commands(bot)

# Now all life control commands are available
```

#### Commands

**Universal Control:**
- `/do <anything>` - Natural language control

**Google Suite:**
- `/email [request]` - Gmail operations
- `/calendar [request]` - Calendar management
- `/drive [request]` - Drive/Docs/Sheets
- `/firebase [request]` - Firebase projects
- `/cloud [request]` - Google Cloud Console
- `/billing` - Check GCP billing

**Servers & Websites:**
- `/deploy [request]` - Deploy websites
- `/host [request]` - Hostinger panel

**Devices:**
- `/computer [task]` - PC control
- `/browse [task]` - Browser automation
- `/phone [command]` - Android control (via ADB over Tailscale)
- `/screenshot` - Take screenshot

**Finance:**
- `/wallet [request]` - Solana wallet operations

#### Examples

```
/do Send John an email about tomorrow's meeting

/calendar add meeting with Bob on Friday at 3pm

/deploy latest changes to hostinger

/wallet check balance

/phone battery

/screenshot
```

All commands route to the remote control system and execute autonomously.

---

## Integration Examples

### Example 1: Multi-Bot Campaign

```python
# Matt (COO) orchestrates a campaign
from bots.shared import BotCoordinator, BotRole, TaskPriority

coord = BotCoordinator(BotRole.MATT)

# Delegate research to Friday
research_task = coord.delegate_task(
    to_bot=BotRole.FRIDAY,
    description="Research competitor pricing strategy",
    priority=TaskPriority.HIGH,
)

# Delegate technical analysis to Jarvis
analysis_task = coord.delegate_task(
    to_bot=BotRole.JARVIS,
    description="Analyze trading volume patterns",
    priority=TaskPriority.MEDIUM,
)

# Wait for completion (Friday's side)
friday_coord = BotCoordinator(BotRole.FRIDAY)
pending = friday_coord.get_pending_tasks()
for task in pending:
    if task.delegated_by == BotRole.MATT:
        friday_coord.claim_task(task.id)

        # Do the research
        result = await browse_web("Research competitor pricing...")

        friday_coord.complete_task(task.id, result=result)
        friday_coord.send_message(
            BotRole.MATT,
            f"Research complete: {result[:100]}...",
            related_task_id=task.id,
        )
```

### Example 2: Self-Healing Bot

```python
from bots.shared import create_watchdog

# Setup watchdog
def alert_handler(alert_type, details):
    if alert_type == "HIGH_MEMORY":
        print(f"Memory alert: {details['memory_mb']:.1f}MB")
        # Trigger garbage collection, restart services, etc.
    elif alert_type == "CRITICAL_STATUS":
        print("CRITICAL: Bot in critical state")
        # Emergency notification

watchdog = create_watchdog(
    bot_name="clawdjarvis",
    memory_threshold_mb=256,
    cpu_threshold_percent=80,
    alert_callback=alert_handler,
)

watchdog.start()

# Bot runs normally...
# Watchdog monitors in background

# On shutdown
watchdog.stop()
```

### Example 3: Budget-Aware API Usage

```python
from bots.shared import track_api_call, check_budget

async def query_llm(bot_name, prompt, use_expensive_model=False):
    # Check budget before expensive call
    if use_expensive_model and not check_budget(bot_name):
        print(f"{bot_name} over budget, using cheaper model")
        use_expensive_model = False

    if use_expensive_model:
        model = "gpt-4o"
        response = await openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        usage = response.usage
        track_api_call(
            bot_name,
            "openai",
            usage.prompt_tokens,
            usage.completion_tokens,
            model,
        )
    else:
        # Use cheaper model
        model = "gpt-4o-mini"
        response = await openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        usage = response.usage
        track_api_call(
            bot_name,
            "openai",
            usage.prompt_tokens,
            usage.completion_tokens,
            model,
        )

    return response.choices[0].message.content
```

### Example 4: Computer Control from Telegram

```python
from bots.shared import browse_web, control_computer
from telebot.async_telebot import AsyncTeleBot

bot = AsyncTeleBot(token)

@bot.message_handler(commands=['research'])
async def handle_research(message):
    query = message.text.split(' ', 1)[1] if ' ' in message.text else ''

    await bot.reply_to(message, f"🔍 Researching: {query}...")

    # Use browser automation on Windows machine
    result = await browse_web(f"""
        Go to Google and search for '{query}'.
        Open the top 3 results.
        Summarize the key findings.
    """)

    await bot.reply_to(message, f"📊 Results:\n\n{result[:3500]}")

@bot.message_handler(commands=['deploy'])
async def handle_deploy(message):
    await bot.reply_to(message, "🚀 Deploying website...")

    # Execute deployment on Windows machine
    result = await control_computer("""
        1. SSH to VPS
        2. cd /var/www/mysite
        3. git pull origin main
        4. npm run build
        5. systemctl restart nginx

        Report deployment status.
    """)

    await bot.reply_to(message, f"✅ Deployment:\n\n{result}")
```

---

## Configuration

### Environment Variables

**Computer Control:**
```bash
JARVIS_LOCAL_IP=100.102.41.120        # Windows machine Tailscale IP
JARVIS_REMOTE_PORT=8765                # Remote control server port
JARVIS_REMOTE_API_KEY=<secret-key>     # API authentication
```

**Coordination:**
```bash
# Uses default path: /root/clawdbots/shared_state.json
# Or override with CLAWDBOT_STATE_FILE
```

**Self-Healing:**
```bash
# Uses default: /root/clawdbots/.heartbeats
# No environment variables required
```

**Cost Tracking:**
```bash
# Uses default: /root/clawdbots/api_costs.json
# No environment variables required
```

### File Locations (VPS)

```
/root/clawdbots/
├── shared_state.json        # Inter-bot coordination
├── api_costs.json           # Cost tracking data
└── .heartbeats/             # Heartbeat files
    ├── clawdjarvis.heartbeat
    ├── clawdmatt.heartbeat
    └── clawdfriday.heartbeat
```

---

## Dependencies

All modules use Python standard library where possible. Optional dependencies:

- `aiohttp` - Required for computer control (HTTP requests)
- `psutil` - Required for health monitoring (memory/CPU metrics)
- `filelock` - Required for coordination (thread-safe file locking)

Install all:
```bash
pip install aiohttp psutil filelock
```

---

## Architecture

### Computer Control Flow

```
┌─────────────────┐          ┌──────────────────┐
│  ClawdBot (VPS) │          │ Windows Machine  │
│                 │          │ (Tailscale)      │
│  browse_web()   │ ─HTTP──> │ remote_control_  │
│  control_comp() │          │ server.py        │
└─────────────────┘          └────────┬─────────┘
                                      │
                             ┌────────▼─────────┐
                             │ Claude Computer  │
                             │ Use API          │
                             │ - Browser        │
                             │ - bash           │
                             │ - str_replace    │
                             └──────────────────┘
```

### Inter-Bot Coordination Flow

```
┌────────────┐     ┌────────────┐     ┌────────────┐
│   Jarvis   │     │    Matt    │     │   Friday   │
│   (CTO)    │     │   (COO)    │     │   (CMO)    │
└──────┬─────┘     └─────┬──────┘     └─────┬──────┘
       │                 │                   │
       │  delegate_task  │                   │
       │ ───────────────>│                   │
       │                 │  delegate_task    │
       │                 │ ─────────────────>│
       │                 │                   │
       │                 │  complete_task    │
       │                 │ <─────────────────│
       │                 │                   │
       │                 │  send_message     │
       │ <───────────────│                   │
       │                 │                   │
       ▼                 ▼                   ▼
  ┌─────────────────────────────────────────────┐
  │       /root/clawdbots/shared_state.json     │
  │  (file-locked, atomic reads/writes)         │
  └─────────────────────────────────────────────┘
```

### Self-Healing Flow

```
┌──────────────────────────────────────────┐
│          ProcessWatchdog                 │
│                                          │
│  ┌────────────┐  ┌────────────────────┐ │
│  │ Health     │  │ Heartbeat Manager  │ │
│  │ Monitor    │  │ (30s interval)     │ │
│  │            │  │                    │ │
│  │ - Memory   │  │ heartbeat files    │ │
│  │ - CPU      │  │ /root/.heartbeats/ │ │
│  │ - Disk     │  └────────────────────┘ │
│  └────────────┘                         │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │ Error Detector                     │ │
│  │ - Pattern matching on log lines   │ │
│  │ - Severity classification          │ │
│  └────────────────────────────────────┘ │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │ Restart Policy                     │ │
│  │ - Exponential backoff              │ │
│  │ - Max attempts: 3                  │ │
│  └────────────────────────────────────┘ │
│                                          │
│           ↓ Alert Callbacks              │
└───────────┼──────────────────────────────┘
            ↓
    ┌───────────────┐
    │ Telegram      │
    │ Notifications │
    └───────────────┘
```

---

## Testing

### Test Computer Control

```python
import asyncio
from bots.shared import check_remote_status, browse_web

async def test_remote():
    status = await check_remote_status()
    print(f"Available: {status['available']}")

    if status["available"]:
        result = await browse_web("Go to google.com and search for 'test'")
        print(result)

asyncio.run(test_remote())
```

### Test Coordination

```python
from bots.shared import BotCoordinator, BotRole, TaskPriority

# Simulate Jarvis delegating to Friday
jarvis = BotCoordinator(BotRole.JARVIS)
task_id = jarvis.delegate_task(
    to_bot=BotRole.FRIDAY,
    description="Test task",
    priority=TaskPriority.MEDIUM,
)

# Simulate Friday checking tasks
friday = BotCoordinator(BotRole.FRIDAY)
tasks = friday.get_pending_tasks()
print(f"Pending tasks: {len(tasks)}")
for task in tasks:
    print(f"  - {task.description} (from {task.delegated_by.value})")
    friday.claim_task(task.id)
    friday.complete_task(task.id, result="Test completed")

# Generate report
print(jarvis.generate_status_report())
```

### Test Self-Healing

```python
from bots.shared import create_watchdog
import time

def my_alert(alert_type, details):
    print(f"ALERT: {alert_type}")
    print(f"Details: {details}")

watchdog = create_watchdog("test-bot", alert_callback=my_alert)
watchdog.start()

# Simulate running bot
time.sleep(120)

# Check status
status = watchdog.get_status()
print(status)

watchdog.stop()
```

### Test Cost Tracking

```python
from bots.shared import track_api_call, get_cost_report, set_daily_limit

# Set limit
set_daily_limit("test-bot", 5.0)

# Track some calls
track_api_call("test-bot", "openai", 1000, 500, "gpt-4o")
track_api_call("test-bot", "anthropic", 2000, 800, "claude-sonnet")
track_api_call("test-bot", "xai", 1500, 600, "grok-3")

# Generate report
print(get_cost_report())
```

---

## Common Patterns

### Pattern 1: Coordinated Research Task

```python
# Matt delegates research to all bots
from bots.shared import BotCoordinator, BotRole, TaskPriority

matt = BotCoordinator(BotRole.MATT)

tasks = [
    ("jarvis", "Analyze technical feasibility of feature X"),
    ("friday", "Research competitor marketing for feature X"),
]

task_ids = []
for bot_name, description in tasks:
    task_id = matt.delegate_task(
        to_bot=BotRole(bot_name),
        description=description,
        priority=TaskPriority.HIGH,
    )
    task_ids.append(task_id)

# Wait for completion...
# Each bot claims, completes, and sends results back
```

### Pattern 2: Budget-Aware LLM Selection

```python
from bots.shared import check_budget, track_api_call

async def smart_query(bot_name, prompt):
    if check_budget(bot_name):
        # Use premium model
        model = "gpt-4o"
        api = "openai"
    else:
        # Use budget model
        model = "gpt-4o-mini"
        api = "openai"

    response = await llm_call(model, prompt)

    # Track cost
    track_api_call(
        bot_name,
        api,
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
        model,
    )

    return response.choices[0].message.content
```

### Pattern 3: Self-Healing with Restart

```python
from bots.shared import ProcessWatchdog, SelfHealingConfig
import subprocess

def restart_bot():
    print("Restarting bot service...")
    subprocess.run(["systemctl", "restart", "clawdjarvis.service"])

config = SelfHealingConfig(
    bot_name="clawdjarvis",
    max_restart_attempts=3,
)

watchdog = ProcessWatchdog(config)
watchdog.on_restart(restart_bot)

# If bot crashes, watchdog calls restart_bot() automatically
watchdog.start()
```

### Pattern 4: Full Life Control

```python
from bots.shared.life_control_commands import register_life_commands
from telebot.async_telebot import AsyncTeleBot

bot = AsyncTeleBot(token)
register_life_commands(bot)

# Now Telegram commands work:
# /do Send John an email
# /calendar add meeting Friday
# /wallet check balance
# /deploy website

asyncio.run(bot.polling())
```

---

## Troubleshooting

### Computer Control Not Working

**Problem:** `browse_web()` returns connection error

**Solutions:**
1. Check Windows machine is running and on Tailscale
2. Verify `remote_control_server.py` is running on Windows
3. Check `JARVIS_REMOTE_API_KEY` matches on both sides
4. Test connectivity: `curl http://100.102.41.120:8765/health`

### Coordination State Corruption

**Problem:** `shared_state.json` corrupted or locked

**Solutions:**
1. Stop all bots
2. Backup and delete `/root/clawdbots/shared_state.json`
3. Restart bots (file will be recreated)
4. Ensure `filelock` package is installed

### Self-Healing Watchdog Not Starting

**Problem:** Watchdog thread doesn't start

**Solutions:**
1. Check `psutil` is installed: `pip install psutil`
2. Verify heartbeat directory is writable
3. Check logs for threading errors

### Cost Tracking Missing Data

**Problem:** `api_costs.json` shows $0.00 costs

**Solutions:**
1. Verify `track_api_call()` is being called after LLM requests
2. Check API provider name matches pricing table
3. Ensure tokens are being counted correctly

---

## Performance Considerations

### Computer Control
- **Latency:** 2-5 seconds per request (Tailscale + LLM processing)
- **Timeout:** 5 minutes default (configurable)
- **Rate limit:** No built-in limit (implement in caller if needed)

### Coordination
- **File locking:** Brief lock (<100ms) for state reads/writes
- **State size:** Grows with tasks - clean up completed tasks periodically
- **Concurrency:** Thread-safe, multiple bots can coordinate simultaneously

### Self-Healing
- **Memory overhead:** ~10MB per watchdog instance
- **CPU overhead:** Negligible (<1%) during monitoring
- **Heartbeat interval:** 30s default (adjust based on needs)

### Cost Tracking
- **File size:** ~1KB per 50 API calls
- **Lookup speed:** O(n) where n = number of days (acceptable for months of data)
- **Cleanup:** Archive old data periodically to keep file small

---

## Security Notes

1. **API Keys:** Never commit `JARVIS_REMOTE_API_KEY` to git
2. **Shared State:** `/root/clawdbots/` directory should be owned by bot user
3. **Remote Control:** Only accessible via Tailscale (private network)
4. **Cost Data:** Contains no sensitive info, but limit read access
5. **Heartbeat Files:** World-readable OK (used for monitoring)

---

## Future Enhancements

Planned additions to shared module library:

- **Observability** - MOLT metrics tracking
- **Campaign Orchestrator** - Multi-bot campaign coordination
- **Sleep Compute** - Background task execution
- **MoltBook** - Knowledge base integration
- **Personality** - Bot personality loading
- **Command Registry** - Centralized command management
- **Message Queue** - Async inter-bot messaging
- **Rate Limiter** - API rate limiting
- **State Manager** - Advanced state persistence
- **Conversation Memory** - Chat history tracking
- **Analytics** - Usage analytics
- **Webhook Handler** - External webhook processing
- **Feature Flags** - Dynamic feature toggles

---

## Contributing

When adding new shared modules:

1. Add module to `bots/shared/`
2. Export in `bots/shared/__init__.py`
3. Document in this README
4. Add tests
5. Update integration examples

---

## License

Part of the Jarvis LifeOS project. Internal use only.

---

## Support

For issues with shared modules:

1. Check this README first
2. Review module docstrings
3. Check `/root/clawdbots/` logs on VPS
4. Test connectivity (for computer control)
5. Verify all dependencies installed

**File Locations Reference:**

| Module | Config Files | Data Files |
|--------|-------------|------------|
| Computer Control | Environment vars | None |
| Coordination | None | `/root/clawdbots/shared_state.json` |
| Self-Healing | None | `/root/clawdbots/.heartbeats/*.heartbeat` |
| Cost Tracking | None | `/root/clawdbots/api_costs.json` |
| Life Control | Environment vars | None |

---

**Version:** 1.0
**Last Updated:** 2026-02-02
**Maintained by:** Jarvis LifeOS Team
