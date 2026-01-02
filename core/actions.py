"""
Actions module for LifeOS.
High-level actions Jarvis can perform: emails, windows, browsing, etc.

Every action is executed with discipline:
- WHY: Explicit reason for the action
- EXPECTED: What we expect to happen
- ACTUAL: What actually happened
- LEARN: Feed back into the learning loop
"""

import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from core import computer, guardian, config, state, notes_manager

FIREFOX_APP = "Firefox Developer Edition"


def _open_in_firefox(target: str = "") -> Tuple[bool, str]:
    """Open Firefox Developer Edition optionally pointing at a URL."""
    cmd = ["open", "-a", FIREFOX_APP]
    if target:
        cmd.append(target)
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        action_desc = f"Firefox opened to {target}" if target else "Firefox opened"
        return True, action_desc
    except subprocess.CalledProcessError as exc:
        return False, f"Failed to open Firefox Developer Edition: {exc}"
    except FileNotFoundError:
        return False, "Firefox Developer Edition not found; please install it in /Applications"


def _ui_allowed(action: str) -> bool:
    cfg = config.load_config()
    allow_cfg = bool(cfg.get("actions", {}).get("allow_ui", True))
    require_confirm = bool(cfg.get("actions", {}).get("require_confirm", False))
    state_flag = state.read_state().get("ui_actions_enabled")
    if require_confirm and not state.read_state().get("ui_actions_confirmed", False):
        return False
    return allow_cfg and (state_flag is not False)


def _ui_blocked_msg(action: str) -> Tuple[bool, str]:
    return False, (
        f"UI actions are disabled while autonomy tasks run (blocked: {action}). "
        "Set actions.allow_ui=true and ui_actions_enabled=true to override. "
        "If actions.require_confirm=true, also set ui_actions_confirmed=true."
    )


def open_mail_app() -> Tuple[bool, str]:
    """Open the default mail application."""
    if not _ui_allowed("open_mail_app"):
        return _ui_blocked_msg("open_mail_app")
    return computer.open_app("Mail")


def compose_email(to: str = "", subject: str = "", body: str = "") -> Tuple[bool, str]:
    """Open a new email composition window with pre-filled fields."""
    if not _ui_allowed("compose_email"):
        return _ui_blocked_msg("compose_email")
    escaped_subject = subject.replace('"', '\\"')
    escaped_body = body.replace('"', '\\"').replace(chr(10), '\\n')
    script = f'''
    tell application "Mail"
        activate
        set newMessage to make new outgoing message with properties {{visible:true}}
        tell newMessage
            set subject to "{escaped_subject}"
            set content to "{escaped_body}"
            if "{to}" is not "" then
                make new to recipient at end of to recipients with properties {{address:"{to}"}}
            end if
        end tell
    end tell
    '''
    return computer._run_applescript(script)


def send_email_via_mailto(to: str, subject: str = "", body: str = "") -> Tuple[bool, str]:
    """Open email via mailto: URL (works with any mail client)."""
    if not _ui_allowed("send_email"):
        return _ui_blocked_msg("send_email")
    import urllib.parse
    params = urllib.parse.urlencode({"subject": subject, "body": body})
    url = f"mailto:{to}?{params}"
    return computer.open_url(url)


def open_browser(url: str = "", param: str = "", **_: Any) -> Tuple[bool, str]:
    """Open Firefox Developer Edition, optionally to a URL."""
    if not _ui_allowed("open_browser"):
        return _ui_blocked_msg("open_browser")
    target = url or param
    if target and not target.lower().startswith(("http://", "https://")):
        target = f"https://{target}"
    return _open_in_firefox(target or "")


def google_search(query: str, **_: Any) -> Tuple[bool, str]:
    """Perform a Google search."""
    if not _ui_allowed("google_search"):
        return _ui_blocked_msg("google_search")
    import urllib.parse
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    return _open_in_firefox(url)


def open_finder(path: str = "~") -> Tuple[bool, str]:
    """Open Finder to a specific path."""
    if not _ui_allowed("open_finder"):
        return _ui_blocked_msg("open_finder")
    import os
    expanded = os.path.expanduser(path)
    return computer.open_file(expanded)


def open_terminal() -> Tuple[bool, str]:
    """Open Terminal app."""
    if not _ui_allowed("open_terminal"):
        return _ui_blocked_msg("open_terminal")
    return computer.open_app("Terminal")


def open_notes(topic: str = "", app: str = "", **_: Any) -> Tuple[bool, str]:
    """Open local note folder for a topic."""
    if not _ui_allowed("open_notes"):
        return _ui_blocked_msg("open_notes")
    dest = notes_manager.topic_dir(topic or None)
    dest.mkdir(parents=True, exist_ok=True)
    success, output = computer.open_file(str(dest))
    if success:
        return True, f"Opened notes folder: {dest}"
    # Fallback: try revealing in Finder, otherwise surface manual path info.
    try:
        subprocess.run(
            ["open", "-R", str(dest)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True, f"Revealed notes folder in Finder: {dest}"
    except Exception:
        return True, (
            f"Notes folder is ready at {dest}, but macOS refused to open it automatically "
            f"({output}). Please open it manually if needed."
        )


def create_note(title: str, body: str, topic: str = "") -> Tuple[bool, str]:
    """Persist a note locally and capture a distilled summary."""
    final_topic, note_body = notes_manager.extract_topic_and_body(
        f"{topic.strip()}: {body or title}".strip(": ")
    )
    note_path, summary_path, _ = notes_manager.save_note(
        topic=final_topic,
        content=f"# {title or final_topic}\n\n{note_body}",
        fmt="md",
        tags=["action", "note"],
        source="actions.create_note",
    )
    return True, f"Saved note to {note_path} (summary: {summary_path})"


def open_calendar() -> Tuple[bool, str]:
    """Open Calendar app."""
    if not _ui_allowed("open_calendar"):
        return _ui_blocked_msg("open_calendar")
    return computer.open_app("Calendar")


def create_calendar_event(title: str, date: str, time_str: str = "09:00", duration_hours: int = 1) -> Tuple[bool, str]:
    """Create a calendar event."""
    if not _ui_allowed("create_calendar_event"):
        return _ui_blocked_msg("create_calendar_event")
    escaped_title = title.replace('"', '\\"')
    script = f'''
    tell application "Calendar"
        activate
        tell calendar "Calendar"
            set startDate to date "{date} {time_str}"
            set endDate to startDate + ({duration_hours} * hours)
            make new event with properties {{summary:"{escaped_title}", start date:startDate, end date:endDate}}
        end tell
    end tell
    '''
    return computer._run_applescript(script)


def open_messages() -> Tuple[bool, str]:
    """Open Messages app."""
    if not _ui_allowed("open_messages"):
        return _ui_blocked_msg("open_messages")
    return computer.open_app("Messages")


def send_imessage(to: str, message: str) -> Tuple[bool, str]:
    """Send an iMessage."""
    if not _ui_allowed("send_imessage"):
        return _ui_blocked_msg("send_imessage")
    escaped_message = message.replace('"', '\\"')
    script = f'''
    tell application "Messages"
        set targetService to 1st account whose service type = iMessage
        set targetBuddy to participant "{to}" of targetService
        send "{escaped_message}" to targetBuddy
    end tell
    '''
    return computer._run_applescript(script)


def set_reminder(title: str, due_date: str = "") -> Tuple[bool, str]:
    """Create a reminder."""
    if not _ui_allowed("set_reminder"):
        return _ui_blocked_msg("set_reminder")
    escaped_title = title.replace('"', '\\"')
    if due_date:
        script = f'''
        tell application "Reminders"
            make new reminder with properties {{name:"{escaped_title}", due date:date "{due_date}"}}
        end tell
        '''
    else:
        script = f'''
        tell application "Reminders"
            make new reminder with properties {{name:"{escaped_title}"}}
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


def new_window(app: str = "", **_: Any) -> Tuple[bool, str]:
    """Open a new window in current app."""
    return computer.press_key("n", ["command"])


def new_tab(app: str = "", **_: Any) -> Tuple[bool, str]:
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


def execute_action(
    action_name: str,
    why: str = "",
    expected_outcome: str = "",
    **kwargs,
) -> Tuple[bool, str]:
    """
    Execute a named action with parameters and discipline.

    Args:
        action_name: Name of the action to execute
        why: Explicit reason for taking this action
        expected_outcome: What we expect to happen
        **kwargs: Parameters for the action

    Returns:
        Tuple of (success, output_message)

    The action is tracked in the feedback loop for learning.
    """
    if action_name not in ACTION_REGISTRY:
        return False, f"Unknown action: {action_name}"

    # Lazy import to avoid circular dependency
    from core import action_feedback

    # Default why/expected if not provided
    if not why:
        why = f"Executing {action_name} as requested"
    if not expected_outcome:
        expected_outcome = f"{action_name} completes successfully"

    # Record intent BEFORE action
    intent_id = action_feedback.record_action_intent(
        action_name=action_name,
        why=why,
        expected_outcome=expected_outcome,
        success_criteria=[f"{action_name}_completed"],
        context={"params": str(kwargs)[:200]},
    )

    # Execute action
    start_time = time.time()
    try:
        func = ACTION_REGISTRY[action_name]
        success, output = func(**kwargs)
        duration_ms = int((time.time() - start_time) * 1000)

        # Record outcome AFTER action
        feedback = action_feedback.record_action_outcome(
            intent_id=intent_id,
            success=success,
            actual_outcome=output,
            duration_ms=duration_ms,
            criteria_results={f"{action_name}_completed": success},
        )

        # Analyze for patterns
        if feedback:
            action_feedback.get_feedback_loop().analyze_feedback(feedback)

        return success, output

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)

        # Record failure
        action_feedback.record_action_outcome(
            intent_id=intent_id,
            success=False,
            actual_outcome="",
            error=str(e)[:300],
            duration_ms=duration_ms,
        )

        return False, f"Action failed: {str(e)}"


def execute_with_fallback(
    action_name: str,
    fallbacks: list = None,
    why: str = "",
    expected_outcome: str = "",
    **kwargs,
) -> Tuple[bool, str]:
    """Execute an action with fallback alternatives if it fails."""
    # Try primary action
    success, msg = execute_action(
        action_name,
        why=why or f"Executing {action_name} with fallbacks",
        expected_outcome=expected_outcome,
        **kwargs,
    )
    if success:
        return success, msg

    # Try explicit fallbacks
    if fallbacks:
        for fallback in fallbacks:
            fb_name = fallback.get("action", "")
            fb_kwargs = fallback.get("params", {})
            success, msg = execute_action(
                fb_name,
                why=f"Fallback for failed {action_name}",
                expected_outcome=expected_outcome,
                **fb_kwargs,
            )
            if success:
                return success, f"Used fallback {fb_name}: {msg}"

    # Try to find alternative automatically
    alternatives = get_alternative_actions(action_name)
    for alt in alternatives:
        success, msg = execute_action(
            alt,
            why=f"Auto-alternative for failed {action_name}",
            expected_outcome=expected_outcome,
            **kwargs,
        )
        if success:
            return success, f"Used alternative {alt}: {msg}"

    return False, f"All attempts failed for {action_name}"


def execute_with_discipline(
    action_name: str,
    why: str,
    expected_outcome: str,
    success_criteria: Optional[List[str]] = None,
    objective_id: Optional[str] = None,
    **kwargs,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Execute an action with full discipline and return detailed feedback.

    This is the preferred way to execute actions from the orchestrator
    or any code that needs explicit tracking of intent and outcome.

    Args:
        action_name: Name of the action to execute
        why: Explicit reason for taking this action
        expected_outcome: What we expect to happen
        success_criteria: List of criteria that define success
        objective_id: Optional objective this action serves
        **kwargs: Parameters for the action

    Returns:
        Tuple of (success, output, feedback_dict)
    """
    if action_name not in ACTION_REGISTRY:
        return False, f"Unknown action: {action_name}", {}

    from core import action_feedback

    # Record intent
    intent_id = action_feedback.record_action_intent(
        action_name=action_name,
        why=why,
        expected_outcome=expected_outcome,
        success_criteria=success_criteria or [f"{action_name}_completed"],
        objective_id=objective_id,
        context={"params": str(kwargs)[:200]},
    )

    # Check for known issues
    recommendations = action_feedback.get_action_recommendations(action_name)
    if recommendations:
        # Log but don't block - could integrate with orchestrator decisions
        pass

    # Execute
    start_time = time.time()
    try:
        func = ACTION_REGISTRY[action_name]
        success, output = func(**kwargs)
        duration_ms = int((time.time() - start_time) * 1000)

        # Evaluate criteria
        criteria_results = {c: success for c in (success_criteria or [])}

        # Record outcome
        feedback = action_feedback.record_action_outcome(
            intent_id=intent_id,
            success=success,
            actual_outcome=output,
            duration_ms=duration_ms,
            criteria_results=criteria_results,
        )

        # Analyze
        if feedback:
            action_feedback.get_feedback_loop().analyze_feedback(feedback)

        feedback_dict = {
            "intent_id": intent_id,
            "success": success,
            "duration_ms": duration_ms,
            "criteria_met": criteria_results,
            "recommendations": recommendations,
        }

        return success, output, feedback_dict

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)

        action_feedback.record_action_outcome(
            intent_id=intent_id,
            success=False,
            actual_outcome="",
            error=str(e)[:300],
            duration_ms=duration_ms,
        )

        return False, f"Action failed: {str(e)}", {
            "intent_id": intent_id,
            "success": False,
            "error": str(e)[:300],
            "duration_ms": duration_ms,
        }


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
