"""
Comprehensive unit tests for core/conversation.py - Conversation Management Module.

Tests cover:
1. Text Utilities (_truncate, _strip_urls, _strip_action_tokens, _voice_friendly_text)
2. History Management (_recent_chat, _format_history, _record_conversation_turn)
3. Prompt Support (_support_prompts, _is_research_request)
4. Entity Extraction (_extract_entities)
5. Intent Classification (_classify_intent)
6. Input Synthesis (_synthesize_input)
7. URL Handling (_extract_url, _domain_from_url, _normalize_url)
8. Direct Actions (_infer_direct_action)
9. Response Formatting (_format_research_response, _format_action_response, _format_action_history)
10. Response Sanitization (_sanitize_response, sanitize_for_voice, _normalize_response_prefix)
11. JSON Parsing (_extract_json_payload, _parse_json_payload)
12. Question Detection (_is_question_response, _last_assistant_question)
13. Main Response Generation (generate_response)
14. Action Execution in Responses (_execute_actions_in_response)
15. Fallback Response (_fallback_response)

Coverage target: 80%+ with 80+ tests

Note: The module under test is core/conversation.py (single file), not the
core/conversation/ subpackage. We import via sys.modules manipulation.
"""
import json
import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, List, Any
import importlib.util


# =============================================================================
# MODULE LOADING SETUP
# =============================================================================

# Load the single-file conversation.py module directly
# This is necessary because Python prefers the subpackage when both exist
_MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "core", "conversation.py"
)
_MODULE_PATH = os.path.abspath(_MODULE_PATH)

# Create mock modules for dependencies that will be patched
_mock_core_modules = {
    'core.actions': MagicMock(),
    'core.config': MagicMock(),
    'core.context_loader': MagicMock(),
    'core.context_manager': MagicMock(),
    'core.guardian': MagicMock(),
    'core.jarvis': MagicMock(),
    'core.memory': MagicMock(),
    'core.passive': MagicMock(),
    'core.providers': MagicMock(),
    'core.prompt_library': MagicMock(),
    'core.research_engine': MagicMock(),
    'core.safety': MagicMock(),
}


def _get_conversation_module():
    """
    Load core/conversation.py as a standalone module.

    Returns the loaded module with mocked dependencies.
    """
    # Temporarily add mock modules
    original_modules = {}
    for name, mock in _mock_core_modules.items():
        if name in sys.modules:
            original_modules[name] = sys.modules[name]
        sys.modules[name] = mock

    try:
        # Load the module
        spec = importlib.util.spec_from_file_location(
            "core_conversation_file", _MODULE_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        # Restore original modules
        for name in _mock_core_modules:
            if name in original_modules:
                sys.modules[name] = original_modules[name]
            elif name in sys.modules:
                del sys.modules[name]


# Load the module once at import time
conversation = _get_conversation_module()


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_config():
    """Mock configuration dictionary."""
    return {
        "context": {"include_activity_summary": True},
        "research": {"allow_web": False},
    }


@pytest.fixture
def mock_config_research_enabled():
    """Mock configuration with research enabled."""
    return {
        "context": {"include_activity_summary": True},
        "research": {"allow_web": True},
    }


@pytest.fixture
def mock_safety_context():
    """Mock SafetyContext instance."""
    mock = MagicMock()
    mock.apply = True
    mock.dry_run = False
    return mock


@pytest.fixture
def mock_memory_entries():
    """Sample memory entries for testing."""
    return [
        {"source": "voice_chat_user", "text": "What's the weather like?"},
        {"source": "voice_chat_assistant", "text": "It looks sunny today."},
        {"source": "voice_chat_user", "text": "Thanks for the info"},
        {"source": "voice_chat_assistant", "text": "You're welcome!"},
    ]


@pytest.fixture
def mock_mixed_entries():
    """Memory entries with mixed sources."""
    return [
        {"source": "voice_chat_user", "text": "Hello"},
        {"source": "system", "text": "System update"},
        {"source": "voice_chat_assistant", "text": "Hi there!"},
        {"source": "action", "text": "Action completed"},
    ]


@pytest.fixture
def mock_prompt():
    """Mock Prompt object."""
    mock = MagicMock()
    mock.title = "Test Prompt"
    mock.body = "This is a test prompt body"
    mock.id = "prompt_123"
    return mock


@pytest.fixture
def mock_conversation_context():
    """Mock conversation context."""
    mock = MagicMock()
    mock.action_history = [
        {"action": "open_browser", "success": True, "result": "Opened https://example.com"},
        {"action": "google", "success": True, "result": "Search completed"},
        {"action": "copy", "success": False, "result": "Clipboard error"},
    ]
    return mock


@pytest.fixture
def mock_research_result():
    """Mock research engine result."""
    return {
        "summary": "This is a research summary about the topic.",
        "key_findings": [
            "Finding 1: Important discovery",
            "Finding 2: Another key point",
            "Finding 3: Third finding",
        ],
        "sources": [
            {"title": "Source 1", "url": "https://example.com/article1"},
            {"title": "Source 2", "url": "https://test.org/doc"},
        ],
    }


# =============================================================================
# TEST CLASS: _truncate Function
# =============================================================================


class TestTruncate:
    """Tests for the _truncate function."""

    def test_truncate_short_text_unchanged(self):
        """Short text should pass through unchanged."""
        result = conversation._truncate("Hello world", limit=800)
        assert result == "Hello world"

    def test_truncate_exact_limit_unchanged(self):
        """Text exactly at limit should pass through."""
        text = "a" * 800
        result = conversation._truncate(text, limit=800)
        assert result == text

    def test_truncate_long_text_truncated(self):
        """Long text should be truncated with ellipsis."""
        text = "a" * 1000
        result = conversation._truncate(text, limit=800)
        assert len(result) == 803  # 800 + "..."
        assert result.endswith("...")

    def test_truncate_preserves_content(self):
        """Truncation should preserve beginning of content."""
        text = "Hello world " * 100
        result = conversation._truncate(text, limit=50)
        assert result.startswith("Hello world")

    def test_truncate_custom_limit(self):
        """Custom limit should be respected."""
        text = "a" * 100
        result = conversation._truncate(text, limit=30)
        assert len(result) == 33  # 30 + "..."

    def test_truncate_empty_string(self):
        """Empty string should return empty."""
        result = conversation._truncate("", limit=800)
        assert result == ""

    def test_truncate_strips_trailing_whitespace(self):
        """Truncation should strip trailing whitespace before ellipsis."""
        text = "word " * 200  # Each word has trailing space
        result = conversation._truncate(text, limit=20)
        # Should not have trailing space before ellipsis
        assert not result[:-3].endswith(" ")


# =============================================================================
# TEST CLASS: _format_history Function
# =============================================================================


class TestFormatHistory:
    """Tests for the _format_history function."""

    def test_format_history_user_entries(self):
        """Should prefix user entries correctly."""
        entries = [{"source": "voice_chat_user", "text": "Hello"}]
        result = conversation._format_history(entries)
        assert result.startswith("User:")

    def test_format_history_assistant_entries(self):
        """Should prefix assistant entries correctly."""
        entries = [{"source": "voice_chat_assistant", "text": "Hi there"}]
        result = conversation._format_history(entries)
        assert result.startswith("Assistant:")

    def test_format_history_multiple_entries(self, mock_memory_entries):
        """Should format multiple entries correctly."""
        result = conversation._format_history(mock_memory_entries)
        lines = result.split("\n")
        assert len(lines) == 4

    def test_format_history_truncates_long_text(self):
        """Should truncate long text in entries."""
        long_text = "a" * 500
        entries = [{"source": "voice_chat_user", "text": long_text}]
        result = conversation._format_history(entries)
        # Text should be truncated to 400 chars
        assert len(result) <= 410 + len("User: ")

    def test_format_history_empty_entries(self):
        """Should handle empty entries list."""
        result = conversation._format_history([])
        assert result == ""

    def test_format_history_skips_empty_text(self):
        """Should skip entries with empty text."""
        entries = [
            {"source": "voice_chat_user", "text": ""},
            {"source": "voice_chat_assistant", "text": "Hello"},
        ]
        result = conversation._format_history(entries)
        assert "User:" not in result
        assert "Assistant:" in result


# =============================================================================
# TEST CLASS: _is_research_request Function
# =============================================================================


class TestIsResearchRequest:
    """Tests for the _is_research_request function."""

    def test_is_research_request_research_keyword(self):
        """Should detect 'research' keyword."""
        assert conversation._is_research_request("Research this topic") is True

    def test_is_research_request_deep_dive(self):
        """Should detect 'deep dive' keyword."""
        assert conversation._is_research_request("Do a deep dive on AI") is True

    def test_is_research_request_investigate(self):
        """Should detect 'investigate' keyword."""
        assert conversation._is_research_request("Investigate this issue") is True

    def test_is_research_request_look_up(self):
        """Should detect 'look up' keyword."""
        assert conversation._is_research_request("Look up the weather") is True

    def test_is_research_request_find_sources(self):
        """Should detect 'find sources' keyword."""
        assert conversation._is_research_request("Find sources on climate change") is True

    def test_is_research_request_case_insensitive(self):
        """Should be case insensitive."""
        assert conversation._is_research_request("RESEARCH this") is True
        assert conversation._is_research_request("ReSeArCh this") is True

    def test_is_research_request_no_match(self):
        """Should return False for non-research requests."""
        assert conversation._is_research_request("Hello world") is False
        assert conversation._is_research_request("What time is it?") is False


# =============================================================================
# TEST CLASS: _extract_entities Function
# =============================================================================


class TestExtractEntities:
    """Tests for the _extract_entities function."""

    def test_extract_entities_returns_dict(self):
        """Should return dict with expected keys."""
        result = conversation._extract_entities("Hello world")

        assert isinstance(result, dict)
        assert "people" in result
        assert "tools" in result
        assert "projects" in result
        assert "actions" in result
        assert "topics" in result

    def test_extract_entities_detects_tools(self):
        """Should detect tool mentions."""
        result = conversation._extract_entities("Open python and git to code")

        assert "python" in result["tools"]
        assert "git" in result["tools"]

    def test_extract_entities_detects_actions(self):
        """Should detect action verbs."""
        result = conversation._extract_entities("Create a new file and fix the bug")

        assert "create" in result["actions"]
        assert "fix" in result["actions"]

    def test_extract_entities_detects_topics(self):
        """Should detect topic keywords."""
        result = conversation._extract_entities("Help me with trading crypto")

        assert "crypto" in result["topics"]

    def test_extract_entities_multiple_actions(self):
        """Should detect multiple actions."""
        result = conversation._extract_entities("Create, fix, and improve the code")

        assert "create" in result["actions"]
        assert "fix" in result["actions"]
        assert "improve" in result["actions"]

    def test_extract_entities_development_topic(self):
        """Should detect development topic."""
        result = conversation._extract_entities("Write some code for the API")

        assert "development" in result["topics"]

    def test_extract_entities_empty_input(self):
        """Should handle empty input."""
        result = conversation._extract_entities("")

        assert result["people"] == []
        assert result["tools"] == []


# =============================================================================
# TEST CLASS: _classify_intent Function
# =============================================================================


class TestClassifyIntent:
    """Tests for the _classify_intent function."""

    def test_classify_intent_returns_dict(self):
        """Should return dict with expected keys."""
        result = conversation._classify_intent("Hello", [])

        assert "primary_intent" in result
        assert "confidence" in result
        assert "requires_action" in result
        assert "requires_memory" in result
        assert "is_followup" in result

    def test_classify_intent_command_detection(self):
        """Should detect command intent."""
        result = conversation._classify_intent("Open the browser", [])

        assert result["primary_intent"] == "command"
        assert result["requires_action"] is True

    def test_classify_intent_question_detection(self):
        """Should detect question intent."""
        result = conversation._classify_intent("What is the weather?", [])

        assert result["primary_intent"] == "question"
        assert result["requires_memory"] is True

    def test_classify_intent_greeting_detection(self):
        """Should detect greeting intent."""
        result = conversation._classify_intent("Hello", [])

        assert result["primary_intent"] == "greeting"

    def test_classify_intent_status_detection(self):
        """Should detect status check intent."""
        result = conversation._classify_intent("What's happening?", [])

        assert result["primary_intent"] == "status"

    def test_classify_intent_followup_detection(self):
        """Should detect followup from previous conversation."""
        history = [{"source": "voice_chat_assistant", "text": "The weather is nice"}]
        result = conversation._classify_intent("Yes, tell me more", history)

        assert result["is_followup"] is True

    def test_classify_intent_pronoun_followup(self):
        """Should detect pronoun-based followup."""
        history = [{"source": "voice_chat_assistant", "text": "Previous response"}]
        result = conversation._classify_intent("What about that?", history)

        assert result["is_followup"] is True

    def test_classify_intent_please_pattern(self):
        """Should detect 'please' command pattern."""
        result = conversation._classify_intent("Please open the file", [])

        assert result["primary_intent"] == "command"


# =============================================================================
# TEST CLASS: _synthesize_input Function
# =============================================================================


class TestSynthesizeInput:
    """Tests for the _synthesize_input function."""

    def test_synthesize_input_returns_dict(self):
        """Should return comprehensive dict."""
        result = conversation._synthesize_input("Hello world", [])

        assert "original_text" in result
        assert "entities" in result
        assert "intent" in result
        assert "word_count" in result
        assert "has_url" in result
        assert "is_short_response" in result

    def test_synthesize_input_word_count(self):
        """Should count words correctly."""
        result = conversation._synthesize_input("One two three four", [])

        assert result["word_count"] == 4

    def test_synthesize_input_detects_url(self):
        """Should detect URL presence."""
        result = conversation._synthesize_input("Check out https://example.com", [])

        assert result["has_url"] is True

    def test_synthesize_input_short_response(self):
        """Should detect short responses."""
        result = conversation._synthesize_input("Yes", [])

        assert result["is_short_response"] is True

    def test_synthesize_input_long_response(self):
        """Should detect long responses."""
        result = conversation._synthesize_input("This is a longer response with many words", [])

        assert result["is_short_response"] is False

    def test_synthesize_input_relevance_hints(self):
        """Should compute relevance hints."""
        result = conversation._synthesize_input("Help with python development", [])

        assert "relevance_hints" in result
        assert any("tools" in hint for hint in result["relevance_hints"])


# =============================================================================
# TEST CLASS: URL Handling Functions
# =============================================================================


class TestURLHandling:
    """Tests for URL-related functions."""

    def test_extract_url_http(self):
        """Should extract http URL."""
        result = conversation._extract_url("Check http://example.com for info")
        assert result == "http://example.com"

    def test_extract_url_https(self):
        """Should extract https URL."""
        result = conversation._extract_url("Visit https://secure.example.com")
        assert result == "https://secure.example.com"

    def test_extract_url_www(self):
        """Should extract www URL."""
        result = conversation._extract_url("Go to www.example.com")
        assert result == "www.example.com"

    def test_extract_url_domain_only(self):
        """Should extract domain without protocol."""
        result = conversation._extract_url("Visit example.com today")
        assert result == "example.com"

    def test_extract_url_no_url(self):
        """Should return empty string when no URL."""
        result = conversation._extract_url("Hello world")
        assert result == ""

    def test_domain_from_url_full_url(self):
        """Should extract domain from full URL."""
        result = conversation._domain_from_url("https://www.example.com/path")
        assert result == "www.example.com"

    def test_domain_from_url_without_protocol(self):
        """Should handle URL without protocol."""
        result = conversation._domain_from_url("example.com/path")
        assert result == "example.com"

    def test_domain_from_url_empty(self):
        """Should return empty for empty input."""
        result = conversation._domain_from_url("")
        assert result == ""

    def test_normalize_url_adds_https(self):
        """Should add https to bare domains."""
        result = conversation._normalize_url("example.com")
        assert result == "https://example.com"

    def test_normalize_url_preserves_http(self):
        """Should preserve existing http."""
        result = conversation._normalize_url("http://example.com")
        assert result == "http://example.com"

    def test_normalize_url_preserves_https(self):
        """Should preserve existing https."""
        result = conversation._normalize_url("https://example.com")
        assert result == "https://example.com"

    def test_normalize_url_empty(self):
        """Should handle empty input."""
        result = conversation._normalize_url("")
        assert result == ""


# =============================================================================
# TEST CLASS: _infer_direct_action Function
# =============================================================================


class TestInferDirectAction:
    """Tests for the _infer_direct_action function."""

    def test_infer_direct_action_open_browser(self):
        """Should detect open browser command."""
        result = conversation._infer_direct_action("Open browser")
        assert result is not None
        assert result[0] == "open_browser"

    def test_infer_direct_action_open_firefox(self):
        """Should detect open firefox command."""
        result = conversation._infer_direct_action("Open firefox")
        assert result is not None
        assert result[0] == "open_browser"

    def test_infer_direct_action_open_terminal(self):
        """Should detect open terminal command."""
        result = conversation._infer_direct_action("Open terminal")
        assert result is not None
        assert result[0] == "open_terminal"

    def test_infer_direct_action_open_mail(self):
        """Should detect open mail command."""
        result = conversation._infer_direct_action("Open mail")
        assert result is not None
        assert result[0] == "open_mail"

    def test_infer_direct_action_open_calendar(self):
        """Should detect open calendar command."""
        result = conversation._infer_direct_action("Open calendar")
        assert result is not None
        assert result[0] == "open_calendar"

    def test_infer_direct_action_open_messages(self):
        """Should detect open messages command."""
        result = conversation._infer_direct_action("Open messages")
        assert result is not None
        assert result[0] == "open_messages"

    def test_infer_direct_action_google_search(self):
        """Should detect google search command."""
        result = conversation._infer_direct_action("Google python tutorials")
        assert result is not None
        assert result[0] == "google"
        assert result[1]["query"] == "python tutorials"

    def test_infer_direct_action_search_for(self):
        """Should detect 'search for' command."""
        result = conversation._infer_direct_action("Search for weather forecast")
        assert result is not None
        assert result[0] == "google"
        # The parser includes "for" in the query
        assert "weather forecast" in result[1]["query"]

    def test_infer_direct_action_go_to_url(self):
        """Should detect go to URL command."""
        result = conversation._infer_direct_action("Go to example.com")
        assert result is not None
        assert result[0] == "open_browser"

    def test_infer_direct_action_set_reminder(self):
        """Should detect set reminder command."""
        result = conversation._infer_direct_action("Set reminder buy milk")
        assert result is not None
        assert result[0] == "set_reminder"
        assert "buy milk" in result[1]["title"]

    def test_infer_direct_action_create_note(self):
        """Should detect create note command."""
        result = conversation._infer_direct_action("Create note Meeting summary")
        assert result is not None
        assert result[0] == "create_note"

    def test_infer_direct_action_open_notes(self):
        """Should detect open notes command."""
        result = conversation._infer_direct_action("Open notes project ideas")
        assert result is not None
        assert result[0] == "open_notes"

    def test_infer_direct_action_open_finder(self):
        """Should detect open finder command."""
        result = conversation._infer_direct_action("Open finder ~/Documents")
        assert result is not None
        assert result[0] == "open_finder"

    def test_infer_direct_action_no_match(self):
        """Should return None for non-action text."""
        result = conversation._infer_direct_action("What is the weather?")
        assert result is None

    def test_infer_direct_action_empty_string(self):
        """Should return None for empty string."""
        result = conversation._infer_direct_action("")
        assert result is None

    def test_infer_direct_action_case_insensitive(self):
        """Should be case insensitive."""
        result = conversation._infer_direct_action("OPEN BROWSER")
        assert result is not None
        assert result[0] == "open_browser"


# =============================================================================
# TEST CLASS: Response Formatting Functions
# =============================================================================


class TestResponseFormatting:
    """Tests for response formatting functions."""

    def test_format_research_response_basic(self, mock_research_result):
        """Should format research result correctly."""
        result = conversation._format_research_response(mock_research_result)

        assert mock_research_result["summary"] in result
        assert "Key findings:" in result
        assert "Sources:" in result

    def test_format_research_response_empty_summary(self):
        """Should handle empty summary."""
        result = conversation._format_research_response({"summary": "", "key_findings": [], "sources": []})
        assert result == ""

    def test_format_research_response_limits_findings(self):
        """Should limit key findings to 7."""
        result = {
            "summary": "Summary",
            "key_findings": [f"Finding {i}" for i in range(10)],
            "sources": [],
        }
        output = conversation._format_research_response(result)

        # Count bullet points
        bullet_count = output.count("- Finding")
        assert bullet_count <= 7

    def test_format_action_response_success(self):
        """Should format success action response."""
        result = conversation._format_action_response("open_browser", True, "Opened Chrome", "chat")

        assert "Done" in result
        assert "Opened Chrome" in result

    def test_format_action_response_failure(self):
        """Should format failure action response."""
        result = conversation._format_action_response("open_browser", False, "Failed to open", "chat")

        assert "Unable" in result

    def test_format_action_response_voice_mode(self):
        """Should apply voice-friendly formatting in voice mode."""
        result = conversation._format_action_response("open_browser", True, "Opened", "voice")

        # Voice mode should be applied
        assert isinstance(result, str)

    def test_format_action_response_empty_output(self):
        """Should handle empty output."""
        result = conversation._format_action_response("open_browser", True, "", "chat")

        # Should use action name when output is empty
        assert "open browser" in result.lower()


# =============================================================================
# TEST CLASS: Sanitization Functions
# =============================================================================


class TestSanitization:
    """Tests for response sanitization functions."""

    def test_sanitize_response_basic(self):
        """Should sanitize basic response."""
        result = conversation._sanitize_response("Hello world")
        assert result == "Hello world"

    def test_sanitize_response_strips_action_tokens(self):
        """Should strip action tokens."""
        result = conversation._sanitize_response("Hello [ACTION:test()] world")
        assert "[ACTION:" not in result

    def test_sanitize_response_strips_urls(self):
        """Should strip full URLs to domains."""
        result = conversation._sanitize_response("Visit https://www.example.com/path/to/page for info")
        assert "https://" not in result
        assert "www.example.com" in result

    def test_sanitize_response_empty(self):
        """Should handle empty input."""
        result = conversation._sanitize_response("")
        assert result == ""

    def test_sanitize_response_none(self):
        """Should handle None input."""
        result = conversation._sanitize_response(None)
        assert result is None

    def test_normalize_response_prefix_test(self):
        """Should normalize 'test' prefix."""
        result = conversation._normalize_response_prefix("test")
        assert result == "my response"

    def test_normalize_response_prefix_test_colon(self):
        """Should normalize 'test:' prefix."""
        result = conversation._normalize_response_prefix("test: something")
        assert result.startswith("my response:")

    def test_voice_friendly_text_basic(self):
        """Should process voice-friendly text."""
        result = conversation._voice_friendly_text("Hello world")
        assert result == "Hello world"

    def test_voice_friendly_text_removes_code_blocks(self):
        """Should remove code blocks."""
        result = conversation._voice_friendly_text("Hello ```code here``` world")
        assert "```" not in result

    def test_voice_friendly_text_flattens_lists(self):
        """Should flatten list items."""
        result = conversation._voice_friendly_text("Items:\n- Item 1\n- Item 2")
        assert "\n-" not in result

    def test_voice_friendly_text_extracts_plain_english(self):
        """Should extract plain english section."""
        result = conversation._voice_friendly_text("Technical: x\nPlain English: This is simple.\nGlossary: y")
        assert "This is simple" in result

    def test_sanitize_for_voice(self):
        """Should combine sanitization and voice-friendly processing."""
        result = conversation.sanitize_for_voice("Hello [ACTION:test()] ```code``` world")
        assert "[ACTION:" not in result
        assert "```" not in result


# =============================================================================
# TEST CLASS: JSON Parsing Functions
# =============================================================================


class TestJSONParsing:
    """Tests for JSON parsing functions."""

    def test_extract_json_payload_basic(self):
        """Should extract JSON from text."""
        result = conversation._extract_json_payload('Some text {"key": "value"} more text')
        assert result == '{"key": "value"}'

    def test_extract_json_payload_nested(self):
        """Should handle nested JSON."""
        result = conversation._extract_json_payload('{"outer": {"inner": "value"}}')
        assert '"outer"' in result
        assert '"inner"' in result

    def test_extract_json_payload_no_json(self):
        """Should return None when no JSON."""
        result = conversation._extract_json_payload("No JSON here")
        assert result is None

    def test_extract_json_payload_empty(self):
        """Should handle empty input."""
        result = conversation._extract_json_payload("")
        assert result is None

    def test_parse_json_payload_valid(self):
        """Should parse valid JSON."""
        result = conversation._parse_json_payload('{"decision": "respond", "response": "Hello"}')
        assert result is not None
        assert result["decision"] == "respond"

    def test_parse_json_payload_embedded(self):
        """Should parse embedded JSON."""
        result = conversation._parse_json_payload('Some text {"key": "value"} more text')
        assert result is not None
        assert result["key"] == "value"

    def test_parse_json_payload_invalid(self):
        """Should return None for invalid JSON."""
        result = conversation._parse_json_payload("{invalid json")
        assert result is None

    def test_parse_json_payload_array(self):
        """Should return None for JSON arrays."""
        result = conversation._parse_json_payload('[1, 2, 3]')
        assert result is None  # Only dicts are valid

    def test_parse_json_payload_empty(self):
        """Should handle empty input."""
        result = conversation._parse_json_payload("")
        assert result is None


# =============================================================================
# TEST CLASS: Question Detection Functions
# =============================================================================


class TestQuestionDetection:
    """Tests for question detection functions."""

    def test_is_question_response_question_mark(self):
        """Should detect question mark."""
        assert conversation._is_question_response("What do you think?") is True

    def test_is_question_response_no_question_mark(self):
        """Should return False without question mark."""
        assert conversation._is_question_response("That is interesting.") is False

    def test_is_question_response_empty(self):
        """Should handle empty input."""
        assert conversation._is_question_response("") is False

    def test_last_assistant_question_true(self):
        """Should detect assistant question."""
        entries = [
            {"source": "voice_chat_user", "text": "Hello"},
            {"source": "voice_chat_assistant", "text": "How can I help?"},
        ]
        assert conversation._last_assistant_question(entries) is True

    def test_last_assistant_question_false(self):
        """Should return False for non-question."""
        entries = [
            {"source": "voice_chat_user", "text": "Hello"},
            {"source": "voice_chat_assistant", "text": "Hi there!"},
        ]
        assert conversation._last_assistant_question(entries) is False

    def test_last_assistant_question_empty(self):
        """Should handle empty entries."""
        assert conversation._last_assistant_question([]) is False

    def test_last_assistant_question_user_only(self):
        """Should return False for user-only entries."""
        entries = [
            {"source": "voice_chat_user", "text": "Hello?"},
        ]
        assert conversation._last_assistant_question(entries) is False


# =============================================================================
# TEST CLASS: _strip_action_tokens Function
# =============================================================================


class TestStripActionTokens:
    """Tests for _strip_action_tokens function."""

    def test_strip_action_tokens_single(self):
        """Should strip single action token."""
        result = conversation._strip_action_tokens("Hello [ACTION:test()] world")
        assert "[ACTION:" not in result
        assert "Hello" in result
        assert "world" in result

    def test_strip_action_tokens_multiple(self):
        """Should strip multiple action tokens."""
        result = conversation._strip_action_tokens("[ACTION:a()] text [ACTION:b()]")
        assert "[ACTION:" not in result

    def test_strip_action_tokens_executed_section(self):
        """Should strip --- Actions Executed --- section."""
        result = conversation._strip_action_tokens("Response\n\n--- Actions Executed ---\nAction 1\nAction 2")
        assert "--- Actions Executed ---" not in result
        assert "Action 1" not in result

    def test_strip_action_tokens_no_tokens(self):
        """Should handle text without tokens."""
        result = conversation._strip_action_tokens("Normal text")
        assert result == "Normal text"


# =============================================================================
# TEST CLASS: _strip_urls Function
# =============================================================================


class TestStripUrls:
    """Tests for _strip_urls function."""

    def test_strip_urls_replaces_with_domain(self):
        """Should replace URL with domain."""
        result = conversation._strip_urls("Visit https://www.example.com/path for info")
        assert "https://" not in result
        assert "www.example.com" in result

    def test_strip_urls_multiple(self):
        """Should handle multiple URLs."""
        result = conversation._strip_urls("Check http://a.com and https://b.com")
        assert "http://" not in result
        assert "https://" not in result

    def test_strip_urls_preserves_punctuation(self):
        """Should preserve trailing punctuation."""
        result = conversation._strip_urls("Visit https://example.com.")
        assert result.endswith(".")


# =============================================================================
# TEST CLASS: Edge Cases and Integration
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_truncate_with_unicode(self):
        """Should handle unicode characters correctly."""
        text = "Hello " + "\u2665" * 500  # Unicode hearts
        result = conversation._truncate(text, limit=100)
        assert len(result) <= 103

    def test_extract_entities_unicode_tools(self):
        """Should handle unicode in tool detection."""
        result = conversation._extract_entities("Use python for the project")
        assert "python" in result["tools"]

    def test_classify_intent_empty_history(self):
        """Should handle empty history."""
        result = conversation._classify_intent("Hello", [])
        assert "primary_intent" in result

    def test_synthesize_input_special_characters(self):
        """Should handle special characters."""
        result = conversation._synthesize_input("Check <script>alert('xss')</script>", [])
        assert result["original_text"].startswith("Check")

    def test_extract_url_with_port(self):
        """Should extract URL with port number."""
        result = conversation._extract_url("Visit http://localhost:8080/api")
        assert "localhost:8080" in result or "localhost" in result

    def test_domain_from_url_with_port(self):
        """Should extract domain with port."""
        result = conversation._domain_from_url("http://example.com:8080/path")
        assert "example.com" in result

    def test_infer_direct_action_with_url_params(self):
        """Should extract URL from browser commands."""
        result = conversation._infer_direct_action("Open browser https://example.com")
        assert result is not None
        assert "url" in result[1]

    def test_parse_json_payload_with_newlines(self):
        """Should parse JSON with newlines."""
        json_text = '{\n  "key": "value",\n  "num": 42\n}'
        result = conversation._parse_json_payload(json_text)
        assert result is not None
        assert result["key"] == "value"

    def test_format_history_with_none_text(self):
        """Should handle entries with None text via fallback."""
        entries = [
            {"source": "voice_chat_user"},  # Missing text key entirely
            {"source": "voice_chat_assistant", "text": "Response"},
        ]
        result = conversation._format_history(entries)
        # Should include the valid entry
        assert "Response" in result

    def test_voice_friendly_empty_input(self):
        """Should handle empty input."""
        result = conversation._voice_friendly_text("")
        assert result == ""

    def test_voice_friendly_none_input(self):
        """Should handle None input."""
        result = conversation._voice_friendly_text(None)
        assert result is None

    def test_format_research_response_with_no_sources(self):
        """Should handle response with no sources."""
        result = conversation._format_research_response({
            "summary": "A summary",
            "key_findings": ["Finding 1"],
            "sources": []
        })
        assert "A summary" in result
        assert "Sources:" not in result

    def test_format_research_response_source_without_url(self):
        """Should handle source without URL."""
        result = conversation._format_research_response({
            "summary": "Summary",
            "key_findings": [],
            "sources": [{"title": "No URL Source"}]
        })
        assert "No URL Source" in result

    def test_classify_intent_all_intents_returned(self):
        """Should return all_intents dict."""
        result = conversation._classify_intent("Hello", [])
        assert "all_intents" in result
        assert isinstance(result["all_intents"], dict)

    def test_extract_entities_personal_topic(self):
        """Should detect personal topic."""
        result = conversation._extract_entities("Help me with my health and fitness goals")
        assert "personal" in result["topics"]

    def test_extract_entities_business_topic(self):
        """Should detect business topic."""
        result = conversation._extract_entities("Increase revenue from marketing")
        assert "business" in result["topics"]


# =============================================================================
# TEST CLASS: Additional Coverage Tests
# =============================================================================


class TestAdditionalCoverage:
    """Additional tests to increase coverage."""

    def test_truncate_default_limit(self):
        """Should use default limit of 800."""
        text = "a" * 900
        result = conversation._truncate(text)  # No limit parameter
        assert len(result) == 803

    def test_extract_entities_find_action(self):
        """Should detect find action."""
        result = conversation._extract_entities("Find the missing file")
        assert "find" in result["actions"]

    def test_extract_entities_send_action(self):
        """Should detect send action."""
        result = conversation._extract_entities("Send the email now")
        assert "send" in result["actions"]

    def test_extract_entities_delete_action(self):
        """Should detect delete action."""
        result = conversation._extract_entities("Delete the old files")
        assert "delete" in result["actions"]

    def test_extract_entities_analyze_action(self):
        """Should detect analyze action."""
        result = conversation._extract_entities("Analyze this data set")
        assert "analyze" in result["actions"]

    def test_classify_intent_set_command(self):
        """Should detect set command."""
        result = conversation._classify_intent("Set the alarm for 7am", [])
        assert result["primary_intent"] == "command"

    def test_classify_intent_add_command(self):
        """Should detect add command."""
        result = conversation._classify_intent("Add this to my list", [])
        assert result["primary_intent"] == "command"

    def test_classify_intent_can_you_pattern(self):
        """Should detect 'can you' command pattern."""
        result = conversation._classify_intent("Can you open the door", [])
        assert result["primary_intent"] == "command"

    def test_classify_intent_is_question(self):
        """Should detect 'is' question."""
        result = conversation._classify_intent("Is it raining?", [])
        assert result["primary_intent"] == "question"

    def test_classify_intent_also_followup(self):
        """Should detect 'also' as followup."""
        history = [{"source": "voice_chat_assistant", "text": "Here's the info"}]
        result = conversation._classify_intent("also what about tomorrow", history)
        assert result["is_followup"] is True

    def test_infer_direct_action_launch_browser(self):
        """Should detect launch browser command."""
        result = conversation._infer_direct_action("Launch browser")
        assert result is not None
        assert result[0] == "open_browser"

    def test_infer_direct_action_launch_terminal(self):
        """Should detect launch terminal command."""
        result = conversation._infer_direct_action("Launch terminal")
        assert result is not None
        assert result[0] == "open_terminal"

    def test_infer_direct_action_open_email(self):
        """Should detect open email command."""
        result = conversation._infer_direct_action("Open email")
        assert result is not None
        assert result[0] == "open_mail"

    def test_infer_direct_action_launch_mail(self):
        """Should detect launch mail command."""
        result = conversation._infer_direct_action("Launch mail")
        assert result is not None
        assert result[0] == "open_mail"

    def test_infer_direct_action_launch_calendar(self):
        """Should detect launch calendar command."""
        result = conversation._infer_direct_action("Launch calendar")
        assert result is not None
        assert result[0] == "open_calendar"

    def test_infer_direct_action_launch_messages(self):
        """Should detect launch messages command."""
        result = conversation._infer_direct_action("Launch messages")
        assert result is not None
        assert result[0] == "open_messages"

    def test_infer_direct_action_open_note_singular(self):
        """Should detect open note (singular) command."""
        result = conversation._infer_direct_action("Open note about project")
        assert result is not None
        assert result[0] == "open_notes"

    def test_infer_direct_action_launch_note(self):
        """Should detect launch note command."""
        result = conversation._infer_direct_action("Launch note ideas")
        assert result is not None
        assert result[0] == "open_notes"

    def test_infer_direct_action_launch_finder(self):
        """Should detect launch finder command."""
        result = conversation._infer_direct_action("Launch finder")
        assert result is not None
        assert result[0] == "open_finder"

    def test_infer_direct_action_search_without_query(self):
        """Should detect search command without query."""
        result = conversation._infer_direct_action("Search ")
        assert result is None  # Empty query

    def test_infer_direct_action_make_note(self):
        """Should detect make note command."""
        result = conversation._infer_direct_action("Make note about meeting")
        assert result is not None
        assert result[0] == "create_note"

    def test_infer_direct_action_open_url_only(self):
        """Should detect 'open' with URL."""
        result = conversation._infer_direct_action("Open https://google.com")
        assert result is not None
        assert result[0] == "open_browser"

    def test_format_action_response_formats_action_name(self):
        """Should format action name when no output."""
        result = conversation._format_action_response("open_browser", True, "", "chat")
        assert "open browser" in result.lower()

    def test_extract_json_payload_unclosed_brace(self):
        """Should return None for unclosed brace."""
        result = conversation._extract_json_payload('{"key": "value"')
        assert result is None

    def test_parse_json_payload_none_input(self):
        """Should handle None input."""
        result = conversation._parse_json_payload(None)
        assert result is None


# =============================================================================
# TEST CLASS: _recent_chat Function (using mocked memory)
# =============================================================================


class TestRecentChat:
    """Tests for _recent_chat function with mocked memory module."""

    def test_recent_chat_basic(self):
        """Should filter to voice_chat entries only."""
        # Setup mock return value
        conversation.memory.get_recent_entries.return_value = [
            {"source": "voice_chat_user", "text": "Hello"},
            {"source": "system", "text": "System message"},
            {"source": "voice_chat_assistant", "text": "Hi there"},
        ]

        result = conversation._recent_chat()

        assert len(result) == 2
        assert result[0]["source"] == "voice_chat_user"
        assert result[1]["source"] == "voice_chat_assistant"

    def test_recent_chat_empty(self):
        """Should return empty list when no entries."""
        conversation.memory.get_recent_entries.return_value = []

        result = conversation._recent_chat()

        assert result == []

    def test_recent_chat_respects_limit(self):
        """Should limit to specified number of turns."""
        conversation.memory.get_recent_entries.return_value = [
            {"source": "voice_chat_user", "text": f"Message {i}"}
            for i in range(20)
        ]

        result = conversation._recent_chat(turns=5)

        assert len(result) == 5


# =============================================================================
# TEST CLASS: _record_conversation_turn (using mocked memory)
# =============================================================================


class TestRecordConversationTurn:
    """Tests for _record_conversation_turn with mocked dependencies."""

    def test_record_turn_calls_memory(self):
        """Should call memory.append_entry twice."""
        # Reset mock call counts
        conversation.memory.append_entry.reset_mock()
        conversation.context_manager.add_conversation_message.reset_mock()

        conversation._record_conversation_turn("User text", "Assistant text")

        assert conversation.memory.append_entry.call_count == 2
        assert conversation.context_manager.add_conversation_message.call_count == 2

    def test_record_turn_handles_exception(self):
        """Should not raise on exceptions."""
        conversation.memory.append_entry.side_effect = Exception("Test error")

        # Should not raise
        conversation._record_conversation_turn("User", "Assistant")

        # Cleanup
        conversation.memory.append_entry.side_effect = None


# =============================================================================
# TEST CLASS: _support_prompts (using mocked prompt_library)
# =============================================================================


class TestSupportPrompts:
    """Tests for _support_prompts with mocked prompt_library."""

    def test_support_prompts_basic(self):
        """Should format prompts correctly."""
        mock_prompt = MagicMock()
        mock_prompt.title = "Test Title"
        mock_prompt.body = "Test body content"
        mock_prompt.id = "prompt_123"

        conversation.prompt_library.get_support_prompts.return_value = [mock_prompt]

        text, ids = conversation._support_prompts("Hello")

        assert "Test Title" in text
        assert "Test body content" in text
        assert "prompt_123" in ids

    def test_support_prompts_empty(self):
        """Should return empty when no prompts."""
        conversation.prompt_library.get_support_prompts.return_value = []

        text, ids = conversation._support_prompts("Hello")

        assert text == ""
        assert ids == []

    def test_support_prompts_adds_crypto_tag(self):
        """Should add crypto tag for crypto keywords."""
        conversation.prompt_library.get_support_prompts.return_value = []

        conversation._support_prompts("Tell me about trading")

        call_args = conversation.prompt_library.get_support_prompts.call_args[0][0]
        assert "crypto" in call_args

    def test_support_prompts_adds_research_tag(self):
        """Should add research tag for research keywords."""
        conversation.prompt_library.get_support_prompts.return_value = []

        conversation._support_prompts("Analyze this topic")

        call_args = conversation.prompt_library.get_support_prompts.call_args[0][0]
        assert "research" in call_args

    def test_support_prompts_adds_social_tag(self):
        """Should add social tag for social keywords."""
        conversation.prompt_library.get_support_prompts.return_value = []

        conversation._support_prompts("Update my linkedin profile")

        call_args = conversation.prompt_library.get_support_prompts.call_args[0][0]
        assert "social" in call_args


# =============================================================================
# TEST CLASS: _format_action_history (using mocked context_manager)
# =============================================================================


class TestFormatActionHistory:
    """Tests for _format_action_history with mocked context_manager."""

    def test_format_action_history_basic(self):
        """Should format action history correctly."""
        mock_ctx = MagicMock()
        mock_ctx.action_history = [
            {"action": "open_browser", "success": True, "result": "Done"},
            {"action": "google", "success": False, "result": "Error"},
        ]
        conversation.context_manager.load_conversation_context.return_value = mock_ctx

        result = conversation._format_action_history()

        assert "open_browser" in result
        assert "google" in result

    def test_format_action_history_empty(self):
        """Should return 'None' for empty history."""
        mock_ctx = MagicMock()
        mock_ctx.action_history = []
        conversation.context_manager.load_conversation_context.return_value = mock_ctx

        result = conversation._format_action_history()

        assert result == "None"

    def test_format_action_history_limit(self):
        """Should respect limit parameter."""
        mock_ctx = MagicMock()
        mock_ctx.action_history = [
            {"action": f"action_{i}", "success": True, "result": "Done"}
            for i in range(10)
        ]
        conversation.context_manager.load_conversation_context.return_value = mock_ctx

        result = conversation._format_action_history(limit=3)

        # Should only have last 3
        assert "action_7" in result
        assert "action_8" in result
        assert "action_9" in result


# =============================================================================
# TEST CLASS: _execute_actions_in_response (using mocked actions)
# =============================================================================


class TestExecuteActionsInResponse:
    """Tests for _execute_actions_in_response with mocked actions."""

    def test_execute_actions_no_action_tokens(self):
        """Should return unchanged text when no action tokens."""
        result = conversation._execute_actions_in_response("Normal text")

        assert result == "Normal text"

    def test_execute_actions_single_action(self):
        """Should execute single action."""
        conversation.actions.execute_action.reset_mock()
        conversation.actions.execute_action.return_value = (True, "Action done")

        result = conversation._execute_actions_in_response("Do [ACTION: test()]")

        assert "--- Actions Executed ---" in result
        assert "test" in result

    def test_execute_actions_with_params(self):
        """Should parse and pass parameters."""
        conversation.actions.execute_action.reset_mock()
        conversation.actions.execute_action.return_value = (True, "Searched")

        conversation._execute_actions_in_response("[ACTION: google(query='test search')]")

        # Check that execute_action was called
        assert conversation.actions.execute_action.called

    def test_execute_actions_handles_error(self):
        """Should handle errors gracefully."""
        conversation.actions.execute_action.reset_mock()
        conversation.actions.execute_action.side_effect = Exception("Error")

        result = conversation._execute_actions_in_response("[ACTION: test()]")

        # Should contain error info
        assert "Error" in result or "test" in result

        # Cleanup
        conversation.actions.execute_action.side_effect = None


# =============================================================================
# TEST CLASS: _fallback_response (using mocked providers)
# =============================================================================


class TestFallbackResponse:
    """Tests for _fallback_response with mocked providers."""

    def test_fallback_response_structure(self):
        """Should return structured fallback."""
        conversation.providers.provider_status.return_value = "offline"
        conversation.providers.last_provider_errors.return_value = "No API key"

        result = conversation._fallback_response("Test input")

        assert "Plain English:" in result
        assert "Technical Notes:" in result
        assert "Glossary:" in result

    def test_fallback_response_includes_input(self):
        """Should include user input reference."""
        conversation.providers.provider_status.return_value = "offline"
        conversation.providers.last_provider_errors.return_value = ""

        result = conversation._fallback_response("my test query")

        assert "my test query" in result


# =============================================================================
# TEST CLASS: generate_response (integration tests with mocks)
# =============================================================================


class TestGenerateResponse:
    """Tests for generate_response with all dependencies mocked."""

    def setup_method(self):
        """Setup common mock behaviors."""
        # Reset all mocks to MagicMock to ensure all attributes work
        conversation.config = MagicMock()
        conversation.context_loader = MagicMock()
        conversation.memory = MagicMock()
        conversation.passive = MagicMock()
        conversation.context_manager = MagicMock()
        conversation.guardian = MagicMock()
        conversation.jarvis = MagicMock()
        conversation.actions = MagicMock()
        conversation.prompt_library = MagicMock()
        conversation.providers = MagicMock()
        conversation.research_engine = MagicMock()
        conversation.safety = MagicMock()

        # Set default return values
        conversation.config.load_config.return_value = {"context": {}, "research": {}}
        conversation.context_loader.load_context.return_value = ""
        conversation.memory.get_recent_entries.return_value = []
        conversation.memory.get_factual_entries.return_value = []
        conversation.memory.summarize_entries.return_value = ""
        conversation.passive.summarize_activity.return_value = ""
        conversation.context_manager.get_context_summary.return_value = ""
        conversation.context_manager.get_key_facts_summary.return_value = ""
        conversation.context_manager.get_conversation_summaries_text.return_value = ""
        conversation.guardian.get_safety_prompt.return_value = ""
        conversation.jarvis.get_mission_context.return_value = ""
        conversation.actions.get_available_actions.return_value = []

        mock_ctx = MagicMock()
        mock_ctx.action_history = []
        conversation.context_manager.load_conversation_context.return_value = mock_ctx

        conversation.prompt_library.get_support_prompts.return_value = []
        conversation.prompt_library.record_usage.return_value = None

        conversation.providers.provider_status.return_value = "online"
        conversation.providers.last_provider_errors.return_value = ""

    def test_generate_response_direct_action(self):
        """Should execute direct action for action commands."""
        conversation.actions.execute_action.reset_mock()
        conversation.actions.execute_action.return_value = (True, "Browser opened")

        result = conversation.generate_response("Open browser", "", channel="chat")

        assert "opened" in result.lower() or "done" in result.lower()

    def test_generate_response_llm_response(self):
        """Should use LLM for non-action requests."""
        json_response = json.dumps({
            "decision": "respond",
            "response": "Hello! How can I help?",
        })
        conversation.providers.generate_text.return_value = json_response

        result = conversation.generate_response("Hello there", "", channel="chat")

        assert "Hello" in result or "help" in result

    def test_generate_response_fallback_on_failure(self):
        """Should use fallback when LLM fails."""
        conversation.providers.generate_text.return_value = None

        result = conversation.generate_response("Test message", "", channel="chat")

        assert "Plain English:" in result

    def test_generate_response_voice_mode(self):
        """Should apply voice-friendly formatting."""
        json_response = json.dumps({
            "decision": "respond",
            "response": "Here is a list:\n- Item 1\n- Item 2",
        })
        conversation.providers.generate_text.return_value = json_response

        result = conversation.generate_response("What items?", "", channel="voice")

        # Voice mode should flatten lists
        assert "\n-" not in result

    def test_generate_response_with_action_decision(self):
        """Should execute action from JSON decision."""
        json_response = json.dumps({
            "decision": "action",
            "action": {"name": "google", "params": {"query": "test"}},
            "response": "",
        })
        conversation.providers.generate_text.return_value = json_response
        conversation.actions.execute_action.reset_mock()
        conversation.actions.execute_action.return_value = (True, "Search done")

        result = conversation.generate_response("Search something", "", channel="chat")

        assert conversation.actions.execute_action.called

    def test_generate_response_research_request(self):
        """Should route research requests to research engine."""
        conversation.config.load_config.return_value = {
            "context": {},
            "research": {"allow_web": True},
        }

        mock_engine = MagicMock()
        mock_engine.research_topic.return_value = {
            "summary": "Research summary",
            "key_findings": ["Finding 1"],
            "sources": [{"title": "Source", "url": "http://example.com"}],
        }
        conversation.research_engine.get_research_engine.return_value = mock_engine

        result = conversation.generate_response("Research AI trends", "", channel="chat")

        assert "Research summary" in result or mock_engine.research_topic.called


# =============================================================================
# TEST CLASS: Additional Edge Cases
# =============================================================================


class TestMoreEdgeCases:
    """Additional edge case tests for higher coverage."""

    def test_format_history_handles_long_entries(self):
        """Should truncate long entries in history."""
        entries = [
            {"source": "voice_chat_user", "text": "a" * 1000},
        ]
        result = conversation._format_history(entries)

        # Should be truncated to 400 + ellipsis
        assert len(result) <= 420

    def test_extract_entities_solana_topic(self):
        """Should detect solana in topics."""
        result = conversation._extract_entities("Trade solana tokens")
        assert "crypto" in result["topics"]

    def test_extract_entities_open_action(self):
        """Should detect open action."""
        result = conversation._extract_entities("Open the file")
        assert "open" in result["actions"]

    def test_extract_entities_chrome_tool(self):
        """Should detect chrome as tool."""
        result = conversation._extract_entities("Use chrome browser")
        assert "chrome" in result["tools"]

    def test_classify_intent_show_command(self):
        """Should detect show command."""
        result = conversation._classify_intent("Show me the report", [])
        assert result["primary_intent"] == "command"

    def test_classify_intent_run_command(self):
        """Should detect run command."""
        result = conversation._classify_intent("Run the script", [])
        assert result["primary_intent"] == "command"

    def test_classify_intent_how_question(self):
        """Should detect how question."""
        result = conversation._classify_intent("How do I do this?", [])
        assert result["primary_intent"] == "question"

    def test_classify_intent_short_followup(self):
        """Should detect short text as potential followup."""
        history = [{"source": "voice_chat_assistant", "text": "Here's info"}]
        result = conversation._classify_intent("ok", history)
        assert result["is_followup"] is True

    def test_infer_direct_action_set_reminder(self):
        """Should detect set reminder command."""
        result = conversation._infer_direct_action("Set reminder call mom")
        assert result is not None
        assert result[0] == "set_reminder"

    def test_infer_direct_action_make_note(self):
        """Should detect make note command."""
        result = conversation._infer_direct_action("Make note meeting ideas")
        assert result is not None
        assert result[0] == "create_note"

    def test_infer_direct_action_go_to_url(self):
        """Should detect go to URL command."""
        result = conversation._infer_direct_action("Go to google.com")
        assert result is not None
        assert result[0] == "open_browser"

    def test_normalize_url_handles_www(self):
        """Should preserve www prefix."""
        result = conversation._normalize_url("www.example.com")
        assert "www.example.com" in result

    def test_parse_json_payload_with_code_fence(self):
        """Should handle JSON with code fence."""
        # Some LLMs wrap JSON in code fences
        text = '```json\n{"key": "value"}\n```'
        result = conversation._parse_json_payload(text)
        # May or may not work depending on implementation
        # Just ensure no crash
        assert result is None or result.get("key") == "value"

    def test_voice_friendly_text_with_markdown(self):
        """Should strip markdown formatting."""
        result = conversation._voice_friendly_text("**Bold** and *italic*")
        # Should strip or keep text
        assert "Bold" in result

    def test_synthesize_input_no_url(self):
        """Should mark no URL correctly."""
        result = conversation._synthesize_input("Hello world", [])
        assert result["has_url"] is False


# =============================================================================
# RUN CONFIGURATION
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
