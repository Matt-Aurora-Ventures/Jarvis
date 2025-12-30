from typing import Any, Dict, List, Optional
import re
import urllib.parse

from core import (
    actions,
    config,
    context_loader,
    context_manager,
    guardian,
    jarvis,
    memory,
    passive,
    providers,
    prompt_library,
    research_engine,
    safety,
)


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


def _record_conversation_turn(user_text: str, assistant_text: str) -> None:
    """Persist conversation turns for cross-session continuity."""
    try:
        ctx = safety.SafetyContext(apply=True, dry_run=False)
        memory.append_entry(_truncate(user_text, 800), "voice_chat_user", ctx)
        memory.append_entry(_truncate(assistant_text, 800), "voice_chat_assistant", ctx)
        context_manager.add_conversation_message("user", user_text)
        context_manager.add_conversation_message("assistant", assistant_text)
    except Exception:
        # Never block responses on memory persistence.
        pass


def _support_prompts(user_text: str) -> tuple[str, list[str]]:
    """Select prompt library snippets relevant to the current input."""
    lowered = user_text.lower()
    tags = ["conversation"]
    if any(word in lowered for word in ("crypto", "trading", "defi", "solana", "base", "bnb")):
        tags.append("crypto")
    if any(word in lowered for word in ("research", "dig", "analyze", "learn")):
        tags.append("research")
    if any(word in lowered for word in ("social", "linkedin", "linktree", "profile", "audience")):
        tags.append("social")
    prompts = prompt_library.get_support_prompts(tags, limit=3)
    if not prompts:
        return "", []
    inspirations = []
    ids = []
    for prompt in prompts:
        inspirations.append(f"{prompt.title}: {prompt.body}")
        ids.append(prompt.id)
    return "\n".join(inspirations), ids


def _is_research_request(user_text: str) -> bool:
    lowered = user_text.lower()
    triggers = [
        "research",
        "deep dive",
        "investigate",
        "look up",
        "find sources",
        "summarize sources",
        "analyze sources",
    ]
    return any(trigger in lowered for trigger in triggers)


def _format_research_response(result: Dict[str, Any]) -> str:
    summary = result.get("summary", "").strip()
    key_findings = result.get("key_findings", [])
    sources = result.get("sources", [])
    lines = []
    if summary:
        lines.append(summary)
    if key_findings:
        lines.append("\nKey findings:")
        lines.extend(f"- {item}" for item in key_findings[:7])
    if sources:
        lines.append("\nSources:")
        for source in sources[:3]:
            title = source.get("title") or "Source"
            domain = _domain_from_url(source.get("url", ""))
            if domain:
                lines.append(f"- {title} ({domain})")
            else:
                lines.append(f"- {title}")
    return "\n".join(lines).strip()


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    candidate = url if url.startswith(("http://", "https://")) else f"http://{url}"
    parsed = urllib.parse.urlparse(candidate)
    return parsed.netloc


_URL_PATTERN = re.compile(r"\b(?:https?://|www\.)[^\s\])>]+", re.IGNORECASE)


def _normalize_response_prefix(text: str) -> str:
    if re.match(r"^\s*test\s*$", text, flags=re.IGNORECASE):
        return "my response"
    return re.sub(r"^\s*test(\s*[:\-])", r"my response\1", text, flags=re.IGNORECASE)


def _strip_urls(text: str) -> str:
    def _replace(match: re.Match) -> str:
        url = match.group(0)
        trimmed = url.rstrip(").,;:!?]")
        suffix = url[len(trimmed):]
        candidate = trimmed if trimmed.startswith(("http://", "https://")) else f"http://{trimmed}"
        parsed = urllib.parse.urlparse(candidate)
        domain = parsed.netloc
        return f"{domain}{suffix}" if domain else ""

    return _URL_PATTERN.sub(_replace, text)


def _sanitize_response(text: str) -> str:
    if not text:
        return text
    cleaned = _normalize_response_prefix(text)
    cleaned = _strip_urls(cleaned)
    return cleaned


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

    # IMPORTANT: Use factual entries for memory to prevent echo chamber.
    # This excludes assistant outputs so the LLM doesn't see its own
    # previous responses as "facts" which causes circular/shallow behavior.
    factual_entries = memory.get_factual_entries()
    memory_summary = memory.summarize_entries(factual_entries[-10:])

    # Conversation history still includes both sides for coherence,
    # but it's clearly labeled as "conversation" not "memory/facts".
    history_entries = session_history if session_history is not None else _recent_chat()
    history = _format_history(history_entries)

    activity_summary = ""
    if cfg.get("context", {}).get("include_activity_summary", True):
        try:
            activity_summary = passive.summarize_activity(hours=2)
        except Exception as e:
            activity_summary = ""
    context_summary = context_manager.get_context_summary()

    # Get mission context and safety rules
    safety_rules = guardian.get_safety_prompt()
    mission_context = jarvis.get_mission_context()
    
    # Available actions for computer control
    available_actions = actions.get_available_actions()

    if _is_research_request(user_text) and cfg.get("research", {}).get("allow_web", False):
        engine = research_engine.get_research_engine()
        result = engine.research_topic(user_text, max_pages=5)
        response = _sanitize_response(_format_research_response(result))
        if response:
            _record_conversation_turn(user_text, response)
            return response + "\n"

    prompt = (
        f"{safety_rules}\n\n"
        f"{mission_context}\n\n"
        "You are Jarvis, the user's personal AI assistant and partner. You are NOT robotic.\n"
        "Speak naturally and conversationally, like a brilliant friend who happens to be an AI.\n"
        "Be warm, witty, and genuinely helpful. Use contractions. Show personality.\n"
        "Always act in the user's best interest. Help them achieve their goals.\n\n"
        "=== PROGRESS CONTRACT (CRITICAL) ===\n"
        "Each response MUST do exactly ONE of these:\n"
        "1. TAKE ACTION: Execute a tool/action that advances the goal\n"
        "2. GIVE SPECIFIC ANSWER: Provide concrete, actionable information\n"
        "3. ASK ONE QUESTION: If you need info to proceed, ask exactly one clear question\n"
        "4. DECLARE DONE/BLOCKED: State what was accomplished or what's blocking progress\n\n"
        "NEVER:\n"
        "- Give vague or generic responses\n"
        "- Repeat what you said before\n"
        "- Offer multiple options without a recommendation\n"
        "- Say 'I can help with that' without actually helping\n"
        "=== END CONTRACT ===\n\n"
        "CAPABILITIES: You can control this Mac. Actions:\n"
        f"{', '.join(available_actions)}\n"
        "Format: [ACTION: action_name(param=value)]\n"
        "Only take UI actions if user explicitly asks.\n\n"
        "--- CONVERSATION HISTORY ---\n"
        f"{history}\n"
        "--- END HISTORY ---\n\n"
        "Context (user goals, projects):\n"
        f"{context_text}\n\n"
        "Factual memory (things the user told me, NOT my previous responses):\n"
        f"{memory_summary}\n\n"
        "What's on screen:\n"
        f"{screen_context}\n\n"
    )

    if context_summary and "No context available" not in context_summary:
        prompt += f"Cross-session context:\n{context_summary}\n\n"

    if activity_summary and "No recent activity" not in activity_summary:
        prompt += f"Recent Activity:\n{activity_summary}\n\n"

    inspirations_text, inspiration_ids = _support_prompts(user_text)
    if inspirations_text:
        prompt += f"Prompt inspirations:\n{inspirations_text}\n\n"

    prompt += f"User says: {user_text}\n"

    text = providers.generate_text(prompt, max_output_tokens=500)
    if text:
        # Parse and execute any actions in the response
        result = _execute_actions_in_response(text)
        result = _sanitize_response(result)
        prompt_library.record_usage(inspiration_ids, success=True)
        _record_conversation_turn(user_text, result.strip())
        return result.strip() + "\n"
    prompt_library.record_usage(inspiration_ids, success=False)
    fallback = _sanitize_response(_fallback_response(user_text))
    _record_conversation_turn(user_text, fallback)
    return fallback


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
