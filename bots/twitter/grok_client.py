"""
Grok AI Client for Twitter Bot
Handles content generation and image creation via xAI API
"""

import os
import logging
import aiohttp
import base64
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

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

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("XAI_API_KEY", "")
        self._session: Optional[aiohttp.ClientSession] = None
        self._daily_image_count = 0
        self._last_image_date: Optional[str] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._session

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
            session = await self._get_session()

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
                        "content": "You are JARVIS, a chrome humanoid AI assistant. Generate concise, engaging tweets in lowercase with casual energy. Never exceed 280 characters."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            async with session.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Grok API error: {resp.status} - {error_text}")
                    return GrokResponse(success=False, error=f"API error: {resp.status}")

                data = await resp.json()
                content = data["choices"][0]["message"]["content"].strip()

                # Ensure content fits tweet
                if len(content) > 280:
                    content = content[:277] + "..."

                # Clean up any quotes if Grok wrapped the response
                content = content.strip('"\'')

                return GrokResponse(
                    success=True,
                    content=content,
                    usage=data.get("usage")
                )

        except Exception as e:
            logger.error(f"Grok generation error: {e}")
            return GrokResponse(success=False, error=str(e))

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
            session = await self._get_session()

            # Enhance prompt with style instructions
            enhanced_prompt = self._enhance_image_prompt(prompt, style)

            payload = {
                "model": self.IMAGE_MODEL,
                "prompt": enhanced_prompt,
                "n": 1,
                "response_format": "b64_json"
            }

            async with session.post(
                f"{self.BASE_URL}/images/generations",
                json=payload
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Grok image API error: {resp.status} - {error_text}")
                    return ImageResponse(success=False, error=f"API error: {resp.status}")

                data = await resp.json()

                if "data" in data and len(data["data"]) > 0:
                    b64_data = data["data"][0].get("b64_json")
                    if b64_data:
                        image_bytes = base64.b64decode(b64_data)
                        self._daily_image_count += 1
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

            "token": """Analyze this Solana token data and give your quick take (1-2 sentences, lowercase, casual):
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
- Each tweet must be under 280 characters
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
            if tweet and len(tweet) <= 280:
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
