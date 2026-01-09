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

# Singleton orchestrator instance
_orchestrator = None
_scheduler = None


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
    global _orchestrator, _scheduler

    if _scheduler is not None:
        stop_scheduler()

    if _orchestrator is not None:
        _orchestrator.close()
        _orchestrator = None
        logger.info("Self-improving orchestrator closed")
