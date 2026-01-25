"""LLM-powered fact synthesis for daily reflections and entity insights."""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

import anthropic

logger = logging.getLogger(__name__)


def synthesize_daily_facts(facts: List[Dict[str, Any]]) -> str:
    """
    Synthesize yesterday's facts into key learnings using Claude 3.5 Sonnet.

    Args:
        facts: List of fact dicts with keys:
            - id: fact ID
            - content: fact content
            - context: situational context
            - source: source system
            - timestamp: ISO timestamp
            - confidence: confidence score
            - entities: list of entity mentions

    Returns:
        Synthesized markdown text with top 5 insights, or skip message if no facts.

    Example output:
        ## Key Insights

        **HIGH CONFIDENCE:**
        1. KR8TIV graduation trade: +140% profit in 2h (bags.fm → Jupiter, 2026-01-24 14:32)
        2. User lucid prefers aggressive risk on high-sentiment tokens (conf: 0.85+)

        **MEDIUM CONFIDENCE:**
        3. Bags.fm graduations correlate with 2h volume spikes (observed 3x yesterday)

        **LOW CONFIDENCE:**
        4. Twitter engagement higher on AI-themed tokens (single observation)
    """
    if not facts:
        return "No facts to synthesize."

    # Group facts by source for context organization
    facts_by_source: Dict[str, List[Dict]] = {}
    for fact in facts:
        source = fact.get("source", "unknown")
        if source not in facts_by_source:
            facts_by_source[source] = []
        facts_by_source[source].append(fact)

    # Build context text organized by source
    context_lines = []
    for source, source_facts in facts_by_source.items():
        context_lines.append(f"\n**Source: {source}** ({len(source_facts)} facts)")
        for fact in source_facts:
            timestamp = fact.get("timestamp", "unknown")
            if isinstance(timestamp, datetime):
                timestamp = timestamp.strftime("%Y-%m-%d %H:%M")
            elif isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamp = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, AttributeError):
                    pass

            content = fact.get("content", "")
            context = fact.get("context", "")
            entities = fact.get("entities", [])
            confidence = fact.get("confidence", 1.0)

            context_lines.append(f"  - [{timestamp}] {content}")
            if context:
                context_lines.append(f"    Context: {context}")
            if entities:
                context_lines.append(f"    Entities: {', '.join(entities)}")
            context_lines.append(f"    Confidence: {confidence:.2f}")

    context_text = "\n".join(context_lines)

    # Build prompt for Claude
    prompt = f"""You are Jarvis, an autonomous AI assistant reviewing yesterday's memory to extract key learnings.

Yesterday's facts organized by source:
{context_text}

**Task:** Synthesize the TOP 5 most important facts to remember long-term.

**Focus on:**
- Trade outcomes (wins, losses, patterns)
- User preferences and behaviors
- Token patterns and signals
- Strategic insights
- Notable events or anomalies

**Format:**
Use confidence markers based on evidence strength:
- **HIGH CONFIDENCE:** Objectively verified facts (trade results, explicit user statements)
- **MEDIUM CONFIDENCE:** Observed patterns (2-3 occurrences, correlations)
- **LOW CONFIDENCE:** Single observations, tentative patterns

**Requirements:**
1. Number each insight (1-5)
2. Include timestamp references for key facts
3. Be concise but specific (one line per insight)
4. Cite evidence strength
5. Focus on actionable insights

If fewer than 5 insights are meaningful, provide fewer. Quality over quantity.

Output markdown format:
## Key Insights

**HIGH CONFIDENCE:**
1. [insight with timestamp]

**MEDIUM CONFIDENCE:**
2. [insight with timestamp]

**LOW CONFIDENCE:**
3. [insight with timestamp]
"""

    try:
        # Initialize Anthropic client (reads ANTHROPIC_API_KEY from env)
        client = anthropic.Anthropic()

        # Call Claude 3.5 Sonnet with low temperature for factual synthesis
        response = client.messages.create(
            model="claude-3-5-sonnet-20250122",
            max_tokens=2000,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Extract synthesis from response
        synthesis = response.content[0].text.strip()
        logger.info(f"Synthesized {len(facts)} facts into daily reflection")
        return synthesis

    except Exception as e:
        logger.error(f"Failed to synthesize daily facts: {e}", exc_info=True)
        # Fallback: return a basic summary
        return f"**Synthesis Error:** Failed to process {len(facts)} facts with Claude API.\n\nError: {str(e)}"


def synthesize_entity_insights(
    entity_name: str,
    entity_type: str,
    facts: List[Dict[str, Any]]
) -> str:
    """
    Synthesize insights about a specific entity using Claude 3.5 Sonnet.

    Args:
        entity_name: Entity name (e.g., '@KR8TIV', 'lucid').
        entity_type: Entity type ('token', 'user', 'strategy', 'other').
        facts: List of facts related to this entity.

    Returns:
        3-5 bullet points of actionable insights.

    Example output:
        - Win rate: 73% (11/15 trades profitable)
        - Avg PnL: +42% per trade, best on bags.fm graduations
        - Success pattern: Buy within 2h of graduation, exit at +50-100%
        - Recent trend (7d): Increased focus on AI-themed tokens
        - Confidence: HIGH (15 trades, consistent pattern)
    """
    if not facts:
        return f"- No data available for {entity_name}"

    # Build context text for the entity
    context_lines = [f"Entity: {entity_name} (type: {entity_type})"]
    context_lines.append(f"Total facts: {len(facts)}\n")

    for fact in facts[-20:]:  # Last 20 facts to avoid token limit
        timestamp = fact.get("timestamp", "unknown")
        if isinstance(timestamp, datetime):
            timestamp = timestamp.strftime("%Y-%m-%d %H:%M")
        elif isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, AttributeError):
                pass

        content = fact.get("content", "")
        context = fact.get("context", "")
        source = fact.get("source", "unknown")

        context_lines.append(f"[{timestamp}] ({source}) {content}")
        if context:
            context_lines.append(f"  Context: {context}")

    context_text = "\n".join(context_lines)

    # Build prompt
    prompt = f"""You are Jarvis analyzing performance and patterns for entity: {entity_name}

{context_text}

**Task:** Produce 3-5 bullet points of actionable insights about this entity.

**Include:**
- Performance summary (if applicable: win rate, avg PnL, success patterns)
- Behavioral patterns (what works, what fails)
- Recent trends (changes in last 7 days)
- Confidence assessment (how reliable is this data?)

**Format:** Concise bullet points, specific numbers/examples.

**Example:**
- Win rate: 73% (11/15 trades profitable)
- Avg PnL: +42% per trade, best on bags.fm graduations
- Success pattern: Buy within 2h of graduation, exit at +50-100%
- Recent trend (7d): Increased focus on AI-themed tokens
- Confidence: HIGH (15 trades, consistent pattern)
"""

    try:
        # Initialize Anthropic client
        client = anthropic.Anthropic()

        # Call Claude with low temperature
        response = client.messages.create(
            model="claude-3-5-sonnet-20250122",
            max_tokens=1000,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Extract insights
        insights = response.content[0].text.strip()
        logger.info(f"Synthesized insights for entity {entity_name} from {len(facts)} facts")
        return insights

    except Exception as e:
        logger.error(f"Failed to synthesize entity insights for {entity_name}: {e}", exc_info=True)
        # Fallback: basic stats
        return f"- Entity: {entity_name}\n- Facts: {len(facts)}\n- Error: Failed to synthesize insights ({str(e)})"
