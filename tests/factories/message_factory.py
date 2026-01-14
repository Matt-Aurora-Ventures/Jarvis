"""
Message Factory

Factory classes for generating message and conversation test data.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from .base import BaseFactory, RandomData, SequenceGenerator


class MessageRole(Enum):
    """Message role."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """Message model for testing."""
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    tokens: int
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class MessageFactory(BaseFactory[Message]):
    """Factory for creating Message test instances."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        role: MessageRole = MessageRole.USER,
        content: Optional[str] = None,
        tokens: Optional[int] = None,
        created_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Message:
        """Build a Message instance."""
        msg_content = content or f"Test message {SequenceGenerator.next('message')}"

        return Message(
            id=id or RandomData.uuid(),
            conversation_id=conversation_id or RandomData.uuid(),
            role=role,
            content=msg_content,
            tokens=tokens or len(msg_content.split()) * 2,
            created_at=created_at or datetime.utcnow(),
            metadata=metadata or {},
        )


class UserMessageFactory(MessageFactory):
    """Factory for user messages."""

    @classmethod
    def _build(cls, **kwargs) -> Message:
        kwargs.setdefault('role', MessageRole.USER)
        return super()._build(**kwargs)


class AssistantMessageFactory(MessageFactory):
    """Factory for assistant messages."""

    @classmethod
    def _build(cls, **kwargs) -> Message:
        kwargs.setdefault('role', MessageRole.ASSISTANT)
        kwargs.setdefault('content', "This is a test assistant response.")
        return super()._build(**kwargs)


class SystemMessageFactory(MessageFactory):
    """Factory for system messages."""

    @classmethod
    def _build(cls, **kwargs) -> Message:
        kwargs.setdefault('role', MessageRole.SYSTEM)
        kwargs.setdefault('content', "You are a helpful assistant.")
        return super()._build(**kwargs)


@dataclass
class Conversation:
    """Conversation model for testing."""
    id: str
    user_id: str
    title: Optional[str]
    messages: List[Message]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationFactory(BaseFactory[Conversation]):
    """Factory for creating Conversation test instances."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        user_id: Optional[str] = None,
        title: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        message_count: int = 0,
        **kwargs
    ) -> Conversation:
        """Build a Conversation instance."""
        now = datetime.utcnow()
        conv_id = id or RandomData.uuid()

        # Generate messages if requested
        if messages is None and message_count > 0:
            messages = []
            for i in range(message_count):
                role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
                messages.append(MessageFactory.build(
                    conversation_id=conv_id,
                    role=role,
                ))

        return Conversation(
            id=conv_id,
            user_id=user_id or RandomData.uuid(),
            title=title,
            messages=messages or [],
            is_active=is_active,
            created_at=created_at or now,
            updated_at=updated_at or now,
            metadata=metadata or {},
        )


class ActiveConversationFactory(ConversationFactory):
    """Factory for active conversations with messages."""

    @classmethod
    def _build(cls, **kwargs) -> Conversation:
        kwargs.setdefault('is_active', True)
        kwargs.setdefault('message_count', 4)
        return super()._build(**kwargs)


@dataclass
class ChatRequest:
    """Chat request model for testing."""
    conversation_id: Optional[str]
    message: str
    model: str
    temperature: float
    max_tokens: int
    stream: bool


class ChatRequestFactory(BaseFactory[ChatRequest]):
    """Factory for chat requests."""

    @classmethod
    def _build(
        cls,
        conversation_id: Optional[str] = None,
        message: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
        **kwargs
    ) -> ChatRequest:
        """Build a ChatRequest instance."""
        return ChatRequest(
            conversation_id=conversation_id,
            message=message or "What is the price of SOL?",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )


@dataclass
class ChatResponse:
    """Chat response model for testing."""
    id: str
    conversation_id: str
    message: str
    tokens_used: int
    model: str
    created_at: datetime


class ChatResponseFactory(BaseFactory[ChatResponse]):
    """Factory for chat responses."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        message: Optional[str] = None,
        tokens_used: Optional[int] = None,
        model: str = "llama-3.3-70b-versatile",
        created_at: Optional[datetime] = None,
        **kwargs
    ) -> ChatResponse:
        """Build a ChatResponse instance."""
        response_msg = message or "The current price of SOL is $150."

        return ChatResponse(
            id=id or RandomData.uuid(),
            conversation_id=conversation_id or RandomData.uuid(),
            message=response_msg,
            tokens_used=tokens_used or len(response_msg.split()) * 2,
            model=model,
            created_at=created_at or datetime.utcnow(),
        )
