"""
ReasoningEngine - Advanced Reasoning Modes

Provides Clawdbot-style transparent reasoning with configurable levels:
- Thinking levels control depth of analysis
- Reasoning modes control visibility to user
- Verbose modes control debug output

Used by Telegram bot and other interfaces for controlled reasoning.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Valid levels and modes
THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"]
REASONING_MODES = ["on", "off", "stream"]
VERBOSE_MODES = ["on", "off", "full"]

# Descriptions for user info
LEVEL_DESCRIPTIONS = {
    "off": "No thinking output - fastest responses",
    "minimal": "Brief one-liner thoughts",
    "low": "Simple step-by-step (2-3 sentences)",
    "medium": "Moderate detail (paragraph)",
    "high": "Detailed analysis (multiple paragraphs)",
    "xhigh": "Exhaustive reasoning (full breakdown)",
}


@dataclass
class ReasoningEngine:
    """
    Engine for generating and formatting reasoning output.

    Attributes:
        thinking_level: Depth of thinking (off/minimal/low/medium/high/xhigh)
        reasoning_mode: Visibility to user (on/off/stream)
        verbose_mode: Debug output level (on/off/full)
    """

    thinking_level: str = "low"
    reasoning_mode: str = "off"
    verbose_mode: str = "off"

    def __post_init__(self):
        """Validate initial values."""
        # Normalize to lowercase
        self.thinking_level = self.thinking_level.lower()
        self.reasoning_mode = self.reasoning_mode.lower()
        self.verbose_mode = self.verbose_mode.lower()

        # Validate
        if self.thinking_level not in THINKING_LEVELS:
            raise ValueError(f"Invalid thinking level: {self.thinking_level}. Valid: {THINKING_LEVELS}")
        if self.reasoning_mode not in REASONING_MODES:
            raise ValueError(f"Invalid reasoning mode: {self.reasoning_mode}. Valid: {REASONING_MODES}")
        if self.verbose_mode not in VERBOSE_MODES:
            raise ValueError(f"Invalid verbose mode: {self.verbose_mode}. Valid: {VERBOSE_MODES}")

    def set_thinking_level(self, level: str) -> None:
        """
        Set thinking level.

        Args:
            level: One of off/minimal/low/medium/high/xhigh

        Raises:
            ValueError: If level is invalid
        """
        level = level.lower()
        if level not in THINKING_LEVELS:
            raise ValueError(f"Invalid thinking level: {level}. Valid: {THINKING_LEVELS}")
        self.thinking_level = level
        logger.info(f"Thinking level set to: {level}")

    def set_reasoning_mode(self, mode: str) -> None:
        """
        Set reasoning mode.

        Args:
            mode: One of on/off/stream

        Raises:
            ValueError: If mode is invalid
        """
        mode = mode.lower()
        if mode not in REASONING_MODES:
            raise ValueError(f"Invalid reasoning mode: {mode}. Valid: {REASONING_MODES}")
        self.reasoning_mode = mode
        logger.info(f"Reasoning mode set to: {mode}")

    def set_verbose_mode(self, mode: str) -> None:
        """
        Set verbose mode.

        Args:
            mode: One of on/off/full

        Raises:
            ValueError: If mode is invalid
        """
        mode = mode.lower()
        if mode not in VERBOSE_MODES:
            raise ValueError(f"Invalid verbose mode: {mode}. Valid: {VERBOSE_MODES}")
        self.verbose_mode = mode
        logger.info(f"Verbose mode set to: {mode}")

    def think(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate thinking output based on current level.

        Args:
            prompt: The question/task to think about
            context: Optional context dict

        Returns:
            Thinking output string (empty if level is 'off')
        """
        if self.thinking_level == "off":
            return ""

        # Generate thinking based on level
        thinking_templates = {
            "minimal": self._think_minimal,
            "low": self._think_low,
            "medium": self._think_medium,
            "high": self._think_high,
            "xhigh": self._think_xhigh,
        }

        generator = thinking_templates.get(self.thinking_level, self._think_low)
        return generator(prompt, context or {})

    def _think_minimal(self, prompt: str, context: Dict) -> str:
        """Generate minimal one-liner thought."""
        # Extract key topic from prompt
        topic = prompt.split("?")[0].split()[-3:]
        topic_str = " ".join(topic) if topic else "this"
        return f"Considering {topic_str}..."

    def _think_low(self, prompt: str, context: Dict) -> str:
        """Generate low-level 2-3 sentence analysis."""
        topic = self._extract_topic(prompt)
        return (
            f"Analyzing {topic}. "
            f"Evaluating key factors and potential outcomes. "
            f"Forming a balanced assessment."
        )

    def _think_medium(self, prompt: str, context: Dict) -> str:
        """Generate medium-level paragraph analysis."""
        topic = self._extract_topic(prompt)
        return (
            f"Taking a closer look at {topic}. "
            f"First, I need to consider the context and relevant factors. "
            f"The key considerations here involve understanding the full picture - "
            f"what we know, what we don't know, and what assumptions we're making. "
            f"Based on this analysis, I can formulate a more informed response. "
            f"Let me weigh the pros and cons before providing my assessment."
        )

    def _think_high(self, prompt: str, context: Dict) -> str:
        """Generate high-level detailed analysis."""
        topic = self._extract_topic(prompt)
        ctx_summary = self._summarize_context(context)

        return (
            f"Deep analysis of: {topic}\n\n"
            f"CONTEXT ASSESSMENT:\n"
            f"{ctx_summary}\n\n"
            f"KEY FACTORS:\n"
            f"1. Understanding the core question and its implications\n"
            f"2. Identifying relevant data points and constraints\n"
            f"3. Evaluating potential approaches and their tradeoffs\n"
            f"4. Considering edge cases and failure modes\n\n"
            f"REASONING PROCESS:\n"
            f"Starting with first principles, I need to break this down systematically. "
            f"The question at hand involves multiple considerations that must be balanced. "
            f"Each factor carries different weight depending on the specific context. "
            f"I'm now synthesizing these elements into a coherent analysis."
        )

    def _think_xhigh(self, prompt: str, context: Dict) -> str:
        """Generate exhaustive xhigh-level breakdown."""
        topic = self._extract_topic(prompt)
        ctx_summary = self._summarize_context(context)

        return (
            f"EXHAUSTIVE ANALYSIS: {topic}\n\n"
            f"{'='*50}\n"
            f"PHASE 1: CONTEXT PARSING\n"
            f"{'='*50}\n"
            f"{ctx_summary}\n\n"
            f"{'='*50}\n"
            f"PHASE 2: PROBLEM DECOMPOSITION\n"
            f"{'='*50}\n"
            f"Breaking down the query into component parts:\n"
            f"- Primary objective: Understand and respond to '{topic}'\n"
            f"- Secondary considerations: Accuracy, completeness, actionability\n"
            f"- Constraints: Available information, time sensitivity\n\n"
            f"{'='*50}\n"
            f"PHASE 3: KNOWLEDGE RETRIEVAL\n"
            f"{'='*50}\n"
            f"Relevant domain knowledge:\n"
            f"- Prior experience with similar queries\n"
            f"- Domain-specific patterns and heuristics\n"
            f"- Potential pitfalls and common mistakes\n\n"
            f"{'='*50}\n"
            f"PHASE 4: REASONING CHAIN\n"
            f"{'='*50}\n"
            f"Step 1: Establish baseline understanding\n"
            f"Step 2: Identify information gaps\n"
            f"Step 3: Generate candidate responses\n"
            f"Step 4: Evaluate and rank options\n"
            f"Step 5: Select optimal response\n"
            f"Step 6: Validate against original question\n\n"
            f"{'='*50}\n"
            f"PHASE 5: CONFIDENCE ASSESSMENT\n"
            f"{'='*50}\n"
            f"Evaluating confidence level in the analysis...\n"
            f"Checking for logical consistency...\n"
            f"Identifying remaining uncertainties..."
        )

    def _extract_topic(self, prompt: str) -> str:
        """Extract main topic from prompt."""
        # Simple extraction - take first clause or question
        if "?" in prompt:
            return prompt.split("?")[0].strip()
        if "." in prompt:
            return prompt.split(".")[0].strip()
        return prompt[:50].strip() if len(prompt) > 50 else prompt.strip()

    def _summarize_context(self, context: Dict) -> str:
        """Summarize context dict for display."""
        if not context:
            return "No additional context provided."

        parts = []
        for key, value in context.items():
            if isinstance(value, str):
                parts.append(f"- {key}: {value[:100]}..." if len(value) > 100 else f"- {key}: {value}")
            else:
                parts.append(f"- {key}: {value}")

        return "\n".join(parts) if parts else "No additional context provided."

    def format_reasoning(self, reasoning: str) -> str:
        """
        Format reasoning output for display based on current mode.

        Args:
            reasoning: Raw reasoning text

        Returns:
            Formatted reasoning (empty if mode is 'off')
        """
        if self.reasoning_mode == "off":
            return ""

        if not reasoning:
            return ""

        if self.reasoning_mode == "on":
            # Formatted block for display after response
            return (
                f"\n---\n"
                f"Thinking ({self.thinking_level}):\n"
                f"{reasoning}\n"
                f"---"
            )

        if self.reasoning_mode == "stream":
            # Streaming format - line by line
            lines = reasoning.split("\n")
            formatted = [f"[think] {line}" for line in lines if line.strip()]
            return "\n".join(formatted)

        return reasoning

    def should_show_intermediate_steps(self) -> bool:
        """Check if intermediate steps should be shown based on verbose mode."""
        return self.verbose_mode in ("on", "full")

    def should_show_debug_info(self) -> bool:
        """Check if debug info should be shown based on verbose mode."""
        return self.verbose_mode == "full"

    def get_status(self) -> Dict[str, str]:
        """
        Get current status as dict.

        Returns:
            Dict with thinking_level, reasoning_mode, verbose_mode
        """
        return {
            "thinking_level": self.thinking_level,
            "reasoning_mode": self.reasoning_mode,
            "verbose_mode": self.verbose_mode,
        }

    def format_status(self) -> str:
        """
        Format status for human-readable display.

        Returns:
            Status string
        """
        return (
            f"Thinking: {self.thinking_level} ({LEVEL_DESCRIPTIONS.get(self.thinking_level, '')})\n"
            f"Reasoning: {self.reasoning_mode}\n"
            f"Verbose: {self.verbose_mode}"
        )

    def get_level_descriptions(self) -> Dict[str, str]:
        """
        Get descriptions for all thinking levels.

        Returns:
            Dict mapping level names to descriptions
        """
        return LEVEL_DESCRIPTIONS.copy()

    async def process_with_reasoning(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        response_generator: Optional[Any] = None,
    ) -> Dict[str, str]:
        """
        Process prompt with reasoning based on current settings.

        Args:
            prompt: The input prompt
            context: Optional context dict
            response_generator: Optional callable to generate actual response

        Returns:
            Dict with 'response' and 'reasoning' keys
        """
        result = {
            "response": "",
            "reasoning": "",
        }

        # Generate thinking if enabled
        if self.thinking_level != "off":
            reasoning = self.think(prompt, context)
            result["reasoning"] = self.format_reasoning(reasoning) if self.reasoning_mode != "off" else ""

            if self.should_show_intermediate_steps():
                logger.debug(f"Reasoning: {reasoning[:200]}...")

        # Generate response (placeholder - actual implementation would call LLM)
        if response_generator:
            result["response"] = await response_generator(prompt, context)
        else:
            # Default placeholder response
            result["response"] = f"Processed: {prompt[:50]}..."

        return result


def get_reasoning_engine(
    thinking_level: str = "low",
    reasoning_mode: str = "off",
    verbose_mode: str = "off",
) -> ReasoningEngine:
    """
    Factory function to create a ReasoningEngine.

    Args:
        thinking_level: Depth of thinking
        reasoning_mode: Visibility to user
        verbose_mode: Debug output level

    Returns:
        Configured ReasoningEngine instance
    """
    return ReasoningEngine(
        thinking_level=thinking_level,
        reasoning_mode=reasoning_mode,
        verbose_mode=verbose_mode,
    )
