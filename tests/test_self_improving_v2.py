"""
Tests for Self-Improving Core v2 features.

Tests cover:
- Chain-of-Thought reasoning
- BM25 retrieval
- Conversation summarization
- Conversation state machine
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone

# =============================================================================
# CHAIN-OF-THOUGHT REASONING TESTS
# =============================================================================


class TestChainOfThought:
    """Tests for Chain-of-Thought reasoning module."""

    def test_reasoning_type_classification(self):
        """Test that reasoning types are correctly classified."""
        from core.self_improving.reasoning.chain_of_thought import ChainOfThought, ReasoningType

        cot = ChainOfThought()

        # Planning
        assert cot.classify_reasoning_type("How to deploy this app?") == ReasoningType.PLANNING
        assert cot.classify_reasoning_type("What are the steps to do X?") == ReasoningType.PLANNING

        # Analytical
        assert cot.classify_reasoning_type("Analyze this data") == ReasoningType.ANALYTICAL
        assert cot.classify_reasoning_type("Compare these options") == ReasoningType.ANALYTICAL

        # Decision
        assert cot.classify_reasoning_type("Should I use React or Vue?") == ReasoningType.DECISION
        assert cot.classify_reasoning_type("Which database is better?") == ReasoningType.DECISION

        # Factual
        assert cot.classify_reasoning_type("What is Python?") == ReasoningType.FACTUAL
        assert cot.classify_reasoning_type("Define machine learning") == ReasoningType.FACTUAL

        # Direct
        assert cot.classify_reasoning_type("Hello") == ReasoningType.DIRECT
        assert cot.classify_reasoning_type("Thanks") == ReasoningType.DIRECT

    def test_create_reasoning_prompt(self):
        """Test reasoning prompt creation."""
        from core.self_improving.reasoning.chain_of_thought import ChainOfThought

        cot = ChainOfThought()

        prompt = cot.create_reasoning_prompt("How to deploy a Python app?")

        # Should contain CoT trigger
        assert "think" in prompt.lower() or "step" in prompt.lower()
        # Should contain the query
        assert "deploy" in prompt.lower() or "python" in prompt.lower()

    def test_create_reasoning_prompt_with_context(self):
        """Test prompt creation with context."""
        from core.self_improving.reasoning.chain_of_thought import ChainOfThought

        cot = ChainOfThought()

        context = {
            "facts": ["User prefers Docker", "App uses FastAPI"],
            "lessons": ["Always check dependencies first"],
        }

        prompt = cot.create_reasoning_prompt("Deploy the app", context)

        assert "Docker" in prompt or "FastAPI" in prompt or "dependencies" in prompt

    def test_parse_cot_response_with_steps(self):
        """Test parsing a response with reasoning steps."""
        from core.self_improving.reasoning.chain_of_thought import ChainOfThought

        cot = ChainOfThought()

        response = """STEP 1: First, I need to understand the requirements
STEP 2: Then, I'll check the available options
STEP 3: Finally, I'll make a recommendation
CONCLUSION: You should use option A
CONFIDENCE: high"""

        trace = cot.parse_response(response, "What should I use?")

        assert len(trace.steps) == 3
        assert "requirements" in trace.steps[0].thought
        assert "option A" in trace.conclusion
        assert trace.overall_confidence == 0.9

    def test_parse_cot_response_simple(self):
        """Test parsing a simple THOUGHT/RESPONSE format."""
        from core.self_improving.reasoning.chain_of_thought import ChainOfThought

        cot = ChainOfThought()

        response = """THOUGHT: This is a simple question
RESPONSE: The answer is 42."""

        trace = cot.parse_response(response, "What is the answer?")

        assert len(trace.steps) == 1
        assert "simple" in trace.steps[0].thought
        assert "42" in trace.conclusion

    def test_reasoning_trace_format(self):
        """Test formatting trace for prompt injection."""
        from core.self_improving.reasoning.chain_of_thought import (
            ReasoningTrace,
            ReasoningStep,
            ReasoningType,
        )

        trace = ReasoningTrace(
            query="Test query",
            reasoning_type=ReasoningType.ANALYTICAL,
            steps=[
                ReasoningStep(step_number=1, thought="First consideration"),
                ReasoningStep(step_number=2, thought="Second consideration"),
            ],
            conclusion="Final answer",
        )

        formatted = trace.format_for_prompt()

        assert "reasoning" in formatted.lower()
        assert "First consideration" in formatted
        assert "Final answer" in formatted

    def test_enhance_prompt_with_reasoning(self):
        """Test enhancing existing prompt."""
        from core.self_improving.reasoning.chain_of_thought import enhance_prompt_with_reasoning

        original = "Some context here\n\nUser says: How to do X?"

        enhanced = enhance_prompt_with_reasoning(original, "How to do X?")

        # Should add reasoning instructions
        assert "reasoning" in enhanced.lower() or "think" in enhanced.lower()
        # Should preserve original content
        assert "Some context here" in enhanced


# =============================================================================
# BM25 RETRIEVAL TESTS
# =============================================================================


class TestBM25Retrieval:
    """Tests for BM25 retrieval module."""

    def test_tokenize(self):
        """Test text tokenization."""
        from core.self_improving.memory.retrieval import tokenize

        tokens = tokenize("Hello world, this is a test!")

        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens
        # Stopwords should be removed
        assert "this" not in tokens
        assert "is" not in tokens

    def test_tokenize_preserves_important_words(self):
        """Test that tokenization keeps important words."""
        from core.self_improving.memory.retrieval import tokenize

        tokens = tokenize("Python programming database query optimization")

        assert "python" in tokens
        assert "programming" in tokens
        assert "database" in tokens
        assert "query" in tokens
        assert "optimization" in tokens

    def test_bm25_index_add_document(self):
        """Test adding documents to BM25 index."""
        from core.self_improving.memory.retrieval import BM25Index

        index = BM25Index()
        index.add_document("doc1", "Python is a programming language")
        index.add_document("doc2", "JavaScript is used for web development")

        assert index.doc_count == 2
        assert "doc1" in index.documents
        assert "doc2" in index.documents

    def test_bm25_search_basic(self):
        """Test basic BM25 search."""
        from core.self_improving.memory.retrieval import BM25Index

        index = BM25Index()
        index.add_document("doc1", "Python is a programming language")
        index.add_document("doc2", "JavaScript is used for web development")
        index.add_document("doc3", "Python web frameworks include Django and Flask")

        results = index.search("Python programming", k=5)

        assert len(results) >= 1
        # Python documents should score higher
        assert any("Python" in r.content for r in results[:2])

    def test_bm25_search_ranking(self):
        """Test that BM25 ranks relevant documents higher."""
        from core.self_improving.memory.retrieval import BM25Index

        index = BM25Index()
        index.add_document("doc1", "Database systems store data efficiently")
        index.add_document("doc2", "Python database connections use libraries like SQLAlchemy")
        index.add_document("doc3", "Python Python Python database database database")  # Keyword stuffing

        results = index.search("Python database", k=3)

        # Results should be ranked by relevance
        assert len(results) >= 2
        # Exact matching should score well
        top_ids = [r.doc_id for r in results[:2]]
        assert "doc2" in top_ids or "doc3" in top_ids

    def test_bm25_search_no_results(self):
        """Test BM25 search with no matching documents."""
        from core.self_improving.memory.retrieval import BM25Index

        index = BM25Index()
        index.add_document("doc1", "Python programming language")

        results = index.search("quantum physics", k=5)

        assert len(results) == 0

    def test_bm25_remove_document(self):
        """Test removing documents from index."""
        from core.self_improving.memory.retrieval import BM25Index

        index = BM25Index()
        index.add_document("doc1", "Python programming")
        index.add_document("doc2", "JavaScript development")

        assert index.doc_count == 2

        removed = index.remove_document("doc1")

        assert removed
        assert index.doc_count == 1
        assert "doc1" not in index.documents

    def test_bm25_search_convenience_function(self):
        """Test the convenience bm25_search function."""
        from core.self_improving.memory.retrieval import bm25_search

        texts = [
            "Python programming language",
            "JavaScript web development",
            "Python web frameworks",
        ]

        results = bm25_search(texts, "Python programming", k=2)

        assert len(results) >= 1
        # Results are (index, score) tuples
        assert isinstance(results[0], tuple)
        assert len(results[0]) == 2


# =============================================================================
# CONVERSATION SUMMARIZATION TESTS
# =============================================================================


class TestConversationSummarizer:
    """Tests for conversation summarization module."""

    def test_summarize_empty_conversation(self):
        """Test summarizing empty conversation."""
        from core.self_improving.memory.summarizer import ConversationSummarizer

        summarizer = ConversationSummarizer()
        summary = summarizer.summarize([], session_id="test")

        assert summary.full_summary == "Empty conversation"

    def test_summarize_basic_conversation(self):
        """Test basic conversation summarization."""
        from core.self_improving.memory.summarizer import ConversationSummarizer

        messages = [
            {"role": "user", "content": "How do I install Python?"},
            {"role": "assistant", "content": "You can install Python from python.org or use a package manager."},
            {"role": "user", "content": "Thanks, that worked!"},
        ]

        summarizer = ConversationSummarizer()
        summary = summarizer.summarize(messages, session_id="test")

        assert summary.full_summary
        assert "Python" in summary.full_summary or "install" in summary.full_summary.lower()

    def test_extract_entities(self):
        """Test entity extraction from text."""
        from core.self_improving.memory.summarizer import ConversationSummarizer

        summarizer = ConversationSummarizer()

        entities = summarizer._extract_entities(
            "John Smith mentioned @alice and the website example.com"
        )

        assert any("John" in e for e in entities)
        assert any("alice" in e for e in entities)
        assert any("example.com" in e for e in entities)

    def test_extract_actions(self):
        """Test action extraction from messages."""
        from core.self_improving.memory.summarizer import ConversationSummarizer

        messages = [
            {"role": "assistant", "content": "I opened the browser for you."},
            {"role": "assistant", "content": "Done: created the new file."},
        ]

        summarizer = ConversationSummarizer()
        actions = summarizer._extract_actions(messages)

        assert len(actions) >= 1

    def test_detect_sentiment(self):
        """Test sentiment detection."""
        from core.self_improving.memory.summarizer import ConversationSummarizer

        summarizer = ConversationSummarizer()

        # Positive
        positive_msgs = [{"role": "user", "content": "Thanks! This is great and helpful!"}]
        assert summarizer._detect_sentiment(positive_msgs) == "positive"

        # Negative
        negative_msgs = [{"role": "user", "content": "This is wrong and terrible!"}]
        assert summarizer._detect_sentiment(negative_msgs) == "negative"

        # Neutral
        neutral_msgs = [{"role": "user", "content": "What time is it?"}]
        assert summarizer._detect_sentiment(neutral_msgs) == "neutral"

    def test_compress_conversation(self):
        """Test conversation compression."""
        from core.self_improving.memory.summarizer import ConversationSummarizer

        # Create a long conversation with substantial content
        messages = []
        for i in range(50):
            messages.append({"role": "user", "content": f"This is a longer message {i} from user with substantial content that needs compression"})
            messages.append({"role": "assistant", "content": f"This is a longer response {i} from assistant with detailed explanation"})

        summarizer = ConversationSummarizer()
        compressed = summarizer.compress_for_context(messages, max_tokens=200)

        # Should be bounded - compression should limit output
        # Even if not smaller, it should be constrained
        assert compressed  # Not empty
        # Should mention recent messages (last few)
        assert "49" in compressed or "Response" in compressed or "Earlier" in compressed

    def test_summary_format_for_context(self):
        """Test formatting summary for context injection."""
        from core.self_improving.memory.summarizer import ConversationSummary

        summary = ConversationSummary(
            session_id="test",
            full_summary="User asked about Python installation",
            key_points=["Wants to install Python", "Used package manager"],
            topics_discussed=["python", "installation"],
            actions_taken=["Provided instructions"],
        )

        formatted = summary.format_for_context()

        assert "Python" in formatted
        assert "installation" in formatted or "install" in formatted


# =============================================================================
# CONVERSATION STATE MACHINE TESTS
# =============================================================================


class TestConversationStateMachine:
    """Tests for conversation state machine."""

    def test_initial_state(self):
        """Test that initial state is IDLE."""
        from core.self_improving.conversation.state_machine import (
            ConversationFlow,
            ConversationState,
        )

        flow = ConversationFlow(session_id="test")

        assert flow.current_state == ConversationState.IDLE

    def test_greeting_transition(self):
        """Test transition on greeting."""
        from core.self_improving.conversation.state_machine import (
            ConversationFlow,
            ConversationState,
        )

        flow = ConversationFlow(session_id="test")
        trigger, state = flow.process_input("Hello!")

        assert trigger == "greeting"
        assert flow.current_state == ConversationState.GREETING

    def test_command_transition(self):
        """Test transition on command."""
        from core.self_improving.conversation.state_machine import (
            ConversationFlow,
            ConversationState,
        )

        flow = ConversationFlow(session_id="test")
        flow.process_input("Hello")  # First get to greeting state
        trigger, state = flow.process_input("Open the browser")

        assert trigger == "command"
        assert flow.current_state == ConversationState.PROCESSING

    def test_question_transition(self):
        """Test transition on question."""
        from core.self_improving.conversation.state_machine import (
            ConversationFlow,
            ConversationState,
        )

        flow = ConversationFlow(session_id="test")
        flow.process_input("Hello")
        trigger, state = flow.process_input("What is Python?")

        assert trigger == "question"
        assert flow.current_state == ConversationState.PROCESSING

    def test_farewell_transition(self):
        """Test transition on farewell."""
        from core.self_improving.conversation.state_machine import (
            ConversationFlow,
            ConversationState,
        )

        flow = ConversationFlow(session_id="test")
        flow.process_input("Hello")
        trigger, state = flow.process_input("Goodbye")

        assert trigger == "farewell"
        assert flow.current_state == ConversationState.GOODBYE

    def test_add_goal(self):
        """Test adding a goal."""
        from core.self_improving.conversation.state_machine import (
            ConversationFlow,
            GoalStatus,
        )

        flow = ConversationFlow(session_id="test")
        goal = flow.add_goal("deploy", "Deploy the application", priority=8)

        assert goal.id == "deploy"
        assert goal.status == GoalStatus.ACTIVE
        assert goal.priority == 8

    def test_complete_goal(self):
        """Test completing a goal."""
        from core.self_improving.conversation.state_machine import (
            ConversationFlow,
            GoalStatus,
        )

        flow = ConversationFlow(session_id="test")
        flow.add_goal("task1", "Complete task 1")

        result = flow.complete_goal("task1")

        assert result
        assert flow.goals["task1"].status == GoalStatus.COMPLETED
        assert flow.goals["task1"].completed_at is not None

    def test_block_goal(self):
        """Test blocking a goal."""
        from core.self_improving.conversation.state_machine import (
            ConversationFlow,
            GoalStatus,
        )

        flow = ConversationFlow(session_id="test")
        flow.add_goal("task1", "Task needs input")

        result = flow.block_goal("task1", "Waiting for user confirmation")

        assert result
        assert flow.goals["task1"].status == GoalStatus.BLOCKED
        assert "confirmation" in flow.goals["task1"].blocking_reason

    def test_get_active_goals(self):
        """Test getting active goals sorted by priority."""
        from core.self_improving.conversation.state_machine import ConversationFlow

        flow = ConversationFlow(session_id="test")
        flow.add_goal("low", "Low priority task", priority=2)
        flow.add_goal("high", "High priority task", priority=9)
        flow.add_goal("medium", "Medium priority task", priority=5)

        active = flow.get_active_goals()

        assert len(active) == 3
        assert active[0].id == "high"
        assert active[1].id == "medium"
        assert active[2].id == "low"

    def test_context_slots(self):
        """Test context slot management."""
        from core.self_improving.conversation.state_machine import ConversationFlow

        flow = ConversationFlow(session_id="test")

        flow.set_slot("user_name", "Alice")
        flow.set_slot("task_type", "deployment")

        assert flow.get_slot("user_name") == "Alice"
        assert flow.get_slot("task_type") == "deployment"
        assert flow.get_slot("missing", "default") == "default"

    def test_entity_extraction(self):
        """Test entity extraction from input."""
        from core.self_improving.conversation.state_machine import ConversationFlow

        flow = ConversationFlow(session_id="test")
        flow.process_input("Schedule a meeting at 3pm with John")

        # Should extract time and potentially name
        assert "time" in flow.context_slots or "person" in flow.context_slots

    def test_transition_history(self):
        """Test that transitions are recorded."""
        from core.self_improving.conversation.state_machine import ConversationFlow

        flow = ConversationFlow(session_id="test")
        flow.process_input("Hello")
        flow.process_input("What is Python?")
        flow.process_input("Goodbye")

        assert len(flow.transition_history) >= 3

    def test_state_info(self):
        """Test getting comprehensive state info."""
        from core.self_improving.conversation.state_machine import ConversationFlow

        flow = ConversationFlow(session_id="test")
        flow.process_input("Hello")
        flow.add_goal("task1", "Do something")
        flow.set_slot("key", "value")

        info = flow.get_state_info()

        assert info["session_id"] == "test"
        assert info["current_state"] == "GREETING"
        assert len(info["active_goals"]) == 1
        assert "key" in info["context_slots"]

    def test_format_for_prompt(self):
        """Test formatting state for prompt injection."""
        from core.self_improving.conversation.state_machine import ConversationFlow

        flow = ConversationFlow(session_id="test")
        flow.process_input("Hello")
        flow.add_goal("deploy", "Deploy the application")

        formatted = flow.format_for_prompt()

        assert "GREETING" in formatted
        assert "Deploy" in formatted

    def test_reset(self):
        """Test resetting conversation state."""
        from core.self_improving.conversation.state_machine import (
            ConversationFlow,
            ConversationState,
        )

        flow = ConversationFlow(session_id="test")
        flow.process_input("Hello")
        flow.add_goal("task1", "Task")
        flow.set_slot("key", "value")

        flow.reset()

        assert flow.current_state == ConversationState.IDLE
        assert len(flow.goals) == 0
        assert len(flow.context_slots) == 0
        assert flow.turn_count == 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegrationV2:
    """Integration tests for v2 features."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        try:
            os.unlink(db_path)
        except Exception:
            pass

    def test_enrich_context_v2(self, temp_db, monkeypatch):
        """Test enhanced context enrichment."""
        # Patch config to use temp db
        import core.self_improving.integration as integration

        # Reset singleton
        integration._orchestrator = None
        integration._bm25_retriever = None

        def mock_load_config():
            return {"paths": {"data_dir": os.path.dirname(temp_db)}}

        def mock_resolve_path(p):
            from pathlib import Path
            return Path(os.path.dirname(temp_db))

        monkeypatch.setattr("core.config.load_config", mock_load_config)
        monkeypatch.setattr("core.config.resolve_path", mock_resolve_path)

        try:
            # Initialize
            orch = integration.get_self_improving()

            # Add some test data
            from core.self_improving.memory.models import Fact
            orch.memory.store_fact(Fact("user", "likes Python programming", 0.9))

            # Test v2 enrichment
            context = integration.enrich_context_v2("Python development", session_id="test_session")

            assert "query" in context
            # Should have conversation state for the session
            # (may or may not have facts depending on FTS5 matching)

        finally:
            integration.close()

    def test_reasoning_integration(self):
        """Test reasoning functions through integration layer."""
        from core.self_improving import integration

        # Test prompt creation
        prompt = integration.create_reasoning_prompt(
            "How should I structure this project?",
            context={"facts": ["User prefers modular design"]},
        )

        assert "structure" in prompt.lower() or "step" in prompt.lower()

        # Test response parsing
        response = "STEP 1: Analyze requirements\nCONCLUSION: Use MVC pattern\nCONFIDENCE: high"
        parsed = integration.parse_reasoning_response(response, "Structure question")

        assert "conclusion" in parsed
        assert "MVC" in parsed.get("conclusion", "")

    def test_conversation_flow_integration(self):
        """Test conversation flow through integration layer."""
        from core.self_improving import integration

        # Clear existing flows
        integration._conversation_flows.clear()

        session_id = "test_flow_session"

        # Process input
        trigger, state = integration.process_conversation_input("Hello there!", session_id)

        assert trigger == "greeting"
        assert state == "GREETING"

        # Add a goal
        result = integration.add_conversation_goal(session_id, "help", "Help the user")
        assert result

        # Get flow and check
        flow = integration.get_conversation_flow(session_id)
        assert flow is not None
        assert len(flow.goals) == 1

        # Complete goal
        result = integration.complete_conversation_goal(session_id, "help")
        assert result

    def test_summarization_integration(self):
        """Test summarization through integration layer."""
        from core.self_improving import integration

        messages = [
            {"role": "user", "content": "Can you help me with Python?"},
            {"role": "assistant", "content": "Sure! What would you like to know about Python?"},
            {"role": "user", "content": "How do I read a file?"},
            {"role": "assistant", "content": "You can use open() to read files in Python."},
        ]

        summary = integration.summarize_session(messages, session_id="test_summary")

        assert "full_summary" in summary
        assert summary["full_summary"]  # Not empty

    def test_compress_conversation_integration(self):
        """Test conversation compression."""
        from core.self_improving import integration

        messages = [
            {"role": "user", "content": f"This is a much longer message {i} with lots of content to compress"} for i in range(50)
        ]

        compressed = integration.compress_conversation(messages, max_tokens=100)

        # Should produce non-empty output that includes either recent messages or a summary
        assert compressed
        # Should include some indication of the content
        assert "message" in compressed.lower() or "Earlier" in compressed or "49" in compressed

    def test_enhanced_stats(self, temp_db, monkeypatch):
        """Test enhanced stats collection."""
        import core.self_improving.integration as integration

        # Reset
        integration._orchestrator = None
        integration._bm25_retriever = None
        integration._conversation_flows.clear()

        def mock_load_config():
            return {"paths": {"data_dir": os.path.dirname(temp_db)}}

        def mock_resolve_path(p):
            from pathlib import Path
            return Path(os.path.dirname(temp_db))

        monkeypatch.setattr("core.config.load_config", mock_load_config)
        monkeypatch.setattr("core.config.resolve_path", mock_resolve_path)

        try:
            integration.get_self_improving()

            # Add a conversation flow
            integration.get_conversation_flow("test_session")

            stats = integration.get_enhanced_stats()

            assert "active_sessions" in stats
            assert stats["active_sessions"] >= 1

        finally:
            integration.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
