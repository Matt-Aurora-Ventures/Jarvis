from typing import Any, Dict, List, Optional, Tuple
import json
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


# ============================================================================
# Enhanced Input Synthesis
# ============================================================================

def _extract_entities(user_text: str) -> Dict[str, List[str]]:
    """
    Extract key entities from user input for better context linking.
    
    Returns dict with entity types: people, tools, projects, actions, topics
    """
    entities: Dict[str, List[str]] = {
        "people": [],
        "tools": [],
        "projects": [],
        "actions": [],
        "topics": [],
    }
    
    lowered = user_text.lower()
    
    # Tool mentions
    tools = ["python", "git", "docker", "npm", "ollama", "cursor", "windsurf", 
             "vscode", "terminal", "browser", "firefox", "chrome", "notion", "obsidian"]
    entities["tools"] = [t for t in tools if t in lowered]
    
    # Action verbs (what user wants done)
    action_patterns = [
        (r"\b(create|make|build|generate)\b", "create"),
        (r"\b(fix|repair|debug|solve)\b", "fix"),
        (r"\b(improve|enhance|optimize|upgrade)\b", "improve"),
        (r"\b(analyze|research|investigate|study)\b", "analyze"),
        (r"\b(delete|remove|clear|clean)\b", "delete"),
        (r"\b(open|launch|start|run)\b", "open"),
        (r"\b(send|share|post|publish)\b", "send"),
        (r"\b(find|search|look for|locate)\b", "find"),
    ]
    for pattern, action in action_patterns:
        if re.search(pattern, lowered):
            entities["actions"].append(action)
    
    # Topic detection
    topic_keywords = {
        "crypto": ["trading", "crypto", "bitcoin", "ethereum", "solana", "defi", "wallet"],
        "development": ["code", "programming", "development", "api", "function", "module"],
        "business": ["revenue", "sales", "marketing", "client", "customer", "project"],
        "personal": ["health", "fitness", "habits", "goals", "schedule", "calendar"],
    }
    for topic, keywords in topic_keywords.items():
        if any(kw in lowered for kw in keywords):
            entities["topics"].append(topic)
    
    return entities


def _classify_intent(user_text: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Classify the user's intent to guide response generation.
    
    Returns dict with:
    - primary_intent: main classification
    - confidence: 0.0-1.0
    - requires_action: bool
    - requires_memory: bool
    - is_followup: bool
    """
    lowered = user_text.lower().strip()
    
    # Check if this is a follow-up to previous conversation
    is_followup = False
    if history:
        last_assistant = None
        for entry in reversed(history):
            if entry.get("source") in ("voice_chat_assistant", "assistant"):
                last_assistant = entry.get("text", "")
                break
        
        # Follow-up indicators
        followup_starters = ["yes", "no", "sure", "okay", "ok", "yeah", "nope", 
                            "that", "this", "it", "do it", "go ahead", "please"]
        if any(lowered.startswith(f) for f in followup_starters):
            is_followup = True
        
        # Pronoun references to previous topic
        if re.match(r"^(what about|how about|and|also|but)", lowered):
            is_followup = True
    
    # Intent classification
    intents = {
        "command": 0.0,      # Direct action request
        "question": 0.0,     # Information seeking
        "clarification": 0.0, # Clarifying previous topic
        "feedback": 0.0,     # Providing feedback/opinion
        "greeting": 0.0,     # Social greeting
        "status": 0.0,       # Status check
    }
    
    # Command detection
    command_patterns = [
        r"^(open|launch|start|run|create|make|build|send|post)\b",
        r"\b(please|can you|could you|would you)\s+\w+",
        r"^(set|add|remove|delete|clear|fix|update)\b",
    ]
    for pattern in command_patterns:
        if re.search(pattern, lowered):
            intents["command"] = max(intents["command"], 0.8)
    
    # Question detection
    if "?" in user_text or lowered.startswith(("what", "how", "why", "when", "where", "who", "which", "is", "are", "can", "could", "should", "would", "do", "does")):
        intents["question"] = 0.8
    
    # Greeting detection  
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "howdy", "yo"]
    if any(g in lowered.split() for g in greetings) or lowered in greetings:
        intents["greeting"] = 0.9
    
    # Status check
    if any(w in lowered for w in ["status", "what's happening", "update me", "how's it going", "what's new"]):
        intents["status"] = 0.85
    
    # Find primary intent
    primary_intent = max(intents, key=intents.get)
    confidence = intents[primary_intent]
    
    return {
        "primary_intent": primary_intent,
        "confidence": confidence,
        "requires_action": primary_intent == "command",
        "requires_memory": primary_intent in ("question", "clarification"),
        "is_followup": is_followup,
        "all_intents": intents,
    }


def _synthesize_input(user_text: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Comprehensive input synthesis combining entity extraction and intent classification.
    
    This is the main entry point for understanding user input.
    """
    entities = _extract_entities(user_text)
    intent = _classify_intent(user_text, history)
    
    # Build synthesis result
    synthesis = {
        "original_text": user_text,
        "entities": entities,
        "intent": intent,
        "word_count": len(user_text.split()),
        "has_url": bool(_extract_url(user_text)),
        "is_short_response": len(user_text.split()) <= 3,
    }
    
    # Compute context relevance hints
    relevance_hints = []
    if entities["tools"]:
        relevance_hints.append(f"tools: {', '.join(entities['tools'])}")
    if entities["topics"]:
        relevance_hints.append(f"topics: {', '.join(entities['topics'])}")
    if intent["is_followup"]:
        relevance_hints.append("continuation of previous topic")
    
    synthesis["relevance_hints"] = relevance_hints
    
    return synthesis


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
_DOMAIN_PATTERN = re.compile(r"\b[a-z0-9.-]+\.[a-z]{2,}\b", re.IGNORECASE)


def _extract_url(text: str) -> str:
    match = _URL_PATTERN.search(text)
    if match:
        return match.group(0)
    match = _DOMAIN_PATTERN.search(text)
    return match.group(0) if match else ""


def _is_question_response(text: str) -> bool:
    cleaned = text.strip()
    return "?" in cleaned or cleaned.endswith("?")


def _last_assistant_question(entries: List[Dict[str, str]]) -> bool:
    for entry in reversed(entries):
        source = entry.get("source")
        if source in ("voice_chat_assistant", "assistant"):
            return _is_question_response(entry.get("text", ""))
    return False


def _infer_direct_action(user_text: str) -> Optional[Tuple[str, Dict[str, str]]]:
    lowered = user_text.lower().strip()
    if not lowered:
        return None

    url = _extract_url(user_text)

    if lowered.startswith(("open browser", "launch browser", "open firefox", "launch firefox")):
        params = {"url": _normalize_url(url)} if url else {}
        return "open_browser", params
    if lowered.startswith(("open terminal", "launch terminal")):
        return "open_terminal", {}
    if lowered.startswith(("open mail", "open email", "launch mail", "launch email")):
        return "open_mail", {}
    if lowered.startswith(("open calendar", "launch calendar")):
        return "open_calendar", {}
    if lowered.startswith(("open messages", "launch messages")):
        return "open_messages", {}
    if lowered.startswith(("open notes", "launch notes", "open note", "launch note")):
        topic = user_text.split("notes", 1)[-1].strip()
        topic = topic or user_text.split("note", 1)[-1].strip()
        params = {"topic": topic} if topic else {}
        return "open_notes", params
    if lowered.startswith(("open finder", "launch finder")):
        path = user_text.split("finder", 1)[-1].strip()
        return "open_finder", {"path": path} if path else {"path": "~"}
    if lowered.startswith(("google ", "search ")):
        query = re.sub(r"^(google|search)\s+", "", user_text, flags=re.IGNORECASE).strip()
        if query:
            return "google", {"query": query}
    if lowered.startswith("search for "):
        query = re.sub(r"^search for\s+", "", user_text, flags=re.IGNORECASE).strip()
        if query:
            return "google", {"query": query}
    if lowered.startswith(("go to ", "open ")):
        if url:
            return "open_browser", {"url": _normalize_url(url)}
    if lowered.startswith("set reminder "):
        title = re.sub(r"^set reminder\s+", "", user_text, flags=re.IGNORECASE).strip()
        if title:
            return "set_reminder", {"title": title}
    if lowered.startswith(("create note ", "make note ")):
        body = re.sub(r"^(create|make)\s+note\s+", "", user_text, flags=re.IGNORECASE).strip()
        if body:
            title = body.split(".")[0].strip()[:60] or "Note"
            return "create_note", {"title": title, "body": body}

    return None


def _normalize_url(candidate: str) -> str:
    if not candidate:
        return candidate
    if candidate.startswith(("http://", "https://")):
        return candidate
    return f"https://{candidate}"


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
    cleaned = _strip_action_tokens(cleaned)
    cleaned = _strip_urls(cleaned)
    return cleaned


def _strip_action_tokens(text: str) -> str:
    cleaned = re.sub(r"\[ACTION:[^\]]+\]", "", text)
    cleaned = re.sub(r"\n+--- Actions Executed ---\n.*", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def _voice_friendly_text(text: str) -> str:
    if not text:
        return text
    cleaned = text
    plain_parts = re.split(r"plain english:", cleaned, flags=re.IGNORECASE, maxsplit=1)
    if len(plain_parts) > 1:
        cleaned = plain_parts[1]
    cleaned = re.split(r"technical notes:", cleaned, flags=re.IGNORECASE, maxsplit=1)[0]
    cleaned = re.split(r"glossary:", cleaned, flags=re.IGNORECASE, maxsplit=1)[0]
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    flattened = []
    for line in lines:
        if re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line):
            line = re.sub(r"^([-*]|\d+\.)\s+", "", line)
        flattened.append(line)
    cleaned = " ".join(flattened)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def sanitize_for_voice(text: str) -> str:
    return _voice_friendly_text(_sanitize_response(text))


def _extract_json_payload(text: str) -> Optional[str]:
    if not text:
        return None
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for idx in range(start, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def _parse_json_payload(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    payload = _extract_json_payload(text)
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def _format_action_history(limit: int = 3) -> str:
    ctx = context_manager.load_conversation_context()
    if not ctx.action_history:
        return "None"
    history = ctx.action_history[-limit:]
    lines = []
    for item in history:
        action = item.get("action", "unknown")
        status = "ok" if item.get("success") else "fail"
        result = item.get("result", "")
        lines.append(f"- {action} ({status}): {result}")
    return "\n".join(lines)


def _format_action_response(action_name: str, success: bool, output: str, channel: str) -> str:
    summary = output.strip() if output else ""
    if not summary:
        summary = action_name.replace("_", " ")
    response = f"{'Done' if success else 'Unable'}: {summary}"
    if channel == "voice":
        return _voice_friendly_text(response)
    return response


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
    user_text: str,
    screen_context: str,
    session_history: Optional[List[Dict[str, str]]] = None,
    channel: str = "chat",
) -> str:
    cfg = config.load_config()
    context_text = context_loader.load_context(update_state=False)

    # ===== ENHANCED INPUT SYNTHESIS =====
    history_entries = session_history if session_history is not None else _recent_chat()
    input_synthesis = _synthesize_input(user_text, history_entries)
    
    # Use synthesis for smarter direct action detection
    direct_action = _infer_direct_action(user_text)
    if direct_action:
        action_name, params = direct_action
        success, output = actions.execute_action(action_name, **params)
        context_manager.add_action_result(action_name, success, output)
        response = _format_action_response(action_name, success, output, channel)
        _record_conversation_turn(user_text, response)
        response = _sanitize_response(response)
        if channel == "voice":
            response = _voice_friendly_text(response)
        return response.strip() + "\n"

    # IMPORTANT: Use factual entries for memory to prevent echo chamber.
    # This excludes assistant outputs so the LLM doesn't see its own
    # previous responses as "facts" which causes circular/shallow behavior.
    factual_entries = memory.get_factual_entries()
    memory_summary = memory.summarize_entries(factual_entries[-10:])

    # Conversation history still includes both sides for coherence,
    # but it's clearly labeled as "conversation" not "memory/facts".
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
            if channel == "voice":
                response = _voice_friendly_text(response)
            return response + "\n"

    channel_rules = (
        "VOICE MODE: Respond in 1-3 short sentences. No lists, no code, no markdown."
        if channel == "voice"
        else "CHAT MODE: Respond naturally. No tool syntax or JSON."
    )

    action_history = _format_action_history(limit=3)

    prompt = (
        f"{safety_rules}\n\n"
        f"{mission_context}\n\n"
        "You are Jarvis, the user's personal AI assistant and partner. You are NOT robotic.\n"
        "Speak naturally and conversationally, like a brilliant friend who happens to be an AI.\n"
        "Be warm, witty, and genuinely helpful. Use contractions. Show personality.\n"
        "Always act in the user's best interest. Help them achieve their goals.\n\n"
        "Return ONLY valid JSON.\n"
        "Schema:\n"
        "{\n"
        '  "decision": "action|respond|question",\n'
        '  "action": {\n'
        '    "name": "action_name",\n'
        '    "params": {"param": "value"},\n'
        '    "why": "short reason",\n'
        '    "expected_outcome": "what should happen"\n'
        "  },\n"
        '  "response": "natural language response"\n'
        "}\n"
        "Rules:\n"
        "- If an explicit user request matches an available action, choose decision=action.\n"
        "- Otherwise choose respond or question. Ask at most ONE question.\n"
        "- Do NOT include markdown, code fences, or tool syntax.\n"
        f"- {channel_rules}\n\n"
        "Available actions:\n"
        f"{', '.join(available_actions)}\n"
        "Recent action history:\n"
        f"{action_history}\n\n"
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

    prompt += f"Input synthesis:\n{json.dumps(input_synthesis, indent=2)[:1200]}\n\n"
    prompt += f"User says: {user_text}\n"

    response_text = ""
    decision_tokens = 180 if channel == "voice" else 400
    response_tokens = 220 if channel == "voice" else 500
    decision_text = providers.generate_text(prompt, max_output_tokens=decision_tokens)
    decision = _parse_json_payload(decision_text)

    if decision:
        decision_type = str(decision.get("decision", "")).lower()
        if decision_type == "action":
            action_payload = decision.get("action") or {}
            action_name = action_payload.get("name") or decision.get("action_name")
            params = action_payload.get("params") or {}
            why = action_payload.get("why", "")
            expected_outcome = action_payload.get("expected_outcome", "")
            if action_name in available_actions:
                if not isinstance(params, dict):
                    params = {}
                success, output = actions.execute_action(
                    action_name,
                    why=why,
                    expected_outcome=expected_outcome,
                    **params,
                )
                context_manager.add_action_result(action_name, success, output)
                response_text = _format_action_response(action_name, success, output, channel)
            else:
                response_text = decision.get("response", "")
        elif decision_type in {"respond", "question"}:
            response_text = decision.get("response", "")

        if decision_type == "question" and _last_assistant_question(history_entries):
            response_text = ""

    if not response_text:
        response_prompt = (
            f"{safety_rules}\n\n"
            f"{mission_context}\n\n"
            "You are Jarvis, the user's personal AI assistant and partner. You are NOT robotic.\n"
            "Speak naturally and conversationally. Avoid tool syntax or JSON.\n"
            f"{channel_rules}\n\n"
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
            response_prompt += f"Cross-session context:\n{context_summary}\n\n"
        if activity_summary and "No recent activity" not in activity_summary:
            response_prompt += f"Recent Activity:\n{activity_summary}\n\n"
        if inspirations_text:
            response_prompt += f"Prompt inspirations:\n{inspirations_text}\n\n"
        response_prompt += f"User says: {user_text}\n"
        response_text = providers.generate_text(response_prompt, max_output_tokens=response_tokens) or ""

    if response_text:
        result = _sanitize_response(response_text)
        if channel == "voice":
            result = _voice_friendly_text(result)
        prompt_library.record_usage(inspiration_ids, success=True)
        _record_conversation_turn(user_text, result.strip())
        return result.strip() + "\n"

    prompt_library.record_usage(inspiration_ids, success=False)
    fallback = _sanitize_response(_fallback_response(user_text))
    if channel == "voice":
        fallback = _voice_friendly_text(fallback)
    _record_conversation_turn(user_text, fallback)
    return fallback


def _execute_actions_in_response(response: str) -> str:
    """Parse and execute [ACTION: ...] commands in the response."""
    import re

    default_param_keys = {
        "google": "query",
        "search": "query",
        "open_browser": "url",
        "open_finder": "path",
        "open_notes": "topic",
        "spotlight": "query",
        "speak": "text",
        "switch_app": "app_name",
        "set_reminder": "title",
    }

    action_pattern = r'\[ACTION:\s*(\w+)\(([^)]*)\)\]'
    matches = re.findall(action_pattern, response)
    
    if not matches:
        return response
    
    action_results = []
    for action_name, params_str in matches:
        try:
            # Parse parameters
            kwargs = {}
            params_raw = params_str.strip()
            if params_raw:
                # Simple param parsing: key='value' or key="value"
                param_pattern = r"(\w+)\s*=\s*['\"]([^'\"]*)['\"]"
                param_matches = re.findall(param_pattern, params_raw)
                for key, value in param_matches:
                    kwargs[key] = value
                if not kwargs:
                    default_key = default_param_keys.get(action_name)
                    if default_key:
                        cleaned = params_raw
                        if (
                            len(cleaned) >= 2
                            and cleaned[0] in ("'", '"')
                            and cleaned[-1] == cleaned[0]
                        ):
                            cleaned = cleaned[1:-1]
                        if cleaned:
                            kwargs[default_key] = cleaned
            
            # Execute the action
            success, msg = actions.execute_action(action_name, **kwargs)
            action_results.append(f"[{action_name}: {'✓' if success else '✗'} {msg[:50]}]")
        except Exception as e:
            action_results.append(f"[{action_name}: ✗ {str(e)[:50]}]")
    
    # Append action results to response
    if action_results:
        response += "\n\n--- Actions Executed ---\n" + "\n".join(action_results)
    
    return response
