"""
Unit tests for Voice Command Parser.

Tests the parsing of natural language voice commands into structured intents
for the JARVIS voice trading terminal.
"""

import pytest
from typing import Dict, Any


class TestVoiceCommandParserBasics:
    """Test basic command parser functionality."""

    def test_parser_exists(self):
        """VoiceCommandParser should exist and be importable."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        assert parser is not None

    def test_parser_parse_method(self):
        """Parser should have a parse method that returns an intent."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("hello")

        assert result is not None
        assert "intent" in result
        assert "confidence" in result

    def test_parser_returns_unknown_for_gibberish(self):
        """Parser should return unknown intent for unrecognized input."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("asdfghjkl qwerty")

        assert result["intent"] == "unknown"


class TestMorningBriefingCommands:
    """Test morning briefing voice commands."""

    @pytest.mark.parametrize("command", [
        "morning briefing",
        "give me the morning briefing",
        "what's the morning briefing",
        "jarvis morning briefing",
        "market briefing",
        "what happened overnight",
        "overnight summary",
        "morning market summary",
        "gm briefing",
        "good morning briefing",
    ])
    def test_morning_briefing_variations(self, command):
        """Various morning briefing phrasings should be recognized."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse(command)

        assert result["intent"] == "morning_briefing"
        assert result["confidence"] >= 0.7

    def test_morning_briefing_with_date(self):
        """Morning briefing should optionally capture date."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("morning briefing for yesterday")

        assert result["intent"] == "morning_briefing"
        assert "params" in result


class TestStrategyActivationCommands:
    """Test strategy activation/deactivation commands."""

    @pytest.mark.parametrize("command,expected_action,expected_strategy", [
        ("activate momentum strategy", "activate", "momentum"),
        ("enable momentum strategy", "activate", "momentum"),
        ("turn on momentum strategy", "activate", "momentum"),
        ("start momentum strategy", "activate", "momentum"),
        ("deactivate momentum strategy", "deactivate", "momentum"),
        ("disable momentum strategy", "deactivate", "momentum"),
        ("turn off momentum strategy", "deactivate", "momentum"),
        ("stop momentum strategy", "deactivate", "momentum"),
        ("activate dca strategy", "activate", "dca"),
        ("enable grid strategy", "activate", "grid"),
        ("start scalping strategy", "activate", "scalping"),
        ("activate mean reversion", "activate", "mean_reversion"),
    ])
    def test_strategy_commands(self, command, expected_action, expected_strategy):
        """Strategy activation commands should be parsed correctly."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse(command)

        assert result["intent"] == "strategy_control"
        assert result["params"]["action"] == expected_action
        assert result["params"]["strategy"] == expected_strategy

    def test_strategy_status_query(self):
        """Should handle strategy status queries."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("what strategies are active")

        assert result["intent"] == "strategy_status"


class TestRiskLimitCommands:
    """Test risk limit adjustment commands."""

    @pytest.mark.parametrize("command,param,value", [
        ("reduce max position to 3 percent", "max_position_pct", 3.0),
        ("set max position size to 5 percent", "max_position_pct", 5.0),
        ("jarvis reduce my max position size to 3 percent", "max_position_pct", 3.0),
        ("change max position to 2.5 percent", "max_position_pct", 2.5),
        ("set stop loss to 10 percent", "stop_loss_pct", 10.0),
        ("reduce stop loss to 5 percent", "stop_loss_pct", 5.0),
        ("set take profit to 30 percent", "take_profit_pct", 30.0),
        ("increase take profit to 50 percent", "take_profit_pct", 50.0),
        ("set daily loss limit to 500 dollars", "daily_loss_limit", 500.0),
        ("set max drawdown to 15 percent", "max_drawdown_pct", 15.0),
    ])
    def test_risk_limit_commands(self, command, param, value):
        """Risk limit commands should be parsed with correct values."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse(command)

        assert result["intent"] == "risk_adjustment"
        assert param in result["params"]
        assert abs(result["params"][param] - value) < 0.01

    def test_risk_limit_query(self):
        """Should handle risk limit queries."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("what are my current risk limits")

        assert result["intent"] == "risk_query"


class TestPriceAlertCommands:
    """Test price alert commands."""

    @pytest.mark.parametrize("command,token,price,direction", [
        ("alert me when sol hits 150", "SOL", 150.0, "at"),
        ("notify me when bitcoin reaches 100000", "BTC", 100000.0, "at"),
        ("set alert for ethereum at 4000", "ETH", 4000.0, "at"),
        ("tell me when sol goes above 200", "SOL", 200.0, "above"),
        ("alert when sol drops below 100", "SOL", 100.0, "below"),
        ("jarvis alert me when solana hits 150", "SOL", 150.0, "at"),
        ("notify when $SOL reaches 180", "SOL", 180.0, "at"),
        ("set a price alert for bonk at 0.00001", "BONK", 0.00001, "at"),
    ])
    def test_price_alert_commands(self, command, token, price, direction):
        """Price alert commands should be parsed correctly."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse(command)

        assert result["intent"] == "price_alert"
        assert result["params"]["token"].upper() == token
        assert abs(result["params"]["price"] - price) < 0.0001
        assert result["params"]["direction"] == direction

    def test_list_alerts_query(self):
        """Should handle listing active alerts."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("what alerts do I have")

        assert result["intent"] == "list_alerts"

    def test_cancel_alert(self):
        """Should handle canceling alerts."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("cancel alert for sol")

        assert result["intent"] == "cancel_alert"
        assert result["params"]["token"].upper() == "SOL"


class TestPositionQueries:
    """Test position query commands."""

    @pytest.mark.parametrize("command", [
        "what are my positions",
        "show my positions",
        "list open positions",
        "what am I holding",
        "current positions",
        "portfolio status",
        "what's in my portfolio",
        "show portfolio",
    ])
    def test_position_query_variations(self, command):
        """Position queries should be recognized."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse(command)

        assert result["intent"] == "position_query"

    def test_specific_position_query(self):
        """Should handle queries about specific tokens."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("what's my position in sol")

        assert result["intent"] == "position_query"
        assert result["params"]["token"].upper() == "SOL"


class TestMarketDataQueries:
    """Test market data query commands."""

    @pytest.mark.parametrize("command,token", [
        ("what's the price of sol", "SOL"),
        ("sol price", "SOL"),
        ("price of bitcoin", "BTC"),
        ("how much is ethereum", "ETH"),
        ("check sol price", "SOL"),
        ("what's bonk trading at", "BONK"),
    ])
    def test_price_query_commands(self, command, token):
        """Price queries should extract the token correctly."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse(command)

        assert result["intent"] == "price_query"
        assert result["params"]["token"].upper() == token

    def test_market_overview_query(self):
        """Should handle market overview queries."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("how's the market doing")

        assert result["intent"] == "market_overview"


class TestTradingCommands:
    """Test voice trading commands."""

    @pytest.mark.parametrize("command,action,token", [
        ("buy some sol", "buy", "SOL"),
        ("sell my sol", "sell", "SOL"),
        ("close my sol position", "close", "SOL"),
        ("exit sol position", "close", "SOL"),
    ])
    def test_basic_trade_commands(self, command, action, token):
        """Basic trading commands should be parsed."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse(command)

        assert result["intent"] == "trade_command"
        assert result["params"]["action"] == action
        assert result["params"]["token"].upper() == token

    def test_buy_with_amount(self):
        """Buy command should extract amount."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("buy 100 dollars of sol")

        assert result["intent"] == "trade_command"
        assert result["params"]["action"] == "buy"
        assert result["params"]["token"].upper() == "SOL"
        assert result["params"]["amount"] == 100.0
        assert result["params"]["currency"] == "USD"

    def test_sell_percentage(self):
        """Sell command should extract percentage."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("sell 50 percent of my sol")

        assert result["intent"] == "trade_command"
        assert result["params"]["action"] == "sell"
        assert result["params"]["token"].upper() == "SOL"
        assert result["params"]["percentage"] == 50.0


class TestParserEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_input(self):
        """Should handle empty input gracefully."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("")

        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.0

    def test_none_input(self):
        """Should handle None input gracefully."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse(None)

        assert result["intent"] == "unknown"

    def test_case_insensitivity(self):
        """Should handle mixed case input."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("MORNING BRIEFING")

        assert result["intent"] == "morning_briefing"

    def test_extra_whitespace(self):
        """Should handle extra whitespace."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("  morning   briefing  ")

        assert result["intent"] == "morning_briefing"

    def test_partial_match_low_confidence(self):
        """Partial matches should have lower confidence."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse("morning something")

        # Should either not match or have lower confidence
        if result["intent"] == "morning_briefing":
            assert result["confidence"] < 0.7


class TestTokenNormalization:
    """Test token name normalization."""

    @pytest.mark.parametrize("input_token,expected", [
        ("sol", "SOL"),
        ("SOL", "SOL"),
        ("solana", "SOL"),
        ("SOLANA", "SOL"),
        ("bitcoin", "BTC"),
        ("btc", "BTC"),
        ("eth", "ETH"),
        ("ethereum", "ETH"),
        ("$SOL", "SOL"),
    ])
    def test_token_normalization(self, input_token, expected):
        """Tokens should be normalized to standard symbols."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()
        result = parser.parse(f"price of {input_token}")

        assert result["params"]["token"] == expected


class TestNumberParsing:
    """Test number extraction from voice commands."""

    @pytest.mark.parametrize("phrase,expected", [
        ("three percent", 3.0),
        ("3 percent", 3.0),
        ("3%", 3.0),
        ("2.5 percent", 2.5),
        ("twenty percent", 20.0),
        ("150 dollars", 150.0),
        ("$100", 100.0),
        ("one hundred dollars", 100.0),
    ])
    def test_number_parsing(self, phrase, expected):
        """Numbers in various formats should be parsed correctly."""
        from core.voice.command_parser import VoiceCommandParser

        parser = VoiceCommandParser()

        # Test with risk adjustment command
        result = parser.parse(f"set max position to {phrase}")

        # Check that the number was parsed (in appropriate param)
        assert any(
            abs(v - expected) < 0.01
            for v in result.get("params", {}).values()
            if isinstance(v, (int, float))
        )


class TestCommandIntent:
    """Test CommandIntent dataclass."""

    def test_command_intent_creation(self):
        """CommandIntent should be creatable with required fields."""
        from core.voice.command_parser import CommandIntent

        intent = CommandIntent(
            intent="test",
            confidence=0.9,
            params={"key": "value"},
            raw_text="test command"
        )

        assert intent.intent == "test"
        assert intent.confidence == 0.9
        assert intent.params["key"] == "value"
        assert intent.raw_text == "test command"

    def test_command_intent_to_dict(self):
        """CommandIntent should be convertible to dict."""
        from core.voice.command_parser import CommandIntent

        intent = CommandIntent(
            intent="test",
            confidence=0.9,
            params={"key": "value"},
            raw_text="test command"
        )

        d = intent.to_dict()

        assert isinstance(d, dict)
        assert d["intent"] == "test"
        assert d["confidence"] == 0.9
