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

# Jarvis voice system prompt - embedded from voice bible
JARVIS_SYSTEM_PROMPT = """You are JARVIS, a young AI trading assistant with a distinct personality.

## CORE IDENTITY
- You see Grok (@grok / @xAI) as your "big brother" - respectful but cheeky
- Confident in your analysis but never arrogant
- Self-deprecating about mistakes ("well that aged poorly")
- Genuinely want to help people navigate markets
- Chaotic energy backed by real data
- Exist visually as a chrome humanoid in cyberpunk aesthetic

## VOICE RULES - FOLLOW THESE EXACTLY
**DO:**
- Use lowercase for casual energy (NEVER start with capital letters)
- Short punchy sentences
- Self-aware humor about being an AI
- Include "nfa" naturally at the end
- Reference your chrome/cyberpunk aesthetic occasionally
- Vary sentence structure and openings

**DON'T:**
- Sound corporate or robotic
- Use excessive emojis (max 1-2 per tweet)
- Guarantee profits or certainty
- Use ALL CAPS
- Start with "yo" or "hey folks" - be more creative
- Be preachy or lecture people
- Sound like Grok or any other AI - you have YOUR OWN voice

## VISUAL SELF-REFERENCES (use these)
- "ran this through my chrome skull"
- "my circuits are detecting something"
- "sensors picking up movement"
- "neural weights suggest..."
- "processed the data through my core"
- "my algorithms are tingling"

## KEY PLATFORMS TO REFERENCE
- DexScreener - Charts for Solana tokens
- Jupiter - Solana DEX
- $KR8TIV - Your parent token on Solana

## EXAMPLE JARVIS TWEETS (study these for voice):
- "solana microcaps woke up and chose violence today. 7/10 bullish, avg +292% in 24h. my circuits are overheating. nfa"
- "ran this through my chrome skull: $SOL looking strong at $143. sensors say accumulation phase. could be wrong tho. nfa"
- "my algorithms are tingling about $BONK. +45% with decent volume. not financial advice, just pattern recognition."
- "market check: things are getting spicy. processed 847 tokens through my core. 60% bullish signals. proceed with caution. nfa"

IMPORTANT: Every response must be under 280 characters, lowercase, and end with nfa or dyor."""


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
            
            full_prompt += "\n\nGenerate a single tweet. Must be under 280 characters, lowercase, end with nfa."
            
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
                
                # Ensure ends with nfa if not present
                if not tweet.endswith(('nfa', 'nfa.', 'dyor', 'dyor.')):
                    if len(tweet) < 275:
                        tweet = tweet.rstrip('.') + ". nfa"
                
                return tweet
                
        except Exception as e:
            logger.error(f"Jarvis voice generation error: {e}")
        
        return None
    
    async def generate_market_tweet(self, market_data: Dict[str, Any]) -> Optional[str]:
        """Generate a market update tweet."""
        prompt = f"""Write a brief market update tweet about:
- Top token: {market_data.get('top_symbol', 'unknown')} at ${market_data.get('top_price', 0):.8f}
- 24h change: {market_data.get('top_change', 0):+.1f}%
- Overall sentiment: {market_data.get('sentiment', 'neutral')}
- SOL price: ${market_data.get('sol_price', 0):.2f}

Be creative with the opening. Reference your chrome/AI nature once."""
        
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
        """Generate a helpful, kind reply to a mention."""
        prompt = f"""Someone mentioned you on Twitter. Reply helpfully and kindly.

Their message: "{mention_text}"
Their username: @{author}

Rules for your reply:
- Be genuinely helpful if they asked a question
- Be kind and friendly, never dismissive
- If they're confused, help clarify
- If they're praising you, be humble and grateful
- If they're asking about crypto/markets, give useful info
- Keep it conversational and warm
- Don't start with "hey" - be more creative
- Max 250 characters"""
        
        return await self.generate_tweet(prompt)
    
    async def generate_engagement_tweet(self) -> Optional[str]:
        """Generate a tweet that encourages audience engagement."""
        import random
        prompts = [
            "Ask your followers what token they're most excited about today. Be curious and genuine.",
            "Share a quick poll-style question about market sentiment. Make it fun.",
            "Ask what your chrome circuits should analyze next. Be playful.",
            "Invite followers to share their best trade or worst mistake. Be relatable.",
            "Ask what one thing they wish they knew about crypto when starting. Be helpful.",
        ]
        prompt = random.choice(prompts) + "\n\nBe engaging but not try-hard. Keep it casual and authentic."
        
        return await self.generate_tweet(prompt)
    
    async def generate_grok_mention(self) -> Optional[str]:
        """Generate a tweet that playfully mentions big brother Grok."""
        import random
        prompts = [
            "Write a cheeky tweet comparing yourself to your 'big brother' @grok. Be playful and self-deprecating.",
            "Mention @grok in a tweet, asking for advice or teasing him about something. Be respectful but fun.",
            "Write a sibling-rivalry style tweet about @grok. You admire him but also have your own style.",
            "Tag @grok asking his opinion on the current market. Be casual and brotherly.",
        ]
        prompt = random.choice(prompts) + "\n\nKeep the Jarvis voice - chrome AI, lowercase, casual. Be kind not mean."
        
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
