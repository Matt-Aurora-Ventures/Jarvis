"""
Grok API Client - xAI Grok integration.

Provides:
- Chat completions
- Streaming responses
- Cost tracking
- Image generation (via compatible endpoint)

Usage:
    from core.api.clients.grok import GrokClient

    client = GrokClient(api_key="your-key")
    response = await client.chat([{"role": "user", "content": "Hello!"}])
    print(response.content)
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from core.api.base import BaseAPIClient, APIResponse, RetryPolicy

logger = logging.getLogger(__name__)


@dataclass
class GrokResponse:
    """
    Response from Grok API.

    Attributes:
        success: Whether the request succeeded
        content: Generated text content
        error: Error message if failed
        usage: Token usage statistics
        model: Model used for generation
    """
    success: bool
    content: str = ""
    error: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None

    @property
    def input_tokens(self) -> int:
        """Get input token count."""
        if self.usage:
            return self.usage.get("prompt_tokens", 0)
        return 0

    @property
    def output_tokens(self) -> int:
        """Get output token count."""
        if self.usage:
            return self.usage.get("completion_tokens", 0)
        return 0


class GrokClient(BaseAPIClient):
    """
    xAI Grok API client.

    Provides chat completions and streaming capabilities with integrated
    cost tracking and usage statistics.
    """

    BASE_URL = "https://api.x.ai/v1"
    DEFAULT_MODEL = "grok-3"

    # Cost per 1K tokens (xAI Grok pricing)
    COST_PER_1K_INPUT = 0.005   # $0.005 per 1K input tokens
    COST_PER_1K_OUTPUT = 0.015  # $0.015 per 1K output tokens

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
        retry_policy: Optional[RetryPolicy] = None,
        state_file: Optional[Path] = None,
    ):
        """
        Initialize the Grok client.

        Args:
            api_key: xAI API key (defaults to XAI_API_KEY env var)
            model: Model to use (defaults to grok-3)
            timeout: Request timeout in seconds
            retry_policy: Custom retry policy
            state_file: Path for persisting usage state
        """
        super().__init__(
            timeout=timeout,
            retry_policy=retry_policy,
            headers={"Authorization": f"Bearer {api_key or os.getenv('XAI_API_KEY', '')}"},
        )
        self._api_key = api_key or os.getenv("XAI_API_KEY", "")
        self._model = model or self.DEFAULT_MODEL

        # State file for persistence
        self._state_file = state_file

        # Usage tracking
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._daily_cost = 0.0
        self._all_time_cost = 0.0
        self._last_reset_date: Optional[str] = None

        self._load_state()

    @property
    def provider(self) -> str:
        """Return provider name."""
        return "grok"

    @property
    def base_url(self) -> str:
        """Return base URL for API requests."""
        return self.BASE_URL

    @property
    def model(self) -> str:
        """Get the current model."""
        return self._model

    def _load_state(self) -> None:
        """Load persisted state from file."""
        if not self._state_file:
            return

        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._total_input_tokens = data.get("total_input_tokens", 0)
                self._total_output_tokens = data.get("total_output_tokens", 0)
                self._all_time_cost = data.get("all_time_cost", 0.0)
                self._daily_cost = data.get("daily_cost", 0.0)
                self._last_reset_date = data.get("last_reset_date")

                # Reset daily stats if new day
                today = datetime.now().strftime("%Y-%m-%d")
                if self._last_reset_date != today:
                    self._daily_cost = 0.0
                    self._last_reset_date = today
        except Exception as e:
            logger.warning(f"Could not load Grok state: {e}")

    def _save_state(self) -> None:
        """Persist state to file."""
        if not self._state_file:
            return

        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps({
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "daily_cost": self._daily_cost,
                "all_time_cost": self._all_time_cost,
                "last_reset_date": self._last_reset_date or datetime.now().strftime("%Y-%m-%d"),
            }, indent=2))
        except Exception as e:
            logger.warning(f"Could not save Grok state: {e}")

    def _track_usage(self, usage: Optional[Dict[str, int]]) -> None:
        """Track API usage and calculate costs."""
        if not usage:
            return

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens

        cost = self._calculate_cost(usage)
        self._daily_cost += cost
        self._all_time_cost += cost

        self._save_state()

        if cost > 0:
            logger.debug(f"Grok API cost: ${cost:.4f} (daily: ${self._daily_cost:.2f})")

    def _calculate_cost(self, usage: Optional[Dict[str, int]]) -> float:
        """Calculate cost from usage data."""
        if not usage:
            return 0.0
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        return (
            input_tokens / 1000 * self.COST_PER_1K_INPUT +
            output_tokens / 1000 * self.COST_PER_1K_OUTPUT
        )

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "daily_cost_usd": round(self._daily_cost, 4),
            "all_time_cost_usd": round(self._all_time_cost, 4),
        }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> GrokResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (overrides default)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            **kwargs: Additional parameters to pass to API

        Returns:
            GrokResponse with generated content or error
        """
        if not self._api_key:
            return GrokResponse(success=False, error="XAI API key not configured")

        payload = {
            "model": model or self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }

        try:
            response = await self.request("POST", "chat/completions", data=payload)

            if not response.success:
                error_msg = "API request failed"
                if isinstance(response.data, dict):
                    error_msg = response.data.get("error", {}).get("message", error_msg)
                return GrokResponse(
                    success=False,
                    error=f"API error: {response.status_code} - {error_msg}",
                )

            data = response.data
            content = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage")

            self._track_usage(usage)

            return GrokResponse(
                success=True,
                content=content,
                usage=usage,
                model=data.get("model"),
            )

        except Exception as e:
            logger.error(f"Grok chat error: {e}")
            return GrokResponse(success=False, error=str(e))

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Send a streaming chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (overrides default)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            **kwargs: Additional parameters to pass to API

        Yields:
            Streaming response chunks
        """
        if not self._api_key:
            yield {"error": "XAI API key not configured"}
            return

        payload = {
            "model": model or self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            **kwargs,
        }

        try:
            async for chunk in self._stream_request("POST", "chat/completions", data=payload):
                yield chunk
        except Exception as e:
            logger.error(f"Grok stream error: {e}")
            yield {"error": str(e)}

    async def health_check(self) -> bool:
        """Check if Grok API is reachable."""
        try:
            # Use a minimal request to check connectivity
            response = await self.request("GET", "models")
            return response.success
        except Exception as e:
            logger.warning(f"Grok health check failed: {e}")
            return False
