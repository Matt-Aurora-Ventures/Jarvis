"""
Learning Extractor for Jarvis Self-Improving Core.

After each conversation ends, Jarvis should extract and store learnings:
- NEW FACTS about the user (preferences, habits, relationships)
- CORRECTIONS to things we got wrong
- IMPLICIT PREFERENCES (how they like things done)
- FOLLOW-UP ITEMS to track

This module MUST use Claude API for extraction (local models aren't reliable enough).
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from core.self_improving.memory.store import MemoryStore
from core.self_improving.memory.models import Fact, Entity, Interaction

logger = logging.getLogger("jarvis.learning")

# Extraction prompt for Claude
EXTRACTION_PROMPT = """Analyze this conversation and extract learnings about the user.

Conversation:
{conversation}

Extract the following (be conservative - only extract what's clearly stated or strongly implied):

1. NEW FACTS about the user (preferences, habits, relationships, work patterns)
   - Only include facts that would be useful to remember for future conversations
   - Include confidence (0.5-1.0) based on how explicit the information was

2. CORRECTIONS to previous beliefs (if any "No, I meant X not Y" patterns)
   - Note what was wrong and what the correction is

3. IMPLICIT PREFERENCES (formatting, response style, communication preferences)
   - Things like "prefers short responses", "likes bullet points", etc.

4. FOLLOW-UP ITEMS (tasks mentioned, deadlines, things to check back on)
   - Include any deadlines or timeframes mentioned

Output as JSON (no markdown code blocks):
{{
    "facts": [
        {{"entity": "user|person_name|project_name", "fact": "specific fact", "confidence": 0.8}}
    ],
    "corrections": [
        {{"old_belief": "what we thought", "new_belief": "what's correct", "evidence": "quote"}}
    ],
    "preferences": [
        {{"domain": "communication|formatting|timing|etc", "preference": "description", "example": "context"}}
    ],
    "follow_ups": [
        {{"item": "what to follow up on", "deadline": "ISO date or null", "remind_user": true}}
    ],
    "entities_mentioned": [
        {{"name": "Name", "type": "person|project|company|concept", "context": "how mentioned"}}
    ]
}}

If nothing to extract, return empty arrays. Be conservative - don't make things up."""


@dataclass
class ExtractionResult:
    """Results from learning extraction."""

    facts: List[Dict[str, Any]] = field(default_factory=list)
    corrections: List[Dict[str, Any]] = field(default_factory=list)
    preferences: List[Dict[str, Any]] = field(default_factory=list)
    follow_ups: List[Dict[str, Any]] = field(default_factory=list)
    entities_mentioned: List[Dict[str, Any]] = field(default_factory=list)
    raw_response: str = ""
    extraction_time: float = 0.0

    def has_learnings(self) -> bool:
        return bool(
            self.facts
            or self.corrections
            or self.preferences
            or self.follow_ups
            or self.entities_mentioned
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "corrections": self.corrections,
            "preferences": self.preferences,
            "follow_ups": self.follow_ups,
            "entities_mentioned": self.entities_mentioned,
            "extraction_time": self.extraction_time,
        }


class LearningExtractor:
    """
    Extracts learnings from conversations using Claude.

    Usage:
        extractor = LearningExtractor(memory_store)
        result = await extractor.extract_from_conversation(messages)
        await extractor.apply_learnings(result)
    """

    def __init__(
        self,
        memory: MemoryStore,
        llm_client: Optional[Any] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.memory = memory
        self.llm_client = llm_client
        self.model = model
        self._extraction_count = 0

    def set_llm_client(self, client: Any):
        """Set the LLM client (Anthropic client)."""
        self.llm_client = client

    def _format_conversation(self, messages: List[Dict[str, str]]) -> str:
        """Format conversation messages for the prompt."""
        lines = []
        for msg in messages[-20:]:  # Last 20 messages max
            role = msg.get("role", msg.get("source", "unknown"))
            content = msg.get("content", msg.get("text", ""))[:500]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _parse_extraction(self, response: str) -> ExtractionResult:
        """Parse the LLM response into structured extraction."""
        result = ExtractionResult(raw_response=response)

        # Clean up response
        clean = response.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```\w*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)

        try:
            data = json.loads(clean)
            result.facts = data.get("facts", [])
            result.corrections = data.get("corrections", [])
            result.preferences = data.get("preferences", [])
            result.follow_ups = data.get("follow_ups", [])
            result.entities_mentioned = data.get("entities_mentioned", [])
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse extraction response: {e}")
            # Try to extract partial data
            result = self._fallback_parse(response)

        return result

    def _fallback_parse(self, response: str) -> ExtractionResult:
        """Fallback parsing when JSON fails."""
        result = ExtractionResult(raw_response=response)

        # Try to extract facts using regex
        fact_pattern = r'"fact":\s*"([^"]+)"'
        matches = re.findall(fact_pattern, response)
        for fact_text in matches:
            result.facts.append({
                "entity": "user",
                "fact": fact_text,
                "confidence": 0.6,
            })

        return result

    async def extract_from_conversation(
        self,
        messages: List[Dict[str, str]],
        session_id: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract learnings from a conversation.

        Args:
            messages: List of conversation messages with role/content or source/text
            session_id: Optional session ID for tracking

        Returns:
            ExtractionResult with facts, corrections, preferences, follow-ups
        """
        if not messages:
            return ExtractionResult()

        if not self.llm_client:
            logger.warning("No LLM client set - skipping extraction")
            return ExtractionResult()

        start_time = datetime.utcnow()
        conversation_text = self._format_conversation(messages)

        prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)

        try:
            response = self.llm_client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            result = self._parse_extraction(response_text)
            result.extraction_time = (datetime.utcnow() - start_time).total_seconds()
            self._extraction_count += 1

            logger.info(
                f"Extracted {len(result.facts)} facts, "
                f"{len(result.corrections)} corrections, "
                f"{len(result.preferences)} preferences, "
                f"{len(result.follow_ups)} follow-ups"
            )

            return result

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return ExtractionResult()

    def extract_from_conversation_sync(
        self,
        messages: List[Dict[str, str]],
        session_id: Optional[str] = None,
    ) -> ExtractionResult:
        """Synchronous version of extract_from_conversation."""
        if not messages:
            return ExtractionResult()

        if not self.llm_client:
            logger.warning("No LLM client set - skipping extraction")
            return ExtractionResult()

        start_time = datetime.utcnow()
        conversation_text = self._format_conversation(messages)

        prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)

        try:
            response = self.llm_client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            result = self._parse_extraction(response_text)
            result.extraction_time = (datetime.utcnow() - start_time).total_seconds()
            self._extraction_count += 1

            return result

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return ExtractionResult()

    def apply_learnings(self, result: ExtractionResult) -> Dict[str, int]:
        """
        Apply extracted learnings to memory.

        Returns count of items stored per category.
        """
        counts = {
            "facts_stored": 0,
            "corrections_applied": 0,
            "preferences_stored": 0,
            "entities_created": 0,
        }

        # Store entities first
        for entity_data in result.entities_mentioned:
            try:
                entity = Entity(
                    name=entity_data["name"],
                    entity_type=entity_data.get("type", "concept"),
                    attributes={"context": entity_data.get("context", "")},
                )
                self.memory.store_entity(entity)
                counts["entities_created"] += 1
            except Exception as e:
                logger.warning(f"Failed to store entity: {e}")

        # Store facts
        for fact_data in result.facts:
            try:
                fact = Fact(
                    entity=fact_data["entity"],
                    fact=fact_data["fact"],
                    confidence=float(fact_data.get("confidence", 0.8)),
                    source="conversation_extraction",
                )
                self.memory.store_fact(fact)
                counts["facts_stored"] += 1
            except Exception as e:
                logger.warning(f"Failed to store fact: {e}")

        # Apply corrections
        for correction in result.corrections:
            try:
                old_belief = correction.get("old_belief", "")
                new_belief = correction.get("new_belief", "")
                if old_belief and new_belief:
                    # Try to find and update the old fact
                    # Store as a new fact with high confidence
                    fact = Fact(
                        entity="user",
                        fact=f"CORRECTION: {new_belief} (was: {old_belief})",
                        confidence=0.95,
                        source="user_correction",
                    )
                    self.memory.store_fact(fact)
                    counts["corrections_applied"] += 1
            except Exception as e:
                logger.warning(f"Failed to apply correction: {e}")

        # Store preferences as facts
        for pref in result.preferences:
            try:
                fact = Fact(
                    entity="user",
                    fact=f"Preference ({pref.get('domain', 'general')}): {pref['preference']}",
                    confidence=0.85,
                    source="preference_extraction",
                )
                self.memory.store_fact(fact)
                counts["preferences_stored"] += 1
            except Exception as e:
                logger.warning(f"Failed to store preference: {e}")

        # Follow-ups are stored as facts with deadline info
        for followup in result.follow_ups:
            try:
                deadline = followup.get("deadline", "")
                fact = Fact(
                    entity="user",
                    fact=f"Follow-up needed: {followup['item']}" + (f" (by {deadline})" if deadline else ""),
                    confidence=0.9,
                    source="followup_extraction",
                )
                self.memory.store_fact(fact)
            except Exception as e:
                logger.warning(f"Failed to store follow-up: {e}")

        logger.info(f"Applied learnings: {counts}")
        return counts

    async def learn_from_session(
        self,
        session_id: str,
        store_interactions: bool = True,
    ) -> ExtractionResult:
        """
        Learn from all interactions in a session.

        This is typically called when a conversation ends.
        """
        interactions = self.memory.get_session_interactions(session_id)

        if not interactions:
            return ExtractionResult()

        # Convert interactions to message format
        messages = []
        for interaction in interactions:
            messages.append({
                "role": "user",
                "content": interaction.user_input,
            })
            if interaction.jarvis_response:
                messages.append({
                    "role": "assistant",
                    "content": interaction.jarvis_response,
                })

        result = await self.extract_from_conversation(messages, session_id)

        if result.has_learnings():
            self.apply_learnings(result)

        return result

    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get statistics about extraction."""
        return {
            "total_extractions": self._extraction_count,
            "facts_in_memory": self.memory.get_stats().get("facts_count", 0),
        }


# Convenience function for quick extraction
def extract_learnings(
    memory: MemoryStore,
    messages: List[Dict[str, str]],
    llm_client: Any,
    apply: bool = True,
) -> ExtractionResult:
    """
    Quick function to extract and optionally apply learnings.

    Args:
        memory: MemoryStore instance
        messages: Conversation messages
        llm_client: Anthropic client
        apply: Whether to apply learnings to memory

    Returns:
        ExtractionResult
    """
    extractor = LearningExtractor(memory, llm_client)
    result = extractor.extract_from_conversation_sync(messages)

    if apply and result.has_learnings():
        extractor.apply_learnings(result)

    return result
