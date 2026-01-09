"""
Integration layer for Self-Improving Core.

Provides a singleton orchestrator and utilities for integrating with:
- core/conversation.py - Response generation
- core/daemon.py - Startup and scheduling
- tg_bot/bot.py - Telegram commands

Enhanced features (v2):
- Chain-of-Thought reasoning
- BM25 retrieval for better context
- Conversation summarization
- Conversation flow state tracking

Usage:
    from core.self_improving.integration import (
        get_self_improving,
        enrich_context,
        record_conversation,
        start_scheduler,
        # New in v2:
        enhance_with_reasoning,
        get_conversation_flow,
        summarize_session,
    )
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("jarvis.self_improving.integration")

# Singleton instances
_orchestrator = None
_scheduler = None
_bm25_retriever = None
_summarizer = None
_conversation_flows: Dict[str, Any] = {}


def get_self_improving():
    """Get or create the singleton self-improving orchestrator."""
    global _orchestrator

    if _orchestrator is None:
        from core.self_improving.orchestrator import SelfImprovingOrchestrator
        from core import config as config_module

        cfg = config_module.load_config()
        data_dir = config_module.resolve_path(
            cfg.get("paths", {}).get("data_dir", "data")
        )
        db_path = str(data_dir / "jarvis_memory.db")

        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)

        _orchestrator = SelfImprovingOrchestrator(db_path=db_path)
        logger.info(f"Self-improving orchestrator initialized: {db_path}")

    return _orchestrator


def set_llm_client(client: Any) -> None:
    """Set the LLM client for the self-improving system."""
    orch = get_self_improving()
    orch.set_llm_client(client)
    logger.info("LLM client set for self-improving system")


def start_scheduler(
    use_async: bool = False,
    on_suggestion: Optional[callable] = None,
) -> Any:
    """
    Start the self-improving scheduler for nightly tasks.

    Args:
        use_async: Use async scheduler (for async applications)
        on_suggestion: Callback function called when a proactive suggestion is generated.
                      Signature: callback(suggestion) where suggestion has .message, .confidence, etc.
    """
    global _scheduler

    if _scheduler is not None:
        return _scheduler

    from core.self_improving.scheduler import SelfImprovingScheduler

    orch = get_self_improving()
    _scheduler = SelfImprovingScheduler(
        orch,
        use_async=use_async,
        on_suggestion=on_suggestion,
    )
    _scheduler.start()
    logger.info("Self-improving scheduler started")

    return _scheduler


def stop_scheduler() -> None:
    """Stop the self-improving scheduler."""
    global _scheduler

    if _scheduler is not None:
        _scheduler.stop()
        _scheduler = None
        logger.info("Self-improving scheduler stopped")


def enrich_context(user_query: str) -> Dict[str, Any]:
    """
    Enrich response context with self-improving data.

    Call this before generating a response to inject:
    - Relevant facts from memory
    - Lessons learned from past reflections
    - Trust level information

    Returns dict with keys:
        - relevant_facts: List of relevant facts
        - lessons_to_apply: List of lessons from reflections
        - trust_levels: Current trust levels by domain
    """
    orch = get_self_improving()

    try:
        context = orch.build_response_context(
            user_query,
            include_reflections=True,
            include_facts=True,
        )

        # Add trust summary
        context["trust_levels"] = orch.get_trust_summary()

        return context
    except Exception as e:
        logger.error(f"Failed to enrich context: {e}")
        return {"query": user_query, "error": str(e)}


def format_context_for_prompt(context: Dict[str, Any]) -> str:
    """Format enriched context as a prompt section."""
    orch = get_self_improving()
    return orch.format_context_for_prompt(context)


def record_conversation(
    user_input: str,
    assistant_response: str,
    session_id: Optional[str] = None,
    feedback: Optional[str] = None,
    extract_learnings: bool = False,
) -> Dict[str, Any]:
    """
    Record a conversation interaction.

    Args:
        user_input: What the user said
        assistant_response: What Jarvis responded
        session_id: Optional session identifier
        feedback: Optional feedback (positive/negative/neutral)
        extract_learnings: If True, also extract learnings from the exchange

    Returns:
        Dict with interaction_id and optional learnings
    """
    orch = get_self_improving()

    result = {"recorded": False}

    try:
        interaction_id = orch.record_interaction(
            user_input=user_input,
            jarvis_response=assistant_response,
            session_id=session_id,
            feedback=feedback,
        )
        result["recorded"] = True
        result["interaction_id"] = interaction_id

        # Optionally extract learnings
        if extract_learnings:
            messages = [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": assistant_response},
            ]
            learnings = orch.learn_from_conversation_sync(messages, session_id)
            result["learnings"] = learnings

    except Exception as e:
        logger.error(f"Failed to record conversation: {e}")
        result["error"] = str(e)

    return result


def record_feedback(interaction_id: int, feedback: str) -> bool:
    """Record feedback on a specific interaction."""
    orch = get_self_improving()
    return orch.record_feedback(interaction_id, feedback)


def execute_action(
    action_name: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a trust-gated action.

    Returns dict with success, message, and result.
    """
    orch = get_self_improving()
    result = orch.execute_action(action_name, params)

    return {
        "success": result.success,
        "message": result.message,
        "result": result.result,
        "action_taken": result.action_taken,
    }


def get_available_actions(domain: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get actions available at current trust level."""
    orch = get_self_improving()
    return orch.get_available_actions(domain)


def record_success(domain: str = "general") -> None:
    """Record a successful interaction to build trust."""
    orch = get_self_improving()
    orch.trust.record_success(domain)


def record_failure(domain: str = "general", major: bool = False) -> None:
    """Record a failed interaction (affects trust)."""
    orch = get_self_improving()
    orch.trust.record_failure(domain, major=major)


def get_trust_level(domain: str = "general") -> int:
    """Get current trust level for a domain."""
    orch = get_self_improving()
    return orch.get_trust_level(domain)


def get_stats() -> Dict[str, Any]:
    """Get comprehensive self-improving stats."""
    orch = get_self_improving()
    return orch.get_stats()


def health_check() -> Dict[str, Any]:
    """Run health check on self-improving system."""
    orch = get_self_improving()
    return orch.health_check()


def run_nightly_cycle() -> Dict[str, Any]:
    """Manually trigger the nightly reflection cycle."""
    orch = get_self_improving()
    return orch.run_nightly_cycle_sync()


def close() -> None:
    """Clean up resources."""
    global _orchestrator, _scheduler, _bm25_retriever, _summarizer, _conversation_flows

    if _scheduler is not None:
        stop_scheduler()

    if _orchestrator is not None:
        _orchestrator.close()
        _orchestrator = None
        logger.info("Self-improving orchestrator closed")

    _bm25_retriever = None
    _summarizer = None
    _conversation_flows.clear()


# =============================================================================
# ENHANCED FEATURES (v2)
# =============================================================================


def get_bm25_retriever():
    """Get or create the BM25 retriever."""
    global _bm25_retriever

    if _bm25_retriever is None:
        try:
            from core.self_improving.memory.retrieval import HybridRetriever
            orch = get_self_improving()
            _bm25_retriever = HybridRetriever(orch.memory)
            _bm25_retriever.build_index()
            logger.info("BM25 retriever initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize BM25 retriever: {e}")
            return None

    return _bm25_retriever


def get_summarizer():
    """Get or create the conversation summarizer."""
    global _summarizer

    if _summarizer is None:
        try:
            from core.self_improving.memory.summarizer import ConversationSummarizer
            _summarizer = ConversationSummarizer()
            logger.info("Conversation summarizer initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize summarizer: {e}")
            return None

    return _summarizer


def enrich_context_v2(user_query: str, session_id: str = "") -> Dict[str, Any]:
    """
    Enhanced context enrichment with BM25 retrieval.

    Includes:
    - BM25-ranked facts (better relevance than FTS5)
    - BM25-ranked reflections
    - Trust levels
    - Conversation flow state
    """
    context = enrich_context(user_query)

    # Add BM25 results
    retriever = get_bm25_retriever()
    if retriever:
        try:
            bm25_results = retriever.search_all(user_query, k=5)

            # Merge with existing facts (BM25 results first)
            bm25_facts = [r.content for r in bm25_results.get("facts", [])]
            if bm25_facts:
                existing_facts = context.get("relevant_facts", [])
                context["relevant_facts"] = bm25_facts + [f for f in existing_facts if f not in bm25_facts][:5]

            # Add BM25 reflections
            bm25_reflections = [r.metadata.get("lesson", r.content) for r in bm25_results.get("reflections", [])]
            if bm25_reflections:
                existing_lessons = context.get("lessons_to_apply", [])
                context["lessons_to_apply"] = bm25_reflections + [l for l in existing_lessons if l not in bm25_reflections][:3]

        except Exception as e:
            logger.warning(f"BM25 enrichment failed: {e}")

    # Add conversation flow state
    if session_id:
        flow = get_conversation_flow(session_id)
        if flow:
            context["conversation_state"] = flow.get_state_info()

    return context


def enhance_with_reasoning(
    prompt: str,
    user_query: str,
    context: Dict[str, Any] = None,
) -> str:
    """
    Enhance a prompt with Chain-of-Thought reasoning instructions.

    Use this to add reasoning to generate_response() prompts.
    """
    try:
        from core.self_improving.reasoning.chain_of_thought import enhance_prompt_with_reasoning
        return enhance_prompt_with_reasoning(prompt, user_query, context)
    except Exception as e:
        logger.warning(f"Failed to enhance with reasoning: {e}")
        return prompt


def create_reasoning_prompt(
    query: str,
    context: Dict[str, Any] = None,
) -> str:
    """
    Create a Chain-of-Thought reasoning prompt for a query.

    Returns a prompt that encourages step-by-step reasoning.
    """
    try:
        from core.self_improving.reasoning.chain_of_thought import create_cot_prompt
        orch = get_self_improving()
        return create_cot_prompt(query, context, orch.memory)
    except Exception as e:
        logger.warning(f"Failed to create reasoning prompt: {e}")
        return f"Query: {query}"


def parse_reasoning_response(response: str, query: str = "") -> Dict[str, Any]:
    """
    Parse a response that used CoT prompting.

    Returns dict with steps, conclusion, confidence.
    """
    try:
        from core.self_improving.reasoning.chain_of_thought import parse_cot_response
        trace = parse_cot_response(response, query)
        return trace.to_dict()
    except Exception as e:
        logger.warning(f"Failed to parse reasoning: {e}")
        return {"conclusion": response, "error": str(e)}


def get_conversation_flow(session_id: str):
    """
    Get or create a conversation flow for a session.

    The flow tracks conversation state, goals, and context slots.
    """
    global _conversation_flows

    if session_id not in _conversation_flows:
        try:
            from core.self_improving.conversation.state_machine import ConversationFlow
            _conversation_flows[session_id] = ConversationFlow(session_id)
            logger.debug(f"Created conversation flow for session: {session_id}")
        except Exception as e:
            logger.warning(f"Failed to create conversation flow: {e}")
            return None

    return _conversation_flows.get(session_id)


def process_conversation_input(
    user_input: str,
    session_id: str,
) -> Tuple[str, str]:
    """
    Process user input through the conversation state machine.

    Returns (detected_trigger, new_state_name)
    """
    flow = get_conversation_flow(session_id)
    if flow:
        trigger, state = flow.process_input(user_input)
        return trigger, state.name
    return "default", "UNKNOWN"


def add_conversation_goal(
    session_id: str,
    goal_id: str,
    description: str,
    priority: int = 5,
) -> bool:
    """Add a goal to a conversation flow."""
    flow = get_conversation_flow(session_id)
    if flow:
        flow.add_goal(goal_id, description, priority)
        return True
    return False


def complete_conversation_goal(session_id: str, goal_id: str) -> bool:
    """Mark a goal as completed."""
    flow = get_conversation_flow(session_id)
    if flow:
        return flow.complete_goal(goal_id)
    return False


def summarize_session(
    messages: List[Dict[str, str]],
    session_id: str = "",
    use_llm: bool = False,
) -> Dict[str, Any]:
    """
    Summarize a conversation session.

    Returns dict with summary, key_points, topics, sentiment.
    """
    summarizer = get_summarizer()
    if summarizer:
        try:
            summary = summarizer.summarize(messages, session_id, use_llm)
            return summary.to_dict()
        except Exception as e:
            logger.warning(f"Session summarization failed: {e}")

    return {"session_id": session_id, "full_summary": "Unable to summarize", "error": "Summarizer unavailable"}


def compress_conversation(
    messages: List[Dict[str, str]],
    max_tokens: int = 1000,
) -> str:
    """
    Compress a conversation for context injection.

    Returns compressed string with recent messages + summary of older.
    """
    summarizer = get_summarizer()
    if summarizer:
        try:
            return summarizer.compress_for_context(messages, max_tokens)
        except Exception as e:
            logger.warning(f"Conversation compression failed: {e}")

    # Fallback: just truncate
    lines = []
    for msg in messages[-5:]:
        role = msg.get("role", msg.get("source", "unknown"))
        lines.append(f"{role}: {msg.get('content', '')[:200]}")
    return "\n".join(lines)


def cleanup_old_sessions(max_age_hours: int = 24) -> int:
    """Clean up old conversation flows."""
    global _conversation_flows

    try:
        from core.self_improving.conversation.state_machine import cleanup_old_flows
        return cleanup_old_flows(max_age_hours)
    except Exception as e:
        logger.warning(f"Session cleanup failed: {e}")
        return 0


def get_enhanced_stats() -> Dict[str, Any]:
    """Get comprehensive stats including v2 features."""
    stats = get_stats()

    # Add BM25 stats
    retriever = get_bm25_retriever()
    if retriever:
        stats["bm25"] = {
            "facts_indexed": len(retriever.bm25_facts.documents),
            "reflections_indexed": len(retriever.bm25_reflections.documents),
        }

    # Add active sessions
    stats["active_sessions"] = len(_conversation_flows)

    return stats
