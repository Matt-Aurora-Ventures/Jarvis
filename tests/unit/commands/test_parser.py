"""
Unit tests for the CommandParser system.

Tests the command parsing infrastructure including:
- Message parsing to extract command and arguments
- Argument extraction with patterns
- Argument validation against schemas
"""

import pytest
from typing import Dict, Any, List, Optional


class TestCommandParserCreation:
    """Test CommandParser instantiation."""

    def test_parser_creation(self):
        """Test creating a parser."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        assert parser is not None

    def test_parser_creation_with_prefix(self):
        """Test creating parser with custom prefix."""
        from core.commands.parser import CommandParser

        parser = CommandParser(prefix="!")

        assert parser.prefix == "!"


class TestMessageParsing:
    """Test message parsing."""

    def test_parse_simple_command(self):
        """Test parsing a simple command."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("/help")

        assert result.command == "help"
        assert result.args == []
        assert result.raw_args == ""

    def test_parse_command_with_args(self):
        """Test parsing command with arguments."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("/trade SOL 10")

        assert result.command == "trade"
        assert result.args == ["SOL", "10"]
        assert result.raw_args == "SOL 10"

    def test_parse_command_with_quoted_args(self):
        """Test parsing command with quoted arguments."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse('/send "Hello World" @user')

        assert result.command == "send"
        assert result.args == ["Hello World", "@user"]

    def test_parse_non_command(self):
        """Test parsing non-command message."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("Hello world")

        assert result.command is None
        assert result.is_command is False

    def test_parse_command_with_bot_mention(self):
        """Test parsing command with @botname suffix."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("/status@JarvisBot extra args")

        assert result.command == "status"
        assert result.args == ["extra", "args"]

    def test_parse_empty_message(self):
        """Test parsing empty message."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("")

        assert result.command is None
        assert result.is_command is False

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only message."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("   ")

        assert result.command is None
        assert result.is_command is False

    def test_parse_prefix_only(self):
        """Test parsing just the prefix."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("/")

        assert result.command is None
        assert result.is_command is False

    def test_parse_preserves_case_in_args(self):
        """Test that argument case is preserved."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("/trade SOL BONK")

        assert result.args == ["SOL", "BONK"]  # Case preserved

    def test_parse_command_lowercase(self):
        """Test command is normalized to lowercase."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("/HELP")

        assert result.command == "help"

    def test_parse_custom_prefix(self):
        """Test parsing with custom prefix."""
        from core.commands.parser import CommandParser

        parser = CommandParser(prefix="!")

        result = parser.parse("!help")

        assert result.command == "help"
        assert parser.parse("/help").command is None


class TestParsedCommandObject:
    """Test ParsedCommand object properties."""

    def test_parsed_command_is_command(self):
        """Test is_command property."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("/help")
        assert result.is_command is True

        result = parser.parse("hello")
        assert result.is_command is False

    def test_parsed_command_original_text(self):
        """Test original_text property."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("/help me please")

        assert result.original_text == "/help me please"

    def test_parsed_command_arg_count(self):
        """Test arg_count property."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("/trade SOL 10 fast")

        assert result.arg_count == 3

    def test_parsed_command_get_arg(self):
        """Test get_arg method with default."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        result = parser.parse("/trade SOL")

        assert result.get_arg(0) == "SOL"
        assert result.get_arg(1) is None
        assert result.get_arg(1, "default") == "default"


class TestArgumentExtraction:
    """Test argument extraction with patterns."""

    def test_extract_args_simple(self):
        """Test extracting arguments with simple pattern."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        pattern = r"(\w+)\s+(\d+)"  # <token> <amount>
        args = parser.extract_args("/trade SOL 100", pattern)

        assert args == {"0": "SOL", "1": "100"}

    def test_extract_args_named_groups(self):
        """Test extracting arguments with named groups."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        pattern = r"(?P<token>\w+)\s+(?P<amount>\d+)"
        args = parser.extract_args("/trade SOL 100", pattern)

        assert args["token"] == "SOL"
        assert args["amount"] == "100"

    def test_extract_args_no_match(self):
        """Test extracting args when pattern doesn't match."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        pattern = r"(\w+)\s+(\d+)"
        args = parser.extract_args("/trade", pattern)

        assert args == {}

    def test_extract_args_optional_groups(self):
        """Test extracting optional arguments."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        pattern = r"(?P<token>\w+)(?:\s+(?P<amount>\d+))?"

        args1 = parser.extract_args("/trade SOL 100", pattern)
        assert args1["token"] == "SOL"
        assert args1["amount"] == "100"

        args2 = parser.extract_args("/trade SOL", pattern)
        assert args2["token"] == "SOL"
        assert args2.get("amount") is None

    def test_extract_args_complex_pattern(self):
        """Test extracting args with complex pattern."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        # Pattern for: /limit buy SOL 100 @ 50.5
        pattern = r"(?P<side>buy|sell)\s+(?P<token>\w+)\s+(?P<amount>\d+)\s*@\s*(?P<price>[\d.]+)"
        args = parser.extract_args("/limit buy SOL 100 @ 50.5", pattern)

        assert args["side"] == "buy"
        assert args["token"] == "SOL"
        assert args["amount"] == "100"
        assert args["price"] == "50.5"


class TestArgumentValidation:
    """Test argument validation against schemas."""

    def test_validate_args_simple_types(self):
        """Test validating simple type constraints."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        schema = {
            "token": {"type": "string", "required": True},
            "amount": {"type": "number", "required": True}
        }

        args = {"token": "SOL", "amount": "100"}

        is_valid = parser.validate_args(args, schema)
        assert is_valid is True

    def test_validate_args_missing_required(self):
        """Test validation fails on missing required field."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        schema = {
            "token": {"type": "string", "required": True},
            "amount": {"type": "number", "required": True}
        }

        args = {"token": "SOL"}  # Missing amount

        is_valid = parser.validate_args(args, schema)
        assert is_valid is False

    def test_validate_args_optional_field(self):
        """Test validation passes with missing optional field."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        schema = {
            "token": {"type": "string", "required": True},
            "amount": {"type": "number", "required": False}
        }

        args = {"token": "SOL"}

        is_valid = parser.validate_args(args, schema)
        assert is_valid is True

    def test_validate_args_type_coercion(self):
        """Test type coercion during validation."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        schema = {
            "amount": {"type": "number", "required": True}
        }

        args = {"amount": "100"}  # String that can be number

        is_valid = parser.validate_args(args, schema)
        assert is_valid is True

    def test_validate_args_invalid_type(self):
        """Test validation fails on invalid type."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        schema = {
            "amount": {"type": "number", "required": True}
        }

        args = {"amount": "not_a_number"}

        is_valid = parser.validate_args(args, schema)
        assert is_valid is False

    def test_validate_args_with_choices(self):
        """Test validation with allowed choices."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        schema = {
            "side": {"type": "string", "choices": ["buy", "sell"]}
        }

        assert parser.validate_args({"side": "buy"}, schema) is True
        assert parser.validate_args({"side": "sell"}, schema) is True
        assert parser.validate_args({"side": "hold"}, schema) is False

    def test_validate_args_with_min_max(self):
        """Test validation with min/max constraints."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        schema = {
            "amount": {"type": "number", "min": 1, "max": 1000}
        }

        assert parser.validate_args({"amount": "100"}, schema) is True
        assert parser.validate_args({"amount": "0"}, schema) is False
        assert parser.validate_args({"amount": "1001"}, schema) is False

    def test_validate_args_with_pattern(self):
        """Test validation with regex pattern."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        schema = {
            "address": {"type": "string", "pattern": r"^[A-Za-z0-9]{32,44}$"}
        }

        valid_address = "So11111111111111111111111111111111111111112"
        invalid_address = "short"

        assert parser.validate_args({"address": valid_address}, schema) is True
        assert parser.validate_args({"address": invalid_address}, schema) is False

    def test_validate_args_returns_errors(self):
        """Test validation returns detailed errors."""
        from core.commands.parser import CommandParser, ValidationResult

        parser = CommandParser()

        schema = {
            "token": {"type": "string", "required": True},
            "amount": {"type": "number", "required": True, "min": 1}
        }

        args = {"amount": "0"}  # Missing token, amount too low

        result = parser.validate_args_detailed(args, schema)

        assert isinstance(result, ValidationResult)
        assert result.is_valid is False
        assert len(result.errors) == 2
        assert any("token" in e.field for e in result.errors)
        assert any("amount" in e.field for e in result.errors)


class TestParserIntegration:
    """Integration tests for parser."""

    def test_full_parsing_workflow(self):
        """Test complete parsing workflow."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        # Parse the message
        parsed = parser.parse("/trade SOL 100")

        assert parsed.is_command
        assert parsed.command == "trade"

        # Extract with pattern
        pattern = r"(?P<token>\w+)\s+(?P<amount>\d+)"
        args = parser.extract_args(parsed.raw_args, pattern)

        assert args["token"] == "SOL"
        assert args["amount"] == "100"

        # Validate
        schema = {
            "token": {"type": "string", "required": True},
            "amount": {"type": "number", "required": True, "min": 1}
        }

        assert parser.validate_args(args, schema) is True

    def test_parse_and_validate_in_one_step(self):
        """Test combined parse and validate."""
        from core.commands.parser import CommandParser

        parser = CommandParser()

        schema = {
            "token": {"type": "string", "required": True, "position": 0},
            "amount": {"type": "number", "required": True, "position": 1}
        }

        result = parser.parse_and_validate("/trade SOL 100", schema)

        assert result.is_valid is True
        assert result.parsed_args["token"] == "SOL"
        assert result.parsed_args["amount"] == 100  # Converted to number
