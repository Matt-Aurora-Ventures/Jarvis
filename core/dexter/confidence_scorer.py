"""
Dexter Confidence Scoring System

Enhances confidence scoring with:
- Historical accuracy-based calibration
- Decision-type specific thresholds
- Outcome tracking and learning
- Confidence decay for stale analysis
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ConfidenceCalibration(str, Enum):
    """Confidence calibration levels based on historical accuracy."""
    OVERCAUTIOUS = "overcautious"  # Confidence too low vs actual accuracy
    WELL_CALIBRATED = "well_calibrated"  # Confidence matches accuracy
    OVERCONFIDENT = "overconfident"  # Confidence too high vs actual accuracy


@dataclass
class ConfidenceThresholds:
    """Decision-type specific confidence thresholds."""
    # Minimum confidence to take action (vs HOLD)
    buy_threshold: float = 70.0
    sell_threshold: float = 70.0

    # High-confidence thresholds for aggressive sizing
    buy_high_confidence: float = 85.0
    sell_high_confidence: float = 85.0

    # Low-confidence cutoff (always HOLD below this)
    absolute_minimum: float = 60.0


@dataclass
class OutcomeRecord:
    """Record of a decision outcome for calibration."""
    decision_id: str
    symbol: str
    decision: str  # BUY, SELL, HOLD
    predicted_confidence: float
    timestamp: str

    # Outcome data (filled in later)
    actual_accuracy_5min: Optional[bool] = None
    actual_accuracy_1h: Optional[bool] = None
    actual_accuracy_4h: Optional[bool] = None

    # P&L data
    pnl_pct_5min: Optional[float] = None
    pnl_pct_1h: Optional[float] = None
    pnl_pct_4h: Optional[float] = None

    # Metadata
    iterations: int = 0
    tools_used: List[str] = field(default_factory=list)
    grok_sentiment: float = 0.0


@dataclass
class ConfidenceCalibrationStats:
    """Statistics for confidence calibration analysis."""
    total_decisions: int = 0

    # Calibration by confidence bucket
    confidence_buckets: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # Format: {"70-75": {"predicted": 72.5, "actual": 68.2, "count": 12}}

    # Overall calibration
    avg_predicted_confidence: float = 0.0
    avg_actual_accuracy_5min: float = 0.0
    avg_actual_accuracy_1h: float = 0.0
    avg_actual_accuracy_4h: float = 0.0

    # Calibration errors
    calibration_error_5min: float = 0.0  # |predicted - actual|
    calibration_error_1h: float = 0.0
    calibration_error_4h: float = 0.0

    # Calibration status
    calibration_status_5min: str = ConfidenceCalibration.WELL_CALIBRATED.value
    calibration_status_1h: str = ConfidenceCalibration.WELL_CALIBRATED.value
    calibration_status_4h: str = ConfidenceCalibration.WELL_CALIBRATED.value


class ConfidenceScorer:
    """
    Enhanced confidence scoring system for Dexter agent.

    Tracks historical accuracy vs predicted confidence and adjusts
    future confidence scores based on calibration.
    """

    def __init__(
        self,
        data_dir: str = "data/dexter/confidence",
        thresholds: Optional[ConfidenceThresholds] = None
    ):
        """
        Initialize confidence scorer.

        Args:
            data_dir: Directory to store confidence records
            thresholds: Custom confidence thresholds (uses defaults if None)
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.thresholds = thresholds or ConfidenceThresholds()

        # Outcome tracking
        self.outcomes: List[OutcomeRecord] = []
        self.outcomes_file = self.data_dir / "outcomes.jsonl"

        # Calibration data
        self.calibration_file = self.data_dir / "calibration.json"
        self.calibration_stats: Optional[ConfidenceCalibrationStats] = None

        # Load existing data
        self._load_outcomes()
        self._calculate_calibration()

        logger.info(f"ConfidenceScorer initialized: {len(self.outcomes)} historical outcomes")

    def score_confidence(
        self,
        raw_confidence: float,
        decision: str,
        symbol: str,
        grok_sentiment: float = 0.0,
        iterations: int = 0,
        tools_used: Optional[List[str]] = None
    ) -> Tuple[float, str]:
        """
        Score and calibrate confidence based on historical accuracy.

        Args:
            raw_confidence: Raw confidence from Grok/analysis (0-100)
            decision: Decision type (BUY, SELL, HOLD)
            symbol: Token symbol
            grok_sentiment: Grok sentiment score
            iterations: Number of ReAct iterations
            tools_used: List of tools used in analysis

        Returns:
            Tuple of (calibrated_confidence, calibration_note)
        """
        # Apply historical calibration adjustment
        calibrated = self._apply_calibration(raw_confidence, decision)

        # Apply decay for low iteration count (rushed analysis)
        if iterations < 3:
            decay_factor = 0.9  # 10% penalty for rushed decisions
            calibrated *= decay_factor
            note = f"Calibrated: {calibrated:.1f}% (rushed analysis penalty)"
        else:
            note = f"Calibrated: {calibrated:.1f}%"

        # Cap at 95% (never 100% certain)
        calibrated = min(calibrated, 95.0)

        # Floor at 0%
        calibrated = max(calibrated, 0.0)

        return calibrated, note

    def should_take_action(self, confidence: float, decision: str) -> bool:
        """
        Determine if confidence is high enough to take action.

        Args:
            confidence: Calibrated confidence score
            decision: Decision type (BUY, SELL, HOLD)

        Returns:
            True if action should be taken, False if should HOLD
        """
        # Always allow HOLD
        if decision == "HOLD":
            return True

        # Check absolute minimum
        if confidence < self.thresholds.absolute_minimum:
            logger.warning(f"Confidence {confidence:.1f}% below absolute minimum {self.thresholds.absolute_minimum:.1f}%")
            return False

        # Check decision-specific thresholds
        if decision == "BUY" and confidence >= self.thresholds.buy_threshold:
            return True
        elif decision == "SELL" and confidence >= self.thresholds.sell_threshold:
            return True

        return False

    def is_high_confidence(self, confidence: float, decision: str) -> bool:
        """
        Check if confidence is high enough for aggressive action.

        Args:
            confidence: Calibrated confidence score
            decision: Decision type

        Returns:
            True if high confidence
        """
        if decision == "BUY":
            return confidence >= self.thresholds.buy_high_confidence
        elif decision == "SELL":
            return confidence >= self.thresholds.sell_high_confidence
        return False

    def record_decision(
        self,
        decision_id: str,
        symbol: str,
        decision: str,
        confidence: float,
        grok_sentiment: float = 0.0,
        iterations: int = 0,
        tools_used: Optional[List[str]] = None
    ) -> OutcomeRecord:
        """
        Record a decision for future calibration.

        Args:
            decision_id: Unique decision ID
            symbol: Token symbol
            decision: Decision type
            confidence: Predicted confidence
            grok_sentiment: Grok sentiment score
            iterations: Number of iterations
            tools_used: Tools used in analysis

        Returns:
            OutcomeRecord
        """
        record = OutcomeRecord(
            decision_id=decision_id,
            symbol=symbol,
            decision=decision,
            predicted_confidence=confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            iterations=iterations,
            tools_used=tools_used or [],
            grok_sentiment=grok_sentiment
        )

        self.outcomes.append(record)
        self._append_outcome(record)

        logger.info(f"Recorded decision {decision_id}: {decision} {symbol} @ {confidence:.1f}%")

        return record

    def update_outcome(
        self,
        decision_id: str,
        actual_accuracy_5min: Optional[bool] = None,
        actual_accuracy_1h: Optional[bool] = None,
        actual_accuracy_4h: Optional[bool] = None,
        pnl_pct_5min: Optional[float] = None,
        pnl_pct_1h: Optional[float] = None,
        pnl_pct_4h: Optional[float] = None
    ) -> bool:
        """
        Update outcome with actual accuracy data.

        Args:
            decision_id: Decision ID to update
            actual_accuracy_5min: Was prediction accurate at 5 min?
            actual_accuracy_1h: Was prediction accurate at 1 hour?
            actual_accuracy_4h: Was prediction accurate at 4 hours?
            pnl_pct_5min: Actual P&L at 5 min
            pnl_pct_1h: Actual P&L at 1 hour
            pnl_pct_4h: Actual P&L at 4 hours

        Returns:
            True if updated successfully
        """
        record = self._find_outcome(decision_id)
        if not record:
            logger.warning(f"Outcome not found: {decision_id}")
            return False

        # Update accuracy
        if actual_accuracy_5min is not None:
            record.actual_accuracy_5min = actual_accuracy_5min
        if actual_accuracy_1h is not None:
            record.actual_accuracy_1h = actual_accuracy_1h
        if actual_accuracy_4h is not None:
            record.actual_accuracy_4h = actual_accuracy_4h

        # Update P&L
        if pnl_pct_5min is not None:
            record.pnl_pct_5min = pnl_pct_5min
        if pnl_pct_1h is not None:
            record.pnl_pct_1h = pnl_pct_1h
        if pnl_pct_4h is not None:
            record.pnl_pct_4h = pnl_pct_4h

        # Recalculate calibration
        self._calculate_calibration()

        logger.info(f"Updated outcome {decision_id}: 5m={actual_accuracy_5min}, 1h={actual_accuracy_1h}")

        return True

    def apply_temporal_decay(self, confidence: float, decision_age_hours: float) -> float:
        """
        Apply confidence decay for stale analysis.

        Market conditions change rapidly. Analysis older than 15 minutes
        should have reduced confidence.

        Args:
            confidence: Current confidence score
            decision_age_hours: Age of decision in hours

        Returns:
            Decayed confidence score
        """
        # Decay schedule
        if decision_age_hours < 0.25:  # < 15 minutes
            decay = 1.0  # No decay
        elif decision_age_hours < 1.0:  # < 1 hour
            decay = 0.95  # 5% decay
        elif decision_age_hours < 4.0:  # < 4 hours
            decay = 0.85  # 15% decay
        elif decision_age_hours < 24.0:  # < 1 day
            decay = 0.70  # 30% decay
        else:
            decay = 0.50  # 50% decay for day-old analysis

        decayed = confidence * decay

        if decay < 1.0:
            logger.info(f"Applied temporal decay: {confidence:.1f}% → {decayed:.1f}% (age: {decision_age_hours:.1f}h)")

        return decayed

    def get_calibration_stats(self) -> ConfidenceCalibrationStats:
        """
        Get current calibration statistics.

        Returns:
            ConfidenceCalibrationStats
        """
        if not self.calibration_stats:
            self._calculate_calibration()

        return self.calibration_stats or ConfidenceCalibrationStats()

    def save_calibration(self) -> str:
        """
        Save calibration statistics to file.

        Returns:
            Path to calibration file
        """
        stats = self.get_calibration_stats()

        with open(self.calibration_file, 'w') as f:
            json.dump(asdict(stats), f, indent=2)

        logger.info(f"Calibration saved to {self.calibration_file}")
        return str(self.calibration_file)

    def generate_calibration_report(self) -> str:
        """
        Generate human-readable calibration report.

        Returns:
            Formatted report string
        """
        stats = self.get_calibration_stats()

        report = f"""
================================================================================
                    DEXTER CONFIDENCE CALIBRATION REPORT
================================================================================

OVERALL CALIBRATION
-------------------
Total Decisions: {stats.total_decisions}
Avg Predicted Confidence: {stats.avg_predicted_confidence:.1f}%

Actual Accuracy:
  5-minute:  {stats.avg_actual_accuracy_5min:.1f}%
  1-hour:    {stats.avg_actual_accuracy_1h:.1f}%
  4-hour:    {stats.avg_actual_accuracy_4h:.1f}%

CALIBRATION ERRORS (|predicted - actual|)
-----------------------------------------
  5-minute:  {stats.calibration_error_5min:.1f} percentage points
  1-hour:    {stats.calibration_error_1h:.1f} percentage points
  4-hour:    {stats.calibration_error_4h:.1f} percentage points

CALIBRATION STATUS
------------------
  5-minute:  {stats.calibration_status_5min.upper()}
  1-hour:    {stats.calibration_status_1h.upper()}
  4-hour:    {stats.calibration_status_4h.upper()}

CONFIDENCE BUCKET ANALYSIS
--------------------------
"""

        if stats.confidence_buckets:
            for bucket, data in sorted(stats.confidence_buckets.items()):
                report += f"\n  {bucket}%: {data['count']} decisions\n"
                report += f"    Predicted: {data['predicted']:.1f}%\n"
                report += f"    Actual:    {data['actual']:.1f}%\n"
        else:
            report += "  (Insufficient data)\n"

        report += "\n" + "=" * 80 + "\n"

        return report

    # Private methods

    def _apply_calibration(self, raw_confidence: float, decision: str) -> float:
        """Apply historical calibration adjustment to raw confidence."""
        if not self.calibration_stats or self.calibration_stats.total_decisions < 10:
            # Not enough data for calibration
            return raw_confidence

        # Use 1-hour calibration as primary (balanced timeframe)
        predicted_avg = self.calibration_stats.avg_predicted_confidence
        actual_avg = self.calibration_stats.avg_actual_accuracy_1h

        if predicted_avg == 0:
            return raw_confidence

        # Calculate calibration ratio
        calibration_ratio = actual_avg / predicted_avg

        # Apply calibration (with dampening to avoid overcorrection)
        dampening = 0.5  # Only apply 50% of the correction
        adjustment = (calibration_ratio - 1.0) * dampening + 1.0

        calibrated = raw_confidence * adjustment

        logger.debug(f"Calibration: {raw_confidence:.1f}% → {calibrated:.1f}% (ratio: {calibration_ratio:.2f})")

        return calibrated

    def _calculate_calibration(self):
        """Calculate calibration statistics from historical outcomes."""
        stats = ConfidenceCalibrationStats()

        # Filter to outcomes with actual data
        outcomes_5min = [o for o in self.outcomes if o.actual_accuracy_5min is not None]
        outcomes_1h = [o for o in self.outcomes if o.actual_accuracy_1h is not None]
        outcomes_4h = [o for o in self.outcomes if o.actual_accuracy_4h is not None]

        stats.total_decisions = len(self.outcomes)

        if not self.outcomes:
            self.calibration_stats = stats
            return

        # Overall averages
        confidences = [o.predicted_confidence for o in self.outcomes]
        stats.avg_predicted_confidence = sum(confidences) / len(confidences)

        # Actual accuracy by timeframe
        if outcomes_5min:
            stats.avg_actual_accuracy_5min = (
                sum(1 for o in outcomes_5min if o.actual_accuracy_5min) / len(outcomes_5min) * 100
            )
            stats.calibration_error_5min = abs(
                stats.avg_predicted_confidence - stats.avg_actual_accuracy_5min
            )
            stats.calibration_status_5min = self._determine_calibration_status(
                stats.avg_predicted_confidence, stats.avg_actual_accuracy_5min
            )

        if outcomes_1h:
            stats.avg_actual_accuracy_1h = (
                sum(1 for o in outcomes_1h if o.actual_accuracy_1h) / len(outcomes_1h) * 100
            )
            stats.calibration_error_1h = abs(
                stats.avg_predicted_confidence - stats.avg_actual_accuracy_1h
            )
            stats.calibration_status_1h = self._determine_calibration_status(
                stats.avg_predicted_confidence, stats.avg_actual_accuracy_1h
            )

        if outcomes_4h:
            stats.avg_actual_accuracy_4h = (
                sum(1 for o in outcomes_4h if o.actual_accuracy_4h) / len(outcomes_4h) * 100
            )
            stats.calibration_error_4h = abs(
                stats.avg_predicted_confidence - stats.avg_actual_accuracy_4h
            )
            stats.calibration_status_4h = self._determine_calibration_status(
                stats.avg_predicted_confidence, stats.avg_actual_accuracy_4h
            )

        # Bucket analysis (by 5% increments)
        buckets: Dict[str, List[OutcomeRecord]] = {}
        for outcome in outcomes_1h:  # Use 1h as primary
            bucket_start = int(outcome.predicted_confidence // 5) * 5
            bucket_end = bucket_start + 5
            bucket_key = f"{bucket_start}-{bucket_end}"

            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(outcome)

        # Calculate bucket stats
        for bucket_key, bucket_outcomes in buckets.items():
            predicted_avg = sum(o.predicted_confidence for o in bucket_outcomes) / len(bucket_outcomes)
            actual_avg = sum(1 for o in bucket_outcomes if o.actual_accuracy_1h) / len(bucket_outcomes) * 100

            stats.confidence_buckets[bucket_key] = {
                "predicted": predicted_avg,
                "actual": actual_avg,
                "count": len(bucket_outcomes)
            }

        self.calibration_stats = stats

    def _determine_calibration_status(
        self,
        predicted: float,
        actual: float
    ) -> str:
        """Determine calibration status based on predicted vs actual."""
        error = predicted - actual

        if abs(error) < 5.0:
            return ConfidenceCalibration.WELL_CALIBRATED.value
        elif error > 5.0:
            return ConfidenceCalibration.OVERCONFIDENT.value
        else:
            return ConfidenceCalibration.OVERCAUTIOUS.value

    def _find_outcome(self, decision_id: str) -> Optional[OutcomeRecord]:
        """Find outcome record by ID."""
        for outcome in self.outcomes:
            if outcome.decision_id == decision_id:
                return outcome
        return None

    def _append_outcome(self, outcome: OutcomeRecord):
        """Append outcome to JSONL file."""
        with open(self.outcomes_file, 'a') as f:
            f.write(json.dumps(asdict(outcome)) + '\n')

    def _load_outcomes(self):
        """Load historical outcomes from file."""
        if not self.outcomes_file.exists():
            return

        with open(self.outcomes_file) as f:
            for line in f:
                outcome_dict = json.loads(line)
                outcome = OutcomeRecord(**outcome_dict)
                self.outcomes.append(outcome)

        logger.info(f"Loaded {len(self.outcomes)} historical outcomes")


__all__ = [
    "ConfidenceScorer",
    "ConfidenceThresholds",
    "ConfidenceCalibration",
    "OutcomeRecord",
    "ConfidenceCalibrationStats"
]
