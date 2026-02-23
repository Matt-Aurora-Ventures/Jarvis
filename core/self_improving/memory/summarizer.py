"""
Conversation Summarizer for Jarvis Memory.

Implements hierarchical summarization for efficient memory:
- Recent messages: Full detail
- Older messages: Summarized
- Very old: Meta-summary

Research basis:
- MemGPT (2023): Hierarchical memory with summarization
- Memoria (Dec 2025): 16× token efficiency with structured summaries

Key features:
1. Extractive + abstractive summarization
2. Key entity preservation
3. Action/decision tracking
4. Semantic chunking
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.summarizer")


@dataclass
class ConversationChunk:
    """A chunk of conversation for summarization."""

    messages: List[Dict[str, str]]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    summary: str = ""
    key_entities: List[str] = field(default_factory=list)
    key_actions: List[str] = field(default_factory=list)
    key_decisions: List[str] = field(default_factory=list)
    token_count: int = 0

    def __post_init__(self):
        if not self.token_count and self.messages:
            # Rough token estimate (1 token ≈ 4 chars)
            total_chars = sum(len(m.get("content", "")) for m in self.messages)
            self.token_count = total_chars // 4


@dataclass
class ConversationSummary:
    """A hierarchical summary of a conversation."""

    session_id: str
    full_summary: str
    key_points: List[str] = field(default_factory=list)
    entities_mentioned: List[str] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    decisions_made: List[str] = field(default_factory=list)
    topics_discussed: List[str] = field(default_factory=list)
    user_sentiment: str = "neutral"  # positive, negative, neutral
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "full_summary": self.full_summary,
            "key_points": self.key_points,
            "entities_mentioned": self.entities_mentioned,
            "actions_taken": self.actions_taken,
            "decisions_made": self.decisions_made,
            "topics_discussed": self.topics_discussed,
            "user_sentiment": self.user_sentiment,
            "created_at": self.created_at.isoformat(),
        }

    def format_for_context(self) -> str:
        """Format summary for injection into prompt context."""
        lines = [f"Session summary: {self.full_summary}"]

        if self.key_points:
            lines.append("Key points: " + "; ".join(self.key_points[:5]))

        if self.topics_discussed:
            lines.append("Topics: " + ", ".join(self.topics_discussed[:5]))

        if self.actions_taken:
            lines.append("Actions: " + "; ".join(self.actions_taken[:3]))

        return "\n".join(lines)


class ConversationSummarizer:
    """
    Summarizes conversations for efficient memory storage.

    Two modes:
    1. Extractive (no LLM): Fast, rule-based extraction
    2. Abstractive (with LLM): Higher quality summaries

    Usage:
        summarizer = ConversationSummarizer()
        summary = summarizer.summarize(messages)
        # Or with LLM:
        summarizer.set_llm_client(anthropic_client)
        summary = await summarizer.summarize_async(messages)
    """

    # Chunk size for hierarchical summarization
    CHUNK_SIZE = 10  # messages per chunk
    MAX_SUMMARY_LENGTH = 500  # chars

    # Patterns for extractive summarization
    ACTION_PATTERNS = [
        r"(?:I|i)\s+(?:opened|created|sent|set|added|removed|updated|fixed|built|ran|started|stopped)\s+\w+",
        r"(?:done|completed|finished):\s*(.+)",
        r"\[ACTION:[^\]]+\]",
    ]

    DECISION_PATTERNS = [
        r"(?:decided|choosing|selected|going with|will use|opted for)\s+(.+)",
        r"(?:yes|no|okay|sure),?\s+(?:I'll|let's|we'll)\s+(.+)",
    ]

    def __init__(self, llm_client: Optional[Any] = None, model: str = "claude-sonnet-4-6"):
        self.llm_client = llm_client
        self.model = model
        self._summaries_cache: Dict[str, ConversationSummary] = {}

    def set_llm_client(self, client: Any):
        """Set LLM client for abstractive summarization."""
        self.llm_client = client

    def _chunk_messages(self, messages: List[Dict[str, str]]) -> List[ConversationChunk]:
        """Split messages into chunks for hierarchical summarization."""
        chunks = []
        for i in range(0, len(messages), self.CHUNK_SIZE):
            chunk_messages = messages[i : i + self.CHUNK_SIZE]
            chunks.append(ConversationChunk(messages=chunk_messages))
        return chunks

    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text (rule-based)."""
        entities = []

        # Capitalized words (potential names, projects)
        capitalized = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        entities.extend(capitalized)

        # @mentions
        mentions = re.findall(r"@(\w+)", text)
        entities.extend(mentions)

        # URLs/domains
        domains = re.findall(r"(?:https?://)?(?:www\.)?([a-z0-9-]+\.[a-z]{2,})", text.lower())
        entities.extend(domains)

        # Deduplicate and limit
        seen = set()
        unique = []
        for e in entities:
            e_lower = e.lower()
            if e_lower not in seen and len(e) > 2:
                seen.add(e_lower)
                unique.append(e)

        return unique[:20]

    def _extract_actions(self, messages: List[Dict[str, str]]) -> List[str]:
        """Extract actions taken from messages."""
        actions = []
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", msg.get("source", ""))

            if role in ("assistant", "voice_chat_assistant"):
                for pattern in self.ACTION_PATTERNS:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    actions.extend(m if isinstance(m, str) else m[0] for m in matches if m)

        return actions[:10]

    def _extract_decisions(self, messages: List[Dict[str, str]]) -> List[str]:
        """Extract decisions made during conversation."""
        decisions = []
        for msg in messages:
            content = msg.get("content", "")
            for pattern in self.DECISION_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                decisions.extend(m if isinstance(m, str) else str(m) for m in matches if m)

        return decisions[:5]

    def _extract_topics(self, messages: List[Dict[str, str]]) -> List[str]:
        """Extract main topics from conversation."""
        # Combine all text
        all_text = " ".join(m.get("content", "") for m in messages)

        # Simple keyword extraction (nouns that appear multiple times)
        words = re.findall(r"\b[a-z]{4,}\b", all_text.lower())
        word_counts = {}
        for w in words:
            word_counts[w] = word_counts.get(w, 0) + 1

        # Filter common words and sort by frequency
        stopwords = {
            "that", "this", "with", "have", "will", "would", "could", "should",
            "just", "like", "know", "think", "want", "need", "make", "going",
            "something", "anything", "everything", "nothing",
        }
        topics = [
            w for w, c in sorted(word_counts.items(), key=lambda x: -x[1])
            if c >= 2 and w not in stopwords
        ]

        return topics[:10]

    def _detect_sentiment(self, messages: List[Dict[str, str]]) -> str:
        """Detect overall user sentiment from conversation."""
        user_messages = [
            m.get("content", "")
            for m in messages
            if m.get("role", m.get("source", "")) in ("user", "voice_chat_user")
        ]
        all_user_text = " ".join(user_messages).lower()

        positive_words = {"thanks", "great", "awesome", "perfect", "love", "excellent", "amazing", "helpful"}
        negative_words = {"wrong", "bad", "terrible", "hate", "awful", "frustrated", "annoyed", "broken"}

        positive_count = sum(1 for w in positive_words if w in all_user_text)
        negative_count = sum(1 for w in negative_words if w in all_user_text)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"

    def _extractive_summary(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate extractive summary without LLM.

        Extracts key sentences using TF-IDF-like scoring.
        """
        if not messages:
            return ""

        # Get all sentences
        sentences = []
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", msg.get("source", ""))
            # Split by sentence boundaries
            msg_sentences = re.split(r"[.!?]+\s+", content)
            for s in msg_sentences:
                s = s.strip()
                if len(s) > 20:  # Skip very short sentences
                    sentences.append((role, s))

        if not sentences:
            return "Brief conversation with no significant content."

        # Score sentences by importance (simple heuristics)
        scored = []
        for role, sentence in sentences:
            score = 0

            # User questions are important
            if role in ("user", "voice_chat_user") and "?" in sentence:
                score += 2

            # Sentences with actions
            if any(re.search(p, sentence, re.IGNORECASE) for p in self.ACTION_PATTERNS):
                score += 3

            # Sentences with numbers/data
            if re.search(r"\d+", sentence):
                score += 1

            # Length penalty for very long sentences
            if len(sentence) > 200:
                score -= 1

            scored.append((score, role, sentence))

        # Sort by score and take top sentences
        scored.sort(key=lambda x: -x[0])
        top_sentences = scored[: min(5, len(scored))]

        # Build summary
        summary_parts = []
        for score, role, sentence in top_sentences:
            prefix = "User asked:" if role in ("user", "voice_chat_user") else "Jarvis:"
            summary_parts.append(f"{prefix} {sentence[:100]}{'...' if len(sentence) > 100 else ''}")

        return " ".join(summary_parts)[: self.MAX_SUMMARY_LENGTH]

    def summarize(
        self,
        messages: List[Dict[str, str]],
        session_id: str = "",
        use_llm: bool = False,
    ) -> ConversationSummary:
        """
        Summarize a conversation (synchronous).

        Args:
            messages: List of conversation messages
            session_id: Session identifier
            use_llm: Whether to use LLM for summarization

        Returns:
            ConversationSummary object
        """
        if not messages:
            return ConversationSummary(
                session_id=session_id,
                full_summary="Empty conversation",
            )

        # Extract structured data
        all_text = " ".join(m.get("content", "") for m in messages)
        entities = self._extract_entities(all_text)
        actions = self._extract_actions(messages)
        decisions = self._extract_decisions(messages)
        topics = self._extract_topics(messages)
        sentiment = self._detect_sentiment(messages)

        # Generate summary
        if use_llm and self.llm_client:
            summary_text = self._llm_summarize_sync(messages)
        else:
            summary_text = self._extractive_summary(messages)

        # Build key points from first/last messages
        key_points = []
        if messages:
            first_user = next(
                (m.get("content", "")[:100] for m in messages if m.get("role", m.get("source", "")) in ("user", "voice_chat_user")),
                "",
            )
            if first_user:
                key_points.append(f"Started with: {first_user}")

            last_user = None
            for m in reversed(messages):
                if m.get("role", m.get("source", "")) in ("user", "voice_chat_user"):
                    last_user = m.get("content", "")[:100]
                    break
            if last_user and last_user != first_user:
                key_points.append(f"Ended with: {last_user}")

        summary = ConversationSummary(
            session_id=session_id,
            full_summary=summary_text,
            key_points=key_points,
            entities_mentioned=entities,
            actions_taken=actions,
            decisions_made=decisions,
            topics_discussed=topics,
            user_sentiment=sentiment,
        )

        # Cache the summary
        if session_id:
            self._summaries_cache[session_id] = summary

        return summary

    def _llm_summarize_sync(self, messages: List[Dict[str, str]]) -> str:
        """Generate summary using LLM (sync)."""
        if not self.llm_client:
            return self._extractive_summary(messages)

        # Format conversation
        conv_lines = []
        for msg in messages[-20:]:  # Last 20 messages max
            role = msg.get("role", msg.get("source", "unknown"))
            content = msg.get("content", "")[:300]
            conv_lines.append(f"{role}: {content}")

        prompt = f"""Summarize this conversation in 2-3 sentences. Focus on:
- What the user wanted
- What was accomplished
- Any important decisions or actions

Conversation:
{chr(10).join(conv_lines)}

Summary (2-3 sentences):"""

        try:
            response = self.llm_client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()[: self.MAX_SUMMARY_LENGTH]
        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}")
            return self._extractive_summary(messages)

    async def summarize_async(
        self,
        messages: List[Dict[str, str]],
        session_id: str = "",
    ) -> ConversationSummary:
        """Async version of summarize with LLM."""
        return self.summarize(messages, session_id, use_llm=True)

    def get_cached_summary(self, session_id: str) -> Optional[ConversationSummary]:
        """Get a cached summary by session ID."""
        return self._summaries_cache.get(session_id)

    def compress_for_context(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
    ) -> str:
        """
        Compress messages for injection into context.

        Returns recent messages + summary of older messages.
        """
        if not messages:
            return ""

        # Estimate tokens
        total_chars = sum(len(m.get("content", "")) for m in messages)
        estimated_tokens = total_chars // 4

        if estimated_tokens <= max_tokens:
            # No compression needed
            lines = []
            for msg in messages:
                role = "User" if msg.get("role", msg.get("source", "")) in ("user", "voice_chat_user") else "Jarvis"
                lines.append(f"{role}: {msg.get('content', '')[:200]}")
            return "\n".join(lines)

        # Split: recent (full) + older (summarized)
        recent_count = max(3, max_tokens // 100)  # ~100 tokens per message
        recent = messages[-recent_count:]
        older = messages[:-recent_count]

        parts = []

        # Summarize older messages
        if older:
            summary = self.summarize(older, use_llm=False)
            parts.append(f"[Earlier: {summary.full_summary}]")

        # Add recent messages
        for msg in recent:
            role = "User" if msg.get("role", msg.get("source", "")) in ("user", "voice_chat_user") else "Jarvis"
            parts.append(f"{role}: {msg.get('content', '')[:200]}")

        return "\n".join(parts)


# Convenience functions
def summarize_conversation(
    messages: List[Dict[str, str]],
    session_id: str = "",
) -> ConversationSummary:
    """Quick conversation summarization."""
    return ConversationSummarizer().summarize(messages, session_id)


def compress_conversation(
    messages: List[Dict[str, str]],
    max_tokens: int = 1000,
) -> str:
    """Quick conversation compression."""
    return ConversationSummarizer().compress_for_context(messages, max_tokens)
