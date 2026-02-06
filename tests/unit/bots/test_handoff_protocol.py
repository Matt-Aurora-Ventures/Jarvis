"""Tests for ClawdBot handoff protocol."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime


# We test the module that will live on VPS - replicate it locally for testing
import sys
import importlib


@pytest.fixture
def handoff_dir(tmp_path):
    """Create a temp handoff directory."""
    d = tmp_path / "handoffs"
    d.mkdir()
    return d


@pytest.fixture
def protocol(handoff_dir):
    """Create a HandoffProtocol with temp dir."""
    # Import from local copy
    from bots.shared.handoff_protocol import HandoffProtocol
    hp = HandoffProtocol("matt")
    hp.pending_file = handoff_dir / "pending.json"
    hp.history_file = handoff_dir / "history.json"
    return hp


@pytest.fixture
def jarvis_protocol(handoff_dir):
    from bots.shared.handoff_protocol import HandoffProtocol
    hp = HandoffProtocol("jarvis")
    hp.pending_file = handoff_dir / "pending.json"
    hp.history_file = handoff_dir / "history.json"
    return hp


class TestRouting:
    def test_routes_infra_to_jarvis(self, protocol):
        result = protocol.route_task("deploy the new trading bot")
        assert result["to"] == "jarvis"
        assert result["status"] == "pending"

    def test_routes_content_to_friday(self, protocol):
        result = protocol.route_task("write a tweet about our launch")
        assert result["to"] == "friday"

    def test_ambiguous_defaults_to_jarvis(self, protocol):
        result = protocol.route_task("do something random")
        assert result["to"] == "jarvis"

    def test_handoff_has_required_fields(self, protocol):
        result = protocol.route_task("fix the server")
        assert "id" in result
        assert "from" in result
        assert "to" in result
        assert "task" in result
        assert "status" in result
        assert "created_at" in result

    def test_from_is_bot_name(self, protocol):
        result = protocol.route_task("anything")
        assert result["from"] == "matt"


class TestCheckIncoming:
    def test_finds_tasks_for_bot(self, protocol, jarvis_protocol):
        protocol.route_task("deploy the server")
        incoming = jarvis_protocol.check_incoming()
        assert len(incoming) == 1
        assert incoming[0]["to"] == "jarvis"

    def test_ignores_tasks_for_other_bots(self, protocol, jarvis_protocol):
        protocol.route_task("write a blog post about our product launch")
        incoming = jarvis_protocol.check_incoming()
        assert len(incoming) == 0


class TestCompleteHandoff:
    def test_marks_complete(self, protocol, jarvis_protocol, handoff_dir):
        h = protocol.route_task("fix the bug in the code")
        jarvis_protocol.complete_handoff(h["id"], "Bug fixed")

        # Should be removed from pending
        remaining = jarvis_protocol.check_incoming()
        assert len(remaining) == 0

        # Should be in history
        history = json.loads((handoff_dir / "history.json").read_text())
        assert len(history) == 1
        assert history[0]["status"] == "completed"
        assert history[0]["result"] == "Bug fixed"


class TestFilterInput:
    def test_strips_log_lines(self, protocol):
        raw = "DEBUG something\nActual task\nINFO noise\nMore task"
        filtered = protocol.filter_input(raw)
        assert "DEBUG" not in filtered
        assert "INFO" not in filtered
        assert "Actual task" in filtered
        assert "More task" in filtered

    def test_strips_traceback(self, protocol):
        raw = "Do this task\nTraceback (most recent call last)\nreal line"
        filtered = protocol.filter_input(raw)
        assert "Traceback" not in filtered


class TestFridayInterjection:
    def test_flags_delete(self):
        from bots.shared.handoff_protocol import FridayInterjection
        assert FridayInterjection.should_interject("rm -rf /data")

    def test_flags_transfer(self):
        from bots.shared.handoff_protocol import FridayInterjection
        assert FridayInterjection.should_interject("send sol to wallet")

    def test_allows_safe_command(self):
        from bots.shared.handoff_protocol import FridayInterjection
        assert not FridayInterjection.should_interject("check status")

    def test_creates_review_request(self):
        from bots.shared.handoff_protocol import FridayInterjection
        req = FridayInterjection.create_review_request("delete everything", "human")
        assert req["type"] == "interjection"
        assert "high-risk" in req["reason"].lower() or "High-risk" in req["reason"]
