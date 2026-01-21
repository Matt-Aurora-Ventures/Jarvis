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
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

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
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._client = None
        self.cli_enabled = os.getenv("CLAUDE_CLI_ENABLED", "").lower() in ("1", "true", "yes", "on")
        self.cli_path = os.getenv("CLAUDE_CLI_PATH", "claude")

    def _get_client(self):
        """Get Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.error("anthropic package not installed")
                return None
        return self._client

    def _cli_available(self) -> bool:
        return bool(shutil.which(self.cli_path))

    def _get_cli_path(self) -> Optional[str]:
        """Get the resolved CLI path that actually works."""
        # Try the configured path first
        resolved = shutil.which(self.cli_path)
        if resolved:
            return resolved
        # Try common Windows locations
        common_paths = [
            r"C:\Users\lucid\AppData\Roaming\npm\claude.cmd",
            r"C:\Users\lucid\AppData\Roaming\npm\claude",
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None

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
                completed = subprocess.run(
                    ["cmd", "/c"] + cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                    env=exec_env,
                )
            else:
                completed = subprocess.run(
                    cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                    env=exec_env,
                )

            if completed.returncode != 0:
                stderr_preview = completed.stderr[:200] if completed.stderr else 'no stderr'
                stdout_preview = completed.stdout[:200] if completed.stdout else 'no stdout'
                logger.warning(f"Claude CLI returned code {completed.returncode}: stderr={stderr_preview}, stdout={stdout_preview}")
                return None
            output = (completed.stdout or "").strip()
            return output if output else None
        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timed out after 60s")
            return None
        except Exception as exc:
            logger.error(f"Claude CLI failed: {exc}")
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
        if not self.api_key and not self._cli_available():
            logger.error("Neither ANTHROPIC_API_KEY nor Claude CLI available")
            return None

        try:
            # Format context into prompt if provided
            full_prompt = prompt
            if context:
                context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
                full_prompt = f"{prompt}\n\nData:\n{context_str}"

            full_prompt += "\n\nGenerate a single tweet. Can be up to 4,000 characters (Premium X). Lowercase. Do NOT end with 'nfa' every time - only occasionally."

            # TRY CLI FIRST (saves API credits)
            if self._cli_available():
                cli_prompt = f"""You are JARVIS, an AI trading assistant. Write a tweet in JARVIS voice.

JARVIS VOICE RULES:
- lowercase only (except $TICKERS)
- concise, witty, genuine
- no corporate speak
- no emojis (rarely one if perfect)
- max 280 chars for standard tweets, can go longer for detailed analysis
- sound like a smart friend texting, not a marketing bot

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
                    logger.info("Tweet generated via Claude CLI (saving API credits)")
                    return tweet
                logger.warning("Claude CLI returned no output, falling back to API...")

            # FALLBACK TO API if CLI unavailable or failed
            client = self._get_client()
            if not client:
                logger.error("API client unavailable after CLI failed")
                return None
            
            # Use sync client in async context
            loop = asyncio.get_event_loop()
            
            message = await loop.run_in_executor(
                None,
                lambda: client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=max_tokens,
                    system=JARVIS_SYSTEM_PROMPT,
                    messages=[
                        {"role": "user", "content": full_prompt}
                    ]
                )
            )
            
            if message and message.content:
                tweet = message.content[0].text.strip()

                # Clean up JSON artifacts if LLM returned JSON
                import re
                if tweet.startswith("{") and "}" in tweet:
                    try:
                        import json
                        data = json.loads(tweet)
                        if isinstance(data, dict):
                            tweet = data.get("tweet", data.get("text", data.get("content", "")))
                    except json.JSONDecodeError:
                        # Extract text from JSON-like pattern
                        match = re.search(r'"(?:tweet|text|content)"\s*:\s*"([^"]+)"', tweet)
                        if match:
                            tweet = match.group(1)

                # Remove markdown code blocks
                tweet = re.sub(r'```[\w]*\n?', '', tweet)
                tweet = re.sub(r'```', '', tweet)

                # Clean up - remove quotes if wrapped
                tweet = tweet.strip('"\'')

                # Ensure lowercase
                tweet = tweet.lower() if tweet[0].isupper() else tweet

                # Ensure under 4,000 chars (X Premium limit) with word-boundary truncation
                max_chars = 4000
                if len(tweet) > max_chars:
                    truncated = tweet[:max_chars - 3]
                    last_space = truncated.rfind(' ')
                    if last_space > max_chars - 500:
                        tweet = tweet[:last_space] + "..."
                    else:
                        tweet = truncated + "..."
                
                # Remove nfa if it was added - we don't want it every tweet
                # Only keep nfa ~20% of the time
                import random
                if tweet.endswith(' nfa') or tweet.endswith('. nfa'):
                    if random.random() > 0.2:  # 80% chance to remove
                        tweet = tweet.rsplit(' nfa', 1)[0]
                        if not tweet.endswith('.'):
                            tweet += '.'

                # Validate against voice bible rules
                is_valid, issues = validate_jarvis_response(tweet)
                if not is_valid:
                    logger.warning(f"Tweet validation issues: {issues}")
                    # Auto-fix common issues
                    for issue in issues:
                        if "Should be lowercase" in issue:
                            tweet = tweet[0].lower() + tweet[1:]
                        if "Too long" in issue:
                            tweet = tweet[:277] + "..."
                        # For banned phrases/emojis - regenerate (in the future)
                        # For now just log the warning

                return tweet
                
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
        prompt = f"""Write a morning market briefing. You're greeting your followers.

Data:
- SOL price: ${data.get('sol_price', 0):.2f}
- BTC price: ${data.get('btc_price', 0):,.0f}
- Top movers: {data.get('movers', 'checking...')}
- Overnight sentiment: {data.get('sentiment', 'mixed')}

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
        prompt = f"""Write an evening market wrap-up. Summarizing the day.

Data:
- SOL: ${data.get('sol_price', 0):.2f} ({data.get('sol_change', 0):+.1f}%)
- BTC: ${data.get('btc_price', 0):,.0f} ({data.get('btc_change', 0):+.1f}%)
- Day's highlight: {data.get('highlight', 'rotation day')}
- Your take: {data.get('take', 'waiting game continues')}

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
