"""
Chain-of-Thought (CoT) Reasoning for Jarvis.

Research basis (2025):
- Zero-shot CoT: "Let's think step by step" improves reasoning by 10-40%
- Structured reasoning reduces hallucination
- Explicit reasoning traces enable debugging and learning

This module provides:
1. Structured reasoning prompts
2. Step-by-step thought parsing
3. Reasoning quality scoring
4. Learning from reasoning failures
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.reasoning")


class ReasoningType(Enum):
    """Types of reasoning tasks."""

    DIRECT = "direct"  # Simple, direct response
    ANALYTICAL = "analytical"  # Analysis required
    PLANNING = "planning"  # Multi-step planning
    CREATIVE = "creative"  # Creative generation
    FACTUAL = "factual"  # Fact retrieval/verification
    DECISION = "decision"  # Decision making


@dataclass
class ReasoningStep:
    """A single step in the reasoning chain."""

    step_number: int
    thought: str
    action: Optional[str] = None  # What action this step leads to
    confidence: float = 0.8
    evidence: Optional[str] = None  # Supporting evidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step_number,
            "thought": self.thought,
            "action": self.action,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


@dataclass
class ReasoningTrace:
    """Complete reasoning trace for a response."""

    query: str
    reasoning_type: ReasoningType
    steps: List[ReasoningStep] = field(default_factory=list)
    conclusion: str = ""
    overall_confidence: float = 0.8
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "reasoning_type": self.reasoning_type.value,
            "steps": [s.to_dict() for s in self.steps],
            "conclusion": self.conclusion,
            "overall_confidence": self.overall_confidence,
            "created_at": self.created_at.isoformat(),
        }

    def format_for_prompt(self) -> str:
        """Format trace as prompt context."""
        if not self.steps:
            return ""

        lines = ["My reasoning:"]
        for step in self.steps:
            lines.append(f"{step.step_number}. {step.thought}")
            if step.evidence:
                lines.append(f"   Evidence: {step.evidence}")

        if self.conclusion:
            lines.append(f"Conclusion: {self.conclusion}")

        return "\n".join(lines)


class ChainOfThought:
    """
    Chain-of-Thought reasoning engine.

    Usage:
        cot = ChainOfThought(memory_store)
        prompt = cot.create_reasoning_prompt(user_query, context)
        # Send prompt to LLM
        trace = cot.parse_response(llm_response)
        # Use trace.conclusion for final response
    """

    # Zero-shot CoT trigger phrases (research-backed)
    COT_TRIGGERS = [
        "Let me think through this step by step.",
        "Let me reason through this carefully.",
        "Let me break this down.",
    ]

    def __init__(self, memory_store: Optional[Any] = None):
        self.memory = memory_store
        self._trace_history: List[ReasoningTrace] = []

    def classify_reasoning_type(self, query: str, context: Dict[str, Any] = None) -> ReasoningType:
        """
        Classify what type of reasoning is needed for a query.

        This helps select the right prompting strategy.
        """
        lowered = query.lower()

        # Planning indicators
        if any(w in lowered for w in ["how to", "steps to", "plan", "process", "workflow"]):
            return ReasoningType.PLANNING

        # Analysis indicators
        if any(w in lowered for w in ["analyze", "compare", "evaluate", "assess", "review"]):
            return ReasoningType.ANALYTICAL

        # Decision indicators
        if any(w in lowered for w in ["should i", "which", "decide", "choose", "better"]):
            return ReasoningType.DECISION

        # Creative indicators
        if any(w in lowered for w in ["create", "write", "generate", "compose", "design"]):
            return ReasoningType.CREATIVE

        # Factual indicators
        if any(w in lowered for w in ["what is", "who is", "when", "where", "define"]):
            return ReasoningType.FACTUAL

        return ReasoningType.DIRECT

    def create_reasoning_prompt(
        self,
        query: str,
        context: Dict[str, Any] = None,
        include_cot: bool = True,
        max_steps: int = 5,
    ) -> str:
        """
        Create a prompt that encourages structured reasoning.

        Args:
            query: User's query
            context: Additional context (facts, history, etc.)
            include_cot: Whether to include CoT trigger
            max_steps: Maximum reasoning steps to request

        Returns:
            Formatted prompt string
        """
        reasoning_type = self.classify_reasoning_type(query, context)
        context = context or {}

        # Build prompt sections
        sections = []

        # Add relevant context
        if context.get("facts"):
            facts_str = "\n".join(f"- {f}" for f in context["facts"][:5])
            sections.append(f"Relevant facts:\n{facts_str}")

        if context.get("lessons"):
            lessons_str = "\n".join(f"- {l}" for l in context["lessons"][:3])
            sections.append(f"Lessons from past experience:\n{lessons_str}")

        if context.get("recent_context"):
            sections.append(f"Recent context: {context['recent_context'][:200]}")

        # Add reasoning-type specific instructions
        type_instructions = self._get_type_instructions(reasoning_type, max_steps)
        sections.append(type_instructions)

        # Add CoT trigger
        if include_cot:
            sections.append(self.COT_TRIGGERS[0])

        # Add query
        sections.append(f"Query: {query}")

        # Add output format
        output_format = self._get_output_format(reasoning_type)
        sections.append(output_format)

        return "\n\n".join(sections)

    def _get_type_instructions(self, reasoning_type: ReasoningType, max_steps: int) -> str:
        """Get reasoning instructions for a specific type."""
        instructions = {
            ReasoningType.DIRECT: (
                "Provide a clear, direct response. "
                "If the answer is simple, give it simply."
            ),
            ReasoningType.ANALYTICAL: (
                f"Analyze this carefully in {max_steps} or fewer steps:\n"
                "1. Identify the key elements to analyze\n"
                "2. Consider different perspectives\n"
                "3. Weigh evidence and factors\n"
                "4. Draw a reasoned conclusion"
            ),
            ReasoningType.PLANNING: (
                f"Create a clear plan with {max_steps} or fewer steps:\n"
                "1. Define the goal clearly\n"
                "2. Identify prerequisites and dependencies\n"
                "3. Outline concrete action steps\n"
                "4. Consider potential obstacles\n"
                "5. Suggest success criteria"
            ),
            ReasoningType.DECISION: (
                f"Help make this decision in {max_steps} or fewer steps:\n"
                "1. Clarify the decision to be made\n"
                "2. List the options available\n"
                "3. Evaluate pros and cons of each\n"
                "4. Consider user's priorities\n"
                "5. Make a recommendation with reasoning"
            ),
            ReasoningType.CREATIVE: (
                "Generate creative content:\n"
                "1. Understand the request and constraints\n"
                "2. Consider the audience/purpose\n"
                "3. Generate the content\n"
                "4. Review for quality and fit"
            ),
            ReasoningType.FACTUAL: (
                "Provide accurate factual information:\n"
                "1. Recall relevant facts\n"
                "2. Verify against known information\n"
                "3. State confidence level\n"
                "4. Note any uncertainties"
            ),
        }
        return instructions.get(reasoning_type, instructions[ReasoningType.DIRECT])

    def _get_output_format(self, reasoning_type: ReasoningType) -> str:
        """Get the expected output format."""
        if reasoning_type == ReasoningType.DIRECT:
            return (
                "Format your response as:\n"
                "THOUGHT: [Brief reasoning]\n"
                "RESPONSE: [Your answer]"
            )

        return (
            "Format your response as:\n"
            "STEP 1: [First reasoning step]\n"
            "STEP 2: [Second reasoning step]\n"
            "... (continue as needed)\n"
            "CONCLUSION: [Final answer/recommendation]\n"
            "CONFIDENCE: [high/medium/low]"
        )

    def parse_response(self, response: str, query: str = "") -> ReasoningTrace:
        """
        Parse an LLM response into a structured reasoning trace.

        Args:
            response: Raw LLM response
            query: Original query (for context)

        Returns:
            ReasoningTrace object
        """
        trace = ReasoningTrace(
            query=query,
            reasoning_type=self.classify_reasoning_type(query),
        )

        # Parse steps
        step_pattern = r"STEP\s*(\d+):\s*(.+?)(?=STEP\s*\d+:|CONCLUSION:|CONFIDENCE:|$)"
        step_matches = re.findall(step_pattern, response, re.DOTALL | re.IGNORECASE)

        for step_num, step_content in step_matches:
            trace.steps.append(
                ReasoningStep(
                    step_number=int(step_num),
                    thought=step_content.strip(),
                )
            )

        # Parse simple THOUGHT format
        if not trace.steps:
            thought_match = re.search(r"THOUGHT:\s*(.+?)(?=RESPONSE:|$)", response, re.DOTALL | re.IGNORECASE)
            if thought_match:
                trace.steps.append(
                    ReasoningStep(
                        step_number=1,
                        thought=thought_match.group(1).strip(),
                    )
                )

        # Parse conclusion
        conclusion_match = re.search(r"CONCLUSION:\s*(.+?)(?=CONFIDENCE:|$)", response, re.DOTALL | re.IGNORECASE)
        if conclusion_match:
            trace.conclusion = conclusion_match.group(1).strip()
        else:
            # Try RESPONSE format
            response_match = re.search(r"RESPONSE:\s*(.+?)$", response, re.DOTALL | re.IGNORECASE)
            if response_match:
                trace.conclusion = response_match.group(1).strip()
            else:
                # Fall back to entire response
                trace.conclusion = response.strip()

        # Parse confidence
        confidence_match = re.search(r"CONFIDENCE:\s*(high|medium|low)", response, re.IGNORECASE)
        if confidence_match:
            confidence_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
            trace.overall_confidence = confidence_map.get(confidence_match.group(1).lower(), 0.7)

        # Store in history
        self._trace_history.append(trace)
        if len(self._trace_history) > 100:
            self._trace_history = self._trace_history[-100:]

        return trace

    def get_reasoning_summary(self, trace: ReasoningTrace) -> str:
        """
        Get a concise summary of the reasoning for logging/debugging.
        """
        if not trace.steps:
            return f"Direct response (confidence: {trace.overall_confidence:.0%})"

        steps_summary = " -> ".join(
            s.thought[:50] + "..." if len(s.thought) > 50 else s.thought
            for s in trace.steps[:3]
        )
        return (
            f"[{trace.reasoning_type.value}] "
            f"{len(trace.steps)} steps: {steps_summary} "
            f"(confidence: {trace.overall_confidence:.0%})"
        )

    def learn_from_feedback(
        self,
        trace: ReasoningTrace,
        feedback: str,
        was_helpful: bool,
    ) -> Dict[str, Any]:
        """
        Learn from feedback on a reasoning trace.

        This can be used to improve future reasoning.
        """
        learning = {
            "trace_summary": self.get_reasoning_summary(trace),
            "feedback": feedback,
            "was_helpful": was_helpful,
            "reasoning_type": trace.reasoning_type.value,
            "step_count": len(trace.steps),
        }

        # If memory store available, store the learning
        if self.memory and hasattr(self.memory, "store_fact"):
            from core.self_improving.memory.models import Fact

            fact_text = (
                f"Reasoning feedback ({trace.reasoning_type.value}): "
                f"{'Helpful' if was_helpful else 'Unhelpful'} - {feedback[:100]}"
            )
            self.memory.store_fact(
                Fact(
                    entity="reasoning",
                    fact=fact_text,
                    confidence=0.8 if was_helpful else 0.6,
                    source="reasoning_feedback",
                )
            )

        logger.info(f"Reasoning feedback recorded: {learning}")
        return learning


# Convenience functions
def create_cot_prompt(
    query: str,
    context: Dict[str, Any] = None,
    memory_store: Any = None,
) -> str:
    """
    Create a Chain-of-Thought prompt for a query.

    This is the main entry point for adding CoT to prompts.
    """
    cot = ChainOfThought(memory_store)
    return cot.create_reasoning_prompt(query, context)


def parse_cot_response(response: str, query: str = "") -> ReasoningTrace:
    """
    Parse a response that used CoT prompting.
    """
    cot = ChainOfThought()
    return cot.parse_response(response, query)


# Integration helper for conversation.py
def enhance_prompt_with_reasoning(
    prompt: str,
    query: str,
    context: Dict[str, Any] = None,
) -> str:
    """
    Enhance an existing prompt with CoT reasoning instructions.

    Use this to add reasoning to generate_response() without
    rewriting the entire prompt.
    """
    cot = ChainOfThought()
    reasoning_type = cot.classify_reasoning_type(query, context)

    # Only add CoT for complex reasoning tasks
    if reasoning_type == ReasoningType.DIRECT:
        return prompt

    cot_section = (
        "\n--- REASONING INSTRUCTIONS ---\n"
        f"{cot.COT_TRIGGERS[0]}\n"
        "Before responding, briefly show your reasoning:\n"
        "1. What is being asked?\n"
        "2. What relevant information do I have?\n"
        "3. What's the best approach?\n"
        "Then provide your response.\n"
        "--- END REASONING ---\n"
    )

    # Insert before "User says:" if present
    if "User says:" in prompt:
        return prompt.replace("User says:", f"{cot_section}\nUser says:")

    return prompt + cot_section
