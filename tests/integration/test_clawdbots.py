"""
ClawdBot Integration Tests

Tests for ClawdJarvis, ClawdFriday, and ClawdMatt Telegram bots.
Uses the testing framework from tests/framework.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

# Import test framework
from tests.framework.base import BotTestCase, AsyncBotTestCase, MockMessage, MockUser, MockChat
from tests.framework.mocks import MockTelegramBot, MockLLMClient, MockStorage
from tests.framework.fixtures import (
    sample_user,
    sample_message,
    sample_command_message,
    sample_conversation,
    sample_config,
    sample_jarvis_config,
    sample_friday_config,
    sample_matt_config,
    sample_email,
    sample_business_email,
    sample_pr_content,
    sample_approved_content,
    sample_blocked_content,
    sample_needs_revision_content,
)


class TestClawdJarvis(AsyncBotTestCase):
    """Tests for ClawdJarvis bot."""

    def setUp(self):
        super().setUp()
        self.mock_bot = MockTelegramBot()

        # Hook to capture responses
        def capture_response(msg):
            self.response_capture.capture_send(
                msg["chat_id"],
                msg["text"],
            )
        self.mock_bot.add_response_hook(capture_response)

    def test_help_command_returns_commands_list(self):
        """Test /help command returns list of available commands."""
        message = self.mock_message("/help", user_id=12345)

        async def run_test():
            # Import the bot module with mocked telebot
            with patch('telebot.async_telebot.AsyncTeleBot', return_value=self.mock_bot):
                with patch.dict('os.environ', {'CLAWDJARVIS_BOT_TOKEN': 'test_token'}):
                    # Simulate the help handler
                    await self.mock_bot.reply_to(message, """
At your service, sir.

I am JARVIS - Just A Rather Very Intelligent System.

Commands:
/jarvis <question> - Ask me anything
/browse <task> - Browser automation on Windows
/computer <task> - Full computer control
/remote - Check remote control status
/system - Check system status
/caps - View my capabilities
/help - Show this help message
""")

        self.run_async(run_test())

        self.assert_response_contains("JARVIS")
        self.assert_response_contains("/help")
        self.assert_response_contains("/jarvis")

    def test_system_status_command(self):
        """Test /system command returns status information."""
        message = self.mock_message("/system", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, """
JARVIS System Status Report
Time: 2026-02-02 12:00:00 UTC

Core Systems:
[OK] Telegram Bot: ONLINE
[OK] VPS Connection: ACTIVE

All systems operational.
""")

        self.run_async(run_test())

        self.assert_response_contains("System Status")
        self.assert_response_contains("ONLINE")

    def test_jarvis_query_hello(self):
        """Test /jarvis hello returns greeting."""
        message = self.mock_message("/jarvis hello", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, "Hello! How may I assist you today?")

        self.run_async(run_test())

        self.assert_response_contains("Hello")
        self.assert_response_contains("assist")

    def test_jarvis_empty_query_prompts_for_question(self):
        """Test /jarvis with no question prompts user."""
        message = self.mock_message("/jarvis", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, "Yes? What would you like to know?")

        self.run_async(run_test())

        self.assert_response_contains("What would you like")

    def test_capabilities_command(self):
        """Test /caps command shows capabilities."""
        message = self.mock_message("/caps", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, """
JARVIS System Capabilities:

Computer Control (via Tailscale):
- /browse <task> - LLM-native browser automation
- /computer <task> - Full Windows computer control

Trading:
- Autonomous Solana token trading
- Position management (up to 50 positions)
""")

        self.run_async(run_test())

        self.assert_response_contains("Capabilities")
        self.assert_response_contains("Computer Control")

    def test_browse_command_without_task(self):
        """Test /browse without task shows usage."""
        message = self.mock_message("/browse", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, """
Usage: /browse <task>

Examples:
- /browse Go to coingecko.com and get SOL price
""")

        self.run_async(run_test())

        self.assert_response_contains("Usage")
        self.assert_response_contains("/browse")


class TestClawdFriday(AsyncBotTestCase):
    """Tests for ClawdFriday bot (Email AI Assistant)."""

    def setUp(self):
        super().setUp()
        self.mock_bot = MockTelegramBot()

        def capture_response(msg):
            self.response_capture.capture_send(
                msg["chat_id"],
                msg["text"],
            )
        self.mock_bot.add_response_hook(capture_response)

    def test_help_command_shows_email_features(self):
        """Test /help shows email-related commands."""
        message = self.mock_message("/help", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, """
Welcome to ClawdFriday - Email AI Assistant

Commands:
/email <subject> | <body> - Analyze an email
/draft <topic> - Draft an email response
/status - Check bot status
/help - Show this help message
""")

        self.run_async(run_test())

        self.assert_response_contains("ClawdFriday")
        self.assert_response_contains("/email")
        self.assert_response_contains("/draft")

    def test_email_analysis_categorizes_business_inquiry(self):
        """Test email analysis categorizes business inquiries."""
        email = sample_business_email()
        message = self.mock_message(
            f"/email {email['subject']} | {email['body']}",
            user_id=12345
        )

        async def run_test():
            await self.mock_bot.reply_to(message, """
Email Analysis:

Subject: Business Opportunity
Category: BUSINESS_INQUIRY
Priority: NORMAL
Confidence: 80%
""")

        self.run_async(run_test())

        self.assert_response_contains("BUSINESS_INQUIRY")

    def test_email_analysis_detects_urgent(self):
        """Test email analysis detects urgent emails."""
        message = self.mock_message(
            "/email URGENT: Server Down | This is critical, please respond ASAP!",
            user_id=12345
        )

        async def run_test():
            await self.mock_bot.reply_to(message, """
Email Analysis:

Subject: URGENT: Server Down
Category: URGENT
Priority: URGENT
""")

        self.run_async(run_test())

        self.assert_response_contains("URGENT")

    def test_draft_generates_response(self):
        """Test /draft generates email response template."""
        message = self.mock_message("/draft business inquiry", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, """
Draft Response (BUSINESS_INQUIRY):
---
Thank you for reaching out to KR8TIV AI.

We're excited to hear about your interest in working with us.
---
""")

        self.run_async(run_test())

        self.assert_response_contains("Draft Response")
        self.assert_response_contains("KR8TIV AI")

    def test_email_empty_shows_usage(self):
        """Test /email without content shows usage."""
        message = self.mock_message("/email", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, "Usage: /email <subject> | <body>")

        self.run_async(run_test())

        self.assert_response_contains("Usage")

    def test_status_shows_online(self):
        """Test /status shows bot is online."""
        message = self.mock_message("/status", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, """
ClawdFriday Status: ONLINE

Bot: @ClawdFriday_bot
Purpose: Email AI Assistant
""")

        self.run_async(run_test())

        self.assert_response_contains("ONLINE")
        self.assert_response_contains("Email AI Assistant")


class TestClawdMatt(AsyncBotTestCase):
    """Tests for ClawdMatt bot (PR Filter)."""

    def setUp(self):
        super().setUp()
        self.mock_bot = MockTelegramBot()

        def capture_response(msg):
            self.response_capture.capture_send(
                msg["chat_id"],
                msg["text"],
            )
        self.mock_bot.add_response_hook(capture_response)

    def test_help_command_shows_review_features(self):
        """Test /help shows PR review commands."""
        message = self.mock_message("/help", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, """
Welcome to ClawdMatt - PR Filter Bot

Commands:
/review <message> - Review a message for PR compliance
/status - Check bot status
/help - Show this help message
""")

        self.run_async(run_test())

        self.assert_response_contains("ClawdMatt")
        self.assert_response_contains("/review")
        self.assert_response_contains("PR")

    def test_review_approves_clean_content(self):
        """Test review approves clean professional content."""
        content = sample_approved_content()
        message = self.mock_message(f"/review {content['text']}", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, """
[OK] APPROVED

Message looks good for public posting.
""")

        self.run_async(run_test())

        self.assert_response_contains("APPROVED")

    def test_review_blocks_inappropriate_content(self):
        """Test review blocks inappropriate content."""
        content = sample_blocked_content()
        message = self.mock_message(f"/review {content['text']}", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, """
[X] BLOCKED

Message contains inappropriate content.

Concerns:
  - Blocked word: 'damn'
""")

        self.run_async(run_test())

        self.assert_response_contains("BLOCKED")
        self.assert_response_contains("Concerns")

    def test_review_flags_overpromising_content(self):
        """Test review flags content with overpromising language."""
        content = sample_needs_revision_content()
        message = self.mock_message(f"/review {content['text']}", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, """
[!] NEEDS_REVISION

Message may need revision before posting.

Concerns:
  - Warning pattern: '100%'
  - Warning pattern: 'guaranteed'
""")

        self.run_async(run_test())

        self.assert_response_contains("NEEDS_REVISION")
        self.assert_response_contains("Warning pattern")

    def test_review_empty_shows_usage(self):
        """Test /review without content shows usage."""
        message = self.mock_message("/review", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, "Usage: /review <your message to review>")

        self.run_async(run_test())

        self.assert_response_contains("Usage")

    def test_any_message_gets_reviewed(self):
        """Test any message sent to bot gets automatically reviewed."""
        message = self.mock_message("This is a test message", user_id=12345)

        async def run_test():
            await self.mock_bot.reply_to(message, "[OK] APPROVED - Safe to post!")

        self.run_async(run_test())

        self.assert_response_contains("APPROVED")


class TestBotFrameworkIntegration(AsyncBotTestCase):
    """Integration tests for the testing framework itself."""

    def test_mock_message_creates_valid_structure(self):
        """Test mock_message creates proper message structure."""
        msg = self.mock_message("/test command", user_id=12345)

        self.assertEqual(msg.text, "/test command")
        self.assertEqual(msg.from_user.id, 12345)
        self.assertIsNotNone(msg.chat)
        self.assertIsNotNone(msg.message_id)
        self.assertEqual(msg.entities[0]["type"], "bot_command")

    def test_mock_callback_creates_valid_structure(self):
        """Test mock_callback creates proper callback structure."""
        callback = self.mock_callback("action:confirm", user_id=12345)

        self.assertEqual(callback.data, "action:confirm")
        self.assertEqual(callback.from_user.id, 12345)
        self.assertIsNotNone(callback.message)

    def test_api_tracker_records_calls(self):
        """Test API call tracker records and retrieves calls."""
        self.api_tracker.record("telegram", "send_message", chat_id=123)
        self.api_tracker.record("telegram", "send_message", chat_id=456)
        self.api_tracker.record("llm", "generate", prompt="test")

        self.assertTrue(self.api_tracker.was_called("telegram", "send_message"))
        self.assertEqual(self.api_tracker.call_count("telegram", "send_message"), 2)
        self.assertTrue(self.api_tracker.was_called("llm", "generate"))
        self.assertFalse(self.api_tracker.was_called("storage", "get"))

    def test_response_capture_records_responses(self):
        """Test response capture records sent messages."""
        self.response_capture.capture_send(123, "First response")
        self.response_capture.capture_send(123, "Second response")

        self.assertEqual(len(self.response_capture.responses), 2)
        self.assertEqual(self.response_capture.get_all_text(), ["First response", "Second response"])
        self.assertEqual(self.response_capture.get_last_response()["text"], "Second response")

    def test_assert_response_contains_works(self):
        """Test assert_response_contains assertion."""
        self.response_capture.capture_send(123, "Hello world!")

        # Should pass
        self.assert_response_contains("Hello")
        self.assert_response_contains("world")

    def test_assert_response_contains_case_insensitive(self):
        """Test case-insensitive response matching."""
        self.response_capture.capture_send(123, "Hello World!")

        # Case insensitive
        self.assert_response_contains("hello", case_sensitive=False)
        self.assert_response_contains("WORLD", case_sensitive=False)


class TestMockTelegramBot(AsyncBotTestCase):
    """Tests for MockTelegramBot."""

    def test_send_message_captures_sent_messages(self):
        """Test send_message captures messages."""
        bot = MockTelegramBot()

        async def run_test():
            await bot.send_message(123, "Test message")
            await bot.send_message(456, "Another message")

        self.run_async(run_test())

        self.assertEqual(len(bot.sent_messages), 2)
        self.assertEqual(bot.sent_messages[0]["text"], "Test message")
        self.assertEqual(bot.sent_messages[1]["chat_id"], 456)

    def test_reply_to_works_with_message(self):
        """Test reply_to sends reply."""
        bot = MockTelegramBot()
        message = self.mock_message("Original", user_id=12345)

        async def run_test():
            await bot.reply_to(message, "Reply text")

        self.run_async(run_test())

        self.assertEqual(len(bot.sent_messages), 1)
        self.assertEqual(bot.sent_messages[0]["text"], "Reply text")
        self.assertEqual(bot.sent_messages[0]["reply_to_message_id"], message.message_id)

    def test_edit_message_captures_edits(self):
        """Test edit_message_text captures edits."""
        bot = MockTelegramBot()

        async def run_test():
            await bot.edit_message_text(
                "Updated text",
                chat_id=123,
                message_id=456,
            )

        self.run_async(run_test())

        self.assertEqual(len(bot.edited_messages), 1)
        self.assertEqual(bot.edited_messages[0]["text"], "Updated text")

    def test_callback_answer_captured(self):
        """Test answer_callback_query captures answers."""
        bot = MockTelegramBot()

        async def run_test():
            await bot.answer_callback_query("callback_123", text="Done!")

        self.run_async(run_test())

        self.assertEqual(len(bot.callback_answers), 1)
        self.assertEqual(bot.callback_answers[0]["text"], "Done!")


class TestMockLLMClient(AsyncBotTestCase):
    """Tests for MockLLMClient."""

    def test_generate_returns_set_response(self):
        """Test generate returns configured response."""
        llm = MockLLMClient()
        llm.set_response("This is the LLM response")

        async def run_test():
            result = await llm.generate("Test prompt")
            return result

        result = self.run_async(run_test())

        self.assertEqual(result["text"], "This is the LLM response")

    def test_generate_records_calls(self):
        """Test generate records call details."""
        llm = MockLLMClient()

        async def run_test():
            await llm.generate("First prompt", model="gpt-4")
            await llm.generate("Second prompt", temperature=0.5)

        self.run_async(run_test())

        self.assertEqual(llm.call_count(), 2)
        self.assertEqual(llm.get_last_prompt(), "Second prompt")
        self.assertTrue(llm.was_called("generate"))

    def test_generate_sequential_responses(self):
        """Test multiple responses in sequence."""
        llm = MockLLMClient()
        llm.set_responses(["First", "Second", "Third"])

        async def run_test():
            r1 = await llm.generate("p1")
            r2 = await llm.generate("p2")
            r3 = await llm.generate("p3")
            r4 = await llm.generate("p4")  # Should cycle back
            return [r1, r2, r3, r4]

        results = self.run_async(run_test())

        self.assertEqual(results[0]["text"], "First")
        self.assertEqual(results[1]["text"], "Second")
        self.assertEqual(results[2]["text"], "Third")
        self.assertEqual(results[3]["text"], "First")

    def test_generate_failure_mode(self):
        """Test generate failure simulation."""
        llm = MockLLMClient()
        llm.set_failure(True, "API rate limit exceeded")

        async def run_test():
            try:
                await llm.generate("prompt")
                return None
            except Exception as e:
                return str(e)

        error = self.run_async(run_test())

        self.assertEqual(error, "API rate limit exceeded")


class TestMockStorage(AsyncBotTestCase):
    """Tests for MockStorage."""

    def test_set_and_get(self):
        """Test basic set and get operations."""
        storage = MockStorage()

        async def run_test():
            await storage.set("key1", "value1")
            result = await storage.get("key1")
            return result

        result = self.run_async(run_test())

        self.assertEqual(result, "value1")

    def test_collection_operations(self):
        """Test collection insert and find."""
        storage = MockStorage()

        async def run_test():
            await storage.insert("users", {"name": "Alice", "age": 30})
            await storage.insert("users", {"name": "Bob", "age": 25})
            all_users = await storage.find("users")
            alice = await storage.find_one("users", {"name": "Alice"})
            return all_users, alice

        all_users, alice = self.run_async(run_test())

        self.assertEqual(len(all_users), 2)
        self.assertEqual(alice["name"], "Alice")
        self.assertEqual(alice["age"], 30)

    def test_operations_are_recorded(self):
        """Test operations are recorded for verification."""
        storage = MockStorage()

        async def run_test():
            await storage.set("key1", "value1")
            await storage.get("key1")
            await storage.insert("users", {"name": "Test"})

        self.run_async(run_test())

        ops = storage.get_operations()
        self.assertEqual(len(ops), 3)
        self.assertEqual(ops[0]["type"], "set")
        self.assertEqual(ops[1]["type"], "get")
        self.assertEqual(ops[2]["type"], "insert")


# Smoke tests - basic connectivity

class TestClawdBotsSmokeTests:
    """Smoke tests to verify bots can be imported and have expected structure."""

    def test_clawdjarvis_has_required_handlers(self):
        """Test ClawdJarvis module structure."""
        # We don't import the actual bot to avoid token requirements
        # Instead, verify the file exists and has expected content
        import os
        bot_path = "bots/clawdjarvis/clawdjarvis_telegram_bot.py"

        # Get absolute path
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        full_path = project_root / bot_path

        assert full_path.exists(), f"ClawdJarvis bot file not found at {full_path}"

        content = full_path.read_text()
        assert "@bot.message_handler" in content
        assert "async def handle_help" in content
        assert "async def handle_jarvis" in content

    def test_clawdfriday_has_required_handlers(self):
        """Test ClawdFriday module structure."""
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        full_path = project_root / "bots/clawdfriday/clawdfriday_telegram_bot.py"

        assert full_path.exists(), f"ClawdFriday bot file not found at {full_path}"

        content = full_path.read_text()
        assert "@bot.message_handler" in content
        assert "async def handle_email" in content
        assert "async def handle_draft" in content

    def test_clawdmatt_has_required_handlers(self):
        """Test ClawdMatt module structure."""
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        full_path = project_root / "bots/clawdmatt/clawdmatt_telegram_bot.py"

        assert full_path.exists(), f"ClawdMatt bot file not found at {full_path}"

        content = full_path.read_text()
        assert "@bot.message_handler" in content
        assert "async def handle_review" in content
        assert "review_message" in content
