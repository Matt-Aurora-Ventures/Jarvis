"""
Tests for Campaign Orchestrator - ClawdBots multi-agent marketing campaigns.

TDD: Tests written FIRST before implementation.
"""

import pytest
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCampaignOrchestrator:
    """Test suite for campaign orchestrator functionality."""

    @pytest.fixture
    def temp_campaigns_file(self, tmp_path):
        """Create a temporary campaigns file for testing."""
        campaigns_file = tmp_path / "campaigns.json"
        return str(campaigns_file)

    @pytest.fixture
    def orchestrator(self, temp_campaigns_file):
        """Create orchestrator instance with temp file."""
        from bots.shared.campaign_orchestrator import CampaignOrchestrator
        return CampaignOrchestrator(campaigns_file=temp_campaigns_file)

    # ============================================
    # Campaign Creation Tests
    # ============================================

    def test_create_campaign_basic(self, orchestrator):
        """Test creating a basic campaign with required fields."""
        campaign_id = orchestrator.create_campaign(
            name="Q1 Launch",
            description="Quarterly product launch campaign",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        assert campaign_id is not None
        assert isinstance(campaign_id, str)
        assert len(campaign_id) > 0

    def test_create_campaign_returns_unique_ids(self, orchestrator):
        """Test that each campaign gets a unique ID."""
        id1 = orchestrator.create_campaign(
            name="Campaign 1",
            description="First campaign",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        id2 = orchestrator.create_campaign(
            name="Campaign 2",
            description="Second campaign",
            start_date="2026-03-01",
            end_date="2026-03-31"
        )

        assert id1 != id2

    def test_create_campaign_persists_to_file(self, orchestrator, temp_campaigns_file):
        """Test that created campaigns are persisted to JSON file."""
        orchestrator.create_campaign(
            name="Persisted Campaign",
            description="Should be saved to file",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        # Read the file directly
        with open(temp_campaigns_file, 'r') as f:
            data = json.load(f)

        assert "campaigns" in data
        assert len(data["campaigns"]) == 1
        assert data["campaigns"][0]["name"] == "Persisted Campaign"

    def test_create_campaign_initializes_empty_tasks(self, orchestrator):
        """Test that new campaigns have empty task list."""
        campaign_id = orchestrator.create_campaign(
            name="Empty Tasks",
            description="Should have no tasks",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        status = orchestrator.get_campaign_status(campaign_id)
        assert status["tasks"] == []

    def test_create_campaign_initializes_metrics(self, orchestrator):
        """Test that new campaigns have initialized metrics."""
        campaign_id = orchestrator.create_campaign(
            name="With Metrics",
            description="Should have zero metrics",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        status = orchestrator.get_campaign_status(campaign_id)
        assert "metrics" in status
        assert status["metrics"]["reach"] == 0
        assert status["metrics"]["engagement"] == 0
        assert status["metrics"]["conversions"] == 0

    # ============================================
    # Task Assignment Tests
    # ============================================

    def test_assign_task_to_jarvis(self, orchestrator):
        """Test assigning a task to Jarvis (CTO role)."""
        campaign_id = orchestrator.create_campaign(
            name="Tech Campaign",
            description="Technical content",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        task_id = orchestrator.assign_task(
            campaign_id=campaign_id,
            bot="jarvis",
            task_type="content_creation",
            content="Write technical blog post about AI trading",
            deadline="2026-02-15"
        )

        assert task_id is not None
        status = orchestrator.get_campaign_status(campaign_id)
        assert len(status["tasks"]) == 1
        assert status["tasks"][0]["bot"] == "jarvis"

    def test_assign_task_to_matt(self, orchestrator):
        """Test assigning a task to Matt (COO role)."""
        campaign_id = orchestrator.create_campaign(
            name="Operations Campaign",
            description="Operational updates",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        task_id = orchestrator.assign_task(
            campaign_id=campaign_id,
            bot="matt",
            task_type="announcement",
            content="Share weekly operations update",
            deadline="2026-02-10"
        )

        assert task_id is not None
        status = orchestrator.get_campaign_status(campaign_id)
        assert status["tasks"][0]["bot"] == "matt"

    def test_assign_task_to_friday(self, orchestrator):
        """Test assigning a task to Friday (CMO role)."""
        campaign_id = orchestrator.create_campaign(
            name="Marketing Campaign",
            description="Marketing push",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        task_id = orchestrator.assign_task(
            campaign_id=campaign_id,
            bot="friday",
            task_type="social_media",
            content="Post viral meme content",
            deadline="2026-02-05"
        )

        assert task_id is not None
        status = orchestrator.get_campaign_status(campaign_id)
        assert status["tasks"][0]["bot"] == "friday"

    def test_assign_task_initial_status_pending(self, orchestrator):
        """Test that new tasks start with pending status."""
        campaign_id = orchestrator.create_campaign(
            name="Status Test",
            description="Testing status",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        orchestrator.assign_task(
            campaign_id=campaign_id,
            bot="jarvis",
            task_type="research",
            content="Research competitor activity",
            deadline="2026-02-20"
        )

        status = orchestrator.get_campaign_status(campaign_id)
        assert status["tasks"][0]["status"] == "pending"

    def test_assign_multiple_tasks(self, orchestrator):
        """Test assigning multiple tasks to different bots."""
        campaign_id = orchestrator.create_campaign(
            name="Multi-Bot Campaign",
            description="Coordinated campaign",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        orchestrator.assign_task(campaign_id, "jarvis", "technical", "Write docs", "2026-02-10")
        orchestrator.assign_task(campaign_id, "matt", "operations", "Coordinate team", "2026-02-12")
        orchestrator.assign_task(campaign_id, "friday", "marketing", "Create buzz", "2026-02-15")

        status = orchestrator.get_campaign_status(campaign_id)
        assert len(status["tasks"]) == 3

        bots = [t["bot"] for t in status["tasks"]]
        assert "jarvis" in bots
        assert "matt" in bots
        assert "friday" in bots

    def test_assign_task_invalid_campaign(self, orchestrator):
        """Test assigning task to non-existent campaign raises error."""
        with pytest.raises(ValueError, match="Campaign not found"):
            orchestrator.assign_task(
                campaign_id="nonexistent-123",
                bot="jarvis",
                task_type="test",
                content="This should fail",
                deadline="2026-02-15"
            )

    # ============================================
    # Task Status Update Tests
    # ============================================

    def test_update_task_status_in_progress(self, orchestrator):
        """Test updating task status to in_progress."""
        campaign_id = orchestrator.create_campaign(
            name="Status Update Test",
            description="Testing updates",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        task_id = orchestrator.assign_task(
            campaign_id=campaign_id,
            bot="jarvis",
            task_type="development",
            content="Build feature",
            deadline="2026-02-20"
        )

        success = orchestrator.update_task_status(
            campaign_id=campaign_id,
            task_id=task_id,
            status="in_progress"
        )

        assert success is True
        status = orchestrator.get_campaign_status(campaign_id)
        assert status["tasks"][0]["status"] == "in_progress"

    def test_update_task_status_completed(self, orchestrator):
        """Test updating task status to completed."""
        campaign_id = orchestrator.create_campaign(
            name="Completion Test",
            description="Testing completion",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        task_id = orchestrator.assign_task(
            campaign_id=campaign_id,
            bot="matt",
            task_type="review",
            content="Review content",
            deadline="2026-02-18"
        )

        orchestrator.update_task_status(campaign_id, task_id, "in_progress")
        orchestrator.update_task_status(campaign_id, task_id, "completed")

        status = orchestrator.get_campaign_status(campaign_id)
        assert status["tasks"][0]["status"] == "completed"

    def test_update_task_status_failed(self, orchestrator):
        """Test updating task status to failed."""
        campaign_id = orchestrator.create_campaign(
            name="Failure Test",
            description="Testing failure",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        task_id = orchestrator.assign_task(
            campaign_id=campaign_id,
            bot="friday",
            task_type="post",
            content="Post content",
            deadline="2026-02-08"
        )

        orchestrator.update_task_status(campaign_id, task_id, "failed")

        status = orchestrator.get_campaign_status(campaign_id)
        assert status["tasks"][0]["status"] == "failed"

    def test_update_task_invalid_status(self, orchestrator):
        """Test that invalid status values are rejected."""
        campaign_id = orchestrator.create_campaign(
            name="Invalid Status Test",
            description="Testing invalid",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        task_id = orchestrator.assign_task(
            campaign_id=campaign_id,
            bot="jarvis",
            task_type="test",
            content="Test task",
            deadline="2026-02-15"
        )

        with pytest.raises(ValueError, match="Invalid status"):
            orchestrator.update_task_status(campaign_id, task_id, "invalid_status")

    # ============================================
    # Campaign Status Tests
    # ============================================

    def test_get_campaign_status_returns_all_fields(self, orchestrator):
        """Test that campaign status includes all required fields."""
        campaign_id = orchestrator.create_campaign(
            name="Full Status Test",
            description="Testing full status",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        status = orchestrator.get_campaign_status(campaign_id)

        assert "id" in status
        assert "name" in status
        assert "description" in status
        assert "start_date" in status
        assert "end_date" in status
        assert "tasks" in status
        assert "metrics" in status
        assert "progress" in status

    def test_get_campaign_progress_calculation(self, orchestrator):
        """Test that progress is calculated correctly."""
        campaign_id = orchestrator.create_campaign(
            name="Progress Test",
            description="Testing progress",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        # Add 4 tasks
        task1 = orchestrator.assign_task(campaign_id, "jarvis", "task", "Task 1", "2026-02-10")
        task2 = orchestrator.assign_task(campaign_id, "matt", "task", "Task 2", "2026-02-12")
        task3 = orchestrator.assign_task(campaign_id, "friday", "task", "Task 3", "2026-02-14")
        task4 = orchestrator.assign_task(campaign_id, "jarvis", "task", "Task 4", "2026-02-16")

        # Complete 2 of them
        orchestrator.update_task_status(campaign_id, task1, "completed")
        orchestrator.update_task_status(campaign_id, task2, "completed")

        status = orchestrator.get_campaign_status(campaign_id)
        assert status["progress"] == 50.0  # 2/4 = 50%

    def test_get_campaign_status_not_found(self, orchestrator):
        """Test getting status of non-existent campaign."""
        status = orchestrator.get_campaign_status("nonexistent-456")
        assert status is None

    # ============================================
    # Campaign Report Tests
    # ============================================

    def test_generate_campaign_report_basic(self, orchestrator):
        """Test generating a basic campaign report."""
        campaign_id = orchestrator.create_campaign(
            name="Report Test Campaign",
            description="Testing reports",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        report = orchestrator.generate_campaign_report(campaign_id)

        assert report is not None
        assert "campaign_name" in report
        assert "summary" in report
        assert "tasks_by_bot" in report
        assert "tasks_by_status" in report

    def test_generate_campaign_report_tasks_by_bot(self, orchestrator):
        """Test report breaks down tasks by bot."""
        campaign_id = orchestrator.create_campaign(
            name="Bot Breakdown Test",
            description="Testing bot breakdown",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        orchestrator.assign_task(campaign_id, "jarvis", "tech", "Tech task 1", "2026-02-10")
        orchestrator.assign_task(campaign_id, "jarvis", "tech", "Tech task 2", "2026-02-12")
        orchestrator.assign_task(campaign_id, "matt", "ops", "Ops task", "2026-02-14")
        orchestrator.assign_task(campaign_id, "friday", "mkt", "Marketing task", "2026-02-16")

        report = orchestrator.generate_campaign_report(campaign_id)

        assert report["tasks_by_bot"]["jarvis"] == 2
        assert report["tasks_by_bot"]["matt"] == 1
        assert report["tasks_by_bot"]["friday"] == 1

    def test_generate_campaign_report_tasks_by_status(self, orchestrator):
        """Test report breaks down tasks by status."""
        campaign_id = orchestrator.create_campaign(
            name="Status Breakdown Test",
            description="Testing status breakdown",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        task1 = orchestrator.assign_task(campaign_id, "jarvis", "task", "Task 1", "2026-02-10")
        task2 = orchestrator.assign_task(campaign_id, "matt", "task", "Task 2", "2026-02-12")
        task3 = orchestrator.assign_task(campaign_id, "friday", "task", "Task 3", "2026-02-14")

        orchestrator.update_task_status(campaign_id, task1, "completed")
        orchestrator.update_task_status(campaign_id, task2, "in_progress")
        # task3 remains pending

        report = orchestrator.generate_campaign_report(campaign_id)

        assert report["tasks_by_status"]["completed"] == 1
        assert report["tasks_by_status"]["in_progress"] == 1
        assert report["tasks_by_status"]["pending"] == 1

    def test_generate_campaign_report_includes_metrics(self, orchestrator):
        """Test report includes campaign metrics."""
        campaign_id = orchestrator.create_campaign(
            name="Metrics Test",
            description="Testing metrics",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        report = orchestrator.generate_campaign_report(campaign_id)

        assert "metrics" in report
        assert "reach" in report["metrics"]
        assert "engagement" in report["metrics"]
        assert "conversions" in report["metrics"]

    def test_generate_campaign_report_not_found(self, orchestrator):
        """Test report generation for non-existent campaign."""
        report = orchestrator.generate_campaign_report("nonexistent-789")
        assert report is None

    # ============================================
    # Metrics Update Tests
    # ============================================

    def test_update_campaign_metrics(self, orchestrator):
        """Test updating campaign metrics."""
        campaign_id = orchestrator.create_campaign(
            name="Metrics Update Test",
            description="Testing metrics update",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        orchestrator.update_metrics(
            campaign_id=campaign_id,
            reach=1000,
            engagement=150,
            conversions=25
        )

        status = orchestrator.get_campaign_status(campaign_id)
        assert status["metrics"]["reach"] == 1000
        assert status["metrics"]["engagement"] == 150
        assert status["metrics"]["conversions"] == 25

    def test_update_metrics_incremental(self, orchestrator):
        """Test that metrics can be updated incrementally."""
        campaign_id = orchestrator.create_campaign(
            name="Incremental Metrics Test",
            description="Testing incremental",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        # First update
        orchestrator.update_metrics(campaign_id, reach=500, engagement=50, conversions=5)

        # Second update - should add to existing
        orchestrator.update_metrics(campaign_id, reach=300, engagement=30, conversions=3, incremental=True)

        status = orchestrator.get_campaign_status(campaign_id)
        assert status["metrics"]["reach"] == 800
        assert status["metrics"]["engagement"] == 80
        assert status["metrics"]["conversions"] == 8

    # ============================================
    # List Campaigns Tests
    # ============================================

    def test_list_all_campaigns(self, orchestrator):
        """Test listing all campaigns."""
        orchestrator.create_campaign("Campaign A", "First", "2026-02-01", "2026-02-28")
        orchestrator.create_campaign("Campaign B", "Second", "2026-03-01", "2026-03-31")
        orchestrator.create_campaign("Campaign C", "Third", "2026-04-01", "2026-04-30")

        campaigns = orchestrator.list_campaigns()

        assert len(campaigns) == 3
        names = [c["name"] for c in campaigns]
        assert "Campaign A" in names
        assert "Campaign B" in names
        assert "Campaign C" in names

    def test_list_campaigns_empty(self, orchestrator):
        """Test listing campaigns when none exist."""
        campaigns = orchestrator.list_campaigns()
        assert campaigns == []

    def test_list_active_campaigns(self, orchestrator):
        """Test listing only active campaigns (within date range)."""
        # Past campaign
        orchestrator.create_campaign("Past", "Old", "2025-01-01", "2025-01-31")
        # Current campaign (active)
        orchestrator.create_campaign("Current", "Active", "2026-01-01", "2026-12-31")
        # Future campaign
        orchestrator.create_campaign("Future", "Coming", "2027-01-01", "2027-12-31")

        active = orchestrator.list_campaigns(active_only=True)

        # Only current should be active (assuming test runs in 2026)
        assert len(active) >= 1
        names = [c["name"] for c in active]
        assert "Current" in names


class TestCampaignOrchestratorEdgeCases:
    """Edge case tests for campaign orchestrator."""

    @pytest.fixture
    def temp_campaigns_file(self, tmp_path):
        """Create a temporary campaigns file for testing."""
        campaigns_file = tmp_path / "campaigns.json"
        return str(campaigns_file)

    @pytest.fixture
    def orchestrator(self, temp_campaigns_file):
        """Create orchestrator instance with temp file."""
        from bots.shared.campaign_orchestrator import CampaignOrchestrator
        return CampaignOrchestrator(campaigns_file=temp_campaigns_file)

    def test_handles_corrupt_json_file(self, temp_campaigns_file):
        """Test handling of corrupt JSON file."""
        # Write corrupt JSON
        with open(temp_campaigns_file, 'w') as f:
            f.write("{ invalid json }")

        from bots.shared.campaign_orchestrator import CampaignOrchestrator
        orchestrator = CampaignOrchestrator(campaigns_file=temp_campaigns_file)

        # Should initialize with empty campaigns, not crash
        campaigns = orchestrator.list_campaigns()
        assert campaigns == []

    def test_handles_missing_file(self, tmp_path):
        """Test handling of missing campaigns file."""
        missing_file = str(tmp_path / "nonexistent" / "campaigns.json")

        from bots.shared.campaign_orchestrator import CampaignOrchestrator
        orchestrator = CampaignOrchestrator(campaigns_file=missing_file)

        # Should create file when first campaign is added
        campaign_id = orchestrator.create_campaign(
            name="First Campaign",
            description="Testing file creation",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        assert campaign_id is not None
        assert os.path.exists(missing_file)

    def test_concurrent_updates_safe(self, orchestrator):
        """Test that file updates are atomic/safe."""
        campaign_id = orchestrator.create_campaign(
            name="Concurrent Test",
            description="Testing concurrency",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        # Add many tasks quickly
        task_ids = []
        for i in range(10):
            task_id = orchestrator.assign_task(
                campaign_id=campaign_id,
                bot=["jarvis", "matt", "friday"][i % 3],
                task_type=f"task_{i}",
                content=f"Task content {i}",
                deadline="2026-02-15"
            )
            task_ids.append(task_id)

        # All tasks should be saved
        status = orchestrator.get_campaign_status(campaign_id)
        assert len(status["tasks"]) == 10

    def test_empty_task_content_allowed(self, orchestrator):
        """Test that empty task content is handled."""
        campaign_id = orchestrator.create_campaign(
            name="Empty Content Test",
            description="Testing empty",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        task_id = orchestrator.assign_task(
            campaign_id=campaign_id,
            bot="jarvis",
            task_type="placeholder",
            content="",  # Empty content
            deadline="2026-02-15"
        )

        assert task_id is not None
        status = orchestrator.get_campaign_status(campaign_id)
        assert status["tasks"][0]["content"] == ""


class TestCampaignOrchestratorIntegration:
    """Integration tests for complete campaign workflows."""

    @pytest.fixture
    def temp_campaigns_file(self, tmp_path):
        """Create a temporary campaigns file for testing."""
        campaigns_file = tmp_path / "campaigns.json"
        return str(campaigns_file)

    @pytest.fixture
    def orchestrator(self, temp_campaigns_file):
        """Create orchestrator instance with temp file."""
        from bots.shared.campaign_orchestrator import CampaignOrchestrator
        return CampaignOrchestrator(campaigns_file=temp_campaigns_file)

    def test_complete_campaign_lifecycle(self, orchestrator):
        """Test a complete campaign from creation to completion."""
        # 1. Create campaign
        campaign_id = orchestrator.create_campaign(
            name="Product Launch Q1",
            description="Launch new AI trading features",
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        # 2. Assign tasks to all bots
        tech_task = orchestrator.assign_task(
            campaign_id, "jarvis", "technical",
            "Write technical documentation", "2026-02-10"
        )
        ops_task = orchestrator.assign_task(
            campaign_id, "matt", "operations",
            "Coordinate launch timeline", "2026-02-12"
        )
        mkt_task = orchestrator.assign_task(
            campaign_id, "friday", "marketing",
            "Create social media content", "2026-02-15"
        )

        # 3. Progress through tasks
        orchestrator.update_task_status(campaign_id, tech_task, "in_progress")
        orchestrator.update_task_status(campaign_id, ops_task, "in_progress")

        # Check progress at 0% complete
        status = orchestrator.get_campaign_status(campaign_id)
        assert status["progress"] == 0.0

        # 4. Complete tasks one by one
        orchestrator.update_task_status(campaign_id, tech_task, "completed")
        status = orchestrator.get_campaign_status(campaign_id)
        assert status["progress"] == pytest.approx(33.33, rel=0.1)

        orchestrator.update_task_status(campaign_id, ops_task, "completed")
        orchestrator.update_task_status(campaign_id, mkt_task, "in_progress")
        orchestrator.update_task_status(campaign_id, mkt_task, "completed")

        # 5. Update metrics
        orchestrator.update_metrics(
            campaign_id,
            reach=50000,
            engagement=5000,
            conversions=500
        )

        # 6. Generate final report
        report = orchestrator.generate_campaign_report(campaign_id)

        assert report["campaign_name"] == "Product Launch Q1"
        assert report["tasks_by_status"]["completed"] == 3
        assert report["metrics"]["reach"] == 50000
        assert report["summary"]["total_tasks"] == 3
        assert report["summary"]["completion_rate"] == 100.0
