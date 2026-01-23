"""
Claude Code Generator for Vibe Coding Pipeline

Generates code via Claude API with context awareness and safety.
All content is scrubbed of sensitive data before sending to Claude.

Usage:
    generator = CodeGenerator()
    result = await generator.generate(
        instruction="Add rate limiting to the API",
        context_files=["core/api/handler.py"]
    )
"""

import os
import logging
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try to import anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None

from core.security.scrubber import get_scrubber, SensitiveScrubber
from core.llm.anthropic_utils import get_anthropic_base_url, get_anthropic_api_key, is_local_anthropic


@dataclass
class CodeResult:
    """Result of code generation."""
    id: str
    code: str
    model: str
    tokens_used: int
    redacted_items: List[str] = field(default_factory=list)
    instruction: str = ""
    context_files: List[str] = field(default_factory=list)
    created_at: str = ""
    success: bool = True
    error: str = ""


@dataclass
class CodeBlock:
    """Extracted code block from response."""
    language: str
    code: str
    filepath: Optional[str] = None


class CodeGenerator:
    """
    Generate code via Claude API with context awareness.

    Features:
    - Automatic sensitive data scrubbing
    - Context-aware file inclusion
    - Code extraction and parsing
    - Result caching for apply/refine
    """

    SYSTEM_PROMPT = """You are Jarvis's internal code generator. You write Python code for the Jarvis trading bot.

RULES:
1. Write clean, production-ready code
2. Include error handling
3. Follow existing code patterns
4. Add type hints
5. Add docstrings for public methods
6. If modifying existing code, show the exact changes needed

OUTPUT FORMAT:
- Start with a brief explanation (1-2 sentences)
- Then the code in ```python blocks
- If modifying a file, specify the filepath: ```python filepath=path/to/file.py
- End with any important notes or warnings

NEVER include actual API keys, passwords, or secrets in code - always use environment variables.
NEVER generate code that could harm the system or leak data."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize code generator.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env)
            model: Model to use (default: claude-sonnet-4-20250514)
        """
        self.api_key = api_key or get_anthropic_api_key()
        if is_local_anthropic():
            self.model = os.getenv("OLLAMA_CODE_MODEL") or os.getenv("OLLAMA_MODEL") or "qwen3-coder"
        else:
            self.model = model
        self.scrubber = get_scrubber()

        # Cache recent results for apply/refine
        self._result_cache: Dict[str, CodeResult] = {}
        self._cache_max_size = 20

        if not ANTHROPIC_AVAILABLE:
            logger.warning("anthropic package not installed - code generation unavailable")

    async def generate(
        self,
        instruction: str,
        context_files: List[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> CodeResult:
        """
        Generate code based on instruction.

        Args:
            instruction: What to build/fix
            context_files: List of file paths to include as context
            max_tokens: Max response length
            temperature: Model temperature (lower = more deterministic)

        Returns:
            CodeResult with generated code and metadata
        """
        result_id = str(uuid.uuid4())[:8]

        if not ANTHROPIC_AVAILABLE or not self.api_key:
            return CodeResult(
                id=result_id,
                code="",
                model=self.model,
                tokens_used=0,
                success=False,
                error="Anthropic API not available or API key missing",
            )

        all_redacted = []

        # Build context from files (scrubbed)
        context = ""
        if context_files:
            for filepath in context_files:
                scrubbed_content, redacted = self.scrubber.scrub_file_content(filepath)
                all_redacted.extend(redacted)

                if scrubbed_content:
                    context += f"\n--- {filepath} ---\n{scrubbed_content}\n"

        # Scrub the instruction itself
        scrubbed_instruction, instruction_redacted = self.scrubber.scrub(instruction)
        all_redacted.extend(instruction_redacted)

        # Build user message
        user_message = ""
        if context:
            user_message += f"CONTEXT FILES:\n{context}\n\n"
        user_message += f"INSTRUCTION:\n{scrubbed_instruction}"

        try:
            client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=get_anthropic_base_url(),
            )

            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=self.SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            code = response.content[0].text
            tokens = response.usage.output_tokens

            result = CodeResult(
                id=result_id,
                code=code,
                model=self.model,
                tokens_used=tokens,
                redacted_items=list(set(all_redacted)),
                instruction=instruction,
                context_files=context_files or [],
                created_at=datetime.now(timezone.utc).isoformat(),
                success=True,
            )

            # Cache result
            self._cache_result(result)

            logger.info(
                f"Generated code: {tokens} tokens, "
                f"{len(all_redacted)} items scrubbed"
            )

            return result

        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return CodeResult(
                id=result_id,
                code="",
                model=self.model,
                tokens_used=0,
                success=False,
                error=str(e),
            )

    async def refine(
        self,
        result_id: str,
        refinement: str,
        max_tokens: int = 4096,
    ) -> CodeResult:
        """
        Refine a previous code generation result.

        Args:
            result_id: ID of previous result
            refinement: What to change/improve

        Returns:
            New CodeResult with refined code
        """
        previous = self._result_cache.get(result_id)

        if not previous:
            return CodeResult(
                id=str(uuid.uuid4())[:8],
                code="",
                model=self.model,
                tokens_used=0,
                success=False,
                error=f"Previous result {result_id} not found in cache",
            )

        # Build refinement instruction
        instruction = f"""PREVIOUS CODE:
{previous.code}

REFINEMENT REQUEST:
{refinement}

Please update the code according to the refinement request."""

        return await self.generate(
            instruction=instruction,
            context_files=previous.context_files,
            max_tokens=max_tokens,
        )

    def _cache_result(self, result: CodeResult):
        """Cache a result for later retrieval."""
        self._result_cache[result.id] = result

        # Prune old entries
        if len(self._result_cache) > self._cache_max_size:
            # Remove oldest entries
            sorted_keys = sorted(
                self._result_cache.keys(),
                key=lambda k: self._result_cache[k].created_at
            )
            for key in sorted_keys[: len(sorted_keys) - self._cache_max_size]:
                del self._result_cache[key]

    def get_cached_result(self, result_id: str) -> Optional[CodeResult]:
        """Get a cached result by ID."""
        return self._result_cache.get(result_id)

    def extract_code_blocks(self, text: str) -> List[CodeBlock]:
        """
        Extract code blocks from Claude response.

        Parses markdown code blocks and extracts language and filepath.
        """
        import re

        blocks = []

        # Pattern for code blocks with optional filepath
        # ```python filepath=path/to/file.py
        pattern = r'```(\w+)?(?:\s+filepath=([^\s]+))?\n(.*?)```'

        for match in re.finditer(pattern, text, re.DOTALL):
            language = match.group(1) or "python"
            filepath = match.group(2)
            code = match.group(3).strip()

            blocks.append(CodeBlock(
                language=language,
                code=code,
                filepath=filepath,
            ))

        return blocks

    def detect_relevant_files(self, instruction: str) -> List[str]:
        """
        Smart detection of relevant files based on instruction.

        Returns list of file paths that might be relevant.
        """
        project_root = Path(__file__).resolve().parents[2]
        files = []
        instruction_lower = instruction.lower()

        # Trading related
        if any(word in instruction_lower for word in ['trade', 'position', 'jupiter', 'swap', 'treasury']):
            files.extend([
                'bots/treasury/trading.py',
                'bots/treasury/jupiter.py',
                'bots/treasury/scorekeeper.py',
            ])

        # Telegram related
        if any(word in instruction_lower for word in ['telegram', 'bot', 'message', 'button', 'callback']):
            files.extend([
                'tg_bot/bot.py',
            ])

        # Sentiment/analysis related
        if any(word in instruction_lower for word in ['sentiment', 'analysis', 'grok', 'report']):
            files.extend([
                'bots/buy_tracker/sentiment_report.py',
            ])

        # Security related
        if any(word in instruction_lower for word in ['key', 'security', 'credential', 'auth', 'scrub']):
            files.extend([
                'core/security/key_manager.py',
                'core/security/scrubber.py',
            ])

        # Twitter/X related
        if any(word in instruction_lower for word in ['twitter', 'tweet', 'x ', 'autonomous']):
            files.extend([
                'bots/twitter/autonomous_engine.py',
                'bots/twitter/jarvis_voice.py',
            ])

        # API related
        if any(word in instruction_lower for word in ['api', 'endpoint', 'request', 'http']):
            files.extend([
                'core/api/client.py',
            ])

        # Return only files that exist
        return [
            str(f) for f in files
            if (project_root / f).exists()
        ]


# Singleton
_generator: Optional[CodeGenerator] = None


def get_code_generator() -> CodeGenerator:
    """Get the singleton code generator."""
    global _generator
    if _generator is None:
        _generator = CodeGenerator()
    return _generator
