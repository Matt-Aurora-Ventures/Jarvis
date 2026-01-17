#!/usr/bin/env python3
"""
Fix asyncio.create_task calls in supervisor.py to use proper tracking.

Untracked tasks can fail silently and cause memory leaks.
"""

from pathlib import Path

SUPERVISOR_FILE = Path(__file__).parent.parent / "bots" / "supervisor.py"


def apply_fixes():
    """Apply task tracking fixes to supervisor.py"""
    print(f"Reading {SUPERVISOR_FILE}...")
    content = SUPERVISOR_FILE.read_text(encoding="utf-8")
    original = content

    # Fix 1: Add import for fire_and_forget
    if "from core.async_utils import" not in content:
        print("Adding async_utils import...")
        # Add after the existing imports
        content = content.replace(
            "from enum import Enum\n",
            "from enum import Enum\n\n# Import safe task tracking\ntry:\n    from core.async_utils import fire_and_forget, TaskTracker\n    TASK_TRACKING_AVAILABLE = True\nexcept ImportError:\n    TASK_TRACKING_AVAILABLE = False\n    fire_and_forget = None\n    TaskTracker = None\n"
        )

    # Fix 2: Replace untracked create_task with fire_and_forget
    # For error alerts
    old_error_alert = "asyncio.create_task(self._send_error_alert("
    new_error_alert = """if TASK_TRACKING_AVAILABLE:
                        fire_and_forget(self._send_error_alert("""

    if "fire_and_forget(self._send_error_alert" not in content:
        print("Fixing error alert task...")
        # This is tricky because of indentation - let's do a more targeted replace
        content = content.replace(
            "                if state.consecutive_failures % 5 == 0:\n                    asyncio.create_task(self._send_error_alert(\n                        name, str(e), state.consecutive_failures, state.restart_count\n                    ))",
            "                if state.consecutive_failures % 5 == 0:\n                    if TASK_TRACKING_AVAILABLE:\n                        fire_and_forget(\n                            self._send_error_alert(name, str(e), state.consecutive_failures, state.restart_count),\n                            name=f\"error_alert_{name}\"\n                        )\n                    else:\n                        asyncio.create_task(self._send_error_alert(\n                            name, str(e), state.consecutive_failures, state.restart_count\n                        ))"
        )

    # Fix 3: Replace untracked create_task for critical alert
    if "fire_and_forget(self._send_critical_alert" not in content:
        print("Fixing critical alert task...")
        content = content.replace(
            "                    # Send critical alert\n                    asyncio.create_task(self._send_critical_alert(name, str(e)))",
            "                    # Send critical alert\n                    if TASK_TRACKING_AVAILABLE:\n                        fire_and_forget(\n                            self._send_critical_alert(name, str(e)),\n                            name=f\"critical_alert_{name}\"\n                        )\n                    else:\n                        asyncio.create_task(self._send_critical_alert(name, str(e)))"
        )

    if content == original:
        print("No changes needed - file may already be patched.")
        return False

    print(f"Writing fixes to {SUPERVISOR_FILE}...")
    SUPERVISOR_FILE.write_text(content, encoding="utf-8")
    print("Done! Supervisor now uses tracked tasks for alerts.")
    return True


if __name__ == "__main__":
    apply_fixes()
