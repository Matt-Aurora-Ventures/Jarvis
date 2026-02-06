"""
Context Storage Backends - Persist conversation contexts.

Provides:
- ContextStorage: Abstract base class defining interface
- InMemoryStorage: Fast, non-persistent storage
- FileStorage: Persistent JSON file storage
"""

from abc import ABC, abstractmethod
import json
import os
import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from threading import Lock

from .session_context import ConversationContext


logger = logging.getLogger(__name__)


class ContextStorage(ABC):
    """
    Abstract base class for context storage backends.

    Subclasses must implement:
    - save_context(context) -> bool
    - load_context(user_id, chat_id) -> Optional[ConversationContext]
    - delete_context(user_id, chat_id) -> bool
    - list_contexts() -> List[ConversationContext]
    """

    @abstractmethod
    def save_context(self, context: ConversationContext) -> bool:
        """
        Save a conversation context.

        Args:
            context: ConversationContext to save

        Returns:
            True if saved successfully, False otherwise
        """
        pass

    @abstractmethod
    def load_context(self, user_id: str, chat_id: str) -> Optional[ConversationContext]:
        """
        Load a conversation context.

        Args:
            user_id: User identifier
            chat_id: Chat identifier

        Returns:
            ConversationContext if found, None otherwise
        """
        pass

    @abstractmethod
    def delete_context(self, user_id: str, chat_id: str) -> bool:
        """
        Delete a conversation context.

        Args:
            user_id: User identifier
            chat_id: Chat identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def list_contexts(self) -> List[ConversationContext]:
        """
        List all stored contexts.

        Returns:
            List of all ConversationContext objects
        """
        pass

    def count(self) -> int:
        """
        Count stored contexts.

        Returns:
            Number of stored contexts
        """
        return len(self.list_contexts())

    def clear_all(self) -> int:
        """
        Clear all stored contexts.

        Returns:
            Number of contexts removed
        """
        contexts = self.list_contexts()
        count = 0
        for ctx in contexts:
            if self.delete_context(ctx.user_id, ctx.chat_id):
                count += 1
        return count


class InMemoryStorage(ContextStorage):
    """
    In-memory storage backend for fast, non-persistent storage.

    Thread-safe using a lock for concurrent access.
    """

    def __init__(self):
        self._contexts: Dict[str, ConversationContext] = {}
        self._lock = Lock()

    def _make_key(self, user_id: str, chat_id: str) -> str:
        """Create storage key from user_id and chat_id."""
        return f"{user_id}:{chat_id}"

    def save_context(self, context: ConversationContext) -> bool:
        """Save context to memory."""
        key = self._make_key(context.user_id, context.chat_id)
        with self._lock:
            self._contexts[key] = context
        return True

    def load_context(self, user_id: str, chat_id: str) -> Optional[ConversationContext]:
        """Load context from memory."""
        key = self._make_key(user_id, chat_id)
        with self._lock:
            return self._contexts.get(key)

    def delete_context(self, user_id: str, chat_id: str) -> bool:
        """Delete context from memory."""
        key = self._make_key(user_id, chat_id)
        with self._lock:
            if key in self._contexts:
                del self._contexts[key]
                return True
            return False

    def list_contexts(self) -> List[ConversationContext]:
        """List all contexts in memory."""
        with self._lock:
            return list(self._contexts.values())

    def count(self) -> int:
        """Count contexts in memory."""
        with self._lock:
            return len(self._contexts)

    def clear_all(self) -> int:
        """Clear all contexts from memory."""
        with self._lock:
            count = len(self._contexts)
            self._contexts.clear()
            return count


class FileStorage(ContextStorage):
    """
    File-based storage backend for persistent JSON storage.

    Stores each context as a separate JSON file in the specified directory.
    Thread-safe using a lock for file operations.
    """

    def __init__(self, storage_path: str):
        """
        Initialize FileStorage.

        Args:
            storage_path: Directory path for storing context files
        """
        self._storage_path = storage_path
        self._lock = Lock()

        # Create directory if it doesn't exist
        os.makedirs(storage_path, exist_ok=True)

    def _sanitize_filename(self, user_id: str, chat_id: str) -> str:
        """
        Create safe filename from user_id and chat_id.

        Replaces unsafe characters with underscores.
        """
        # Replace unsafe characters
        safe_user = re.sub(r'[^\w\-]', '_', user_id)
        safe_chat = re.sub(r'[^\w\-]', '_', chat_id)
        return f"{safe_user}_{safe_chat}.json"

    def _get_filepath(self, user_id: str, chat_id: str) -> str:
        """Get full file path for a context."""
        filename = self._sanitize_filename(user_id, chat_id)
        return os.path.join(self._storage_path, filename)

    def save_context(self, context: ConversationContext) -> bool:
        """Save context to JSON file."""
        filepath = self._get_filepath(context.user_id, context.chat_id)

        try:
            with self._lock:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(context.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save context to {filepath}: {e}")
            return False

    def load_context(self, user_id: str, chat_id: str) -> Optional[ConversationContext]:
        """Load context from JSON file."""
        filepath = self._get_filepath(user_id, chat_id)

        if not os.path.exists(filepath):
            return None

        try:
            with self._lock:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            return ConversationContext.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load context from {filepath}: {e}")
            return None

    def delete_context(self, user_id: str, chat_id: str) -> bool:
        """Delete context JSON file."""
        filepath = self._get_filepath(user_id, chat_id)

        if not os.path.exists(filepath):
            return False

        try:
            with self._lock:
                os.remove(filepath)
            return True
        except Exception as e:
            logger.error(f"Failed to delete {filepath}: {e}")
            return False

    def list_contexts(self) -> List[ConversationContext]:
        """List all contexts from JSON files."""
        contexts = []

        try:
            with self._lock:
                for filename in os.listdir(self._storage_path):
                    if filename.endswith('.json'):
                        filepath = os.path.join(self._storage_path, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            ctx = ConversationContext.from_dict(data)
                            contexts.append(ctx)
                        except Exception as e:
                            logger.warning(f"Failed to load {filepath}: {e}")
        except Exception as e:
            logger.error(f"Failed to list contexts: {e}")

        return contexts

    def count(self) -> int:
        """Count context files."""
        try:
            with self._lock:
                return len([f for f in os.listdir(self._storage_path) if f.endswith('.json')])
        except Exception:
            return 0
