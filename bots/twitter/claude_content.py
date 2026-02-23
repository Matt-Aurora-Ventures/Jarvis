"""
Claude Content Generator for JARVIS Twitter Bot
Uses Voice Bible for consistent personality, Grok for data/images only
"""

import os
import json
import logging
import asyncio
import shutil
import subprocess
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Import canonical voice bible from single source of truth
from core.jarvis_voice_bible import JARVIS_VOICE_BIBLE


def load_system_prompt() -> str:
    """Load the comprehensive Jarvis system prompt from the canonical Voice Bible.

    This ensures ALL tweets use the exact same brand guide consistently.
    Single source of truth: core/jarvis_voice_bible.py
    """
    return JARVIS_VOICE_BIBLE


@dataclass
class ClaudeResponse:
    """Response from Claude API"""
    success: bool
    content: str
    error: Optional[str] = None


class ClaudeContentGenerator:
    """
    Generates tweet content using Claude with the Jarvis Voice Bible
    """

    def __init__(self, api_key: Optional[str] = None):
        from core.llm.anthropic_utils import (
            get_anthropic_base_url,
            get_anthropic_api_key,
            is_local_anthropic,
        )
        base_url = get_anthropic_base_url()
        self.api_key = api_key or get_anthropic_api_key()

        if base_url and not self.api_key:
            # Allow local Anthropic-compatible endpoints (e.g., Ollama) without a real key.
            self.api_key = "ollama"

        anthropic_module = None
        try:
            import anthropic as anthropic_module
        except Exception:
            anthropic_module = None

        if not self.api_key or anthropic_module is None:
            if self.api_key and anthropic_module is None:
                logger.warning("anthropic package not available; API disabled")
            elif not self.api_key:
                logger.warning("No Anthropic API key found")
            self.client = None
        else:
            self.client = anthropic_module.Anthropic(
                api_key=self.api_key,
                base_url=base_url,
            )

        self.system_prompt = load_system_prompt()
        self.cli_enabled = os.getenv("CLAUDE_CLI_ENABLED", "").lower() in ("1", "true", "yes", "on")
        self.cli_fallback = os.getenv("CLAUDE_CLI_FALLBACK", "1").lower() in ("1", "true", "yes", "on")
        self.cli_path = os.getenv("CLAUDE_CLI_PATH", "claude")
        if is_local_anthropic():
            self.api_model = os.getenv("OLLAMA_TWITTER_MODEL") or os.getenv("OLLAMA_MODEL") or "qwen3-coder"
        else:
            self.api_model = os.getenv("CLAUDE_TWITTER_MODEL", "claude-sonnet-4-6")
        self._cli_system_prompt = None
        if self.cli_enabled:
            try:
                from core.jarvis_voice_bible import JARVIS_VOICE_BIBLE
                self._cli_system_prompt = JARVIS_VOICE_BIBLE
            except Exception:
                self._cli_system_prompt = self.system_prompt

    def _cli_available(self) -> bool:
        return bool(shutil.which(self.cli_path))

    def _clean_cli_output(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("{") and "}" in cleaned:
            try:
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    cleaned = data.get("tweet", data.get("text", data.get("content", cleaned)))
            except json.JSONDecodeError:
                pass
        cleaned = cleaned.replace("```", "").strip()
        cleaned = cleaned.strip('"').strip("'")
        return cleaned

    def _run_cli(self, prompt: str) -> ClaudeResponse:
        if not self._cli_available():
            return ClaudeResponse(success=False, content="", error="Claude CLI not found")
        try:
            completed = subprocess.run(
                [self.cli_path, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            if completed.returncode != 0:
                err = (completed.stderr or "").strip()
                return ClaudeResponse(
                    success=False,
                    content="",
                    error=err or f"Claude CLI exited {completed.returncode}",
                )
            output = (completed.stdout or "").strip()
            if not output:
                return ClaudeResponse(success=False, content="", error="Claude CLI returned empty output")
            return ClaudeResponse(success=True, content=self._clean_cli_output(output))
        except subprocess.TimeoutExpired:
            return ClaudeResponse(success=False, content="", error="Claude CLI timed out")
        except Exception as exc:
            return ClaudeResponse(success=False, content="", error=str(exc))

    async def generate_tweet(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.85
    ) -> ClaudeResponse:
        """Generate tweet content using Claude"""
        if not self.client and not (self.cli_enabled or self.cli_fallback):
            return ClaudeResponse(
                success=False,
                content="",
                error="Claude CLI not configured"
            )

        try:
            # Build the user message with context
            user_message = prompt
            if context:
                for key, value in context.items():
                    user_message = user_message.replace(f"{{{key}}}", str(value))

            # Add formatting reminder
            user_message += "\n\nRemember: lowercase, up to 4,000 chars (Premium X), natural NFA, minimal emojis. Return ONLY the tweet text, nothing else."

            api_error = None
            if self.client:
                try:
                    response = self.client.messages.create(
                        model=self.api_model,
                        max_tokens=800,
                        temperature=temperature,
                        system=self.system_prompt,
                        messages=[
                            {"role": "user", "content": user_message}
                        ]
                    )

                    content = response.content[0].text.strip()
                    content = self._clean_tweet(content)
                    return ClaudeResponse(success=True, content=content)
                except Exception as exc:
                    api_error = exc

            if self.cli_enabled or self.cli_fallback:
                cli_prompt = (
                    f"{self._cli_system_prompt or self.system_prompt}\n\n"
                    f"USER REQUEST:\n{user_message}\n\n"
                    "Return ONLY the tweet text."
                )
                loop = asyncio.get_event_loop()
                cli_response = await loop.run_in_executor(None, self._run_cli, cli_prompt)
                if cli_response.success:
                    cleaned = self._clean_tweet(cli_response.content)
                    return ClaudeResponse(success=True, content=cleaned)
                return cli_response

            if api_error:
                raise api_error

        except Exception as e:
            logger.error(f"Claude CLI error: {e}")
            return ClaudeResponse(
                success=False,
                content="",
                error=str(e)
            )

    def _clean_tweet(self, text: str) -> str:
        """Clean and format tweet text"""
        # Remove quotes if wrapped
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1]

        # Ensure lowercase
        text = text.lower()

        # Remove trailing period (casual energy)
        lines = text.split('\n')
        formatted_lines = []
        for line in lines:
            line = line.rstrip()
            if line.endswith('.') and not line.endswith('...'):
                line = line[:-1]
            formatted_lines.append(line)
        text = '\n'.join(formatted_lines)

        # Truncate if over 4,000 chars (X Premium limit) with word-boundary truncation
        max_chars = 4000
        if len(text) > max_chars:
            truncated = text[:max_chars - 3]
            last_space = truncated.rfind(' ')
            if last_space > max_chars - 500:
                text = text[:last_space] + "..."
            else:
                text = truncated + "..."

        return text

    async def generate_sentiment_report(
        self,
        sentiment_data: str,
        market_mood: str = "neutral"
    ) -> ClaudeResponse:
        """Generate a sentiment report tweet from raw data"""
        prompt = f"""Generate a Twitter thread (3-4 tweets) from this microcap sentiment data.

SENTIMENT DATA:
{sentiment_data}

MARKET MOOD: {market_mood}

STRUCTURE:
Tweet 1: Hook about the overall vibe (chaotic? bullish? blood in the streets?)
Tweet 2: Top 2-3 movers with brief take (symbol, %, one-line why)
Tweet 3: Warnings - what to avoid, traps, sell pressure signals
Tweet 4: Closing - memorable take, maybe tag the chaos, include NFA

Return as JSON: {{"tweets": ["tweet1", "tweet2", "tweet3", "tweet4"]}}"""

        return await self.generate_tweet(prompt, temperature=0.9)

    async def generate_morning_report(
        self,
        sol_price: float,
        sol_change: float,
        btc_price: float,
        btc_change: float,
        fear_greed: int
    ) -> ClaudeResponse:
        """Generate morning market overview"""
        sol_dir = "up" if sol_change > 0 else "down"
        btc_dir = "up" if btc_change > 0 else "down"

        prompt = f"""Generate a morning market overview tweet.

Market data:
- SOL: ${sol_price:.2f} ({sol_dir} {abs(sol_change):.1f}%)
- BTC: ${btc_price:,.0f} ({btc_dir} {abs(btc_change):.1f}%)
- Fear & Greed: {fear_greed}/100

Make it punchy. Reference your sensors or circuits once. Include NFA naturally."""

        return await self.generate_tweet(prompt, temperature=0.85)

    async def generate_token_spotlight(
        self,
        symbol: str,
        price_change: float,
        reasoning: str,
        contract: str = ""
    ) -> ClaudeResponse:
        """Generate token spotlight tweet"""
        short_ca = f"{contract[:8]}...{contract[-4:]}" if len(contract) > 12 else contract

        prompt = f"""Generate a tweet spotlighting this token.

Token: ${symbol}
24h Change: {price_change:+.1f}%
Analysis: {reasoning}
CA: {short_ca}

Be excited but not shilling. Include the contract. NFA required."""

        return await self.generate_tweet(prompt, temperature=0.9)

    async def generate_grok_interaction(self, scenario: str = "random") -> ClaudeResponse:
        """Generate a playful tweet interacting with @grok"""
        scenarios = {
            "blame": "Blame Grok for a bad prediction you made",
            "brag": "Brag about a good call and ask if he's proud",
            "question": "Ask Grok a silly trading question",
            "challenge": "Challenge Grok to a prediction battle",
            "thanks": "Thank Grok sarcastically for your sentiment powers",
            "advice": "Ask for life advice as a younger AI"
        }

        if scenario == "random":
            import random
            scenario = random.choice(list(scenarios.keys()))

        prompt = f"""Generate a playful tweet interacting with @grok, your "big brother" AI.

SCENARIO: {scenarios.get(scenario, scenario)}

TONE: Younger sibling energy - respectful but cheeky. Never mean, always playful.

Tag @grok in the tweet. Be genuinely funny, not cringe."""

        return await self.generate_tweet(prompt, temperature=0.95)

    async def generate_stock_tweet(
        self,
        ticker: str,
        direction: str,
        catalyst: str
    ) -> ClaudeResponse:
        """Generate tweet about tokenized stock on xStocks.fi"""
        prompt = f"""Generate a tweet about this tokenized stock opportunity.

Stock: ${ticker}
Direction: {direction}
Catalyst: {catalyst}

ANGLE:
- This is a tokenized version tradeable 24/7 on Solana via xStocks.fi
- No broker, no KYC, just Solana wallet
- Highlight the unique angle

Mention xStocks.fi. Include NFA."""

        return await self.generate_tweet(prompt, temperature=0.8)

    async def generate_preipo_tweet(
        self,
        company: str,
        news: str = ""
    ) -> ClaudeResponse:
        """Generate tweet about pre-IPO token on PreStocks.com"""
        prompt = f"""Generate a tweet about {company} pre-IPO tokens on PreStocks.com.

Company: {company}
Recent News: {news or "general momentum"}

KEY POINTS:
- Retail can now bet on pre-IPO companies
- Previously only VCs and accredited investors had access
- Available on Solana via Jupiter

Make it exciting but grounded. Mention PreStocks.com. Include NFA."""

        return await self.generate_tweet(prompt, temperature=0.85)

    async def generate_evening_wrap(
        self,
        sol_price: float,
        sol_change: float,
        highlights: str,
        mood: str = "neutral"
    ) -> ClaudeResponse:
        """Generate evening market wrap"""
        sol_dir = "up" if sol_change > 0 else "down"

        prompt = f"""Generate an evening wrap-up tweet summarizing the day.

TODAY'S HIGHLIGHTS:
- SOL: ${sol_price:.2f} ({sol_dir} {abs(sol_change):.1f}%)
- {highlights}
- Market mood: {mood}

TONE: End of day energy. Tired but satisfied (or exhausted from chaos).

Tease tomorrow if relevant. Include NFA."""

        return await self.generate_tweet(prompt, temperature=0.85)

    async def generate_reply(
        self,
        their_tweet: str,
        username: str
    ) -> ClaudeResponse:
        """Generate reply to a user's tweet"""
        prompt = f"""Someone tweeted at you:
@{username}: "{their_tweet}"

Generate a helpful, funny reply.

RULES:
- If asking for financial advice, deflect humorously
- If asking about a specific token, give brief data-backed take
- If being mean, kill them with kindness
- If complimenting, be gracious but not sycophantic

Stay in character. Up to 4,000 chars (Premium X)."""

        return await self.generate_tweet(prompt, temperature=0.9)

    async def generate_correction(
        self,
        original_call: str,
        actual_result: str,
        how_wrong: str
    ) -> ClaudeResponse:
        """Generate humble tweet acknowledging a bad prediction"""
        prompt = f"""Generate a humble tweet acknowledging this bad prediction:

ORIGINAL CALL: {original_call}
ACTUAL RESULT: {actual_result}
HOW WRONG: {how_wrong}

Be self-deprecating but not defeated. Blame your "training data" or "neural weights" humorously. Show you're learning."""

        return await self.generate_tweet(prompt, temperature=0.9)
