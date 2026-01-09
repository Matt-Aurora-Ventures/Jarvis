"""
Reflexion Engine for Jarvis Self-Improving Core.

Based on the Reflexion paper (NeurIPS 2023):
- Agents improve through verbal self-reflection, not weight updates
- Store reflections in episodic memory
- Use reflections to guide future decisions

The nightly reflection cycle:
1. Gather problematic interactions (negative feedback, retries, confusion)
2. Ask Claude Opus to analyze what went wrong
3. Generate concrete lessons and new approaches
4. Store reflections for future use
5. Prune old, unused reflections

Key insight: Storing "what I did wrong and what to do differently" as text
beats model fine-tuning for fast, continuous improvement.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from core.self_improving.memory.store import MemoryStore
from core.self_improving.memory.models import Reflection, Interaction

logger = logging.getLogger("jarvis.reflexion")

# System prompt for reflection generation
REFLECTION_SYSTEM_PROMPT = """You are a self-improving AI assistant analyzing your own failures.
Be honest, specific, and actionable. The goal is to generate concrete rules that will prevent
similar failures in the future.

Guidelines:
- Be specific about what went wrong, not vague
- Identify root causes, not just symptoms
- Generate actionable rules, not platitudes
- Consider edge cases the rule should handle
- Keep lessons concise (1-2 sentences)"""

# Prompt for analyzing failures
FAILURE_ANALYSIS_PROMPT = """Analyze these problematic interactions where I (Jarvis) failed or caused confusion.

Interactions with issues:
{interactions}

For EACH interaction, provide:
1. What happened (factual, brief)
2. Why it failed (root cause analysis)
3. What I should do differently (specific action)
4. A concrete rule to remember (1-2 sentences, actionable)

Output as JSON (no markdown):
{{
    "reflections": [
        {{
            "trigger": "situation that triggered the failure",
            "what_happened": "factual description",
            "why_failed": "root cause",
            "lesson": "concrete rule to remember",
            "new_approach": "what to do instead"
        }}
    ]
}}

Be specific and actionable. Generic advice like "be more careful" is not helpful."""

# Prompt for consolidating reflections
CONSOLIDATION_PROMPT = """Review these reflections and identify patterns or redundancies.

Reflections:
{reflections}

Tasks:
1. Identify reflections that are essentially the same lesson
2. Merge similar reflections into stronger, more general rules
3. Flag reflections that are too vague to be useful
4. Suggest which reflections should be kept vs. removed

Output as JSON:
{{
    "merged": [
        {{
            "ids_to_merge": [1, 3, 5],
            "consolidated_lesson": "the merged, stronger rule",
            "consolidated_approach": "the merged approach"
        }}
    ],
    "to_remove": [2, 7],
    "to_keep": [4, 6],
    "summary": "brief summary of the consolidation"
}}"""


@dataclass
class ReflectionBatch:
    """A batch of reflections from a single reflection cycle."""

    reflections: List[Reflection] = field(default_factory=list)
    interactions_analyzed: int = 0
    cycle_time: datetime = field(default_factory=datetime.utcnow)
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflections": [r.to_dict() for r in self.reflections],
            "interactions_analyzed": self.interactions_analyzed,
            "cycle_time": self.cycle_time.isoformat(),
            "duration_seconds": self.duration_seconds,
        }


class ReflexionEngine:
    """
    Self-improvement through verbal reflection.

    Usage:
        engine = ReflexionEngine(memory, llm_client)

        # Nightly reflection (run at 3am)
        batch = await engine.run_reflection_cycle()

        # Before responding, get relevant reflections
        reflections = engine.get_relevant_reflections("user asked about X")

        # After using a reflection, mark it
        engine.mark_reflection_used(reflection_id)
    """

    def __init__(
        self,
        memory: MemoryStore,
        llm_client: Optional[Any] = None,
        model: str = "claude-sonnet-4-20250514",
        opus_model: str = "claude-opus-4-20250514",
    ):
        self.memory = memory
        self.llm_client = llm_client
        self.model = model  # For routine analysis
        self.opus_model = opus_model  # For deep reflection
        self._reflection_count = 0

    def set_llm_client(self, client: Any):
        """Set the LLM client."""
        self.llm_client = client

    def _format_interactions(self, interactions: List[Interaction]) -> str:
        """Format interactions for the prompt."""
        lines = []
        for i, interaction in enumerate(interactions, 1):
            feedback = interaction.feedback or "unknown"
            lines.append(
                f"[{i}] User: {interaction.user_input[:300]}\n"
                f"    Jarvis: {interaction.jarvis_response[:300] if interaction.jarvis_response else 'N/A'}\n"
                f"    Feedback: {feedback}"
            )
        return "\n\n".join(lines)

    def _parse_reflections(self, response: str) -> List[Reflection]:
        """Parse LLM response into Reflection objects."""
        reflections = []

        clean = response.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```\w*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)

        try:
            data = json.loads(clean)
            for r in data.get("reflections", []):
                reflections.append(
                    Reflection(
                        trigger=r.get("trigger", ""),
                        what_happened=r.get("what_happened", ""),
                        why_failed=r.get("why_failed", ""),
                        lesson=r.get("lesson", ""),
                        new_approach=r.get("new_approach", ""),
                    )
                )
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse reflection response: {e}")

        return reflections

    async def run_reflection_cycle(
        self,
        hours_lookback: int = 24,
        max_interactions: int = 20,
        use_opus: bool = True,
    ) -> ReflectionBatch:
        """
        Run a full reflection cycle on recent problematic interactions.

        This is the core of the Reflexion pattern - analyzing failures
        and generating concrete lessons for future improvement.

        Args:
            hours_lookback: How far back to look for problems
            max_interactions: Maximum interactions to analyze
            use_opus: Whether to use Claude Opus (better quality)

        Returns:
            ReflectionBatch with generated reflections
        """
        start_time = datetime.utcnow()
        batch = ReflectionBatch(cycle_time=start_time)

        if not self.llm_client:
            logger.warning("No LLM client - skipping reflection cycle")
            return batch

        # Get problematic interactions
        problems = self.memory.get_problematic_interactions(
            hours=hours_lookback,
            limit=max_interactions,
        )

        if not problems:
            logger.info("No problematic interactions found - nothing to reflect on")
            return batch

        batch.interactions_analyzed = len(problems)
        interactions_text = self._format_interactions(problems)

        prompt = FAILURE_ANALYSIS_PROMPT.format(interactions=interactions_text)
        model = self.opus_model if use_opus else self.model

        try:
            response = self.llm_client.messages.create(
                model=model,
                max_tokens=2000,
                system=REFLECTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            reflections = self._parse_reflections(response_text)

            # Store reflections
            for reflection in reflections:
                if reflection.lesson:  # Only store if there's an actual lesson
                    self.memory.store_reflection(reflection)
                    batch.reflections.append(reflection)
                    self._reflection_count += 1

            batch.duration_seconds = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                f"Reflection cycle complete: analyzed {len(problems)} interactions, "
                f"generated {len(batch.reflections)} reflections in {batch.duration_seconds:.1f}s"
            )

        except Exception as e:
            logger.error(f"Reflection cycle failed: {e}")

        return batch

    def run_reflection_cycle_sync(
        self,
        hours_lookback: int = 24,
        max_interactions: int = 20,
        use_opus: bool = True,
    ) -> ReflectionBatch:
        """Synchronous version of run_reflection_cycle."""
        start_time = datetime.utcnow()
        batch = ReflectionBatch(cycle_time=start_time)

        if not self.llm_client:
            logger.warning("No LLM client - skipping reflection cycle")
            return batch

        problems = self.memory.get_problematic_interactions(
            hours=hours_lookback,
            limit=max_interactions,
        )

        if not problems:
            logger.info("No problematic interactions found")
            return batch

        batch.interactions_analyzed = len(problems)
        interactions_text = self._format_interactions(problems)
        prompt = FAILURE_ANALYSIS_PROMPT.format(interactions=interactions_text)
        model = self.opus_model if use_opus else self.model

        try:
            response = self.llm_client.messages.create(
                model=model,
                max_tokens=2000,
                system=REFLECTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            reflections = self._parse_reflections(response_text)

            for reflection in reflections:
                if reflection.lesson:
                    self.memory.store_reflection(reflection)
                    batch.reflections.append(reflection)
                    self._reflection_count += 1

            batch.duration_seconds = (datetime.utcnow() - start_time).total_seconds()

        except Exception as e:
            logger.error(f"Reflection cycle failed: {e}")

        return batch

    def get_relevant_reflections(
        self,
        context: str,
        limit: int = 5,
        mark_as_applied: bool = False,
    ) -> List[Reflection]:
        """
        Get reflections relevant to the current context.

        Call this before generating a response to inject relevant lessons.

        Args:
            context: The current user query or situation
            limit: Maximum reflections to return
            mark_as_applied: Whether to mark reflections as used

        Returns:
            List of relevant Reflection objects
        """
        reflections = self.memory.get_relevant_reflections(context, limit)

        if mark_as_applied:
            for r in reflections:
                if r.id:
                    self.memory.mark_reflection_applied(r.id)

        return reflections

    def format_reflections_for_prompt(
        self,
        reflections: List[Reflection],
    ) -> str:
        """Format reflections for inclusion in a prompt."""
        if not reflections:
            return ""

        lines = ["**Lessons from past mistakes (apply if relevant):**"]
        for r in reflections:
            lines.append(f"- {r.lesson}")
            if r.new_approach:
                lines.append(f"  → {r.new_approach}")

        return "\n".join(lines)

    async def reflect_on_single_failure(
        self,
        user_input: str,
        jarvis_response: str,
        feedback: str,
        error_details: Optional[str] = None,
    ) -> Optional[Reflection]:
        """
        Generate a reflection for a single failure immediately.

        Use this for significant failures that shouldn't wait for nightly cycle.
        """
        if not self.llm_client:
            return None

        prompt = f"""Analyze this single failure and generate a reflection.

User: {user_input[:500]}
My response: {jarvis_response[:500]}
Feedback: {feedback}
{f"Error details: {error_details}" if error_details else ""}

Generate a single reflection:
{{
    "trigger": "situation description",
    "what_happened": "what went wrong",
    "why_failed": "root cause",
    "lesson": "concrete rule to remember",
    "new_approach": "what to do instead"
}}"""

        try:
            response = self.llm_client.messages.create(
                model=self.model,
                max_tokens=500,
                system=REFLECTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text

            clean = response_text.strip()
            if clean.startswith("```"):
                clean = re.sub(r"^```\w*\n?", "", clean)
                clean = re.sub(r"\n?```$", "", clean)

            data = json.loads(clean)
            reflection = Reflection(
                trigger=data.get("trigger", ""),
                what_happened=data.get("what_happened", ""),
                why_failed=data.get("why_failed", ""),
                lesson=data.get("lesson", ""),
                new_approach=data.get("new_approach", ""),
            )

            if reflection.lesson:
                self.memory.store_reflection(reflection)
                return reflection

        except Exception as e:
            logger.warning(f"Failed to reflect on single failure: {e}")

        return None

    async def consolidate_reflections(self, max_age_days: int = 30) -> Dict[str, Any]:
        """
        Consolidate and prune old reflections.

        Run periodically (weekly) to:
        - Merge similar reflections
        - Remove redundant ones
        - Strengthen patterns

        Returns summary of consolidation.
        """
        if not self.llm_client:
            return {"error": "No LLM client"}

        # Get recent reflections
        reflections = self.memory.get_relevant_reflections("", limit=50)

        if len(reflections) < 5:
            return {"message": "Not enough reflections to consolidate"}

        reflections_text = "\n".join(
            f"[{r.id}] {r.lesson} | Approach: {r.new_approach}"
            for r in reflections
            if r.id
        )

        prompt = CONSOLIDATION_PROMPT.format(reflections=reflections_text)

        try:
            response = self.llm_client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            # Parse and apply consolidation
            # (Implementation depends on how aggressive you want consolidation to be)
            return {"status": "consolidation_proposed", "raw": response.content[0].text}

        except Exception as e:
            logger.error(f"Consolidation failed: {e}")
            return {"error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the reflexion engine."""
        memory_stats = self.memory.get_stats()
        return {
            "total_reflections": memory_stats.get("reflections_count", 0),
            "reflections_generated_this_session": self._reflection_count,
        }


# Convenience function for quick reflection
def reflect_on_failure(
    memory: MemoryStore,
    user_input: str,
    jarvis_response: str,
    feedback: str,
    llm_client: Any,
) -> Optional[Reflection]:
    """Quick function to generate and store a reflection."""
    engine = ReflexionEngine(memory, llm_client)
    import asyncio
    return asyncio.run(
        engine.reflect_on_single_failure(user_input, jarvis_response, feedback)
    )
