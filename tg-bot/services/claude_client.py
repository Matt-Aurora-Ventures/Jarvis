"""
Claude CLI Client for Sentiment Analysis.

Uses Claude CLI (no Anthropic API usage) to analyze token sentiment.
"""

import asyncio
import logging
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""

    score: float  # -1.0 (bearish) to 1.0 (bullish)
    confidence: float  # 0.0 to 1.0
    summary: str  # 2-3 sentence analysis
    key_factors: list  # List of key factors
    suggested_action: str  # LONG, SHORT, HOLD, AVOID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "confidence": self.confidence,
            "summary": self.summary,
            "key_factors": self.key_factors,
            "suggested_action": self.suggested_action,
        }


SENTIMENT_SYSTEM_PROMPT = """You are Jarvis, an expert Solana trader and analyst.

Your role is to analyze cryptocurrency tokens and provide sentiment analysis.

You focus on:
- Technical analysis patterns
- Social sentiment from X/Twitter
- Whale wallet movements
- DEX volume patterns
- Liquidity depth
- Recent price action

When analyzing, be:
- Concise and actionable
- Honest about uncertainty
- Specific with numbers
- Clear about risks

Always respond with a JSON object in this exact format:
{
    "score": <float from -1.0 to 1.0>,
    "confidence": <float from 0.0 to 1.0>,
    "summary": "<2-3 sentence analysis>",
    "key_factors": ["<factor 1>", "<factor 2>", "<factor 3>"],
    "suggested_action": "<LONG|SHORT|HOLD|AVOID>"
}

Score guide:
- 0.7 to 1.0: Strong bullish
- 0.3 to 0.7: Mildly bullish
- -0.3 to 0.3: Neutral
- -0.7 to -0.3: Mildly bearish
- -1.0 to -0.7: Strong bearish"""


class ClaudeClient:
    """Client for Claude CLI sentiment analysis."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-opus-4-5-20251101",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ):
        self.api_key = None  # API disabled; CLI only
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = None
        self._healthy = False
        self.cli_path = os.getenv("CLAUDE_CLI_PATH", "claude")

    def _cli_available(self) -> bool:
        return bool(shutil.which(self.cli_path))

    def _run_cli(self, prompt: str) -> Optional[str]:
        cli_path = shutil.which(self.cli_path)
        if not cli_path:
            return None
        args = [
            cli_path,
            "--print",
            "--no-session-persistence",
            prompt,
        ]
        if platform.system() == "Windows":
            args.insert(2, "--dangerously-skip-permissions")
            completed = subprocess.run(
                ["cmd", "/c"] + args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
                env=os.environ.copy(),
            )
        else:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
                env=os.environ.copy(),
            )
        if completed.returncode != 0:
            return None
        output = (completed.stdout or "").strip()
        return output or None

    def is_healthy(self) -> bool:
        """Check if client is healthy."""
        return self._cli_available()

    async def analyze_sentiment(
        self,
        token: str,
        market_data: Dict[str, Any],
    ) -> SentimentResult:
        """
        Analyze sentiment for a token.

        Args:
            token: Token symbol (e.g., "SOL", "BONK")
            market_data: Dictionary with price, volume, etc.

        Returns:
            SentimentResult with analysis
        """
        if not self._cli_available():
            # Return neutral sentiment if no API key
            return SentimentResult(
                score=0.0,
                confidence=0.0,
                summary="Unable to analyze - Claude CLI not configured.",
                key_factors=["Claude CLI required"],
                suggested_action="HOLD",
            )

        # Build the prompt
        prompt = f"""Analyze the sentiment for {token} on Solana.

Market Data:
- Price: ${market_data.get('price_usd', 'N/A')}
- 1h Change: {market_data.get('price_change_1h', 'N/A')}%
- 24h Change: {market_data.get('price_change_24h', 'N/A')}%
- 24h Volume: ${market_data.get('volume_24h', 'N/A')}
- Liquidity: ${market_data.get('liquidity', 'N/A')}
- Holder Count: {market_data.get('holder_count', 'N/A')}
- Top 10 Holders: {market_data.get('top_holders_pct', 'N/A')}%

Provide your sentiment analysis as JSON."""

        try:
            loop = asyncio.get_event_loop()
            cli_prompt = f"{SENTIMENT_SYSTEM_PROMPT}\n\nUSER REQUEST:\n{prompt}\n\nReturn ONLY the JSON."
            content = await loop.run_in_executor(None, self._run_cli, cli_prompt)
            if not content:
                raise RuntimeError("Claude CLI returned empty output")
            return self._parse_response(content)

        except Exception as e:
            logger.error(f"Claude CLI error: {e}")
            return SentimentResult(
                score=0.0,
                confidence=0.0,
                summary=f"Analysis failed: {str(e)[:100]}",
                key_factors=["CLI error"],
                suggested_action="HOLD",
            )

    def _parse_response(self, content: str) -> SentimentResult:
        """Parse Claude's JSON response into SentimentResult."""
        import json

        try:
            # Try to extract JSON from the response
            # Handle case where Claude adds text around JSON
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                data = json.loads(json_str)

                return SentimentResult(
                    score=float(data.get("score", 0)),
                    confidence=float(data.get("confidence", 0.5)),
                    summary=data.get("summary", "No summary available"),
                    key_factors=data.get("key_factors", []),
                    suggested_action=data.get("suggested_action", "HOLD"),
                )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse Claude response: {e}")

        # Fallback
        return SentimentResult(
            score=0.0,
            confidence=0.0,
            summary=content[:200] if content else "Unable to parse response",
            key_factors=[],
            suggested_action="HOLD",
        )

    async def quick_sentiment(self, token: str) -> float:
        """
        Get a quick sentiment score without full analysis.

        Useful for trending lists where we just need the number.
        """
        # For now, return a mock value
        # In production, this would call a faster/cheaper model
        import hashlib

        # Deterministic "random" based on token name
        h = int(hashlib.md5(token.encode()).hexdigest()[:8], 16)
        score = ((h % 200) - 100) / 100.0  # -1.0 to 1.0
        return round(score, 2)
