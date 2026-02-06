"""Tests for the MorningBrief system."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from bots.shared.morning_brief import MorningBrief, BOTS, HANDOFFS_DIR, TASKS_FILE, BRIEF_MARKER


@pytest.fixture
def brief():
    return MorningBrief()


class TestMorningBriefInit:
    """Test MorningBrief basics."""

    def test_creates_instance(self):
        mb = MorningBrief()
        assert isinstance(mb, MorningBrief)

    def test_has_generate_methods(self):
        mb = MorningBrief()
        assert hasattr(mb, "generate_brief")
        assert hasattr(mb, "generate_brief_sync")


class TestGenerateBrief:
    """Test brief generation."""

    @pytest.mark.asyncio
    async def test_generate_brief_returns_string(self, brief):
        with patch("bots.shared.morning_brief.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout="inactive\n")
            result = await brief.generate_brief()
            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_brief_contains_sections(self, brief):
        with patch("bots.shared.morning_brief.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout="inactive\n")
            result = await brief.generate_brief()
            assert "MORNING BRIEF" in result
            assert "SYSTEM HEALTH" in result
            assert "PENDING HANDOFFS" in result
            assert "ERRORS" in result
            assert "ACTIVE TASKS" in result
            assert "RECOMMENDATIONS" in result

    def test_generate_brief_sync_returns_string(self, brief):
        with patch("bots.shared.morning_brief.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout="inactive\n")
            result = brief.generate_brief_sync()
            assert isinstance(result, str)
            assert "MORNING BRIEF" in result


class TestSystemHealth:
    """Test system health section of the brief."""

    def test_healthy_bots_show_ok(self, brief):
        with patch("bots.shared.morning_brief.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout="active\n")
            result = brief._generate()
            for bot in BOTS:
                assert bot in result
            assert "[OK]" in result

    def test_down_bots_show_down(self, brief):
        with patch("bots.shared.morning_brief.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout="inactive\n")
            result = brief._generate()
            assert "[DOWN]" in result

    def test_subprocess_error_handled(self, brief):
        with patch("bots.shared.morning_brief.subprocess") as mock_sub:
            mock_sub.run.side_effect = Exception("command failed")
            result = brief._generate()
            assert "Health check error" in result


class TestPendingHandoffs:
    """Test pending handoffs section."""

    def test_no_handoffs_file(self, brief, tmp_path):
        with patch("bots.shared.morning_brief.subprocess") as mock_sub, \
             patch("bots.shared.morning_brief.HANDOFFS_DIR", tmp_path):
            mock_sub.run.return_value = MagicMock(stdout="inactive\n")
            result = brief._generate()
            assert "No pending handoffs" in result

    def test_with_pending_handoffs(self, brief, tmp_path):
        pending = [{"status": "pending", "to": "jarvis", "task": "Deploy new version"}]
        pf = tmp_path / "pending.json"
        pf.write_text(json.dumps(pending))
        with patch("bots.shared.morning_brief.subprocess") as mock_sub, \
             patch("bots.shared.morning_brief.HANDOFFS_DIR", tmp_path):
            mock_sub.run.return_value = MagicMock(stdout="inactive\n")
            result = brief._generate()
            assert "jarvis" in result
            assert "Deploy new version" in result


class TestActiveTasks:
    """Test active tasks section."""

    def test_no_tasks_file(self, brief, tmp_path):
        with patch("bots.shared.morning_brief.subprocess") as mock_sub, \
             patch("bots.shared.morning_brief.TASKS_FILE", tmp_path / "nope.json"):
            mock_sub.run.return_value = MagicMock(stdout="inactive\n")
            result = brief._generate()
            assert "No task file found" in result

    def test_with_active_tasks(self, brief, tmp_path):
        tasks = [{"status": "active", "description": "Fix auth bug"}]
        tf = tmp_path / "tasks.json"
        tf.write_text(json.dumps(tasks))
        with patch("bots.shared.morning_brief.subprocess") as mock_sub, \
             patch("bots.shared.morning_brief.TASKS_FILE", tf):
            mock_sub.run.return_value = MagicMock(stdout="inactive\n")
            result = brief._generate()
            assert "Fix auth bug" in result


class TestShouldSend:
    """Test the should_send logic."""

    def test_should_send_at_8am(self, tmp_path):
        marker = tmp_path / ".brief_sent"
        with patch("bots.shared.morning_brief.datetime") as mock_dt, \
             patch("bots.shared.morning_brief.BRIEF_MARKER", marker):
            mock_dt.utcnow.return_value = datetime(2026, 2, 2, 8, 0, 0)
            assert MorningBrief.should_send() is True

    def test_should_not_send_at_wrong_hour(self):
        with patch("bots.shared.morning_brief.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 2, 2, 14, 0, 0)
            assert MorningBrief.should_send() is False

    def test_should_not_send_if_already_sent_today(self, tmp_path):
        marker = tmp_path / ".brief_sent"
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        marker.write_text(today_str)
        # Patch only BRIEF_MARKER; use real datetime so strftime works
        with patch("bots.shared.morning_brief.BRIEF_MARKER", marker), \
             patch("bots.shared.morning_brief.datetime") as mock_dt:
            # Return a real datetime at 8:00 today
            now = datetime(2026, 2, 2, 8, 0, 0)
            mock_dt.utcnow.return_value = now
            # The code calls now.strftime which works on real datetime
            # But also reads marker and compares to now.strftime("%Y-%m-%d")
            # Since marker has today_str="2026-02-02" but now.strftime gives "2026-02-02"
            marker.write_text("2026-02-02")
            assert MorningBrief.should_send() is False


class TestMarkSent:
    """Test mark_sent writes marker file."""

    def test_mark_sent_creates_file(self, tmp_path):
        marker = tmp_path / ".brief_sent"
        with patch("bots.shared.morning_brief.BRIEF_MARKER", marker):
            MorningBrief.mark_sent()
            assert marker.exists()
            content = marker.read_text().strip()
            # Should be today's date
            assert len(content) == 10  # YYYY-MM-DD


class TestBriefFormat:
    """Test brief output format."""

    @pytest.mark.asyncio
    async def test_brief_has_date_header(self, brief):
        with patch("bots.shared.morning_brief.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout="inactive\n")
            result = await brief.generate_brief()
            assert "MORNING BRIEF" in result

    @pytest.mark.asyncio
    async def test_brief_section_ordering(self, brief):
        with patch("bots.shared.morning_brief.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(stdout="inactive\n")
            result = await brief.generate_brief()
            health_pos = result.index("SYSTEM HEALTH")
            handoff_pos = result.index("PENDING HANDOFFS")
            error_pos = result.index("ERRORS")
            task_pos = result.index("ACTIVE TASKS")
            rec_pos = result.index("RECOMMENDATIONS")
            assert health_pos < handoff_pos < error_pos < task_pos < rec_pos
