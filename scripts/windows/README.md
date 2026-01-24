# Jarvis Supervisor Auto-Startup on Windows

This directory contains scripts to configure Windows Task Scheduler to automatically start the Jarvis supervisor daemon on system boot.

## Files

| File | Purpose |
|------|---------|
| `start-jarvis-supervisor.ps1` | PowerShell script to start the supervisor (with checks) |
| `stop-jarvis-supervisor.ps1` | PowerShell script to stop the supervisor |
| `jarvis-supervisor-task.xml` | Task Scheduler configuration |
| `install-startup-task.ps1` | Install the scheduled task |
| `uninstall-startup-task.ps1` | Remove the scheduled task |
| `README.md` | This documentation |

## Features

- Automatic startup on system boot (30-second delay)
- Checks if supervisor is already running (prevents duplicates)
- Waits for network connectivity before starting
- Restarts on failure (up to 3 times with 1-minute intervals)
- Logs all actions to `logs/supervisor-startup.log`
- Runs as current user (no elevation required)

## Installation

### Step 1: Test the Startup Script Manually

Before installing the scheduled task, test the startup script to ensure it works:

```powershell
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts\windows
powershell -ExecutionPolicy Bypass -File .\start-jarvis-supervisor.ps1
```

Check the output for any errors. The supervisor should start successfully.

### Step 2: Install the Scheduled Task

Run the installation script **as Administrator**:

```powershell
# Right-click PowerShell and "Run as Administrator"
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts\windows
.\install-startup-task.ps1
```

The script will:
1. Check if the task already exists (and offer to replace it)
2. Register the scheduled task from the XML configuration
3. Display task details and verification

### Step 3: Verify Installation

Check that the task was created:

```powershell
Get-ScheduledTask -TaskName "Jarvis Supervisor Daemon" -TaskPath "\Jarvis\"
```

You should see:
- **State**: Ready
- **Trigger**: Boot (30s delay)
- **User**: lucid

## Usage

### Manual Start

To start the supervisor manually via the scheduled task:

```powershell
Start-ScheduledTask -TaskName "Jarvis Supervisor Daemon" -TaskPath "\Jarvis\"
```

Or run the PowerShell script directly:

```powershell
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts\windows
powershell -ExecutionPolicy Bypass -File .\start-jarvis-supervisor.ps1
```

### Manual Stop

To stop the supervisor:

```powershell
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts\windows
powershell -ExecutionPolicy Bypass -File .\stop-jarvis-supervisor.ps1
```

### Check Logs

View startup logs:

```powershell
notepad C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\supervisor-startup.log
```

Or tail in PowerShell:

```powershell
Get-Content C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\supervisor-startup.log -Wait -Tail 20
```

### Check If Running

Check if the supervisor is running:

```powershell
Get-Process python | Where-Object { $_.CommandLine -like "*supervisor.py*" }
```

Or check the lock file:

```powershell
Get-Content C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\.supervisor.lock | ConvertFrom-Json
```

## Uninstallation

To remove the scheduled task, run **as Administrator**:

```powershell
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts\windows
.\uninstall-startup-task.ps1
```

This will:
1. Ask for confirmation
2. Remove the scheduled task
3. The supervisor will NOT start automatically after the next boot

The scripts themselves remain in the directory and can be used manually.

## Configuration

### Startup Delay

The task waits **30 seconds** after boot before starting the supervisor. This allows:
- Network to initialize
- Docker Desktop to start (if required)
- System services to be ready

To change the delay, edit `jarvis-supervisor-task.xml`:

```xml
<Delay>PT30S</Delay>  <!-- 30 seconds -->
```

Change to:
- `PT1M` = 1 minute
- `PT2M` = 2 minutes
- `PT45S` = 45 seconds

Then reinstall the task.

### Restart on Failure

The task will restart the supervisor if it fails:
- **Max retries**: 3
- **Retry interval**: 1 minute

To change, edit `jarvis-supervisor-task.xml`:

```xml
<RestartOnFailure>
  <Interval>PT1M</Interval>  <!-- 1 minute -->
  <Count>3</Count>            <!-- 3 retries -->
</RestartOnFailure>
```

### Python Path

If Python is installed elsewhere, edit `start-jarvis-supervisor.ps1`:

```powershell
$PythonExe = "C:\Users\lucid\AppData\Local\Programs\Python\Python312\python.exe"
```

## Troubleshooting

### Task doesn't start on boot

1. Check Task Scheduler for errors:
   ```powershell
   Get-ScheduledTaskInfo -TaskName "Jarvis Supervisor Daemon" -TaskPath "\Jarvis\"
   ```

2. Check the startup log:
   ```powershell
   notepad C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\supervisor-startup.log
   ```

3. Verify network requirement:
   - The task requires network connectivity
   - Check: `RunOnlyIfNetworkAvailable: true` in XML

### Supervisor starts but stops immediately

1. Check if supervisor script has errors:
   ```powershell
   cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis
   python bots\supervisor.py
   ```

2. Check environment variables are set

3. Check if Docker is running (if required)

### Multiple instances running

The startup script checks for existing instances via:
1. Lock file at `.supervisor.lock`
2. Process search for `supervisor.py`

If duplicates exist, stop all:

```powershell
.\stop-jarvis-supervisor.ps1
```

Then start fresh:

```powershell
.\start-jarvis-supervisor.ps1
```

### Task runs but supervisor doesn't start

Check Task Scheduler History:
1. Open Task Scheduler GUI
2. Navigate to `\Jarvis\Supervisor Daemon`
3. Enable "History" in the Actions pane
4. Review recent execution events

Common causes:
- Execution policy blocking PowerShell scripts
- Python path incorrect
- Working directory incorrect

### Permission Issues

If the task fails due to permissions:

1. Ensure task runs as current user (`lucid`)
2. Check that scripts are not blocked:
   ```powershell
   Unblock-File .\start-jarvis-supervisor.ps1
   Unblock-File .\stop-jarvis-supervisor.ps1
   ```

## Advanced: Using schtasks Command

Instead of the XML file, you can create the task via command line:

```batch
schtasks /Create /TN "\Jarvis\Supervisor Daemon" ^
  /TR "powershell.exe -ExecutionPolicy Bypass -NoProfile -File 'C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts\windows\start-jarvis-supervisor.ps1'" ^
  /SC ONSTART ^
  /DELAY 0000:30 ^
  /RU lucid ^
  /RL LIMITED ^
  /F
```

To delete:

```batch
schtasks /Delete /TN "\Jarvis\Supervisor Daemon" /F
```

## Security Notes

- The task runs with **LeastPrivilege** (no admin rights)
- Scripts use `-ExecutionPolicy Bypass` to avoid policy restrictions
- Lock file prevents duplicate instances
- No sensitive data is logged

## Dependencies

The startup script checks for:
- Python executable
- Supervisor script
- Network connectivity
- Docker Desktop (optional warning)

If any are missing, the script logs an error and exits.

## See Also

- Main supervisor: `bots/supervisor.py`
- Supervisor documentation: `docs/SUPERVISOR.md` (if exists)
- Environment configuration: `.env`
