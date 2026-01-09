"""
Self-Improving Orchestrator for Jarvis.

This is the main entry point that ties together:
- Memory store (SQLite)
- Trust ladder (gradual autonomy)
- Reflexion engine (nightly self-improvement)
- Proactive engine (suggestions)
- Learning extractor (conversation analysis)
- Action framework (autonomous actions)

The orchestrator provides:
1. Unified initialization
2. Context building for responses
3. Scheduled tasks (nightly reflection)
4. State management
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from core.self_improving.memory.store import MemoryStore
from core.self_improving.memory.models import Interaction, Fact, ContextBundle
from core.self_improving.trust.ladder import TrustManager, TrustLevel
from core.self_improving.reflexion.engine import ReflexionEngine
from core.self_improving.proactive.engine import ProactiveEngine
from core.self_improving.learning.extractor import LearningExtractor
from core.self_improving.actions.framework import (
    ActionRegistry,
    ActionResult,
    ActionContext,
    create_default_registry,
)

logger = logging.getLogger("jarvis.orchestrator")


class SelfImprovingOrchestrator:
    """
    Main orchestrator for the self-improving Jarvis system.

    Usage:
        # Initialize
        orchestrator = SelfImprovingOrchestrator(
            db_path="data/jarvis_memory.db",
            llm_client=anthropic_client,
        )

        # Before responding to user
        context = orchestrator.build_response_context(user_query)

        # After conversation
        orchestrator.learn_from_conversation(messages, session_id)

        # Nightly (scheduled)
        orchestrator.run_nightly_cycle()
    """

    def __init__(
        self,
        db_path: str = "data/jarvis_memory.db",
        llm_client: Optional[Any] = None,
        model: str = "claude-sonnet-4-20250514",
        opus_model: str = "claude-opus-4-20250514",
    ):
        # Core components
        self.memory = MemoryStore(db_path)
        self.trust = TrustManager(self.memory)
        self.llm_client = llm_client
        self.model = model
        self.opus_model = opus_model

        # Subsystems
        self.reflexion = ReflexionEngine(
            self.memory,
            llm_client,
            model,
            opus_model,
        )
        self.proactive = ProactiveEngine(
            self.memory,
            self.trust,
            llm_client,
            model,
        )
        self.learning = LearningExtractor(
            self.memory,
            llm_client,
            model,
        )
        self.actions = create_default_registry(self.memory, self.trust)

        # State
        self._initialized_at = datetime.utcnow()
        self._last_reflection: Optional[datetime] = None
        self._session_count = 0

        logger.info("Self-improving orchestrator initialized")

    def set_llm_client(self, client: Any):
        """Set/update the LLM client for all subsystems."""
        self.llm_client = client
        self.reflexion.set_llm_client(client)
        self.proactive.set_llm_client(client)
        self.learning.set_llm_client(client)

    # =========================================================================
    # CONTEXT BUILDING
    # =========================================================================

    def build_response_context(
        self,
        user_query: str,
        include_reflections: bool = True,
        include_facts: bool = True,
    ) -> Dict[str, Any]:
        """
        Build context for generating a response.

        This retrieves relevant:
        - Facts from memory
        - Past reflections (lessons learned)
        - Recent conversation context
        - Trust level information

        Returns a dict that can be injected into prompts.
        """
        context_bundle = self.memory.build_context(user_query)

        # Get relevant reflections
        reflections = []
        if include_reflections:
            reflections = self.reflexion.get_relevant_reflections(
                user_query,
                limit=3,
                mark_as_applied=True,
            )

        # Format for prompt
        context = {
            "query": user_query,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if include_facts and context_bundle.facts:
            context["relevant_facts"] = [
                f"{f.entity}: {f.fact}" for f in context_bundle.facts[:10]
            ]

        if reflections:
            context["lessons_to_apply"] = [
                f"{r.lesson}" for r in reflections
            ]

        if context_bundle.recent_interactions:
            context["recent_context"] = [
                i.user_input[:100] for i in context_bundle.recent_interactions[:3]
            ]

        return context

    def format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """Format context dict as a prompt section."""
        sections = []

        if context.get("relevant_facts"):
            sections.append(
                "**What I know:**\n" +
                "\n".join(f"- {f}" for f in context["relevant_facts"])
            )

        if context.get("lessons_to_apply"):
            sections.append(
                "**Lessons to apply:**\n" +
                "\n".join(f"- {l}" for l in context["lessons_to_apply"])
            )

        return "\n\n".join(sections) if sections else ""

    # =========================================================================
    # CONVERSATION HANDLING
    # =========================================================================

    def start_session(self, session_id: Optional[str] = None) -> str:
        """Start a new conversation session."""
        if not session_id:
            session_id = f"session_{datetime.utcnow().timestamp()}"
        self._session_count += 1
        logger.info(f"Started session: {session_id}")
        return session_id

    def record_interaction(
        self,
        user_input: str,
        jarvis_response: str,
        session_id: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> int:
        """Record a conversation interaction."""
        interaction = Interaction(
            user_input=user_input,
            jarvis_response=jarvis_response,
            session_id=session_id,
            feedback=feedback,
        )
        return self.memory.store_interaction(interaction)

    def record_feedback(self, interaction_id: int, feedback: str) -> bool:
        """Record feedback on an interaction."""
        return self.memory.update_interaction_feedback(interaction_id, feedback)

    async def learn_from_conversation(
        self,
        messages: List[Dict[str, str]],
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract and apply learnings from a conversation.

        Call this when a conversation ends.
        """
        result = await self.learning.extract_from_conversation(messages, session_id)

        if result.has_learnings():
            counts = self.learning.apply_learnings(result)
            return {
                "extracted": True,
                "facts": len(result.facts),
                "corrections": len(result.corrections),
                "preferences": len(result.preferences),
                "applied": counts,
            }

        return {"extracted": False, "reason": "No learnings found"}

    def learn_from_conversation_sync(
        self,
        messages: List[Dict[str, str]],
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synchronous version of learn_from_conversation."""
        result = self.learning.extract_from_conversation_sync(messages, session_id)

        if result.has_learnings():
            counts = self.learning.apply_learnings(result)
            return {
                "extracted": True,
                "facts": len(result.facts),
                "corrections": len(result.corrections),
                "preferences": len(result.preferences),
                "applied": counts,
            }

        return {"extracted": False, "reason": "No learnings found"}

    # =========================================================================
    # PROACTIVE SUGGESTIONS
    # =========================================================================

    async def check_for_suggestion(
        self,
        current_context: Dict[str, Any],
        domain: str = "general",
    ):
        """Check if a proactive suggestion should be made."""
        return await self.proactive.check_for_suggestion(current_context, domain)

    def record_suggestion_outcome(
        self,
        suggestion_id: str,
        accepted: bool,
        feedback: Optional[str] = None,
    ) -> bool:
        """Record user response to a suggestion."""
        return self.proactive.record_outcome(suggestion_id, accepted, feedback)

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def execute_action(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Optional[ActionContext] = None,
    ) -> ActionResult:
        """Execute an action if trust level permits."""
        return self.actions.execute(action_name, params, context)

    def get_available_actions(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get actions available at current trust level."""
        return self.actions.get_available_actions(domain)

    # =========================================================================
    # TRUST MANAGEMENT
    # =========================================================================

    def get_trust_level(self, domain: str = "general") -> TrustLevel:
        """Get current trust level for a domain."""
        return self.trust.get_level(domain)

    def get_trust_summary(self) -> Dict[str, Any]:
        """Get trust summary across all domains."""
        return self.trust.get_summary()

    def set_trust_level(self, domain: str, level: int) -> None:
        """Manually set trust level (admin function)."""
        self.trust.set_level(domain, level)

    # =========================================================================
    # SCHEDULED TASKS
    # =========================================================================

    async def run_nightly_cycle(self) -> Dict[str, Any]:
        """
        Run the nightly self-improvement cycle.

        This should be scheduled to run at ~3am:
        1. Run reflection on past 24h of failures
        2. Consolidate old reflections
        3. Update prediction accuracy
        4. Generate improvement proposals
        """
        logger.info("Starting nightly reflection cycle")
        results = {
            "started_at": datetime.utcnow().isoformat(),
            "reflection": None,
            "predictions_resolved": 0,
        }

        # Run reflection cycle
        try:
            batch = await self.reflexion.run_reflection_cycle(
                hours_lookback=24,
                max_interactions=20,
                use_opus=True,  # Use best model for reflection
            )
            results["reflection"] = {
                "interactions_analyzed": batch.interactions_analyzed,
                "reflections_generated": len(batch.reflections),
                "duration_seconds": batch.duration_seconds,
            }
            self._last_reflection = datetime.utcnow()
        except Exception as e:
            logger.error(f"Reflection cycle failed: {e}")
            results["reflection"] = {"error": str(e)}

        # Check for predictions to resolve
        unresolved = self.memory.get_unresolved_predictions(limit=10)
        # In real implementation, would check if predictions can be resolved

        results["completed_at"] = datetime.utcnow().isoformat()
        logger.info(f"Nightly cycle complete: {results}")

        return results

    def run_nightly_cycle_sync(self) -> Dict[str, Any]:
        """Synchronous version of run_nightly_cycle."""
        logger.info("Starting nightly reflection cycle (sync)")
        results = {
            "started_at": datetime.utcnow().isoformat(),
            "reflection": None,
        }

        try:
            batch = self.reflexion.run_reflection_cycle_sync(
                hours_lookback=24,
                max_interactions=20,
                use_opus=True,
            )
            results["reflection"] = {
                "interactions_analyzed": batch.interactions_analyzed,
                "reflections_generated": len(batch.reflections),
                "duration_seconds": batch.duration_seconds,
            }
            self._last_reflection = datetime.utcnow()
        except Exception as e:
            logger.error(f"Reflection cycle failed: {e}")
            results["reflection"] = {"error": str(e)}

        results["completed_at"] = datetime.utcnow().isoformat()
        return results

    # =========================================================================
    # DIAGNOSTICS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        memory_stats = self.memory.get_stats()
        trust_summary = self.trust.get_summary()
        proactive_stats = self.proactive.get_stats()
        reflexion_stats = self.reflexion.get_stats()

        return {
            "initialized_at": self._initialized_at.isoformat(),
            "uptime_hours": (datetime.utcnow() - self._initialized_at).total_seconds() / 3600,
            "sessions": self._session_count,
            "last_reflection": self._last_reflection.isoformat() if self._last_reflection else None,
            "memory": memory_stats,
            "trust": trust_summary,
            "proactive": proactive_stats,
            "reflexion": reflexion_stats,
        }

    def health_check(self) -> Dict[str, Any]:
        """Run health checks on all subsystems."""
        checks = {
            "memory": False,
            "trust": False,
            "reflexion": False,
            "proactive": False,
            "llm_client": False,
        }

        try:
            self.memory.get_stats()
            checks["memory"] = True
        except Exception as e:
            checks["memory_error"] = str(e)

        try:
            self.trust.get_summary()
            checks["trust"] = True
        except Exception as e:
            checks["trust_error"] = str(e)

        try:
            self.reflexion.get_stats()
            checks["reflexion"] = True
        except Exception as e:
            checks["reflexion_error"] = str(e)

        try:
            self.proactive.get_stats()
            checks["proactive"] = True
        except Exception as e:
            checks["proactive_error"] = str(e)

        checks["llm_client"] = self.llm_client is not None

        checks["healthy"] = all([
            checks["memory"],
            checks["trust"],
            checks["reflexion"],
            checks["proactive"],
        ])

        return checks

    def close(self):
        """Clean up resources."""
        self.memory.close()
        logger.info("Orchestrator closed")


# Convenience function for quick setup
def create_orchestrator(
    db_path: str = "data/jarvis_memory.db",
    llm_client: Optional[Any] = None,
) -> SelfImprovingOrchestrator:
    """Create and return a configured orchestrator."""
    return SelfImprovingOrchestrator(db_path, llm_client)
