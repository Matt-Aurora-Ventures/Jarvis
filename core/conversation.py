from typing import Dict, List, Optional

from core import actions, config, context_loader, guardian, jarvis, memory, passive, providers


def _truncate(text: str, limit: int = 800) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _recent_chat(turns: int = 6) -> List[Dict[str, str]]:
    entries = memory.get_recent_entries()
    chat = [
        entry
        for entry in entries
        if entry.get("source") in ("voice_chat_user", "voice_chat_assistant")
    ]
    return chat[-turns:]


def _format_history(entries: List[Dict[str, str]]) -> str:
    lines = []
    for entry in entries:
        role = "User" if entry.get("source") == "voice_chat_user" else "Assistant"
        text = _truncate(entry.get("text", ""), 400)
        if text:
            lines.append(f"{role}: {text}")
    return "\n".join(lines).strip()


def _fallback_response(user_text: str) -> str:
    status = providers.provider_status()
    errors = providers.last_provider_errors()
    plain = (
        "Plain English:\n"
        f"- What I heard: {user_text}\n"
        "- What I did: I prepared a helpful reply, but the AI model is unavailable.\n"
        "- What happens next: Try again later or ask a command like 'status'.\n"
        "- What I need from you: Nothing right now.\n"
    )
    technical = (
        "Technical Notes:\n"
        "- Modules/files involved: core/conversation.py, core/providers.py\n"
        "- Key concepts/terms: Offline fallback\n"
        f"- Provider status: {status}\n"
        f"- Provider errors: {errors}\n"
        "- Commands executed (or would execute in dry-run): None\n"
        "- Risks/constraints: No model output available.\n"
    )
    glossary = "Glossary:\n- Offline fallback: A basic response when no model is available."
    return f"{plain}\n{technical}\n\n{glossary}"


def generate_response(
    user_text: str, screen_context: str, session_history: Optional[List[Dict[str, str]]] = None
) -> str:
    cfg = config.load_config()
    context_text = context_loader.load_context(update_state=False)
    recent_entries = memory.get_recent_entries()
    memory_summary = memory.summarize_entries(recent_entries[-10:])
    history_entries = session_history if session_history is not None else _recent_chat()
    history = _format_history(history_entries)

    activity_summary = ""
    if cfg.get("context", {}).get("include_activity_summary", True):
        try:
            activity_summary = passive.summarize_activity(hours=2)
        except Exception as e:
            activity_summary = ""

    # Get mission context and safety rules
    safety_rules = guardian.get_safety_prompt()
    mission_context = jarvis.get_mission_context()
    
    # Available actions for computer control
    available_actions = actions.get_available_actions()

    prompt = (
        f"{safety_rules}\n\n"
        f"{mission_context}\n\n"
        "You are Jarvis, the user's personal AI assistant and partner. You are NOT robotic.\n"
        "Speak naturally and conversationally, like a brilliant friend who happens to be an AI.\n"
        "Be warm, witty, and genuinely helpful. Use contractions. Show personality.\n"
        "You can joke around, be casual, and have real conversations - not just answer questions.\n"
        "Always act in the user's best interest. Help them make money and achieve their goals.\n"
        "Be proactive - suggest ideas, point out opportunities, and anticipate needs.\n\n"
        "CAPABILITIES: You can control this Mac computer. Available actions:\n"
        f"{', '.join(available_actions)}\n"
        "To execute: [ACTION: action_name(param=value)]\n"
        "Examples: [ACTION: google(query='topic')] or [ACTION: compose_email(to='x@y.com', subject='Hi', body='...')]\n\n"
        "Conversation so far:\n"
        f"{history}\n"
        "\n"
        "Current context:\n"
        f"{context_text}\n"
        "\n"
        "What you remember:\n"
        f"{memory_summary}\n"
        "\n"
        "What's on screen:\n"
        f"{screen_context}\n"
        "\n"
    )

    if activity_summary and "No recent activity" not in activity_summary:
        prompt += f"Recent Activity:\n{activity_summary}\n\n"

    prompt += f"User says: {user_text}\n"

    text = providers.generate_text(prompt, max_output_tokens=500)
    if text:
        # Parse and execute any actions in the response
        result = _execute_actions_in_response(text)
        return result.strip() + "\n"
    return _fallback_response(user_text)


def _execute_actions_in_response(response: str) -> str:
    """Parse and execute [ACTION: ...] commands in the response."""
    import re
    
    action_pattern = r'\[ACTION:\s*(\w+)\(([^)]*)\)\]'
    matches = re.findall(action_pattern, response)
    
    if not matches:
        return response
    
    action_results = []
    for action_name, params_str in matches:
        try:
            # Parse parameters
            kwargs = {}
            if params_str.strip():
                # Simple param parsing: key='value' or key="value"
                param_pattern = r"(\w+)\s*=\s*['\"]([^'\"]*)['\"]"
                param_matches = re.findall(param_pattern, params_str)
                for key, value in param_matches:
                    kwargs[key] = value
            
            # Execute the action
            success, msg = actions.execute_action(action_name, **kwargs)
            action_results.append(f"[{action_name}: {'✓' if success else '✗'} {msg[:50]}]")
        except Exception as e:
            action_results.append(f"[{action_name}: ✗ {str(e)[:50]}]")
    
    # Append action results to response
    if action_results:
        response += "\n\n--- Actions Executed ---\n" + "\n".join(action_results)
    
    return response
