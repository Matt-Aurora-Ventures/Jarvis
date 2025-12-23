from typing import Dict, List, Optional

from core import config, context_loader, memory, providers


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

    prompt = (
        "You are LifeOS in chat mode. Respond concisely and helpfully.\n"
        "Output with these exact sections:\n"
        "Plain English:\n"
        "- What I heard\n"
        "- What I did\n"
        "- What happens next\n"
        "- What I need from you\n"
        "Technical Notes:\n"
        "- Modules/files involved\n"
        "- Key concepts/terms\n"
        "- Commands executed (or would execute in dry-run)\n"
        "- Risks/constraints\n"
        "Glossary:\n"
        "- 1 term with a simple definition\n"
        "\n"
        "Conversation history:\n"
        f"{history}\n"
        "\n"
        "Context:\n"
        f"{context_text}\n"
        "\n"
        "Recent Memory Summary:\n"
        f"{memory_summary}\n"
        "\n"
        "Screen Context:\n"
        f"{screen_context}\n"
        "\n"
        f"User says: {user_text}\n"
    )

    text = providers.generate_text(prompt, max_output_tokens=500)
    if text:
        return text.strip() + "\n"
    return _fallback_response(user_text)
