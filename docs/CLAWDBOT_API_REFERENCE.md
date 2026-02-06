# ClawdBot API Reference

Complete API documentation for ClawdBots shared modules (`bots/shared/`).

**Version:** 1.0
**Last Updated:** 2026-02-02

---

## Table of Contents

- [Core Modules](#core-modules)
  - [computer_capabilities](#computer_capabilities)
  - [coordination](#coordination)
- [Infrastructure Modules](#infrastructure-modules)
  - [self_healing](#self_healing)
  - [cost_tracker](#cost_tracker)
- [Utility Modules](#utility-modules)
  - [life_control_commands](#life_control_commands)

---

# Core Modules

## computer_capabilities

Provides remote computer control capabilities for ClawdBots running on VPS to control Daryl's Windows machine via Tailscale.

**Module:** `bots.shared.computer_capabilities`

### Classes

#### RemoteComputerControl

Main class for remote computer control.

```python
class RemoteComputerControl:
    def __init__(self)
```

Initialize remote control client. Configuration comes from environment variables:
- `JARVIS_LOCAL_IP` - Tailscale IP of Windows machine (default: 100.102.41.120)
- `JARVIS_REMOTE_PORT` - Remote control server port (default: 8765)
- `JARVIS_REMOTE_API_KEY` - Authentication key

**Example:**
```python
from bots.shared.computer_capabilities import RemoteComputerControl

remote = RemoteComputerControl()
```

---

### browse(task: str) -> Dict[str, Any]

Browser automation on Windows machine. The LLM navigates web pages like a human - reads DOM, understands content, clicks by meaning not coordinates.

**Parameters:**
- `task` (str): Natural language task description

**Returns:**
- Dict with keys:
  - `success` (bool): Whether task succeeded
  - `result` (str): Task result or output

**Example:**
```python
result = await remote.browse("Go to twitter.com and check my notifications")
# {'success': True, 'result': 'You have 3 new notifications...'}

result = await remote.browse("Search google for 'solana ecosystem' and summarize results")
```

---

### computer(task: str) -> Dict[str, Any]

Full computer control on Windows machine. Can do ANYTHING you can do on the computer: open/control applications, read/write files, run commands, take screenshots.

**Parameters:**
- `task` (str): Natural language task description

**Returns:**
- Dict with keys:
  - `success` (bool): Whether task succeeded
  - `output` (str): Task output

**Example:**
```python
result = await remote.computer("Check what programs are running")
result = await remote.computer("Create a folder called 'reports' on the desktop")
result = await remote.computer("Open Chrome and take a screenshot")
```

---

### telegram_send(chat: str, message: str) -> Dict[str, Any]

Send Telegram message via Web interface on Windows. Uses Telegram Web - useful when bot API is limited or need to send from Daryl's personal account.

**Parameters:**
- `chat` (str): Chat name or username
- `message` (str): Message to send

**Returns:**
- Dict with keys:
  - `success` (bool): Whether message was sent
  - `result` (str): Confirmation or error

**Example:**
```python
result = await remote.telegram_send("Saved Messages", "Reminder: check portfolio")
result = await remote.telegram_send("Trading Group", "SOL looking bullish!")
```

---

### telegram_read(chat: str, count: int = 10) -> Dict[str, Any]

Read recent messages from a Telegram chat.

**Parameters:**
- `chat` (str): Chat name or username
- `count` (int, optional): Number of messages to read (default: 10)

**Returns:**
- Dict with keys:
  - `success` (bool): Whether read succeeded
  - `result` (str): Message list

**Example:**
```python
result = await remote.telegram_read("Trading Group", count=20)
```

---

### is_available() -> bool

Check if Windows machine is reachable.

**Returns:**
- `bool`: True if machine is reachable and healthy

**Example:**
```python
if await remote.is_available():
    print("Windows machine is online")
```

---

### Convenience Functions

Module provides high-level convenience functions that wrap the RemoteComputerControl class:

#### browse_web(task: str) -> str

Browse the web on Daryl's Windows machine.

**Parameters:**
- `task` (str): Natural language browsing task

**Returns:**
- `str`: Result string or error message

**Example:**
```python
from bots.shared.computer_capabilities import browse_web

result = await browse_web("Go to coingecko.com and get SOL price")
result = await browse_web("Check my twitter notifications")
result = await browse_web("Go to pump.fun and find trending tokens")
```

---

#### control_computer(task: str) -> str

Control Daryl's Windows computer.

**Parameters:**
- `task` (str): Natural language computer control task

**Returns:**
- `str`: Result string or error message

**Example:**
```python
from bots.shared.computer_capabilities import control_computer

result = await control_computer("What files are on the desktop?")
result = await control_computer("Open calculator")
result = await control_computer("Take a screenshot and save it")
```

---

#### send_telegram_web(chat: str, message: str) -> str

Send Telegram message via Web on Daryl's computer.

**Parameters:**
- `chat` (str): Chat name or username
- `message` (str): Message to send

**Returns:**
- `str`: Success message or error

**Example:**
```python
from bots.shared.computer_capabilities import send_telegram_web

await send_telegram_web("Saved Messages", "Reminder: check portfolio")
await send_telegram_web("Trading Group", "SOL looking bullish!")
```

---

#### read_telegram_web(chat: str, count: int = 10) -> str

Read recent Telegram messages via Web.

**Parameters:**
- `chat` (str): Chat name or username
- `count` (int, optional): Number of messages to read (default: 10)

**Returns:**
- `str`: Message list or error

**Example:**
```python
from bots.shared.computer_capabilities import read_telegram_web

messages = await read_telegram_web("Trading Group", count=20)
```

---

#### check_remote_status() -> Dict[str, Any]

Check if Windows machine is available for remote control.

**Returns:**
- Dict with keys:
  - `available` (bool): Whether machine is reachable
  - `host` (str): Tailscale IP
  - `capabilities` (List[str]): Available capabilities (if online)
  - `error` (str): Error message (if offline)

**Example:**
```python
from bots.shared.computer_capabilities import check_remote_status

status = await check_remote_status()
if status["available"]:
    print(f"Machine online at {status['host']}")
    print(f"Capabilities: {status['capabilities']}")
```

---

#### get_capabilities_prompt() -> str

Get the capabilities description prompt for LLM context.

**Returns:**
- `str`: Markdown-formatted capabilities description

**Example:**
```python
from bots.shared.computer_capabilities import get_capabilities_prompt

prompt = get_capabilities_prompt()
# Use in system prompt
```

---

### Constants

#### COMPUTER_CAPABILITIES_PROMPT

Multi-line string containing detailed description of computer control capabilities for LLM context.

```python
from bots.shared.computer_capabilities import COMPUTER_CAPABILITIES_PROMPT

print(COMPUTER_CAPABILITIES_PROMPT)
```

---

## coordination

Inter-bot coordination system for ClawdBots. Provides task handoff, messaging, and status reporting between the three ClawdBots (Jarvis/CTO, Matt/COO, Friday/CMO).

**Module:** `bots.shared.coordination`
**Storage:** `/root/clawdbots/shared_state.json`

### Enums

#### BotRole

Bot roles with their titles.

```python
class BotRole(Enum):
    JARVIS = "jarvis"  # CTO - Technical lead, trading, orchestration
    MATT = "matt"      # COO - Operations, PR filtering, coordination
    FRIDAY = "friday"  # CMO - Marketing, communications, content
```

**Properties:**
- `title` -> str: Get executive title ("CTO", "COO", "CMO")

**Example:**
```python
from bots.shared.coordination import BotRole

role = BotRole.JARVIS
print(role.title)  # "CTO"
print(role.value)  # "jarvis"
```

---

#### TaskPriority

Task priority levels (lower number = higher priority).

```python
class TaskPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
```

**Example:**
```python
from bots.shared.coordination import TaskPriority

priority = TaskPriority.HIGH
```

---

#### TaskStatus

Task lifecycle status.

```python
class TaskStatus(Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
```

**Example:**
```python
from bots.shared.coordination import TaskStatus

status = TaskStatus.PENDING
```

---

#### HealthStatus

Health status levels.

```python
class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
```

**Methods:**
- `is_operational()` -> bool: Returns True if HEALTHY or DEGRADED

**Example:**
```python
from bots.shared.coordination import HealthStatus

status = HealthStatus.DEGRADED
if status.is_operational():
    print("System is still operational")
```

---

### Data Classes

#### CoordinationTask

A task delegated between bots. Tracks the full lifecycle from delegation through completion.

```python
@dataclass
class CoordinationTask:
    id: str
    description: str
    delegated_by: BotRole
    delegated_to: BotRole
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    claimed_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    failure_reason: Optional[str] = None
```

**Methods:**
- `to_dict()` -> Dict[str, Any]: Serialize to dictionary
- `from_dict(data: Dict[str, Any])` -> CoordinationTask: Deserialize from dictionary (classmethod)

**Example:**
```python
from bots.shared.coordination import CoordinationTask, BotRole, TaskPriority

task = CoordinationTask(
    id="task_abc123",
    description="Research competitor marketing strategy",
    delegated_by=BotRole.JARVIS,
    delegated_to=BotRole.FRIDAY,
    priority=TaskPriority.HIGH,
    context={"competitor": "SolanaAI", "focus": "twitter"}
)
```

---

#### BotMessage

A message between bots. Used for notifications, requests, and coordination communication.

```python
@dataclass
class BotMessage:
    id: str
    from_bot: BotRole
    to_bot: BotRole
    content: str
    related_task_id: Optional[str] = None
    read: bool = False
    created_at: Optional[str] = None
```

**Methods:**
- `to_dict()` -> Dict[str, Any]: Serialize to dictionary
- `from_dict(data: Dict[str, Any])` -> BotMessage: Deserialize from dictionary (classmethod)

**Example:**
```python
from bots.shared.coordination import BotMessage, BotRole

msg = BotMessage(
    id="msg_xyz789",
    from_bot=BotRole.MATT,
    to_bot=BotRole.JARVIS,
    content="Campaign ready for review",
    related_task_id="task_abc123"
)
```

---

#### BotStatus

Current status of a bot. Used for health monitoring and coordination.

```python
@dataclass
class BotStatus:
    bot: BotRole
    online: bool = True
    current_task: Optional[str] = None
    tasks_completed: int = 0
    tasks_pending: int = 0
    last_heartbeat: Optional[str] = None
    error: Optional[str] = None
```

**Methods:**
- `to_dict()` -> Dict[str, Any]: Serialize to dictionary
- `from_dict(data: Dict[str, Any])` -> BotStatus: Deserialize from dictionary (classmethod)

**Example:**
```python
from bots.shared.coordination import BotStatus, BotRole

status = BotStatus(
    bot=BotRole.JARVIS,
    online=True,
    current_task="Analyzing market data",
    tasks_completed=42,
    tasks_pending=3
)
```

---

### Main Class

#### BotCoordinator

Coordinates tasks and messages between ClawdBots. Each bot creates its own BotCoordinator instance. All coordinators share state via the same JSON file. Thread-safe via file locking (when filelock is available).

```python
class BotCoordinator:
    def __init__(
        self,
        bot_role: BotRole,
        state_file: Optional[str] = None
    )
```

**Parameters:**
- `bot_role` (BotRole): The role of this bot (JARVIS, MATT, or FRIDAY)
- `state_file` (str, optional): Path to shared state file (default: /root/clawdbots/shared_state.json)

**Example:**
```python
from bots.shared.coordination import BotCoordinator, BotRole

coord = BotCoordinator(BotRole.JARVIS)
```

---

### Task Delegation Methods

#### delegate_task(to_bot: BotRole, description: str, priority: TaskPriority = TaskPriority.MEDIUM, context: Optional[Dict[str, Any]] = None) -> str

Delegate a task to another bot.

**Parameters:**
- `to_bot` (BotRole): Bot to delegate the task to
- `description` (str): Task description
- `priority` (TaskPriority, optional): Task priority level (default: MEDIUM)
- `context` (Dict[str, Any], optional): Additional context/metadata

**Returns:**
- `str`: The task ID

**Raises:**
- `CoordinationError`: If delegating to self

**Example:**
```python
task_id = coord.delegate_task(
    to_bot=BotRole.FRIDAY,
    description="Research competitor marketing strategy",
    priority=TaskPriority.HIGH,
    context={"competitor": "SolanaAI"}
)
```

---

#### claim_task(task_id: str) -> bool

Claim a task delegated to this bot.

**Parameters:**
- `task_id` (str): ID of the task to claim

**Returns:**
- `bool`: True if claimed successfully, False otherwise

**Example:**
```python
if coord.claim_task(task_id):
    print("Task claimed, starting work...")
```

---

#### complete_task(task_id: str, result: Optional[str] = None, artifacts: Optional[List[str]] = None) -> bool

Mark a task as completed.

**Parameters:**
- `task_id` (str): ID of the task
- `result` (str, optional): Result description
- `artifacts` (List[str], optional): List of output file paths

**Returns:**
- `bool`: True if completed successfully, False otherwise

**Example:**
```python
coord.complete_task(
    task_id,
    result="Competitor analysis complete. They focus on DeFi.",
    artifacts=["/reports/competitor_analysis.pdf"]
)
```

---

#### fail_task(task_id: str, reason: str) -> bool

Mark a task as failed.

**Parameters:**
- `task_id` (str): ID of the task
- `reason` (str): Reason for failure

**Returns:**
- `bool`: True if marked as failed, False otherwise

**Example:**
```python
coord.fail_task(task_id, "API rate limit exceeded")
```

---

#### get_task(task_id: str) -> Optional[CoordinationTask]

Get a task by ID.

**Parameters:**
- `task_id` (str): ID of the task

**Returns:**
- `CoordinationTask | None`: Task object or None if not found

**Example:**
```python
task = coord.get_task(task_id)
if task:
    print(f"Task status: {task.status.value}")
```

---

#### get_pending_tasks() -> List[CoordinationTask]

Get all pending tasks delegated to this bot.

**Returns:**
- `List[CoordinationTask]`: List of pending tasks

**Example:**
```python
pending = coord.get_pending_tasks()
for task in pending:
    print(f"Pending: {task.description}")
```

---

#### get_tasks_by_status(status: TaskStatus) -> List[CoordinationTask]

Get tasks by status for this bot.

**Parameters:**
- `status` (TaskStatus): Status to filter by

**Returns:**
- `List[CoordinationTask]`: List of tasks matching status

**Example:**
```python
from bots.shared.coordination import TaskStatus

in_progress = coord.get_tasks_by_status(TaskStatus.IN_PROGRESS)
```

---

### Messaging Methods

#### send_message(to_bot: BotRole, content: str, related_task_id: Optional[str] = None) -> str

Send a message to another bot.

**Parameters:**
- `to_bot` (BotRole): Bot to send message to
- `content` (str): Message content
- `related_task_id` (str, optional): Optional related task ID

**Returns:**
- `str`: The message ID

**Example:**
```python
msg_id = coord.send_message(
    BotRole.MATT,
    "Campaign ready for review",
    related_task_id=task_id
)
```

---

#### get_unread_messages() -> List[BotMessage]

Get all unread messages for this bot.

**Returns:**
- `List[BotMessage]`: List of unread messages

**Example:**
```python
messages = coord.get_unread_messages()
for msg in messages:
    print(f"From {msg.from_bot.value}: {msg.content}")
    coord.mark_message_read(msg.id)
```

---

#### mark_message_read(message_id: str) -> bool

Mark a message as read.

**Parameters:**
- `message_id` (str): ID of the message

**Returns:**
- `bool`: True if marked, False if not found

**Example:**
```python
coord.mark_message_read(msg_id)
```

---

### Status Methods

#### update_status(current_task: Optional[str] = None, tasks_completed: int = 0, tasks_pending: int = 0, error: Optional[str] = None) -> None

Update this bot's status.

**Parameters:**
- `current_task` (str, optional): Current task description
- `tasks_completed` (int, optional): Number of completed tasks (default: 0)
- `tasks_pending` (int, optional): Number of pending tasks (default: 0)
- `error` (str, optional): Current error state (if any)

**Example:**
```python
coord.update_status(
    current_task="Analyzing market sentiment",
    tasks_completed=42,
    tasks_pending=3
)
```

---

#### heartbeat() -> None

Update heartbeat timestamp for this bot. Should be called periodically to indicate the bot is alive.

**Example:**
```python
# In main loop
while running:
    coord.heartbeat()
    await asyncio.sleep(30)
```

---

#### get_my_status() -> BotStatus

Get this bot's current status.

**Returns:**
- `BotStatus`: Current status object

**Example:**
```python
status = coord.get_my_status()
print(f"I've completed {status.tasks_completed} tasks")
```

---

#### get_all_bot_statuses() -> Dict[BotRole, BotStatus]

Get status of all bots.

**Returns:**
- `Dict[BotRole, BotStatus]`: Dictionary mapping BotRole to BotStatus

**Example:**
```python
all_status = coord.get_all_bot_statuses()
for role, status in all_status.items():
    print(f"{role.value}: {'online' if status.online else 'offline'}")
```

---

### Reporting Methods

#### generate_status_report() -> str

Generate a human-readable status report for all bots.

**Returns:**
- `str`: Formatted status report string

**Example:**
```python
report = coord.generate_status_report()
print(report)
```

Example output:
```
==================================================
CLAWDBOTS STATUS REPORT
Generated: 2026-02-02T14:30:00+00:00
Generated by: jarvis (CTO)
==================================================

BOT STATUS:
------------------------------
  [OK] JARVIS (CTO) - Analyzing market data
  [OK] MATT (COO)
  [--] FRIDAY (CMO)
       ERROR: Connection timeout

TASK SUMMARY:
------------------------------
  Active tasks: 5
  Completed tasks: 127

==================================================
```

---

### Convenience Functions

#### get_coordinator(role: str) -> BotCoordinator

Get a BotCoordinator for the specified role.

**Parameters:**
- `role` (str): Role name ('jarvis', 'matt', or 'friday')

**Returns:**
- `BotCoordinator`: Coordinator instance

**Raises:**
- `ValueError`: If invalid role name

**Example:**
```python
from bots.shared.coordination import get_coordinator

coord = get_coordinator("jarvis")
```

---

### Exceptions

#### CoordinationError

Raised when a coordination operation fails.

```python
class CoordinationError(Exception):
    pass
```

**Example:**
```python
from bots.shared.coordination import CoordinationError

try:
    coord.delegate_task(BotRole.JARVIS, "Self-delegation test")
except CoordinationError as e:
    print(f"Error: {e}")
```

---

# Infrastructure Modules

## self_healing

Process health monitoring, automatic restart on crash, memory/CPU threshold alerts, heartbeat mechanism, and log error detection for ClawdBots on VPS.

**Module:** `bots.shared.self_healing`
**Dependencies:** psutil (optional, for resource monitoring)

### Configuration Classes

#### SelfHealingConfig

Configuration for self-healing watchdog.

```python
@dataclass
class SelfHealingConfig:
    bot_name: str = "unknown"
    heartbeat_interval: int = 30
    health_check_interval: int = 60
    max_restart_attempts: int = 3
    restart_cooldown: int = 300
    memory_threshold_mb: int = 512
    cpu_threshold_percent: int = 80
    log_file: Optional[Path] = None
    heartbeat_dir: Optional[Path] = None
```

**Attributes:**
- `bot_name` (str): Identifier for the bot (e.g., "clawdjarvis")
- `heartbeat_interval` (int): Seconds between heartbeat updates (default: 30)
- `health_check_interval` (int): Seconds between health checks (default: 60)
- `max_restart_attempts` (int): Maximum restart attempts before giving up (default: 3)
- `restart_cooldown` (int): Seconds to wait between restart attempts (default: 300)
- `memory_threshold_mb` (int): Memory usage threshold in MB (default: 512)
- `cpu_threshold_percent` (int): CPU usage threshold as percentage (default: 80)
- `log_file` (Path, optional): Path to log file for error detection
- `heartbeat_dir` (Path, optional): Directory for heartbeat files (default: /root/clawdbots/.heartbeats)

**Example:**
```python
from bots.shared.self_healing import SelfHealingConfig

config = SelfHealingConfig(
    bot_name="clawdjarvis",
    memory_threshold_mb=256,
    heartbeat_interval=30,
)
```

---

#### ResourceThresholds

Resource usage thresholds for alerts.

```python
@dataclass
class ResourceThresholds:
    memory_mb: int = 512
    cpu_percent: int = 80
    disk_percent: int = 90
```

**Methods:**
- `is_memory_exceeded(current_mb: float)` -> bool: Check if memory exceeds threshold
- `is_cpu_exceeded(current_percent: float)` -> bool: Check if CPU exceeds threshold
- `is_disk_exceeded(current_percent: float)` -> bool: Check if disk exceeds threshold

**Example:**
```python
from bots.shared.self_healing import ResourceThresholds

thresholds = ResourceThresholds(memory_mb=256)
if thresholds.is_memory_exceeded(300):
    print("Memory threshold exceeded!")
```

---

#### RestartPolicy

Policy for restart decisions.

```python
@dataclass
class RestartPolicy:
    max_attempts: int = 3
    cooldown_seconds: int = 300
    backoff_multiplier: float = 2.0
```

**Methods:**
- `should_restart(attempt_count: Optional[int] = None)` -> bool: Determine if restart should be attempted
- `get_backoff_delay(attempt: Optional[int] = None)` -> float: Calculate delay before next restart (exponential backoff)
- `record_restart()` -> None: Record a restart attempt
- `reset()` -> None: Reset restart attempt counter

**Example:**
```python
from bots.shared.self_healing import RestartPolicy

policy = RestartPolicy(max_attempts=5, cooldown_seconds=60)
if policy.should_restart():
    delay = policy.get_backoff_delay()
    await asyncio.sleep(delay)
    # Perform restart
    policy.record_restart()
```

---

### Error Detection Classes

#### ErrorPattern

Pattern for detecting errors in log lines.

```python
@dataclass
class ErrorPattern:
    name: str
    regex: str
    severity: str = "medium"
    action: Optional[Callable[[Match], None]] = None
    description: str = ""
```

**Attributes:**
- `name` (str): Identifier for this pattern
- `regex` (str): Regular expression to match
- `severity` (str): Severity level ("low", "medium", "high", "critical")
- `action` (Callable, optional): Optional callback when pattern matches
- `description` (str): Human-readable description

**Methods:**
- `match(line: str)` -> Optional[Match]: Check if line matches this pattern

**Example:**
```python
from bots.shared.self_healing import ErrorPattern

pattern = ErrorPattern(
    name="out_of_memory",
    regex=r"MemoryError|OutOfMemory",
    severity="critical",
    description="Memory allocation failure"
)

if pattern.match(log_line):
    print("Memory error detected!")
```

---

#### ErrorMatch

Result of an error pattern match.

```python
@dataclass
class ErrorMatch:
    name: str
    severity: str
    line: str
    match: Match
    timestamp: datetime = field(default_factory=datetime.now)
```

---

#### LogErrorDetector

Detects error patterns in log lines. Monitors log output for known error patterns and triggers alerts or actions based on severity.

```python
class LogErrorDetector:
    def __init__(
        self,
        bot_name: str,
        patterns: Optional[List[ErrorPattern]] = None
    )
```

**Parameters:**
- `bot_name` (str): Bot identifier for logging
- `patterns` (List[ErrorPattern], optional): Custom patterns (defaults used if None)

**Default Patterns:**
- critical_error: CRITICAL level logs
- error_log: ERROR level logs
- exception: Python exceptions/tracebacks
- memory_error: Memory allocation failures
- connection_error: Network connection failures
- timeout_error: Operation timeouts
- rate_limit: API rate limiting
- auth_error: Authentication failures
- telegram_conflict: Telegram polling conflicts

**Methods:**

##### add_pattern(pattern: ErrorPattern) -> None

Add a custom error pattern.

**Example:**
```python
detector.add_pattern(ErrorPattern(
    name="custom_error",
    regex=r"CUSTOM ERROR:",
    severity="high"
))
```

##### check_line(line: str) -> List[ErrorMatch]

Check a log line for error patterns.

**Parameters:**
- `line` (str): Log line to check

**Returns:**
- `List[ErrorMatch]`: List of matching error patterns

**Example:**
```python
matches = detector.check_line("ERROR: Connection failed")
for match in matches:
    print(f"Detected {match.name}: {match.severity}")
```

##### get_error_summary(since: Optional[datetime] = None) -> Dict[str, Any]

Get summary of detected errors.

**Parameters:**
- `since` (datetime, optional): Only include errors after this time

**Returns:**
- Dict with keys:
  - `total_errors` (int): Total error count
  - `by_severity` (Dict[str, int]): Count by severity level
  - `by_name` (Dict[str, int]): Count by error name
  - `most_recent` (ErrorMatch | None): Most recent error

**Example:**
```python
summary = detector.get_error_summary()
print(f"Total errors: {summary['total_errors']}")
print(f"Critical errors: {summary['by_severity'].get('critical', 0)}")
```

##### clear_history() -> None

Clear error history.

**Example:**
```python
from bots.shared.self_healing import LogErrorDetector

detector = LogErrorDetector(bot_name="clawdjarvis")

# Check log lines
for line in log_lines:
    matches = detector.check_line(line)
    if matches:
        alert_admin(matches)

# Get summary
summary = detector.get_error_summary()
```

---

### Heartbeat Classes

#### HeartbeatManager

Manages heartbeat signals for process liveness detection. Writes periodic heartbeat files that can be monitored by external systems (systemd, cron watchdog, etc.)

```python
class HeartbeatManager:
    def __init__(
        self,
        bot_name: str,
        interval: int = 30,
        heartbeat_dir: Optional[Path] = None
    )
```

**Parameters:**
- `bot_name` (str): Bot identifier
- `interval` (int): Seconds between heartbeats (default: 30)
- `heartbeat_dir` (Path, optional): Directory for heartbeat files

**Methods:**

##### record_heartbeat() -> None

Record a heartbeat timestamp.

**Example:**
```python
heartbeat.record_heartbeat()
```

##### is_alive(tolerance_multiplier: float = 2.0) -> bool

Check if heartbeat is recent enough to be considered alive.

**Parameters:**
- `tolerance_multiplier` (float): How many intervals before considered dead (default: 2.0)

**Returns:**
- `bool`: True if heartbeat is within tolerance

**Example:**
```python
if heartbeat.is_alive():
    print("Bot is alive")
```

##### get_seconds_since_heartbeat() -> float

Get seconds since last heartbeat.

**Returns:**
- `float`: Seconds since last heartbeat (inf if never)

**Example:**
```python
seconds = heartbeat.get_seconds_since_heartbeat()
print(f"Last heartbeat {seconds:.1f}s ago")
```

##### start_background() -> None

Start background heartbeat thread.

**Example:**
```python
heartbeat.start_background()
```

##### stop() -> None

Stop background heartbeat thread.

**Example:**
```python
from bots.shared.self_healing import HeartbeatManager

heartbeat = HeartbeatManager(bot_name="clawdjarvis", interval=30)
heartbeat.start_background()

# ... bot runs ...

heartbeat.stop()
```

---

### Health Monitoring Classes

#### HealthMonitor

Monitors process health metrics (memory, CPU, etc.).

```python
class HealthMonitor:
    def __init__(self, config: SelfHealingConfig)
```

**Parameters:**
- `config` (SelfHealingConfig): Self-healing configuration

**Methods:**

##### get_memory_usage_mb() -> float

Get current memory usage in MB.

**Returns:**
- `float`: Memory usage in megabytes

**Example:**
```python
memory = monitor.get_memory_usage_mb()
print(f"Using {memory:.1f} MB")
```

##### get_cpu_usage_percent() -> float

Get current CPU usage percentage.

**Returns:**
- `float`: CPU usage percentage (0-100)

**Example:**
```python
cpu = monitor.get_cpu_usage_percent()
print(f"CPU: {cpu:.1f}%")
```

##### check_health() -> HealthStatus

Check overall process health.

**Returns:**
- `HealthStatus`: Health status based on resource usage

**Example:**
```python
status = monitor.check_health()
if status == HealthStatus.CRITICAL:
    alert_admin()
```

##### get_health_report() -> Dict[str, Any]

Get detailed health report.

**Returns:**
- Dict with keys:
  - `bot_name` (str)
  - `status` (str): Health status value
  - `operational` (bool): Whether operational
  - `memory_mb` (float): Current memory usage
  - `memory_threshold_mb` (int): Memory threshold
  - `memory_exceeded` (bool): Whether memory exceeded
  - `cpu_percent` (float): Current CPU usage
  - `cpu_threshold_percent` (int): CPU threshold
  - `cpu_exceeded` (bool): Whether CPU exceeded
  - `timestamp` (str): ISO timestamp

**Example:**
```python
from bots.shared.self_healing import HealthMonitor, SelfHealingConfig

config = SelfHealingConfig(bot_name="clawdjarvis", memory_threshold_mb=256)
monitor = HealthMonitor(config)

report = monitor.get_health_report()
print(f"Status: {report['status']}")
print(f"Memory: {report['memory_mb']:.1f} / {report['memory_threshold_mb']} MB")
print(f"CPU: {report['cpu_percent']:.1f}%")
```

---

### Main Watchdog Class

#### ProcessWatchdog

Main watchdog that orchestrates self-healing. Monitors process health, triggers alerts, and coordinates restarts. Runs as a background thread alongside the main bot.

```python
class ProcessWatchdog:
    def __init__(self, config: SelfHealingConfig)
```

**Parameters:**
- `config` (SelfHealingConfig): Self-healing configuration

**Type Aliases:**
```python
AlertCallback = Callable[[str, Dict[str, Any]], None]
RestartCallback = Callable[[], None]
```

**Methods:**

##### on_alert(callback: AlertCallback) -> None

Register callback for alerts.

**Parameters:**
- `callback` (Callable): Function(alert_type, details) to call on alert

**Example:**
```python
def handle_alert(alert_type: str, details: Dict[str, Any]):
    send_telegram(f"ALERT: {alert_type}\n{details}")

watchdog.on_alert(handle_alert)
```

##### on_restart(callback: RestartCallback) -> None

Register callback for restarts.

**Parameters:**
- `callback` (Callable): Function() to call on restart

**Example:**
```python
def handle_restart():
    logger.critical("Restarting bot...")
    cleanup_resources()

watchdog.on_restart(handle_restart)
```

##### start() -> None

Start the watchdog background thread.

**Example:**
```python
watchdog.start()
```

##### stop() -> None

Stop the watchdog.

**Example:**
```python
watchdog.stop()
```

##### should_restart() -> Tuple[bool, str]

Determine if bot should restart.

**Returns:**
- Tuple of (should_restart, reason)

**Example:**
```python
should_restart, reason = watchdog.should_restart()
if should_restart:
    logger.warning(f"Restart needed: {reason}")
```

##### check_log_line(line: str) -> List[ErrorMatch]

Check a log line for errors.

**Parameters:**
- `line` (str): Log line to check

**Returns:**
- `List[ErrorMatch]`: List of error matches

**Example:**
```python
for line in get_log_tail():
    errors = watchdog.check_log_line(line)
    if errors:
        for error in errors:
            logger.warning(f"Error detected: {error.name}")
```

##### get_status() -> Dict[str, Any]

Get comprehensive watchdog status.

**Returns:**
- Dict with keys:
  - `bot_name` (str)
  - `watchdog_running` (bool)
  - `restart_count` (int)
  - `health` (Dict): Health report
  - `errors` (Dict): Error summary
  - `heartbeat` (Dict): Heartbeat info

**Example:**
```python
from bots.shared.self_healing import ProcessWatchdog, SelfHealingConfig

config = SelfHealingConfig(
    bot_name="clawdjarvis",
    memory_threshold_mb=256,
    heartbeat_interval=30,
)

watchdog = ProcessWatchdog(config)

def alert_handler(alert_type, details):
    send_telegram_alert(alert_type, details)

watchdog.on_alert(alert_handler)
watchdog.start()

# ... bot runs ...

status = watchdog.get_status()
print(f"Watchdog running: {status['watchdog_running']}")
print(f"Health: {status['health']['status']}")

watchdog.stop()
```

---

### Convenience Functions

#### create_watchdog(bot_name: str, memory_threshold_mb: int = 256, cpu_threshold_percent: int = 80, heartbeat_interval: int = 30, health_check_interval: int = 60, max_restart_attempts: int = 3, alert_callback: Optional[AlertCallback] = None) -> ProcessWatchdog

Create a configured watchdog for a bot.

**Parameters:**
- `bot_name` (str): Name of the bot
- `memory_threshold_mb` (int): Memory alert threshold (default: 256)
- `cpu_threshold_percent` (int): CPU alert threshold (default: 80)
- `heartbeat_interval` (int): Seconds between heartbeats (default: 30)
- `health_check_interval` (int): Seconds between health checks (default: 60)
- `max_restart_attempts` (int): Max restart attempts (default: 3)
- `alert_callback` (AlertCallback, optional): Optional callback for alerts

**Returns:**
- `ProcessWatchdog`: Configured watchdog instance

**Example:**
```python
from bots.shared.self_healing import create_watchdog

watchdog = create_watchdog(
    bot_name="clawdjarvis",
    memory_threshold_mb=256,
    alert_callback=lambda alert_type, details: send_alert(alert_type, details)
)
watchdog.start()
```

---

#### send_telegram_alert(chat_id: str, bot_token: str, alert_type: str, details: Dict[str, Any]) -> bool

Send alert via Telegram.

**Parameters:**
- `chat_id` (str): Telegram chat ID
- `bot_token` (str): Bot API token
- `alert_type` (str): Type of alert
- `details` (Dict[str, Any]): Alert details

**Returns:**
- `bool`: True if sent successfully

**Example:**
```python
from bots.shared.self_healing import send_telegram_alert

success = send_telegram_alert(
    chat_id="123456789",
    bot_token="bot_token_here",
    alert_type="HIGH_MEMORY",
    details={"memory_mb": 512, "threshold_mb": 256}
)
```

---

## cost_tracker

Tracks API costs per bot (OpenAI, Anthropic, X.AI/Grok), enforces daily/monthly cost limits, alerts when approaching limits, and generates cost reports.

**Module:** `bots.shared.cost_tracker`
**Storage:** `/root/clawdbots/api_costs.json`

### Constants

#### DEFAULT_STORAGE_PATH

Default path for cost tracking data.

```python
DEFAULT_STORAGE_PATH = Path("/root/clawdbots/api_costs.json")
```

---

#### DEFAULT_DAILY_LIMIT

Default daily cost limit per bot in USD.

```python
DEFAULT_DAILY_LIMIT = 10.0
```

---

#### ALERT_THRESHOLD

Alert threshold as percentage of daily limit.

```python
ALERT_THRESHOLD = 0.8  # 80%
```

---

#### API_PRICING

API pricing per 1K tokens. Format: provider -> model -> {input_per_1k, output_per_1k}

```python
API_PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "openai": {
        "gpt-4": {"input_per_1k": 0.03, "output_per_1k": 0.06},
        "gpt-4o": {"input_per_1k": 0.015, "output_per_1k": 0.06},
        "gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.0006},
        "gpt-3.5-turbo": {"input_per_1k": 0.0005, "output_per_1k": 0.0015},
    },
    "anthropic": {
        "claude-opus": {"input_per_1k": 0.015, "output_per_1k": 0.075},
        "claude-sonnet": {"input_per_1k": 0.003, "output_per_1k": 0.015},
        "claude-haiku": {"input_per_1k": 0.00025, "output_per_1k": 0.00125},
    },
    "xai": {
        "grok-2": {"input_per_1k": 0.03, "output_per_1k": 0.06},
        "grok-3": {"input_per_1k": 0.001, "output_per_1k": 0.001},
    },
    "groq": {
        "llama": {"input_per_1k": 0.00059, "output_per_1k": 0.00079},
        "mixtral": {"input_per_1k": 0.00024, "output_per_1k": 0.00024},
    },
}
```

---

### Main Class

#### ClawdBotCostTracker

Tracks API costs for ClawdBots. Stores data in JSON format.

```python
class ClawdBotCostTracker:
    def __init__(
        self,
        storage_path: Optional[Path] = None,
        alert_callback: Optional[Callable[[str, float, float, float], None]] = None
    )
```

**Parameters:**
- `storage_path` (Path, optional): Path to JSON storage file (default: /root/clawdbots/api_costs.json)
- `alert_callback` (Callable, optional): Optional callback for budget alerts. Signature: (bot_name, current_cost, limit, percentage) -> None

**Storage Format:**
```json
{
  "daily": {
    "2026-02-02": [
      {
        "bot_name": "clawdmatt",
        "api": "openai",
        "input_tokens": 1000,
        "output_tokens": 500,
        "cost_usd": 0.06,
        "timestamp": "2026-02-02T10:30:00"
      }
    ]
  },
  "limits": {
    "clawdmatt": 10.0,
    "clawdjarvis": 10.0
  }
}
```

**Methods:**

##### track_api_call(bot_name: str, api: str, input_tokens: int, output_tokens: int, model: Optional[str] = None) -> float

Track an API call.

**Parameters:**
- `bot_name` (str): Name of the bot (e.g., "clawdmatt")
- `api` (str): API provider (e.g., "openai", "anthropic", "xai")
- `input_tokens` (int): Number of input tokens
- `output_tokens` (int): Number of output tokens
- `model` (str, optional): Optional model name for more specific pricing

**Returns:**
- `float`: Cost of the call in USD

**Example:**
```python
tracker = ClawdBotCostTracker()
cost = tracker.track_api_call("clawdmatt", "openai", 1000, 500)
print(f"Cost: ${cost:.4f}")
```

##### get_daily_cost(bot_name: Optional[str] = None) -> float

Get total cost for today.

**Parameters:**
- `bot_name` (str, optional): Optional bot to filter by

**Returns:**
- `float`: Total cost in USD

**Example:**
```python
# All bots
total = tracker.get_daily_cost()

# Specific bot
matt_cost = tracker.get_daily_cost(bot_name="clawdmatt")
```

##### get_monthly_cost(bot_name: Optional[str] = None) -> float

Get total cost for current month.

**Parameters:**
- `bot_name` (str, optional): Optional bot to filter by

**Returns:**
- `float`: Total cost in USD

**Example:**
```python
monthly = tracker.get_monthly_cost()
matt_monthly = tracker.get_monthly_cost(bot_name="clawdmatt")
```

##### check_budget(bot_name: str) -> bool

Check if bot is under daily budget.

**Parameters:**
- `bot_name` (str): Name of the bot

**Returns:**
- `bool`: True if under budget, False if at or over limit

**Example:**
```python
if tracker.check_budget("clawdmatt"):
    # Make API call
    make_openai_request()
else:
    logger.warning("Budget exceeded, skipping API call")
```

##### set_daily_limit(bot_name: str, limit: float) -> None

Set daily cost limit for a bot.

**Parameters:**
- `bot_name` (str): Name of the bot
- `limit` (float): Daily limit in USD

**Example:**
```python
tracker.set_daily_limit("clawdmatt", 15.0)
```

##### set_alert_callback(callback: Callable[[str, float, float, float], None]) -> None

Set the alert callback function.

**Parameters:**
- `callback` (Callable): Function with signature (bot_name, current, limit, percent)

**Example:**
```python
def alert_handler(bot_name, current, limit, percent):
    send_telegram(f"{bot_name} at {percent*100:.1f}% of budget")

tracker.set_alert_callback(alert_handler)
```

##### get_cost_report() -> str

Generate human-readable cost report.

**Returns:**
- `str`: Formatted cost report string

**Example:**
```python
from bots.shared.cost_tracker import ClawdBotCostTracker

tracker = ClawdBotCostTracker()

# Track calls
tracker.track_api_call("clawdmatt", "openai", 1000, 500)
tracker.track_api_call("clawdjarvis", "anthropic", 2000, 1000)

# Generate report
print(tracker.get_cost_report())
```

Example output:
```
ClawdBots API Cost Report
==============================

Date: 2026-02-02
Daily Total: $0.2100

Per-Bot Breakdown:
--------------------
  clawdjarvis: $0.1500 / $10.00 (1.5%)
  clawdmatt: $0.0600 / $10.00 (0.6%)

Monthly Total: $5.4200

Per-API Breakdown (today):
--------------------
  anthropic: $0.1500 (1 calls, 3000 tokens)
  openai: $0.0600 (1 calls, 1500 tokens)
```

---

### Module-Level Functions

Convenience functions that use a global tracker instance.

#### get_tracker(storage_path: Optional[Path] = None, force_new: bool = False) -> ClawdBotCostTracker

Get the global tracker instance.

**Parameters:**
- `storage_path` (Path, optional): Optional storage path override
- `force_new` (bool): Force create a new instance (default: False)

**Returns:**
- `ClawdBotCostTracker`: Tracker instance

**Example:**
```python
from bots.shared.cost_tracker import get_tracker

tracker = get_tracker()
```

---

#### track_api_call(bot_name: str, api: str, input_tokens: int, output_tokens: int, model: Optional[str] = None) -> float

Track an API call (uses global tracker).

**Parameters:**
- `bot_name` (str): Name of the bot
- `api` (str): API provider
- `input_tokens` (int): Number of input tokens
- `output_tokens` (int): Number of output tokens
- `model` (str, optional): Optional model name

**Returns:**
- `float`: Cost in USD

**Example:**
```python
from bots.shared.cost_tracker import track_api_call

cost = track_api_call("clawdmatt", "openai", 1000, 500)
```

---

#### get_daily_cost(bot_name: Optional[str] = None) -> float

Get today's total cost (uses global tracker).

**Parameters:**
- `bot_name` (str, optional): Optional bot to filter by

**Returns:**
- `float`: Total cost in USD

**Example:**
```python
from bots.shared.cost_tracker import get_daily_cost

total = get_daily_cost()
matt_cost = get_daily_cost(bot_name="clawdmatt")
```

---

#### get_monthly_cost(bot_name: Optional[str] = None) -> float

Get current month's total cost (uses global tracker).

**Parameters:**
- `bot_name` (str, optional): Optional bot to filter by

**Returns:**
- `float`: Total cost in USD

**Example:**
```python
from bots.shared.cost_tracker import get_monthly_cost

monthly = get_monthly_cost()
```

---

#### check_budget(bot_name: str) -> bool

Check if bot is under daily budget (uses global tracker).

**Parameters:**
- `bot_name` (str): Name of the bot

**Returns:**
- `bool`: True if under budget

**Example:**
```python
from bots.shared.cost_tracker import check_budget

if check_budget("clawdmatt"):
    make_api_call()
```

---

#### set_daily_limit(bot_name: str, limit: float) -> None

Set daily cost limit for a bot (uses global tracker).

**Parameters:**
- `bot_name` (str): Name of the bot
- `limit` (float): Daily limit in USD

**Example:**
```python
from bots.shared.cost_tracker import set_daily_limit

set_daily_limit("clawdmatt", 15.0)
```

---

#### get_cost_report() -> str

Generate cost report (uses global tracker).

**Returns:**
- `str`: Formatted cost report

**Example:**
```python
from bots.shared.cost_tracker import get_cost_report

print(get_cost_report())
```

---

# Utility Modules

## life_control_commands

Full autonomous control via Telegram for ClawdBots. Provides natural language control of Gmail, Calendar, Drive, deployments, Firebase, phone, wallet, and more.

**Module:** `bots.shared.life_control_commands`

### Main Function

#### register_life_commands(bot) -> bot

Register all life control commands on a Telegram bot.

**Parameters:**
- `bot`: Telegram bot instance (telebot.TeleBot)

**Returns:**
- `bot`: The same bot instance with commands registered

**Example:**
```python
from bots.shared.life_control_commands import register_life_commands
import telebot

bot = telebot.TeleBot(token)
register_life_commands(bot)

bot.polling()
```

---

### Telegram Commands

All commands require remote control to be available. If not available, returns error message.

#### /do or /jarvis

Execute ANY natural language request.

**Usage:** `/do <what you want>`

**Examples:**
- `/do Send John an email about the meeting`
- `/do Check my calendar for tomorrow`
- `/do Deploy the website changes`
- `/do Create a new Firebase project`

Routes to `control_computer()` which handles everything with full access to browser, SSH, file system.

---

#### /email, /gmail, /mail

Gmail operations.

**Usage:** `/email [request]`

**Examples:**
- `/email check inbox`
- `/email send to john@example.com about the project`
- `/email show recent from Bob`

Uses `browse_web()` to navigate Gmail interface.

---

#### /calendar, /cal, /schedule

Google Calendar operations.

**Usage:** `/calendar [request]`

**Examples:**
- `/calendar show today`
- `/calendar add meeting with Bob on Friday at 3pm`
- `/calendar check next week`

Uses `browse_web()` to navigate Google Calendar.

---

#### /drive, /docs, /sheets

Google Drive/Docs operations.

**Usage:** `/drive [request]`

**Examples:**
- `/drive show recent`
- `/drive open Project Plan doc`
- `/drive create new sheet`

Uses `browse_web()` to navigate Google Drive.

---

#### /deploy, /host, /hostinger

Website deployment.

**Usage:** `/deploy [request]`

**Examples:**
- `/deploy latest changes to hostinger`
- `/deploy check status`
- `/host show logs`

Uses `control_computer()` for SSH deployment or `browse_web()` for Hostinger panel.

---

#### /firebase, /gcloud, /cloud

Firebase/Google Cloud operations.

**Usage:** `/firebase [request]` or `/gcloud [request]`

**Examples:**
- `/firebase show projects`
- `/firebase create new project MyApp`
- `/gcloud check billing`

Uses `browse_web()` to navigate Firebase Console or Google Cloud Console.

---

#### /billing

Google Cloud billing check.

**Usage:** `/billing`

Shows:
- Current month charges
- Active projects
- Payment method on file

Uses `browse_web()` to navigate Google Cloud Billing.

---

#### /wallet, /sol, /solana

Solana wallet operations.

**Usage:** `/wallet [request]`

**Examples:**
- `/wallet check balance`
- `/wallet show tokens`
- `/wallet send 1 SOL to <address>` (prepares but doesn't execute without confirmation)

Uses `control_computer()` to access treasury wallet.

**WARNING:** Sending operations require explicit confirmation.

---

#### /phone, /android

Android phone control via ADB over Tailscale.

**Usage:** `/phone [command]`

**Examples:**
- `/phone battery`
- `/phone screenshot`
- `/phone show notifications`

Uses `control_computer()` to run ADB commands to phone at `100.88.183.6:5555`.

---

#### /screenshot, /screen

Take screenshot of desktop.

**Usage:** `/screenshot`

Uses `control_computer()` to capture screen and save to Desktop.

---

#### /help, /commands

Show all available commands.

**Usage:** `/help`

Returns formatted list of all life control commands with examples.

---

### Complete Usage Example

```python
from bots.shared.life_control_commands import register_life_commands
import telebot

# Create bot
bot = telebot.TeleBot("YOUR_TOKEN_HERE")

# Register all life control commands
register_life_commands(bot)

# Start polling
print("Bot is running with full life control...")
bot.polling()
```

**In Telegram:**
```
User: /do Send an email to john@example.com about tomorrow's meeting
Bot: Processing: Send an email to john@example.com about tom...
Bot: Result: Email sent successfully to john@example.com with subject "Tomorrow's Meeting"

User: /calendar add meeting with Bob on Friday at 3pm
Bot: Calendar: add meeting with Bob on Friday at 3pm...
Bot: Calendar: Event "Meeting with Bob" added for Friday, Feb 7 at 3:00 PM

User: /wallet check balance
Bot: Wallet: check balance...
Bot: Wallet: Treasury Balance:
     SOL: 12.45
     USDC: 1,234.56
```

---

## Summary

The ClawdBot shared modules provide:

1. **Computer Control** (`computer_capabilities`) - Remote browser automation and full computer control via Tailscale
2. **Coordination** (`coordination`) - Task delegation, messaging, and status reporting between the three ClawdBots
3. **Self-Healing** (`self_healing`) - Process health monitoring, automatic restart, error detection, and heartbeat
4. **Cost Tracking** (`cost_tracker`) - API cost tracking with budget limits and alerts
5. **Life Control** (`life_control_commands`) - Natural language control of email, calendar, deployments, wallet, and more via Telegram

All modules are production-ready and battle-tested on the ClawdBots VPS deployment.

---

**End of API Reference**
