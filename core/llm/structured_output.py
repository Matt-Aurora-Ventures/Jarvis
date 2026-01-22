"""Structured LLM outputs using Instructor library."""
from typing import TypeVar, Type, Optional, List, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")

try:
    import instructor
    HAS_INSTRUCTOR = True
except ImportError:
    HAS_INSTRUCTOR = False
    instructor = None

# Always import Pydantic for model definitions
try:
    from pydantic import BaseModel
except ImportError:
    from dataclasses import dataclass as BaseModel


# Pre-defined structured output models
class ExtractedEntity(BaseModel):
    """An extracted entity from text."""
    name: str
    type: str
    confidence: float


class SentimentAnalysis(BaseModel):
    """Sentiment analysis result."""
    sentiment: str  # positive, negative, neutral
    score: float  # -1 to 1
    reasoning: str


class TradingSignal(BaseModel):
    """Structured trading signal from AI analysis."""
    symbol: str
    action: str  # buy, sell, hold
    confidence: float  # 0 to 1
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasoning: str
    timeframe: str = "short"  # short, medium, long


class TaskExtraction(BaseModel):
    """Extracted task from natural language."""
    task_type: str
    description: str
    parameters: dict
    priority: str = "medium"


class ConversationIntent(BaseModel):
    """Detected intent from user message."""
    intent: str
    entities: List[ExtractedEntity]
    confidence: float
    requires_action: bool


class StructuredLLM:
    """
    Wrapper for getting structured outputs from LLMs using Instructor.
    
    Instructor patches OpenAI/Anthropic clients to return Pydantic models
    instead of raw text, with automatic retries and validation.
    """
    
    def __init__(self, client: Any = None, provider: str = "openai"):
        """
        Initialize with an LLM client.
        
        Args:
            client: OpenAI or Anthropic client instance
            provider: "openai" or "anthropic"
        """
        self.provider = provider
        self._client = None
        
        if not HAS_INSTRUCTOR:
            logger.warning("Instructor not installed. Structured outputs disabled.")
            return
        
        if client is not None:
            self._patch_client(client)
    
    def _patch_client(self, client: Any):
        """Patch the client with Instructor."""
        if not HAS_INSTRUCTOR:
            return
        
        if self.provider == "openai":
            self._client = instructor.from_openai(client)
        elif self.provider == "anthropic":
            self._client = instructor.from_anthropic(client)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def extract(
        self,
        response_model: Type[T],
        messages: List[dict],
        model: str = "gpt-4o-mini",
        max_retries: int = 2,
        **kwargs
    ) -> Optional[T]:
        """
        Extract structured data from LLM response.
        
        Args:
            response_model: Pydantic model class to extract
            messages: Chat messages
            model: Model to use
            max_retries: Retries on validation failure
            
        Returns:
            Instance of response_model or None
        """
        if not HAS_INSTRUCTOR or self._client is None:
            logger.warning("Instructor not available")
            return None
        
        try:
            return self._client.chat.completions.create(
                model=model,
                response_model=response_model,
                messages=messages,
                max_retries=max_retries,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Structured extraction failed: {e}")
            return None
    
    def analyze_sentiment(self, text: str, model: str = "gpt-4o-mini") -> Optional[SentimentAnalysis]:
        """Analyze sentiment of text."""
        return self.extract(
            SentimentAnalysis,
            messages=[
                {"role": "system", "content": "Analyze the sentiment of the given text."},
                {"role": "user", "content": text}
            ],
            model=model
        )
    
    def extract_trading_signal(self, analysis: str, model: str = "gpt-4o-mini") -> Optional[TradingSignal]:
        """Extract trading signal from analysis text."""
        return self.extract(
            TradingSignal,
            messages=[
                {"role": "system", "content": "Extract a structured trading signal from the analysis. Be conservative with confidence scores."},
                {"role": "user", "content": analysis}
            ],
            model=model
        )
    
    def extract_intent(self, message: str, model: str = "gpt-4o-mini") -> Optional[ConversationIntent]:
        """Extract user intent from message."""
        return self.extract(
            ConversationIntent,
            messages=[
                {"role": "system", "content": "Analyze the user message and extract their intent and any entities mentioned."},
                {"role": "user", "content": message}
            ],
            model=model
        )
    
    def extract_task(self, message: str, model: str = "gpt-4o-mini") -> Optional[TaskExtraction]:
        """Extract actionable task from message."""
        return self.extract(
            TaskExtraction,
            messages=[
                {"role": "system", "content": "Extract an actionable task from the user's message. Identify the task type and any parameters."},
                {"role": "user", "content": message}
            ],
            model=model
        )


def create_structured_client(api_key: str = None, provider: str = "openai") -> Optional[StructuredLLM]:
    """
    Create a structured LLM client.
    
    Args:
        api_key: API key (uses env var if not provided)
        provider: "openai" or "anthropic"
    """
    if not HAS_INSTRUCTOR:
        return None
    
    import os
    
    if provider == "openai":
        from openai import OpenAI
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            logger.warning("No OpenAI API key found")
            return None
        client = OpenAI(api_key=key)
        return StructuredLLM(client, provider="openai")
    
    elif provider == "anthropic":
        from anthropic import Anthropic
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            logger.warning("No Anthropic API key found")
            return None
        from core.llm.anthropic_utils import get_anthropic_base_url

        client = Anthropic(
            api_key=key,
            base_url=get_anthropic_base_url(),
        )
        return StructuredLLM(client, provider="anthropic")
    
    return None
