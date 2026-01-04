# Timeout Protection & Hang Prevention

## Problem
The system was experiencing constant hangs on terminal commands, with operations blocking for hours. This was caused by:
- No timeout enforcement on subprocess calls
- Extremely long command chains (20+ chained commands with `&&`)
- Async operations without timeout protection
- No validation of potentially hanging commands

## Solution Implemented

### 1. Centralized Timeout Configuration ([core/timeout_config.py](core/timeout_config.py))

**Aggressive timeout defaults:**
- `subprocess_quick`: 5s (for fast commands like `git status`)
- `subprocess_default`: 10s (default for all commands)
- `subprocess_medium`: 15s (for medium tasks)
- `subprocess_long`: 30s (maximum for most operations)
- `subprocess_critical`: 60s (only for truly critical ops)

**Intelligent timeout selection:**
- Auto-detects quick commands (ls, pwd, echo, git status, etc.)
- Auto-detects long commands (pip install, git clone, downloads)
- Analyzes command chain length to adjust timeout
- Prevents command chains with 5+ operations

### 2. Safe Subprocess Wrapper ([core/safe_subprocess.py](core/safe_subprocess.py))

**Features:**
- **Aggressive timeout enforcement** - All commands get automatic timeout
- **Force kill on timeout** - Kills entire process tree, not just parent
- **Auto-timeout detection** - Determines appropriate timeout from command
- **Async support** - `run_command_async()` for async operations
- **Live output streaming** - `run_with_live_output()` with timeout protection
- **Command validation** - Blocks dangerous/hanging commands before execution

**Functions:**
```python
# Sync execution with timeout
result = safe_subprocess.run_command_safe(command, timeout=15)

# Async execution with timeout  
result = await safe_subprocess.run_command_async(command, timeout=20)

# Live output with timeout
result = safe_subprocess.run_with_live_output(command, callback=print)
```

### 3. Command Validator ([core/command_validator.py](core/command_validator.py))

**Prevents hanging commands:**
- Blocks commands with 5+ chained operations
- Blocks infinite loops (`while true`)
- Blocks blocking commands (`tail -f`, `watch`, etc.)
- Warns about long-running servers without background flag
- Suggests running servers in background

**Validation patterns blocked:**
- Long git chains with multiple fetch/log operations
- Infinite loops
- Blocking tail/watch commands
- Development servers (jupyter, flask, npm start) without background flag
- Commands over 500 characters

**Auto-fix capabilities:**
- Adds timeouts to slow operations (git clone, npm install)
- Suggests splitting long command chains
- Recommends background execution for servers

### 4. Updated Core Modules

**Files updated to use safe_subprocess:**
- [core/computer.py](core/computer.py) - `run_shell()` now uses safe_subprocess
- [core/autonomous_agent.py](core/autonomous_agent.py) - `_terminal_tool()` uses safe_subprocess
- [core/self_healing.py](core/self_healing.py) - Imports safe_subprocess
- [core/learning_validator.py](core/learning_validator.py) - Test execution with timeouts

**Scripts updated:**
- [scripts/monitor_positions.py](scripts/monitor_positions.py) - Added 10s API timeout, 60s check timeout

### 5. Timeout Protection Matrix

| Operation Type | Default Timeout | Notes |
|---------------|----------------|--------|
| git status, ls, pwd | 5s | Quick commands |
| Generic command | 10s | Safe default |
| API calls | 10-15s | Network operations |
| git clone, pip install | 30-60s | Long operations |
| Test execution | 30s | Test suites |
| Position monitoring | 60s | Trading checks |

## Usage

### Sync Command Execution
```python
from core import safe_subprocess

# Auto timeout (10s default)
result = safe_subprocess.run_command_safe("git status")

# Custom timeout
result = safe_subprocess.run_command_safe("pip install requests", timeout=60)

# Check result
if result["timed_out"]:
    print(f"Command killed after {result['timeout']}s")
elif result["blocked"]:
    print(f"Command blocked: {result['stderr']}")
else:
    print(result["stdout"])
```

### Async Command Execution
```python
import asyncio
from core import safe_subprocess

async def run_checks():
    result = await safe_subprocess.run_command_async("git log -1")
    return result["stdout"]
```

### Command Validation
```python
from core.command_validator import validate_before_run

is_safe, error, warnings = validate_before_run(command)
if not is_safe:
    print(f"Blocked: {error}")
else:
    for warning in warnings:
        print(f"Warning: {warning}")
```

## Impact

**Before:**
- Commands hanging for hours
- No automatic recovery
- Terminal sessions blocked indefinitely
- Manual intervention required constantly

**After:**
- All commands timeout within 10-60s
- Automatic process killing
- Validation prevents hanging commands
- System remains responsive
- Clear timeout/error messages

## Configuration

Edit timeouts in [core/timeout_config.py](core/timeout_config.py):

```python
TIMEOUTS = {
    "subprocess_default": 10,  # Adjust default timeout
    "subprocess_long": 30,     # Adjust max timeout
    # ... other settings
}
```

Add patterns to block in [core/command_validator.py](core/command_validator.py):

```python
HANGING_COMMAND_PATTERNS = [
    r"your_blocking_pattern",
    # ... other patterns
]
```

## Testing

Test the timeout protection:

```bash
# Should timeout after 10s
./venv311/bin/python -c "from core.safe_subprocess import run_command_safe; print(run_command_safe('sleep 100'))"

# Should be blocked
./venv311/bin/python -c "from core.safe_subprocess import run_command_safe; print(run_command_safe('while true; do echo loop; done'))"
```

## Future Improvements

1. Add timeout metrics/monitoring
2. Machine learning to predict optimal timeouts
3. Automatic timeout adjustment based on historical execution times
4. Better handling of background processes
5. Integration with process monitoring tools

## Related Files

- [core/timeout_config.py](core/timeout_config.py) - Timeout configuration
- [core/safe_subprocess.py](core/safe_subprocess.py) - Safe subprocess wrapper
- [core/command_validator.py](core/command_validator.py) - Command validation
- [core/computer.py](core/computer.py) - Computer control with timeouts
- [core/autonomous_agent.py](core/autonomous_agent.py) - Agent terminal tools
- [scripts/monitor_positions.py](scripts/monitor_positions.py) - Async monitoring
