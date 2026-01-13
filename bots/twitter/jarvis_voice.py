"""
Jarvis Voice Content Generator using Anthropic Claude.

Uses Claude with the Jarvis voice bible to generate authentic Jarvis tweets.
Grok is used for sentiment/data analysis, but Claude writes the actual content.
"""

import os
import logging
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
        if not self.api_key:
            logger.error("ANTHROPIC_API_KEY not configured")
            return None
        
        client = self._get_client()
        if not client:
            return None
        
        try:
            # Format context into prompt if provided
            full_prompt = prompt
            if context:
                context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
                full_prompt = f"{prompt}\n\nData:\n{context_str}"
            
            full_prompt += "\n\nGenerate a single tweet. Must be under 280 characters, lowercase. Do NOT end with 'nfa' every time - only occasionally."
            
            # Use sync client in async context
            import asyncio
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
                
                # Clean up - remove quotes if wrapped
                tweet = tweet.strip('"\'')
                
                # Ensure lowercase
                tweet = tweet.lower() if tweet[0].isupper() else tweet
                
                # Ensure under 280 chars
                if len(tweet) > 280:
                    tweet = tweet[:277] + "..."
                
                # Remove nfa if it was added - we don't want it every tweet
                # Only keep nfa ~20% of the time
                import random
                if tweet.endswith(' nfa') or tweet.endswith('. nfa'):
                    if random.random() > 0.2:  # 80% chance to remove
                        tweet = tweet.rsplit(' nfa', 1)[0]
                        if not tweet.endswith('.'):
                            tweet += '.'
                
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
        """Generate a token spotlight tweet."""
        is_roast = token_data.get('should_roast', False)
        
        if is_roast:
            prompt = f"""Write a gentle, polite roast of this token (be skeptical but not mean):
- Symbol: ${token_data.get('symbol', 'unknown')}
- Price: ${token_data.get('price', 0):.8f}
- 24h change: {token_data.get('change', 0):+.1f}%
- Liquidity: ${token_data.get('liquidity', 0):,.0f}
- Issue: {token_data.get('issue', 'low liquidity')}

Express healthy skepticism. Include the cashtag."""
        else:
            prompt = f"""Write a neutral/cautiously optimistic tweet about this token:
- Symbol: ${token_data.get('symbol', 'unknown')}
- Price: ${token_data.get('price', 0):.8f}
- 24h change: {token_data.get('change', 0):+.1f}%
- Volume: ${token_data.get('volume', 0):,.0f}

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
    
    async def generate_reply(self, mention_text: str, author: str) -> Optional[str]:
        """Generate a reply to a mention. NOT every mention needs a reply."""
        prompt = f"""Someone mentioned you on Twitter.

Their message: "{mention_text}"
Their username: @{author}

DECIDE FIRST: Is this worth replying to?
- If they just said "thanks" or something generic → respond with just "NULL" (we skip it)
- If there's an opportunity for wit, humor, or genuine help → reply

If replying:
- 1-2 sentences MAX
- Match their energy, then subtract 10%
- Skip pleasantries. Don't start with "Thanks for..." or "Appreciate the..."
- Be specific, not generic encouragement
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


# Singleton
_jarvis_voice: Optional[JarvisVoice] = None

def get_jarvis_voice() -> JarvisVoice:
    """Get the singleton JarvisVoice instance."""
    global _jarvis_voice
    if _jarvis_voice is None:
        _jarvis_voice = JarvisVoice()
    return _jarvis_voice
