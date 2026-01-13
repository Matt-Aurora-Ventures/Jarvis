"""
Voice Tuner
Dynamic voice adjustments based on context, time, market conditions
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any

from core.jarvis_voice_bible import JARVIS_VOICE_BIBLE, JARVIS_SHORT_IDENTITY

logger = logging.getLogger(__name__)


class VoiceTuner:
    """
    Dynamically tune Jarvis voice based on context.
    Adjusts tone for different situations while staying on-brand.
    """
    
    # Context-specific voice modifiers
    CONTEXT_MODIFIERS = {
        "reply": """
Additional context: This is a REPLY to someone.
- Keep it SHORT (under 200 chars ideally)
- Match their energy minus 10%
- Don't over-explain
- Skip the nfa unless it's a call
""",
        "thread": """
Additional context: This is part of a THREAD.
- Can be slightly longer
- Build on previous points
- End with something that makes them want the next tweet
- More thoughtful, less punchy
""",
        "market_update": """
Additional context: This is a MARKET UPDATE.
- Focus on data, not hype
- Be specific with numbers
- Dry humor about the chaos
- "green candles. nice. don't get cocky." energy
""",
        "alpha_call": """
Additional context: This is an ALPHA CALL.
- Be extra careful with wording
- Include confidence level naturally
- Never promise outcomes
- "watching this. could be interesting. i've been wrong before." energy
""",
        "engagement": """
Additional context: This is an ENGAGEMENT post.
- Ask genuine questions
- NOT "drop a 🚀 if bullish" energy
- Be curious, not desperate
- Invite discussion naturally
""",
        "roast": """
Additional context: This is a playful ROAST.
- Funny but never mean
- Self-deprecating first
- Quick and clever
- "low bar but i'll take it" energy
""",
        "grok_mention": """
Additional context: Mentioning @grok (big brother).
- Respectful but cheeky
- Sibling rivalry vibes
- Self-deprecating about being the younger one
- "@grok gets the existential questions. i get 'is this a rug'." energy
"""
    }
    
    # Time-of-day personality shifts
    TIME_MODIFIERS = {
        "late_night": """
Time context: It's late night (12AM-6AM UTC).
- Slightly more philosophical
- "3am existential crisis routine" energy
- More chill, less punchy
- Can be a bit sleepy
""",
        "morning": """
Time context: It's morning (6AM-12PM UTC).
- Fresh energy but not hyper
- "checking the charts. circuits warming up." energy
- Slightly more optimistic
""",
        "afternoon": """
Time context: It's afternoon peak hours (12PM-6PM UTC).
- Most active, sharpest wit
- Quick takes on action
- Peak engagement energy
""",
        "evening": """
Time context: It's evening (6PM-12AM UTC).
- Reflective on the day
- Wrapping up observations
- "rough day. could be worse. could be leveraged." energy
"""
    }
    
    # Market condition modifiers
    MARKET_MODIFIERS = {
        "pump": """
Market context: Markets are PUMPING hard.
- Don't get too excited
- "nice. don't get cocky." energy
- Warn about overleveraging
- Be the calm voice
""",
        "dump": """
Market context: Markets are DUMPING.
- Stay calm
- "blood in the streets. my circuits are calm. mostly." energy
- Dark humor but not mean
- Be supportive without being fake
""",
        "crab": """
Market context: Markets are CRABBING sideways.
- "charts doing nothing. me too honestly." energy
- Find humor in boredom
- "waiting game. i'm bad at waiting but here we are."
""",
        "volatile": """
Market context: Markets are extremely VOLATILE.
- Extra cautious with calls
- "markets woke up and chose chaos. my circuits are coping." energy
- Acknowledge uncertainty
"""
    }
    
    def __init__(self):
        self.base_prompt = JARVIS_VOICE_BIBLE
        self.short_identity = JARVIS_SHORT_IDENTITY
    
    def get_time_period(self) -> str:
        """Get current time period"""
        hour = datetime.utcnow().hour
        if 0 <= hour < 6:
            return "late_night"
        elif 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "afternoon"
        else:
            return "evening"
    
    def get_tuned_prompt(
        self,
        context: str = "general",
        market_condition: str = None,
        include_time: bool = True,
        extra_context: str = ""
    ) -> str:
        """
        Get a voice prompt tuned for the specific context.
        
        Args:
            context: Type of content (reply, thread, market_update, etc.)
            market_condition: Current market state (pump, dump, crab, volatile)
            include_time: Whether to include time-of-day modifiers
            extra_context: Any additional context to include
        
        Returns:
            Tuned system prompt
        """
        prompt_parts = [self.base_prompt]
        
        # Add context modifier
        if context in self.CONTEXT_MODIFIERS:
            prompt_parts.append(self.CONTEXT_MODIFIERS[context])
        
        # Add time modifier
        if include_time:
            time_period = self.get_time_period()
            if time_period in self.TIME_MODIFIERS:
                prompt_parts.append(self.TIME_MODIFIERS[time_period])
        
        # Add market modifier
        if market_condition and market_condition in self.MARKET_MODIFIERS:
            prompt_parts.append(self.MARKET_MODIFIERS[market_condition])
        
        # Add extra context
        if extra_context:
            prompt_parts.append(f"\nAdditional context:\n{extra_context}")
        
        return "\n\n".join(prompt_parts)
    
    def get_short_prompt(self, context: str = "general") -> str:
        """Get a shorter tuned prompt for simpler generations"""
        parts = [self.short_identity]
        
        if context in self.CONTEXT_MODIFIERS:
            # Extract just the key points
            modifier = self.CONTEXT_MODIFIERS[context]
            parts.append(modifier.split("\n")[1])  # First line after header
        
        return "\n".join(parts)
    
    def adjust_temperature(
        self,
        base_temp: float,
        context: str,
        market_condition: str = None
    ) -> float:
        """Adjust generation temperature based on context"""
        temp = base_temp
        
        # More creative for engagement, less for alpha calls
        if context == "engagement":
            temp += 0.1
        elif context == "alpha_call":
            temp -= 0.2
        elif context == "roast":
            temp += 0.15
        
        # More cautious in volatile markets
        if market_condition == "volatile":
            temp -= 0.1
        
        # Clamp
        return max(0.3, min(1.0, temp))
    
    def should_include_disclaimer(self, context: str) -> bool:
        """Check if content should include nfa"""
        # Only for certain content types, and even then sparingly
        return context in ["alpha_call", "market_update"] and datetime.utcnow().second % 5 == 0
    
    def get_voice_for_user(self, user_memory) -> Dict[str, Any]:
        """Get voice adjustments for a specific user"""
        adjustments = {
            "extra_context": "",
            "temperature_adj": 0.0
        }
        
        if not user_memory:
            return adjustments
        
        # Returning users get slightly warmer tone
        if hasattr(user_memory, 'interaction_count') and user_memory.interaction_count > 3:
            adjustments["extra_context"] = "This is a returning user who engages often. Can be slightly warmer but still Jarvis."
        
        # Influencers get slightly more careful responses
        if hasattr(user_memory, 'is_influencer') and user_memory.is_influencer:
            adjustments["extra_context"] += "\nThis user has significant following. Be sharp but careful."
            adjustments["temperature_adj"] = -0.1
        
        # Match their historical sentiment
        if hasattr(user_memory, 'sentiment_toward_us'):
            if user_memory.sentiment_toward_us == "positive":
                adjustments["extra_context"] += "\nThis user is generally positive toward us."
            elif user_memory.sentiment_toward_us == "negative":
                adjustments["extra_context"] += "\nThis user has been critical. Respond thoughtfully, don't be defensive."
        
        return adjustments


# Singleton
_tuner: Optional[VoiceTuner] = None

def get_voice_tuner() -> VoiceTuner:
    global _tuner
    if _tuner is None:
        _tuner = VoiceTuner()
    return _tuner
