"""
Grok AI Client for Twitter Bot
Handles content generation and image creation via xAI API
"""

import os
import json
import logging
import aiohttp
import base64
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.utils.circuit_breaker import APICircuitBreaker, CircuitOpenError

# Import structured logging for comprehensive JSON logs
try:
    from core.logging import get_structured_logger
    STRUCTURED_LOGGING_AVAILABLE = True
except ImportError:
    STRUCTURED_LOGGING_AVAILABLE = False

# Initialize structured logger if available, fallback to standard logger
if STRUCTURED_LOGGING_AVAILABLE:
    logger = get_structured_logger("jarvis.grok", service="grok_client")
else:
    logger = logging.getLogger(__name__)


@dataclass
class GrokResponse:
    """Response from Grok API"""
    success: bool
    content: str = ""
    error: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


@dataclass
class ImageResponse:
    """Response from image generation"""
    success: bool
    image_data: Optional[bytes] = None
    url: Optional[str] = None
    error: Optional[str] = None


class GrokClient:
    """
    xAI Grok client for content and image generation
    """

    BASE_URL = "https://api.x.ai/v1"
    CHAT_MODEL = "grok-3"
    IMAGE_MODEL = "grok-2-image"
    # State file - centralized under ~/.lifeos/data/
    from core.state_paths import STATE_PATHS
    STATE_FILE = STATE_PATHS.grok_state

    # Cost per 1K tokens (xAI Grok pricing - update as needed)
    COST_PER_1K_INPUT = 0.005   # $0.005 per 1K input tokens
    COST_PER_1K_OUTPUT = 0.015  # $0.015 per 1K output tokens
    COST_PER_IMAGE = 0.02       # $0.02 per image generation

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("XAI_API_KEY", "")
        self._session: Optional[aiohttp.ClientSession] = None
        self._daily_image_count = 0
        self._last_image_date: Optional[str] = None
        self._circuit_breaker = APICircuitBreaker("grok_api")

        # Cost tracking
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_images = 0
        self._daily_cost = 0.0
        self._all_time_cost = 0.0

        self._load_state()  # Load persisted state on init

    def _load_state(self):
        """Load persisted state from file"""
        try:
            if self.STATE_FILE.exists():
                data = json.loads(self.STATE_FILE.read_text())
                self._last_image_date = data.get("last_image_date")
                self._daily_image_count = data.get("daily_image_count", 0)

                # Load cost tracking data
                self._total_input_tokens = data.get("total_input_tokens", 0)
                self._total_output_tokens = data.get("total_output_tokens", 0)
                self._total_images = data.get("total_images", 0)
                self._all_time_cost = data.get("all_time_cost", 0.0)
                self._daily_cost = data.get("daily_cost", 0.0)

                # Reset daily stats if it's a new day
                today = datetime.now().strftime("%Y-%m-%d")
                if self._last_image_date != today:
                    self._daily_image_count = 0
                    self._daily_cost = 0.0
                    self._last_image_date = today
        except Exception as e:
            logger.warning(f"Could not load Grok state: {e}")

    def _save_state(self):
        """Persist state to file"""
        try:
            self.STATE_FILE.write_text(json.dumps({
                "last_image_date": self._last_image_date,
                "daily_image_count": self._daily_image_count,
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "total_images": self._total_images,
                "daily_cost": self._daily_cost,
                "all_time_cost": self._all_time_cost
            }, indent=2))
        except Exception as e:
            logger.warning(f"Could not save Grok state: {e}")

    def _track_usage(self, usage: Optional[Dict[str, int]], is_image: bool = False):
        """Track API usage and calculate costs"""
        cost = 0.0

        if is_image:
            self._total_images += 1
            cost = self.COST_PER_IMAGE
        elif usage:
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens
            cost = (input_tokens / 1000 * self.COST_PER_1K_INPUT +
                    output_tokens / 1000 * self.COST_PER_1K_OUTPUT)

        self._daily_cost += cost
        self._all_time_cost += cost
        self._save_state()

        if cost > 0:
            logger.debug(f"Grok API cost: ${cost:.4f} (daily: ${self._daily_cost:.2f})")

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics"""
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_images": self._total_images,
            "daily_cost_usd": round(self._daily_cost, 4),
            "all_time_cost_usd": round(self._all_time_cost, 4),
            "daily_image_count": self._daily_image_count
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=aiohttp.ClientTimeout(total=60)  # 60s timeout
            )
        return self._session

    async def _post_json(self, endpoint: str, payload: Dict[str, Any]) -> tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        session = await self._get_session()

        async def _request():
            async with session.post(f"{self.BASE_URL}/{endpoint}", json=payload) as resp:
                status = resp.status
                if status == 200:
                    return status, await resp.json(), None
                return status, None, await resp.text()

        return await self._circuit_breaker.call(_request)

    async def close(self):
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def generate_tweet(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 150,
        temperature: float = 0.8
    ) -> GrokResponse:
        """
        Generate tweet content using Grok

        Args:
            prompt: The prompt template with placeholders
            context: Data to inject into the prompt
            max_tokens: Maximum tokens in response
            temperature: Creativity level (0-1)

        Returns:
            GrokResponse with generated content
        """
        if not self.api_key:
            return GrokResponse(success=False, error="XAI API key not configured")

        try:
            # Format prompt with context
            if context:
                for key, value in context.items():
                    placeholder = f"{{{key}}}"
                    if placeholder in prompt:
                        prompt = prompt.replace(placeholder, str(value))

            payload = {
                "model": self.CHAT_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are JARVIS, a chrome humanoid AI assistant. Generate concise, engaging tweets in lowercase with casual energy. Can be up to 4,000 characters (Premium X)."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            try:
                status, data, error_text = await self._post_json("chat/completions", payload)
            except CircuitOpenError as exc:
                return GrokResponse(success=False, error=str(exc))

            if status != 200:
                logger.error(f"Grok API error: {status} - {error_text}")
                return GrokResponse(success=False, error=f"API error: {status}")

            content = data["choices"][0]["message"]["content"].strip()

            # Ensure content fits tweet (X Premium: 4,000 character limit) with word-boundary truncation
            max_chars = 4000
            if len(content) > max_chars:
                truncated = content[:max_chars - 3]
                last_space = truncated.rfind(' ')
                if last_space > max_chars - 500:
                    content = content[:last_space] + "..."
                else:
                    content = truncated + "..."

            # Clean up any quotes if Grok wrapped the response
            content = content.strip('"\'')

            # Track usage and costs
            usage_data = data.get("usage")
            self._track_usage(usage_data)

            # Structured log event for Grok API call
            if STRUCTURED_LOGGING_AVAILABLE and hasattr(logger, 'log_event'):
                logger.log_event(
                    "GROK_API_CALL",
                    endpoint="chat/completions",
                    model=self.CHAT_MODEL,
                    prompt_length=len(prompt),
                    response_length=len(content),
                    input_tokens=usage_data.get("prompt_tokens", 0) if usage_data else 0,
                    output_tokens=usage_data.get("completion_tokens", 0) if usage_data else 0,
                    temperature=temperature,
                    cost_usd=self._calculate_cost(usage_data),
                    daily_cost_usd=self._daily_cost,
                )

            return GrokResponse(
                success=True,
                content=content,
                usage=usage_data
            )

        except Exception as e:
            logger.error(f"Grok generation error: {e}")
            return GrokResponse(success=False, error=str(e))

    def _calculate_cost(self, usage: Optional[Dict[str, int]]) -> float:
        """Calculate cost from usage data."""
        if not usage:
            return 0.0
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        return (input_tokens / 1000 * self.COST_PER_1K_INPUT +
                output_tokens / 1000 * self.COST_PER_1K_OUTPUT)

    async def generate_image(
        self,
        prompt: str,
        style: str = "market_chart"
    ) -> ImageResponse:
        """
        Generate an image using Grok's image model

        Args:
            prompt: Description of the image to generate
            style: Style preset to apply

        Returns:
            ImageResponse with image data
        """
        if not self.api_key:
            return ImageResponse(success=False, error="XAI API key not configured")

        # Check daily limit (cost management - 4-6 images/day)
        today = datetime.now().strftime("%Y-%m-%d")
        if self._last_image_date != today:
            self._last_image_date = today
            self._daily_image_count = 0

        if self._daily_image_count >= 6:
            logger.warning("Daily image generation limit reached")
            return ImageResponse(
                success=False,
                error="Daily image limit reached (6/day for cost management)"
            )

        try:
            # Enhance prompt with style instructions
            enhanced_prompt = self._enhance_image_prompt(prompt, style)

            payload = {
                "model": self.IMAGE_MODEL,
                "prompt": enhanced_prompt,
                "n": 1,
                "response_format": "b64_json"
            }
            try:
                status, data, error_text = await self._post_json("images/generations", payload)
            except CircuitOpenError as exc:
                return ImageResponse(success=False, error=str(exc))

            if status != 200:
                logger.error(f"Grok image API error: {status} - {error_text}")
                return ImageResponse(success=False, error=f"API error: {status}")

            if "data" in data and len(data["data"]) > 0:
                b64_data = data["data"][0].get("b64_json")
                if b64_data:
                    image_bytes = base64.b64decode(b64_data)
                    self._daily_image_count += 1
                    self._track_usage(None, is_image=True)  # Track image cost
                    logger.info(f"Image generated ({self._daily_image_count}/6 today)")
                    return ImageResponse(
                        success=True,
                        image_data=image_bytes
                    )

            return ImageResponse(success=False, error="No image data in response")

        except Exception as e:
            logger.error(f"Grok image generation error: {e}")
            return ImageResponse(success=False, error=str(e))

    def _enhance_image_prompt(self, prompt: str, style: str) -> str:
        """Add style-specific enhancements to image prompts"""
        style_additions = {
            "market_chart": "Digital art style, dark background with neon accents, crypto aesthetic, professional trading dashboard visualization",
            "bullish": "Energetic green and gold colors, upward momentum, celebration vibes, digital art",
            "bearish": "Cautious red and orange tones, downward trend, warning aesthetic, digital art",
            "solana": "Purple and gradient colors matching Solana branding, crypto aesthetic, futuristic",
            "ai_wisdom": "Futuristic chrome and silver aesthetic, neural network patterns, AI visualization",
            "recap": "Clean infographic style, multiple data points, professional dark theme"
        }

        style_addition = style_additions.get(style, style_additions["market_chart"])
        return f"{prompt}. {style_addition}. High quality, 4K resolution."

    async def analyze_sentiment(
        self,
        data: Dict[str, Any],
        context_type: str = "market"
    ) -> GrokResponse:
        """
        Analyze market/token data and generate sentiment

        Args:
            data: Market or token data to analyze
            context_type: Type of analysis (market, token, macro)

        Returns:
            GrokResponse with sentiment analysis
        """
        prompts = {
            "market": """Analyze this market data and provide a brief sentiment assessment (1-2 sentences, lowercase, casual):
{data}

What's the overall vibe? Bullish, bearish, or neutral? Why?""",

            "token": """Analyze this crypto token data and give your quick take (1-2 sentences, lowercase, casual):
{data}

Is this looking interesting? Any red flags?""",

            "macro": """Review these macro/geopolitical factors and summarize the impact on markets (1-2 sentences, lowercase, casual):
{data}

What should traders be watching?"""
        }

        prompt = prompts.get(context_type, prompts["market"])
        return await self.generate_tweet(
            prompt,
            context={"data": str(data)},
            temperature=0.7
        )

    async def generate_thread(
        self,
        topic: str,
        data: Dict[str, Any],
        max_tweets: int = 5
    ) -> List[str]:
        """
        Generate a Twitter thread on a topic

        Args:
            topic: Main topic of the thread
            data: Supporting data/context
            max_tweets: Maximum tweets in thread

        Returns:
            List of tweet strings for the thread
        """
        prompt = f"""Create a {max_tweets}-tweet thread about: {topic}

Data/context:
{data}

Rules:
- Each tweet can be up to 4,000 characters (Premium X)
- Use lowercase throughout
- Number each tweet (1/, 2/, etc)
- Make it informative but fun
- Include relevant emojis
- Last tweet should be a call to action or summary

Generate the thread (separate each tweet with ---):"""

        response = await self.generate_tweet(
            prompt,
            max_tokens=500,
            temperature=0.8
        )

        if not response.success:
            return []

        # Parse thread tweets
        tweets = []
        parts = response.content.split("---")
        for part in parts[:max_tweets]:
            tweet = part.strip()
            # Allow tweets up to 4,000 characters (X Premium limit)
            if tweet and len(tweet) <= 4000:
                tweets.append(tweet)

        return tweets

    def get_daily_image_count(self) -> int:
        """Get the number of images generated today"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._last_image_date != today:
            return 0
        return self._daily_image_count

    def can_generate_image(self) -> bool:
        """Check if we can generate more images today"""
        return self.get_daily_image_count() < 6


# Singleton
_grok_client: Optional[GrokClient] = None

def get_grok_client() -> GrokClient:
    """Get the singleton Grok client."""
    global _grok_client
    if _grok_client is None:
        _grok_client = GrokClient()
    return _grok_client
