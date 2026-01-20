"""
Unit Tests for Dexter Confidence Scoring System

Tests:
- Confidence calibration based on historical accuracy
- Decision-type specific thresholds
- Outcome tracking and learning
- Confidence decay for stale analysis
- Calibration statistics and reporting
"""

import unittest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from core.dexter.confidence_scorer import (
    ConfidenceScorer,
    ConfidenceThresholds,
    ConfidenceCalibration,
    OutcomeRecord,
    ConfidenceCalibrationStats
)


class TestConfidenceThresholds(unittest.TestCase):
    """Test confidence threshold configuration."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = ConfidenceThresholds()

        self.assertEqual(thresholds.buy_threshold, 70.0)
        self.assertEqual(thresholds.sell_threshold, 70.0)
        self.assertEqual(thresholds.buy_high_confidence, 85.0)
        self.assertEqual(thresholds.sell_high_confidence, 85.0)
        self.assertEqual(thresholds.absolute_minimum, 60.0)

    def test_custom_thresholds(self):
        """Test custom threshold configuration."""
        thresholds = ConfidenceThresholds(
            buy_threshold=75.0,
            sell_threshold=80.0,
            absolute_minimum=65.0
        )

        self.assertEqual(thresholds.buy_threshold, 75.0)
        self.assertEqual(thresholds.sell_threshold, 80.0)
        self.assertEqual(thresholds.absolute_minimum, 65.0)


class TestConfidenceScorerInitialization(unittest.TestCase):
    """Test ConfidenceScorer initialization."""

    def test_init_creates_directory(self):
        """Test initialization creates data directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            data_path = Path(tmpdir)
            self.assertTrue(data_path.exists())

    def test_init_with_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_thresholds = ConfidenceThresholds(buy_threshold=80.0)
            scorer = ConfidenceScorer(
                data_dir=tmpdir,
                thresholds=custom_thresholds
            )

            self.assertEqual(scorer.thresholds.buy_threshold, 80.0)

    def test_init_loads_existing_outcomes(self):
        """Test initialization loads existing outcome data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some outcome data
            outcomes_file = Path(tmpdir) / "outcomes.jsonl"
            with open(outcomes_file, 'w') as f:
                outcome = OutcomeRecord(
                    decision_id="test1",
                    symbol="SOL",
                    decision="BUY",
                    predicted_confidence=75.0,
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                f.write(json.dumps({
                    "decision_id": outcome.decision_id,
                    "symbol": outcome.symbol,
                    "decision": outcome.decision,
                    "predicted_confidence": outcome.predicted_confidence,
                    "timestamp": outcome.timestamp,
                    "actual_accuracy_5min": None,
                    "actual_accuracy_1h": None,
                    "actual_accuracy_4h": None,
                    "pnl_pct_5min": None,
                    "pnl_pct_1h": None,
                    "pnl_pct_4h": None,
                    "iterations": 0,
                    "tools_used": [],
                    "grok_sentiment": 0.0
                }) + '\n')

            # Load scorer
            scorer = ConfidenceScorer(data_dir=tmpdir)

            self.assertEqual(len(scorer.outcomes), 1)
            self.assertEqual(scorer.outcomes[0].decision_id, "test1")


class TestConfidenceScoring(unittest.TestCase):
    """Test confidence scoring and calibration."""

    def test_score_confidence_basic(self):
        """Test basic confidence scoring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            calibrated, note = scorer.score_confidence(
                raw_confidence=75.0,
                decision="BUY",
                symbol="SOL"
            )

            # Without historical data, should be close to raw
            self.assertGreater(calibrated, 0.0)
            self.assertLessEqual(calibrated, 95.0)
            self.assertIsInstance(note, str)

    def test_score_confidence_with_iterations(self):
        """Test confidence scoring considers iteration count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Low iterations (rushed)
            rushed_conf, rushed_note = scorer.score_confidence(
                raw_confidence=80.0,
                decision="BUY",
                symbol="SOL",
                iterations=1
            )

            # High iterations (thorough)
            thorough_conf, thorough_note = scorer.score_confidence(
                raw_confidence=80.0,
                decision="BUY",
                symbol="SOL",
                iterations=10
            )

            # Rushed should have penalty
            self.assertLess(rushed_conf, thorough_conf)
            self.assertIn("rushed", rushed_note.lower())

    def test_score_confidence_caps_at_95(self):
        """Test confidence is capped at 95%."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            calibrated, _ = scorer.score_confidence(
                raw_confidence=100.0,
                decision="BUY",
                symbol="SOL",
                iterations=10
            )

            self.assertLessEqual(calibrated, 95.0)

    def test_score_confidence_floor_at_0(self):
        """Test confidence is floored at 0%."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            calibrated, _ = scorer.score_confidence(
                raw_confidence=-10.0,
                decision="BUY",
                symbol="SOL"
            )

            self.assertGreaterEqual(calibrated, 0.0)


class TestActionThresholds(unittest.TestCase):
    """Test should_take_action and is_high_confidence."""

    def test_should_take_action_buy(self):
        """Test BUY action threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Above threshold
            self.assertTrue(scorer.should_take_action(75.0, "BUY"))

            # Below threshold
            self.assertFalse(scorer.should_take_action(65.0, "BUY"))

    def test_should_take_action_sell(self):
        """Test SELL action threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Above threshold
            self.assertTrue(scorer.should_take_action(75.0, "SELL"))

            # Below threshold
            self.assertFalse(scorer.should_take_action(65.0, "SELL"))

    def test_should_take_action_hold_always_allowed(self):
        """Test HOLD is always allowed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            self.assertTrue(scorer.should_take_action(0.0, "HOLD"))
            self.assertTrue(scorer.should_take_action(50.0, "HOLD"))
            self.assertTrue(scorer.should_take_action(100.0, "HOLD"))

    def test_should_take_action_absolute_minimum(self):
        """Test absolute minimum threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            thresholds = ConfidenceThresholds(absolute_minimum=65.0)
            scorer = ConfidenceScorer(data_dir=tmpdir, thresholds=thresholds)

            # Below absolute minimum
            self.assertFalse(scorer.should_take_action(60.0, "BUY"))
            self.assertFalse(scorer.should_take_action(60.0, "SELL"))

    def test_is_high_confidence_buy(self):
        """Test high confidence detection for BUY."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # High confidence
            self.assertTrue(scorer.is_high_confidence(90.0, "BUY"))

            # Not high confidence
            self.assertFalse(scorer.is_high_confidence(80.0, "BUY"))

    def test_is_high_confidence_sell(self):
        """Test high confidence detection for SELL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # High confidence
            self.assertTrue(scorer.is_high_confidence(90.0, "SELL"))

            # Not high confidence
            self.assertFalse(scorer.is_high_confidence(80.0, "SELL"))


class TestOutcomeTracking(unittest.TestCase):
    """Test outcome recording and updating."""

    def test_record_decision(self):
        """Test recording a decision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            record = scorer.record_decision(
                decision_id="test1",
                symbol="SOL",
                decision="BUY",
                confidence=75.0,
                grok_sentiment=80.0,
                iterations=5,
                tools_used=["market_data", "sentiment"]
            )

            self.assertEqual(record.decision_id, "test1")
            self.assertEqual(record.symbol, "SOL")
            self.assertEqual(record.decision, "BUY")
            self.assertEqual(record.predicted_confidence, 75.0)
            self.assertEqual(len(scorer.outcomes), 1)

    def test_record_decision_persists_to_file(self):
        """Test decision is persisted to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            scorer.record_decision(
                decision_id="test1",
                symbol="SOL",
                decision="BUY",
                confidence=75.0
            )

            # Check file exists and has content
            outcomes_file = Path(tmpdir) / "outcomes.jsonl"
            self.assertTrue(outcomes_file.exists())

            with open(outcomes_file) as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 1)

    def test_update_outcome(self):
        """Test updating outcome with actual data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Record decision
            scorer.record_decision(
                decision_id="test1",
                symbol="SOL",
                decision="BUY",
                confidence=75.0
            )

            # Update with actual outcome
            success = scorer.update_outcome(
                decision_id="test1",
                actual_accuracy_5min=True,
                actual_accuracy_1h=True,
                pnl_pct_5min=2.5,
                pnl_pct_1h=5.0
            )

            self.assertTrue(success)

            # Check updated values
            record = scorer.outcomes[0]
            self.assertTrue(record.actual_accuracy_5min)
            self.assertTrue(record.actual_accuracy_1h)
            self.assertEqual(record.pnl_pct_5min, 2.5)
            self.assertEqual(record.pnl_pct_1h, 5.0)

    def test_update_outcome_not_found(self):
        """Test updating non-existent outcome."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            success = scorer.update_outcome(
                decision_id="nonexistent",
                actual_accuracy_5min=True
            )

            self.assertFalse(success)


class TestTemporalDecay(unittest.TestCase):
    """Test confidence decay for stale analysis."""

    def test_decay_fresh_analysis(self):
        """Test no decay for fresh analysis (< 15 min)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            decayed = scorer.apply_temporal_decay(
                confidence=80.0,
                decision_age_hours=0.1  # 6 minutes
            )

            self.assertEqual(decayed, 80.0)

    def test_decay_1hour_analysis(self):
        """Test decay for 1-hour old analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            decayed = scorer.apply_temporal_decay(
                confidence=80.0,
                decision_age_hours=0.5  # 30 minutes
            )

            # Should have 5% decay
            self.assertLess(decayed, 80.0)
            self.assertGreater(decayed, 75.0)

    def test_decay_4hour_analysis(self):
        """Test decay for 4-hour old analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            decayed = scorer.apply_temporal_decay(
                confidence=80.0,
                decision_age_hours=2.0
            )

            # Should have 15% decay
            self.assertLess(decayed, 70.0)

    def test_decay_old_analysis(self):
        """Test significant decay for old analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            decayed = scorer.apply_temporal_decay(
                confidence=80.0,
                decision_age_hours=24.0  # 1 day
            )

            # Should have 30% decay
            self.assertLess(decayed, 60.0)


class TestCalibrationStats(unittest.TestCase):
    """Test calibration statistics calculation."""

    def test_get_calibration_stats_empty(self):
        """Test calibration stats with no data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            stats = scorer.get_calibration_stats()

            self.assertEqual(stats.total_decisions, 0)
            self.assertEqual(stats.avg_predicted_confidence, 0.0)

    def test_get_calibration_stats_with_data(self):
        """Test calibration stats with data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Add some decisions
            for i in range(5):
                scorer.record_decision(
                    decision_id=f"test{i}",
                    symbol="SOL",
                    decision="BUY",
                    confidence=70.0 + i * 5.0
                )

            # Update outcomes
            for i in range(5):
                scorer.update_outcome(
                    decision_id=f"test{i}",
                    actual_accuracy_1h=(i % 2 == 0)  # 60% accuracy
                )

            stats = scorer.get_calibration_stats()

            self.assertEqual(stats.total_decisions, 5)
            self.assertGreater(stats.avg_predicted_confidence, 0.0)
            self.assertGreater(stats.avg_actual_accuracy_1h, 0.0)

    def test_calibration_status_well_calibrated(self):
        """Test well-calibrated status detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Create well-calibrated data (predicted ≈ actual)
            for i in range(10):
                scorer.record_decision(
                    decision_id=f"test{i}",
                    symbol="SOL",
                    decision="BUY",
                    confidence=73.0  # Close to 70% actual
                )
                scorer.update_outcome(
                    decision_id=f"test{i}",
                    actual_accuracy_1h=(i < 7)  # 70% accuracy
                )

            stats = scorer.get_calibration_stats()

            # Should be well-calibrated (73% predicted vs 70% actual = 3 point diff)
            self.assertEqual(
                stats.calibration_status_1h,
                ConfidenceCalibration.WELL_CALIBRATED.value
            )

    def test_calibration_status_overconfident(self):
        """Test overconfident status detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Create overconfident data (predicted >> actual)
            for i in range(10):
                scorer.record_decision(
                    decision_id=f"test{i}",
                    symbol="SOL",
                    decision="BUY",
                    confidence=90.0  # High confidence
                )
                scorer.update_outcome(
                    decision_id=f"test{i}",
                    actual_accuracy_1h=(i < 5)  # 50% accuracy
                )

            stats = scorer.get_calibration_stats()

            # Should be overconfident (90% predicted vs 50% actual)
            self.assertEqual(
                stats.calibration_status_1h,
                ConfidenceCalibration.OVERCONFIDENT.value
            )

    def test_calibration_status_overcautious(self):
        """Test overcautious status detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Create overcautious data (predicted << actual)
            for i in range(10):
                scorer.record_decision(
                    decision_id=f"test{i}",
                    symbol="SOL",
                    decision="BUY",
                    confidence=60.0  # Low confidence
                )
                scorer.update_outcome(
                    decision_id=f"test{i}",
                    actual_accuracy_1h=True  # 100% accuracy
                )

            stats = scorer.get_calibration_stats()

            # Should be overcautious (60% predicted vs 100% actual)
            self.assertEqual(
                stats.calibration_status_1h,
                ConfidenceCalibration.OVERCAUTIOUS.value
            )


class TestCalibrationReporting(unittest.TestCase):
    """Test calibration reporting features."""

    def test_save_calibration(self):
        """Test saving calibration to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Add some data
            scorer.record_decision(
                decision_id="test1",
                symbol="SOL",
                decision="BUY",
                confidence=75.0
            )

            path = scorer.save_calibration()

            # Check file exists
            self.assertTrue(Path(path).exists())

            # Check file is valid JSON
            with open(path) as f:
                data = json.load(f)
                self.assertIn("total_decisions", data)

    def test_generate_calibration_report(self):
        """Test generating calibration report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Add some data
            for i in range(5):
                scorer.record_decision(
                    decision_id=f"test{i}",
                    symbol="SOL",
                    decision="BUY",
                    confidence=70.0 + i * 5.0
                )

            report = scorer.generate_calibration_report()

            # Check report structure
            self.assertIn("CONFIDENCE CALIBRATION REPORT", report)
            self.assertIn("OVERALL CALIBRATION", report)
            self.assertIn("CALIBRATION STATUS", report)
            self.assertIsInstance(report, str)
            self.assertGreater(len(report), 100)


class TestCalibrationAdjustment(unittest.TestCase):
    """Test historical calibration adjustments."""

    def test_calibration_adjustment_insufficient_data(self):
        """Test no adjustment when insufficient data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Only a few decisions (< 10)
            for i in range(3):
                scorer.record_decision(
                    decision_id=f"test{i}",
                    symbol="SOL",
                    decision="BUY",
                    confidence=75.0
                )

            calibrated, _ = scorer.score_confidence(
                raw_confidence=80.0,
                decision="BUY",
                symbol="SOL"
            )

            # Should not apply significant adjustment
            self.assertAlmostEqual(calibrated, 80.0, delta=10.0)

    def test_calibration_adjustment_with_data(self):
        """Test adjustment with sufficient calibration data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Create overconfident pattern
            for i in range(20):
                scorer.record_decision(
                    decision_id=f"test{i}",
                    symbol="SOL",
                    decision="BUY",
                    confidence=80.0
                )
                # 50% actual accuracy
                scorer.update_outcome(
                    decision_id=f"test{i}",
                    actual_accuracy_1h=(i % 2 == 0)
                )

            # Score new confidence
            calibrated, _ = scorer.score_confidence(
                raw_confidence=80.0,
                decision="BUY",
                symbol="SOL",
                iterations=5
            )

            # Should be adjusted downward (overconfident pattern)
            self.assertLess(calibrated, 80.0)


if __name__ == '__main__':
    unittest.main()
