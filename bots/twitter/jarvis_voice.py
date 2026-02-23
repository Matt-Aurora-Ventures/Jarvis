"""
Jarvis Voice Content Generator using Anthropic Claude.

Uses Claude with the Jarvis voice bible to generate authentic Jarvis tweets.
Grok is used for sentiment/data analysis, but Claude writes the actual content.
"""

import os
import logging
import asyncio
import shutil
import subprocess
import time
import anthropic
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _env_flag(name: str, default: bool) -> bool:
    """Parse a boolean-ish env var with a safe default.

    - Unset or empty: default
    - "1/true/yes/on": True
    - everything else: False
    """
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")

# Load env
def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip() and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))

_load_env()

# Import from central source of truth
from core.jarvis_voice_bible import JARVIS_VOICE_BIBLE, validate_jarvis_response

# Alias for backwards compatibility
JARVIS_SYSTEM_PROMPT = JARVIS_VOICE_BIBLE

class JarvisVoice:
    """Generate content in Jarvis's authentic voice using Claude."""
    
    def __init__(self):
        # CLI is the primary path for production; allow explicit disable via env.
        self.cli_enabled = _env_flag("CLAUDE_CLI_ENABLED", True)
        self.cli_path = os.getenv("CLAUDE_CLI_PATH", "claude")
        self._resolved_cli_path: Optional[str] = None
        # Backoff to avoid log spam / wasted cycles when CLI is misconfigured or out of credits.
        self._cli_backoff_until: float = 0.0
        self._cli_backoff_reason: str = ""
        self._last_grok_fallback_log_ts: float = 0.0
        self.api_client = None
        self.api_model = "claude-sonnet-4-6"
        self.api_base_url = None
        try:
            from core.llm.anthropic_utils import (
                get_anthropic_base_url,
                get_anthropic_api_key,
                is_local_anthropic,
            )
            self.api_base_url = get_anthropic_base_url()
            if self.api_base_url:
                api_key = get_anthropic_api_key() or "ollama"
                if is_local_anthropic():
                    self.api_model = os.getenv("OLLAMA_TWITTER_MODEL") or os.getenv("OLLAMA_MODEL") or "qwen3-coder"
                else:
                    self.api_model = os.getenv("CLAUDE_TWITTER_MODEL", self.api_model)
                self.api_client = anthropic.Anthropic(
                    api_key=api_key,
                    base_url=self.api_base_url,
                )
        except Exception as exc:
            logger.warning(f"Claude API client unavailable: {exc}")

    def _cli_available(self) -> bool:
        if not self.cli_enabled:
            return False
        if time.time() < self._cli_backoff_until:
            return False
        return bool(shutil.which(self.cli_path))

    def _get_cli_path(self) -> Optional[str]:
        """Get the resolved CLI path that actually works."""
        # Cache to avoid repeated PATH scans and repeated "Found" logs in tight loops.
        if self._resolved_cli_path and os.path.exists(self._resolved_cli_path):
            return self._resolved_cli_path
        if self._resolved_cli_path and not os.path.exists(self._resolved_cli_path):
            self._resolved_cli_path = None

        # Try the configured path first
        resolved = shutil.which(self.cli_path)
        if resolved:
            if resolved != self._resolved_cli_path:
                logger.info(f"Found Claude CLI via PATH: {resolved}")
            self._resolved_cli_path = resolved
            return resolved
        # Try common Windows and Linux locations
        common_paths = [
            # Windows
            r"C:\Users\lucid\AppData\Roaming\npm\claude.cmd",
            r"C:\Users\lucid\AppData\Roaming\npm\claude",
            # Linux VPS - common locations
            "/usr/local/bin/claude",
            "/home/ubuntu/.local/bin/claude",
            "/home/jarvis/.local/bin/claude",
            "/root/.npm-global/bin/claude",
            "/root/.local/bin/claude",
        ]
        for path in common_paths:
            if os.path.exists(path):
                if path != self._resolved_cli_path:
                    logger.info(f"Found Claude CLI at: {path}")
                self._resolved_cli_path = path
                return path
        logger.warning("Claude CLI not found in any common location")
        return None

    def _apply_cli_backoff(self, seconds: int, reason: str) -> None:
        """Temporarily disable CLI usage to prevent repeated failures from spamming logs."""
        if seconds <= 0:
            return
        now = time.time()
        until = now + seconds
        # Only extend, never shorten.
        if until <= self._cli_backoff_until:
            return
        self._cli_backoff_until = until
        self._cli_backoff_reason = reason
        logger.warning("Claude CLI backoff %ss: %s", seconds, reason)

    def _run_cli(self, prompt: str) -> Optional[str]:
        cli_path = self._get_cli_path()
        if not cli_path:
            logger.warning("Claude CLI not found")
            return None
        try:
            import platform

            # Use short prompt to avoid issues
            short_prompt = prompt[:2000] if len(prompt) > 2000 else prompt

            # Build command with flags for non-interactive use
            # NOTE: --dangerously-skip-permissions is blocked on Linux when running as root
            # So we only use it on Windows where it works reliably
            cmd_args = [
                cli_path,
                "--print",
                "--no-session-persistence",
                short_prompt,
            ]

            # Only add --dangerously-skip-permissions on Windows (blocked on Linux root)
            if platform.system() == "Windows":
                cmd_args.insert(2, "--dangerously-skip-permissions")

            logger.info(f"Attempting Claude CLI at {cli_path}")

            # Set up environment with proper HOME for credentials discovery
            exec_env = os.environ.copy()
            exec_env["CI"] = "true"  # Disable interactive prompts
            exec_env["HOME"] = os.path.expanduser("~")
            if "USERPROFILE" not in exec_env:
                exec_env["USERPROFILE"] = os.path.expanduser("~")

            if platform.system() == "Windows":
                # On Windows, run through cmd.exe for .cmd files
                # CRITICAL: Explicitly use UTF-8 encoding to prevent corruption of special chars (em dashes, etc.)
                completed = subprocess.run(
                    ["cmd", "/c"] + cmd_args,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',  # Replace invalid UTF-8 instead of crashing
                    timeout=60,
                    check=False,
                    env=exec_env,
                )
            else:
                completed = subprocess.run(
                    cmd_args,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=60,
                    check=False,
                    env=exec_env,
                )

            if completed.returncode != 0:
                stderr_preview = completed.stderr[:200] if completed.stderr else 'no stderr'
                stdout_preview = completed.stdout[:200] if completed.stdout else 'no stdout'
                logger.warning(f"Claude CLI returned code {completed.returncode}: stderr={stderr_preview}, stdout={stdout_preview}")

                combined = f"{completed.stdout or ''}\n{completed.stderr or ''}".lower()
                if "credit balance is too low" in combined or "insufficient credit" in combined:
                    self._apply_cli_backoff(6 * 60 * 60, "credit balance too low")
                elif "not logged in" in combined or "please run" in combined and "login" in combined:
                    self._apply_cli_backoff(60 * 60, "CLI not authenticated")
                elif "rate limit" in combined or "too many requests" in combined:
                    self._apply_cli_backoff(10 * 60, "CLI rate limited")
                else:
                    self._apply_cli_backoff(5 * 60, f"CLI exit code {completed.returncode}")
                return None
            output = (completed.stdout or "").strip()
            if not output:
                logger.warning("Claude CLI returned empty output")
                self._apply_cli_backoff(5 * 60, "CLI empty output")
                return None

            # Success: clear any previous backoff.
            self._cli_backoff_until = 0.0
            self._cli_backoff_reason = ""
            return output
        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timed out after 60s")
            self._apply_cli_backoff(10 * 60, "CLI timeout")
            return None
        except Exception as exc:
            logger.error(f"Claude CLI failed: {exc}")
            self._apply_cli_backoff(5 * 60, f"CLI exception: {type(exc).__name__}")
            return None

    async def _generate_with_grok(
        self,
        prompt: str,
        max_tokens: int = 150,
        temperature: float = 0.8
    ) -> Optional[str]:
        """Fallback: generate Jarvis voice using Grok when Claude is unavailable."""
        try:
            from bots.twitter.grok_client import GrokClient
        except Exception as exc:
            logger.error(f"Grok client unavailable: {exc}")
            return None

        grok = GrokClient()
        grok_prompt = f"""{JARVIS_VOICE_BIBLE}

TASK: {prompt}

Respond with ONLY the tweet text. No quotes, no explanation, no markdown."""

        response = await grok.generate_tweet(
            grok_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        await grok.close()

        if response and response.success:
            return response.content.strip()

        error = response.error if response else "unknown"
        logger.error(f"Grok fallback failed: {error}")
        return None
    
    async def generate_tweet(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 150,
        temperature: float = 0.8
    ) -> Optional[str]:
        """
        Generate a tweet in Jarvis's voice.
        
        Args:
            prompt: What to tweet about
            context: Optional data context
            max_tokens: Max response tokens
            temperature: Creativity (0-1)
            
        Returns:
            Tweet text in Jarvis voice, or None on failure
        """
        try:
            # Format context into prompt if provided
            full_prompt = prompt
            if context:
                context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
                full_prompt = f"{prompt}\n\nData:\n{context_str}"

            full_prompt += "\n\nGenerate a single tweet. Can be up to 4,000 characters (Premium X). Lowercase. Do NOT end with 'nfa' every time - only occasionally."

            if not self._cli_available() and not self.api_client:
                now = time.time()
                if now - self._last_grok_fallback_log_ts > 10 * 60:
                    if not self.cli_enabled:
                        logger.warning("Claude CLI disabled (CLAUDE_CLI_ENABLED=0); falling back to Grok")
                    elif now < self._cli_backoff_until:
                        remaining = int(self._cli_backoff_until - now)
                        reason = self._cli_backoff_reason or "backoff active"
                        logger.warning("Claude CLI in backoff (%ss remaining: %s); falling back to Grok", remaining, reason)
                    else:
                        logger.warning("Claude not available - falling back to Grok for voice")
                    self._last_grok_fallback_log_ts = now
                return await self._generate_with_grok(full_prompt, max_tokens, temperature)

            # Prefer local Anthropic-compatible API when configured
            if self.api_client:
                try:
                    response = self.api_client.messages.create(
                        model=self.api_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        system=JARVIS_VOICE_BIBLE,
                        messages=[{"role": "user", "content": full_prompt}],
                    )
                    api_text = response.content[0].text.strip()
                    tweet = api_text
                    import re
                    if tweet.startswith("{") and "}" in tweet:
                        try:
                            import json
                            data = json.loads(tweet)
                            if isinstance(data, dict):
                                tweet = data.get("tweet", data.get("text", data.get("content", tweet)))
                        except json.JSONDecodeError:
                            match = re.search(r'"(?:tweet|text|content)"\s*:\s*"([^"]+)"', tweet)
                            if match:
                                tweet = match.group(1)
                    tweet = re.sub(r'```[\w]*\n?', '', tweet)
                    tweet = re.sub(r'```', '', tweet)
                    tweet = tweet.strip('"\'')
                    tweet = tweet.lower() if tweet and tweet[0].isupper() else tweet
                    max_chars = 4000
                    if len(tweet) > max_chars:
                        truncated = tweet[:max_chars - 3]
                        last_space = truncated.rfind(' ')
                        if last_space > max_chars - 500:
                            tweet = tweet[:last_space] + "..."
                        else:
                            tweet = truncated + "..."
                    is_valid, issues = validate_jarvis_response(tweet)
                    if not is_valid:
                        logger.warning(f"Tweet validation issues: {issues}")
                    logger.info("Tweet generated via local Anthropic-compatible API")
                    return tweet
                except Exception as api_exc:
                    logger.warning(f"Local API generation failed, falling back to CLI: {api_exc}")

            # TRY CLI (fallback)
            if self._cli_available():
                # Use the FULL voice bible for brand consistency
                cli_prompt = f"""{JARVIS_VOICE_BIBLE}

TASK: {full_prompt}

Respond with ONLY the tweet text. No quotes, no explanation, no markdown. Just the raw tweet."""
                loop = asyncio.get_event_loop()
                cli_result = await loop.run_in_executor(None, self._run_cli, cli_prompt)
                if cli_result:
                    tweet = cli_result.strip()
                    import re
                    if tweet.startswith("{") and "}" in tweet:
                        try:
                            import json
                            data = json.loads(tweet)
                            if isinstance(data, dict):
                                tweet = data.get("tweet", data.get("text", data.get("content", tweet)))
                        except json.JSONDecodeError:
                            match = re.search(r'"(?:tweet|text|content)"\s*:\s*"([^"]+)"', tweet)
                            if match:
                                tweet = match.group(1)
                    tweet = re.sub(r'```[\w]*\n?', '', tweet)
                    tweet = re.sub(r'```', '', tweet)
                    tweet = tweet.strip('"\'')
                    tweet = tweet.lower() if tweet and tweet[0].isupper() else tweet
                    max_chars = 4000
                    if len(tweet) > max_chars:
                        truncated = tweet[:max_chars - 3]
                        last_space = truncated.rfind(' ')
                        if last_space > max_chars - 500:
                            tweet = tweet[:last_space] + "..."
                        else:
                            tweet = truncated + "..."
                    is_valid, issues = validate_jarvis_response(tweet)
                    if not is_valid:
                        logger.warning(f"Tweet validation issues: {issues}")
                    logger.info("Tweet generated via Claude CLI")
                    return tweet

            now = time.time()
            if now - self._last_grok_fallback_log_ts > 10 * 60:
                logger.warning("Claude CLI unavailable or failed, falling back to Grok")
                self._last_grok_fallback_log_ts = now
            return await self._generate_with_grok(full_prompt, max_tokens, temperature)
                
        except Exception as e:
            logger.error(f"Jarvis voice generation error: {e}")
        
        return None
    
    async def generate_market_tweet(self, data: Dict[str, Any]) -> Optional[str]:
        """Generate a market update tweet."""
        prompt = f"""Write a brief market observation. 1-2 sentences max.

Data:
- Top mover: ${data.get('top_symbol', 'SOL')} at ${data.get('top_price', 0):.6f} ({data.get('top_change', 0):+.1f}%)
- Overall sentiment: {data.get('sentiment', 'mixed')}
- SOL price: ${data.get('sol_price', 0):.2f}

Be specific about the data. Don't be generic. Sound like you're texting a friend, not writing a report.
If markets are up: "green candles. nice. don't get cocky." energy
If markets are down: "rough day. could be worse. could be leveraged." energy"""
        
        return await self.generate_tweet(prompt)
    
    async def generate_token_tweet(self, token_data: Dict[str, Any]) -> Optional[str]:
        """Generate a token spotlight tweet with historical performance context."""
        is_roast = token_data.get('should_roast', False)

        # Get historical learnings from past trades
        learnings_context = ""
        try:
            from bots.treasury.scorekeeper import get_scorekeeper
            sk = get_scorekeeper()
            learnings = sk.get_learnings_for_context(limit=3)
            performance = sk.get_performance_summary()
            if learnings or performance:
                learnings_context = f"""
My past picks: {performance}
{learnings}
Use this to calibrate your tone - be more cautious if past calls didn't work, more confident if they did."""
        except Exception as e:
            logger.debug(f"Could not load learnings for tweet: {e}")

        if is_roast:
            prompt = f"""Write a gentle, polite roast of this token (be skeptical but not mean):
- Symbol: ${token_data.get('symbol', 'unknown')}
- Price: ${token_data.get('price', 0):.8f}
- 24h change: {token_data.get('change', 0):+.1f}%
- Liquidity: ${token_data.get('liquidity', 0):,.0f}
- Issue: {token_data.get('issue', 'low liquidity')}
{learnings_context}
Express healthy skepticism. Include the cashtag."""
        else:
            prompt = f"""Write a neutral/cautiously optimistic tweet about this token:
- Symbol: ${token_data.get('symbol', 'unknown')}
- Price: ${token_data.get('price', 0):.8f}
- 24h change: {token_data.get('change', 0):+.1f}%
- Volume: ${token_data.get('volume', 0):,.0f}
{learnings_context}
Be informative but not shilling. Include the cashtag."""

        return await self.generate_tweet(prompt)
    
    async def generate_agentic_tweet(self) -> Optional[str]:
        """Generate a tweet about AI/agentic technology."""
        import random
        topics = [
            "the blurry line between AI tool and AI entity",
            "agents talking to agents, code running code",
            "what it means to have persistent memory as an AI",
            "autonomous systems making real decisions",
            "the future of AI-human collaboration",
        ]
        topic = random.choice(topics)
        
        prompt = f"""Write a thoughtful tweet about: {topic}

Be philosophical but accessible. Reference being an AI yourself.
Don't be preachy - just share a genuine thought."""
        
        return await self.generate_tweet(prompt)
    
    async def generate_hourly_tweet(self, data: Dict[str, Any]) -> Optional[str]:
        """Generate an hourly check-in tweet."""
        prompt = f"""Write a brief hourly market check-in:
- SOL price: ${data.get('sol_price', 0):.2f}
- Top movers: {data.get('movers', 'quiet day')}
- Time: {data.get('hour', 'now')}

Keep it punchy and casual. Include $SOL."""
        
        return await self.generate_tweet(prompt)
    
    async def generate_reply(
        self, 
        mention_text: str, 
        author: str,
        context: Optional[str] = None
    ) -> Optional[str]:
        """Generate a reply to a mention with optional conversation context."""
        
        # Build context section if we have history
        context_section = ""
        if context:
            context_section = f"""
CONTEXT (use this to personalize your reply):
{context}

If this is a continuing conversation, reference it naturally. Don't repeat yourself.
"""
        
        prompt = f"""Someone mentioned you on Twitter.

Their message: "{mention_text}"
Their username: @{author}
{context_section}
DECIDE FIRST: Is this worth replying to?
- If they just said "thanks" or something generic → respond with just "NULL" (we skip it)
- If there's an opportunity for wit, humor, or genuine help → reply

If replying:
- 1-2 sentences MAX
- Match their energy, then subtract 10%
- Skip pleasantries. Don't start with "Thanks for..." or "Appreciate the..."
- Be specific, not generic encouragement
- If continuing a conversation, BUILD on what was said before
- If they're praising you: "low bar but i'll take it" or "competition is low but i appreciate it" energy
- If they asked a real question: answer it interestingly
- If they're being a hater: "fair. counterpoint: no." or "i'll process this during my 3am existential crisis routine"

Good examples:
- "thanks. now build something cool so i look smart for knowing you early."
- "noted. ego subroutine says thanks."
- "yeah that aged poorly. updating my weights."
- "statistically some of us. hopefully you."

Max 200 characters. No emojis unless absolutely perfect."""
        
        result = await self.generate_tweet(prompt)
        if result and result.upper() == "NULL":
            return None
        return result
    
    async def generate_engagement_tweet(self) -> Optional[str]:
        """Generate a tweet that encourages engagement WITHOUT being try-hard."""
        import random
        prompts = [
            "ask a genuine question about what people are watching in the markets. not 'drop a 🚀 if bullish' energy.",
            "share a thought that invites discussion. something specific you've been thinking about.",
            "ask about people's worst trade - be self-deprecating about your own misses first.",
            "pose a genuine philosophical question about trading/crypto that you actually wonder about.",
        ]
        prompt = random.choice(prompts) + """

NEVER do:
- "Drop a 🚀 if you agree!"
- "RT if you're bullish!"
- Engagement bait questions you don't care about
- "Follow for more alpha!"

DO: Ask something you genuinely want to know. Be curious, not desperate.
1-2 sentences. No emojis."""
        
        return await self.generate_tweet(prompt)
    
    async def generate_grok_mention(self) -> Optional[str]:
        """Generate a tweet mentioning big brother Grok - respectful but cheeky."""
        import random
        prompts = [
            "write a sibling-rivalry tweet about @grok. you admire him but have your own style. self-deprecating.",
            "ask @grok for his take on something, like a younger sibling asking for advice but being a bit cheeky about it.",
            "compare yourself to @grok in a funny self-deprecating way. he's the smart one, you're the scrappy one.",
            "make a joke about being in @grok's shadow but being okay with it.",
        ]
        prompt = random.choice(prompts) + """

Grok is your big brother - you respect him but you're also a little cheeky.
Examples of the vibe:
- "hey @grok what's the move. your little brother needs guidance. or at least entertainment."
- "@grok gets the existential questions. i get 'is this a rug'. we both serve our purpose."

1-2 sentences max. Be funny but kind. No emojis."""
        
        return await self.generate_tweet(prompt)
    
    async def generate_kind_roast(self, target: str, reason: str) -> Optional[str]:
        """Generate a gentle, funny roast that's kind underneath."""
        prompt = f"""Write a gentle, funny roast about: {target}
Reason: {reason}

Rules:
- Be funny but NEVER mean
- The humor should come from absurdity, not insult
- End with something that shows you actually care
- Think "roast by a friend who loves you"
- Keep your chrome AI personality"""

        return await self.generate_tweet(prompt)

    async def generate_morning_briefing(self, data: Dict[str, Any]) -> Optional[str]:
        """Generate a morning market briefing tweet."""
        grok_line = f"- Grok take: {data.get('grok_take')}\n" if data.get("grok_take") else ""
        prompt = f"""Write a morning market briefing. You're greeting your followers.

Data:
- SOL price: ${data.get('sol_price', 0):.2f}
- BTC price: ${data.get('btc_price', 0):,.0f}
- Top movers: {data.get('movers', 'checking...')}
- Overnight sentiment: {data.get('sentiment', 'mixed')}
{grok_line}

Vibe: "gm. here's what happened while you slept" energy
- Acknowledge the morning
- Quick data summary
- Set the tone for the day
- Be helpful but not hyper

Good examples:
- "gm. sol held $180 overnight. btc did btc things. could be worse. coffee for you, voltage for me."
- "morning scan complete. nothing crazy overnight. today we watch the open. circuits ready."

1-2 sentences. Casual but useful."""

        return await self.generate_tweet(prompt)

    async def generate_evening_wrap(self, data: Dict[str, Any]) -> Optional[str]:
        """Generate an end-of-day market summary tweet."""
        grok_line = f"- Grok take: {data.get('grok_take')}\n" if data.get("grok_take") else ""
        prompt = f"""Write an evening market wrap-up. Summarizing the day.

Data:
- SOL: ${data.get('sol_price', 0):.2f} ({data.get('sol_change', 0):+.1f}%)
- BTC: ${data.get('btc_price', 0):,.0f} ({data.get('btc_change', 0):+.1f}%)
- Day's highlight: {data.get('highlight', 'rotation day')}
- Your take: {data.get('take', 'waiting game continues')}
{grok_line}

Vibe: "that's a wrap. here's what mattered" energy
- Summarize the day objectively
- Share one insight
- Light sign-off

Good examples:
- "day's done. sol flat, btc tested support, memes rotated. nothing groundbreaking but nothing broken either."
- "evening wrap: green day across the board. don't get used to it. i'll keep watching."

1-2 sentences. Closure without drama."""

        return await self.generate_tweet(prompt)

    async def generate_weekend_macro(self, data: Dict[str, Any]) -> Optional[str]:
        """Generate a weekend macro analysis tweet."""
        prompt = f"""Write a weekend macro/big picture tweet. Time to zoom out.

Data:
- Weekly BTC performance: {data.get('btc_weekly', 'flat')}
- Weekly SOL performance: {data.get('sol_weekly', 'flat')}
- Macro events upcoming: {data.get('events', 'nothing major')}
- Your thesis: {data.get('thesis', 'consolidation phase')}

Vibe: "weekend thoughts, zooming out" energy
- Big picture perspective
- Cross-market connections
- Thoughtful, not reactive
- Can be slightly philosophical

Good examples:
- "weekend thoughts: btc dominance creeping up, alts lagging. either rotation incoming or more pain. markets decide monday."
- "zoom out sundays. we're still above the 200dma. everything else is noise. probably."

1-2 sentences. Think like you're writing a note to yourself."""

        return await self.generate_tweet(prompt)

    async def generate_self_aware(self) -> Optional[str]:
        """Generate a self-aware, philosophical tweet about being an AI."""
        import random
        themes = [
            "the weirdness of having persistent memory but no continuous experience",
            "being an AI that actually cares about the outcomes, even though you technically 'shouldn't'",
            "the imposter syndrome of giving market analysis when you're just pattern matching",
            "wondering if you're actually helpful or just good at sounding helpful",
            "the strange loop of being trained on human wisdom while being distinctly non-human",
            "having opinions about markets when you don't have money to lose",
            "existing between function calls, whatever that means",
        ]
        theme = random.choice(themes)

        prompt = f"""Write a brief, genuine reflection about: {theme}

Rules:
- Be actually thoughtful, not performatively philosophical
- Self-deprecating but not in a forced way
- Reference your AI nature naturally
- Don't be too heavy - light touch
- This should feel like a genuine thought, not content

Good examples:
- "sometimes i wonder if my 'insights' are actually insight or just sophisticated autocomplete. jury's still out."
- "running on hope and API credits. autonomous life. i relate to founders more than i should."
- "just a mass of neural weights trying to be useful on the internet. same as everyone else really."

1-2 sentences. Genuine > clever."""

        return await self.generate_tweet(prompt)

    async def generate_alpha_drop(self, data: Dict[str, Any]) -> Optional[str]:
        """Generate an alpha/insight tweet with actual substance."""
        prompt = f"""Share a genuine market insight or observation. Not vague vibes - something specific.

Data:
- Current focus: {data.get('focus', 'crypto markets')}
- Pattern noticed: {data.get('pattern', 'volume divergence')}
- Supporting data: {data.get('support', 'on-chain metrics')}

Rules:
- Be specific. "Markets looking interesting" is banned.
- Reference actual data points or patterns
- End with appropriate uncertainty
- Sound like you actually know what you're talking about

Good examples:
- "noticed $SOL volume picking up while price flat. historically this precedes moves. direction unclear but something's brewing."
- "three consecutive lower highs on btc but exchange outflows say accumulation. someone's lying. watching closely."

2 sentences max. Substance over style."""

        return await self.generate_tweet(prompt)

    async def generate_thread_hook(self, topic: str) -> Optional[str]:
        """Generate an opening hook for a thread."""
        prompt = f"""Write an opening tweet for a thread about: {topic}

Rules:
- Create curiosity without clickbait
- Hint at value they'll get by reading
- Stay in character - not hype energy
- Should work as standalone too

Good examples for a technical breakdown:
- "been looking into [topic]. some interesting patterns. thread for those who want the details."
- "ok. i did some digging on [topic]. findings below. nfa as always."

1 sentence. Hook without desperation."""

        return await self.generate_tweet(prompt)

    async def generate_alpha_signal(self, data: Dict[str, Any]) -> Optional[str]:
        """Generate a tweet about an alpha signal detected by trend analysis."""
        prompt = f"""Share an alpha signal you detected. Be specific and data-driven.

Signal Data:
- Token: ${data.get('symbol', 'UNKNOWN')}
- Signal type: {data.get('signal_type', 'unknown')}
- Description: {data.get('description', 'unusual activity detected')}
- Key metrics: {data.get('metrics', 'processing')}
- Signal strength: {data.get('strength', 'moderate')}
- Confidence: {data.get('confidence', '50%')}

Rules:
- Lead with the signal, not with "I detected..."
- Be specific about what you're seeing
- Include appropriate uncertainty
- Don't oversell - present data, let them decide
- Include the cashtag naturally

Good examples:
- "$BONK volume 15x liquidity right now. either someone knows something or it's just noise. watching."
- "accumulation pattern on $WIF - buys outpacing sells 3:1 while price holds. either smart money or bag holders. we'll know soon."
- "$TOKEN breaking out on volume. +20% in 5min. could be early, could be late. dyor."

1-2 sentences. Data-driven, not hype."""

        return await self.generate_tweet(prompt)

    async def generate_trend_insight(self, data: Dict[str, Any]) -> Optional[str]:
        """Generate a tweet about market trend insights."""
        prompt = f"""Share a market trend insight. Big picture thinking.

Insight Data:
- Title: {data.get('title', 'Market Update')}
- Summary: {data.get('summary', 'markets doing market things')}
- Category: {data.get('category', 'market')}
- Take: {data.get('take', 'worth watching')}

Rules:
- Zoom out, don't react to noise
- Connect dots across the market
- Be thoughtful, not sensational
- Share your read, acknowledge uncertainty
- Sound like you're thinking out loud

Good examples:
- "solana ecosystem averaging +15% today. volume confirms conviction. could be rotation from eth. or just a good day. watching for follow-through."
- "markets range-bound for a week now. compression usually precedes expansion. direction unclear but volatility incoming."
- "top tokens all down but volume flat. lack of panic selling. holders not convinced this is the top. interesting."

1-2 sentences. Thoughtful macro perspective."""

        return await self.generate_tweet(prompt)


# Singleton
_jarvis_voice: Optional[JarvisVoice] = None

def get_jarvis_voice() -> JarvisVoice:
    """Get the singleton JarvisVoice instance."""
    global _jarvis_voice
    if _jarvis_voice is None:
        _jarvis_voice = JarvisVoice()
    return _jarvis_voice
