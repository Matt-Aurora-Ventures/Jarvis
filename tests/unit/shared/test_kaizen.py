"""Tests for bots.shared.kaizen - Autonomous Kaizen self-improvement loops."""

import json
import tempfile
from pathlib import Path

import pytest

from bots.shared.kaizen import (
    CapabilityLoop,
    CohesionLoop,
    CorrectionLoop,
    KaizenEngine,
    StrategyLoop,
)


@pytest.fixture
def tmp_data_dir(tmp_path):
    return str(tmp_path)


class TestCorrectionLoop:
    def test_record_and_retrieve(self, tmp_data_dir):
        cl = CorrectionLoop(tmp_data_dir)
        cl.record_correction("timeout", "API timed out after 30s", "increased timeout to 60s", "clawdmatt")
        results = cl.get_corrections_for("timeout")
        assert len(results) == 1
        assert results[0]["fix_applied"] == "increased timeout to 60s"
        assert results[0]["bot"] == "clawdmatt"

    def test_no_match_returns_empty(self, tmp_data_dir):
        cl = CorrectionLoop(tmp_data_dir)
        cl.record_correction("timeout", "detail", "fix", "bot1")
        assert cl.get_corrections_for("auth_error") == []

    def test_multiple_corrections_same_type(self, tmp_data_dir):
        cl = CorrectionLoop(tmp_data_dir)
        cl.record_correction("timeout", "d1", "f1", "bot1")
        cl.record_correction("timeout", "d2", "f2", "bot2")
        assert len(cl.get_corrections_for("timeout")) == 2

    def test_empty_file(self, tmp_data_dir):
        cl = CorrectionLoop(tmp_data_dir)
        assert cl.get_corrections_for("anything") == []

    def test_corrupted_file(self, tmp_data_dir):
        cl = CorrectionLoop(tmp_data_dir)
        cl.corrections_file.write_text("NOT JSON")
        assert cl._load() == []


class TestStrategyLoop:
    def test_no_data_returns_empty(self, tmp_data_dir):
        sl = StrategyLoop(tmp_data_dir)
        assert sl.analyze_patterns() == []

    def test_recurring_error_detected(self, tmp_data_dir):
        corrections = [
            {"error_type": "timeout", "bot": "b1"} for _ in range(3)
        ]
        Path(tmp_data_dir, "corrections.json").write_text(json.dumps(corrections))
        sl = StrategyLoop(tmp_data_dir)
        insights = sl.analyze_patterns()
        assert any(i["type"] == "recurring_error" for i in insights)
        assert insights[0]["severity"] == "medium"

    def test_high_severity_at_5(self, tmp_data_dir):
        corrections = [{"error_type": "crash", "bot": "b1"} for _ in range(5)]
        Path(tmp_data_dir, "corrections.json").write_text(json.dumps(corrections))
        sl = StrategyLoop(tmp_data_dir)
        insights = sl.analyze_patterns()
        recurring = [i for i in insights if i["type"] == "recurring_error"]
        assert recurring[0]["severity"] == "high"

    def test_budget_warning(self, tmp_data_dir):
        Path(tmp_data_dir, "cost_tracker.json").write_text(
            json.dumps({"daily_total": 9.5, "daily_limit": 10.0})
        )
        sl = StrategyLoop(tmp_data_dir)
        insights = sl.analyze_patterns()
        assert any(i["type"] == "budget_warning" for i in insights)

    def test_no_budget_warning_under_threshold(self, tmp_data_dir):
        Path(tmp_data_dir, "cost_tracker.json").write_text(
            json.dumps({"daily_total": 5.0, "daily_limit": 10.0})
        )
        sl = StrategyLoop(tmp_data_dir)
        insights = sl.analyze_patterns()
        assert not any(i["type"] == "budget_warning" for i in insights)

    def test_insights_saved_to_file(self, tmp_data_dir):
        sl = StrategyLoop(tmp_data_dir)
        sl.analyze_patterns()
        assert sl.insights_file.exists()
        data = json.loads(sl.insights_file.read_text())
        assert "generated_at" in data
        assert "insights" in data


class TestCapabilityLoop:
    def test_request_and_list(self, tmp_data_dir):
        cap = CapabilityLoop(tmp_data_dir)
        req = cap.request_skill("web-scraper", "need to scrape data", "clawdjarvis")
        assert req["status"] == "pending"
        pending = cap.get_pending_requests()
        assert len(pending) == 1

    def test_approve_request(self, tmp_data_dir):
        cap = CapabilityLoop(tmp_data_dir)
        cap.request_skill("web-scraper", "need it", "bot1")
        cap.approve_request("web-scraper")
        assert len(cap.get_pending_requests()) == 0

    def test_approve_nonexistent(self, tmp_data_dir):
        cap = CapabilityLoop(tmp_data_dir)
        cap.approve_request("nonexistent")  # should not raise


class TestCohesionLoop:
    def test_share_and_retrieve(self, tmp_data_dir):
        co = CohesionLoop(tmp_data_dir)
        co.share_observation("bot1", "market is volatile", "market")
        obs = co.get_recent_observations()
        assert len(obs) == 1
        assert obs[0]["observation"] == "market is volatile"

    def test_exclude_bot(self, tmp_data_dir):
        co = CohesionLoop(tmp_data_dir)
        co.share_observation("bot1", "obs1")
        co.share_observation("bot2", "obs2")
        obs = co.get_recent_observations(exclude_bot="bot1")
        assert all(o["bot"] != "bot1" for o in obs)

    def test_filter_category(self, tmp_data_dir):
        co = CohesionLoop(tmp_data_dir)
        co.share_observation("bot1", "obs1", "market")
        co.share_observation("bot1", "obs2", "error_fix")
        obs = co.get_recent_observations(category="market")
        assert len(obs) == 1

    def test_cap_at_100(self, tmp_data_dir):
        co = CohesionLoop(tmp_data_dir)
        for i in range(110):
            co.share_observation("bot1", f"obs{i}")
        all_obs = co._load()
        assert len(all_obs) == 100

    def test_limit(self, tmp_data_dir):
        co = CohesionLoop(tmp_data_dir)
        for i in range(20):
            co.share_observation("bot1", f"obs{i}")
        obs = co.get_recent_observations(limit=5)
        assert len(obs) == 5


class TestKaizenEngine:
    def test_on_error_records_both(self, tmp_data_dir):
        ke = KaizenEngine(tmp_data_dir)
        ke.on_error("timeout", "slow api", "retry with backoff", "clawdmatt")
        assert len(ke.correction.get_corrections_for("timeout")) == 1
        obs = ke.cohesion.get_recent_observations(category="error_fix")
        assert len(obs) == 1

    def test_request_tool(self, tmp_data_dir):
        ke = KaizenEngine(tmp_data_dir)
        req = ke.request_tool("pdf-reader", "need to parse docs", "clawdjarvis")
        assert req["status"] == "pending"

    def test_share_learning(self, tmp_data_dir):
        ke = KaizenEngine(tmp_data_dir)
        ke.share_learning("bot1", "use exponential backoff for rate limits", "best_practice")
        obs = ke.cohesion.get_recent_observations(category="best_practice")
        assert len(obs) == 1

    def test_weekly_analysis(self, tmp_data_dir):
        ke = KaizenEngine(tmp_data_dir)
        # No data = no insights
        assert ke.weekly_analysis() == []
