"""
Actions module for LifeOS.
High-level actions Jarvis can perform: emails, windows, browsing, etc.
"""

import subprocess
import time
from typing import Any, Dict, Optional, Tuple

from core import computer, guardian


def open_mail_app() -> Tuple[bool, str]:
    """Open the default mail application."""
    return computer.open_app("Mail")


def compose_email(to: str = "", subject: str = "", body: str = "") -> Tuple[bool, str]:
    """Open a new email composition window with pre-filled fields."""
    script = f'''
    tell application "Mail"
        activate
        set newMessage to make new outgoing message with properties {{visible:true}}
        tell newMessage
            set subject to "{subject.replace('"', '\\"')}"
            set content to "{body.replace('"', '\\"').replace(chr(10), '\\n')}"
            if "{to}" is not "" then
                make new to recipient at end of to recipients with properties {{address:"{to}"}}
            end if
        end tell
    end tell
    '''
    return computer._run_applescript(script)


def send_email_via_mailto(to: str, subject: str = "", body: str = "") -> Tuple[bool, str]:
    """Open email via mailto: URL (works with any mail client)."""
    import urllib.parse
    params = urllib.parse.urlencode({"subject": subject, "body": body})
    url = f"mailto:{to}?{params}"
    return computer.open_url(url)


def open_browser(url: str = "") -> Tuple[bool, str]:
    """Open default browser, optionally to a URL."""
    if url:
        return computer.open_url(url)
    return computer.open_app("Safari")


def google_search(query: str) -> Tuple[bool, str]:
    """Perform a Google search."""
    import urllib.parse
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    return computer.open_url(url)


def open_finder(path: str = "~") -> Tuple[bool, str]:
    """Open Finder to a specific path."""
    import os
    expanded = os.path.expanduser(path)
    return computer.open_file(expanded)


def open_terminal() -> Tuple[bool, str]:
    """Open Terminal app."""
    return computer.open_app("Terminal")


def open_notes() -> Tuple[bool, str]:
    """Open Notes app."""
    return computer.open_app("Notes")


def create_note(title: str, body: str) -> Tuple[bool, str]:
    """Create a new note in Notes app."""
    script = f'''
    tell application "Notes"
        activate
        tell account "iCloud"
            make new note at folder "Notes" with properties {{name:"{title.replace('"', '\\"')}", body:"{body.replace('"', '\\"')}"}}
        end tell
    end tell
    '''
    return computer._run_applescript(script)


def open_calendar() -> Tuple[bool, str]:
    """Open Calendar app."""
    return computer.open_app("Calendar")


def create_calendar_event(title: str, date: str, time_str: str = "09:00", duration_hours: int = 1) -> Tuple[bool, str]:
    """Create a calendar event."""
    script = f'''
    tell application "Calendar"
        activate
        tell calendar "Calendar"
            set startDate to date "{date} {time_str}"
            set endDate to startDate + ({duration_hours} * hours)
            make new event with properties {{summary:"{title.replace('"', '\\"')}", start date:startDate, end date:endDate}}
        end tell
    end tell
    '''
    return computer._run_applescript(script)


def open_messages() -> Tuple[bool, str]:
    """Open Messages app."""
    return computer.open_app("Messages")


def send_imessage(to: str, message: str) -> Tuple[bool, str]:
    """Send an iMessage."""
    script = f'''
    tell application "Messages"
        set targetService to 1st account whose service type = iMessage
        set targetBuddy to participant "{to}" of targetService
        send "{message.replace('"', '\\"')}" to targetBuddy
    end tell
    '''
    return computer._run_applescript(script)


def set_reminder(title: str, due_date: str = "") -> Tuple[bool, str]:
    """Create a reminder."""
    if due_date:
        script = f'''
        tell application "Reminders"
            make new reminder with properties {{name:"{title.replace('"', '\\"')}", due date:date "{due_date}"}}
        end tell
        '''
    else:
        script = f'''
        tell application "Reminders"
            make new reminder with properties {{name:"{title.replace('"', '\\"')}"}}
        end tell
        '''
    return computer._run_applescript(script)


def speak(text: str, voice: str = "Alex") -> Tuple[bool, str]:
    """Make the computer speak."""
    try:
        subprocess.run(["say", "-v", voice, text], check=True, timeout=30)
        return True, f"Spoke: {text[:50]}..."
    except Exception as e:
        return False, str(e)


def get_current_app() -> str:
    """Get the currently focused application."""
    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
    success, output = computer._run_applescript(script)
    return output if success else "Unknown"


def list_running_apps() -> list:
    """List all running applications."""
    script = 'tell application "System Events" to get name of every process whose visible is true'
    success, output = computer._run_applescript(script)
    if success and output:
        return [app.strip() for app in output.split(",")]
    return []


def switch_to_app(app_name: str) -> Tuple[bool, str]:
    """Switch to a specific application."""
    return computer.open_app(app_name)


def minimize_window() -> Tuple[bool, str]:
    """Minimize the current window."""
    return computer.press_key("m", ["command"])


def close_window() -> Tuple[bool, str]:
    """Close the current window."""
    return computer.press_key("w", ["command"])


def new_window() -> Tuple[bool, str]:
    """Open a new window in current app."""
    return computer.press_key("n", ["command"])


def new_tab() -> Tuple[bool, str]:
    """Open a new tab in current app."""
    return computer.press_key("t", ["command"])


def save_file() -> Tuple[bool, str]:
    """Save the current file."""
    return computer.press_key("s", ["command"])


def copy() -> Tuple[bool, str]:
    """Copy selection."""
    return computer.press_key("c", ["command"])


def paste() -> Tuple[bool, str]:
    """Paste clipboard."""
    return computer.press_key("v", ["command"])


def cut() -> Tuple[bool, str]:
    """Cut selection."""
    return computer.press_key("x", ["command"])


def undo() -> Tuple[bool, str]:
    """Undo last action."""
    return computer.press_key("z", ["command"])


def select_all() -> Tuple[bool, str]:
    """Select all."""
    return computer.press_key("a", ["command"])


def spotlight_search(query: str = "") -> Tuple[bool, str]:
    """Open Spotlight search."""
    success, msg = computer.press_key("space", ["command"])
    if success and query:
        time.sleep(0.3)
        return computer.type_text(query)
    return success, msg


# Action registry for natural language mapping
ACTION_REGISTRY = {
    "open_mail": open_mail_app,
    "compose_email": compose_email,
    "send_email": send_email_via_mailto,
    "open_browser": open_browser,
    "google": google_search,
    "search": google_search,
    "open_finder": open_finder,
    "open_terminal": open_terminal,
    "open_notes": open_notes,
    "create_note": create_note,
    "open_calendar": open_calendar,
    "create_event": create_calendar_event,
    "open_messages": open_messages,
    "send_message": send_imessage,
    "set_reminder": set_reminder,
    "speak": speak,
    "switch_app": switch_to_app,
    "minimize": minimize_window,
    "close_window": close_window,
    "new_window": new_window,
    "new_tab": new_tab,
    "save": save_file,
    "copy": copy,
    "paste": paste,
    "cut": cut,
    "undo": undo,
    "select_all": select_all,
    "spotlight": spotlight_search,
}


def execute_action(action_name: str, **kwargs) -> Tuple[bool, str]:
    """Execute a named action with parameters."""
    if action_name not in ACTION_REGISTRY:
        return False, f"Unknown action: {action_name}"
    
    try:
        func = ACTION_REGISTRY[action_name]
        return func(**kwargs)
    except Exception as e:
        return False, f"Action failed: {str(e)}"


def execute_with_fallback(action_name: str, fallbacks: list = None, **kwargs) -> Tuple[bool, str]:
    """Execute an action with fallback alternatives if it fails."""
    # Try primary action
    success, msg = execute_action(action_name, **kwargs)
    if success:
        return success, msg
    
    # Try fallbacks
    if fallbacks:
        for fallback in fallbacks:
            fb_name = fallback.get("action", "")
            fb_kwargs = fallback.get("params", {})
            success, msg = execute_action(fb_name, **fb_kwargs)
            if success:
                return success, f"Used fallback {fb_name}: {msg}"
    
    # Try to find alternative automatically
    alternatives = get_alternative_actions(action_name)
    for alt in alternatives:
        success, msg = execute_action(alt, **kwargs)
        if success:
            return success, f"Used alternative {alt}: {msg}"
    
    return False, f"All attempts failed for {action_name}"


def get_alternative_actions(action_name: str) -> list:
    """Get alternative actions for a given action."""
    alternatives = {
        "compose_email": ["send_email", "open_mail"],
        "send_email": ["compose_email", "open_mail"],
        "google": ["open_browser"],
        "search": ["spotlight", "google"],
        "open_notes": ["create_note"],
        "create_note": ["open_notes"],
        "send_message": ["open_messages"],
        "create_event": ["open_calendar"],
    }
    return alternatives.get(action_name, [])


def get_available_actions() -> list:
    """Get list of available actions."""
    return list(ACTION_REGISTRY.keys())
