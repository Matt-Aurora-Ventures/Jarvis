"""
Data Quality Metrics
Prompt #90: Comprehensive data quality scoring and monitoring

Provides quality metrics for collected data.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json

from core.data.validation import DataValidator, get_data_validator
from core.data.anomaly import AnomalyDetector, get_anomaly_detector

logger = logging.getLogger("jarvis.data.quality")


# =============================================================================
# MODELS
# =============================================================================

class QualityDimension(Enum):
    """Dimensions of data quality"""
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"


@dataclass
class DimensionScore:
    """Score for a single quality dimension"""
    dimension: QualityDimension
    score: float  # 0.0 to 1.0
    sample_size: int
    issues: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    """Complete quality report"""
    overall_score: float
    dimension_scores: Dict[str, DimensionScore]
    record_count: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    recommendations: List[str] = field(default_factory=list)


# =============================================================================
# QUALITY METRICS
# =============================================================================

class QualityMetrics:
    """
    Calculates comprehensive data quality metrics.

    Dimensions:
    - Completeness: Required fields populated
    - Accuracy: Values within expected ranges
    - Consistency: No contradictory data
    - Timeliness: Data freshness
    - Uniqueness: No duplicates
    - Validity: Passes validation rules
    """

    # Required fields for completeness
    REQUIRED_FIELDS = [
        "user_hash",
        "time_bucket",
        "token_mint",
        "side",
    ]

    # Fields that should have values
    EXPECTED_FIELDS = [
        "amount_bucket",
        "outcome",
        "strategy_name",
    ]

    def __init__(
        self,
        db_path: str = None,
        validator: DataValidator = None,
        anomaly_detector: AnomalyDetector = None,
    ):
        self.db_path = db_path or os.getenv("TRADE_DATA_DB", "data/trade_data.db")
        self._validator = validator or get_data_validator()
        self._anomaly_detector = anomaly_detector or get_anomaly_detector()

    # =========================================================================
    # QUALITY ASSESSMENT
    # =========================================================================

    async def assess_quality(
        self,
        since: datetime = None,
        until: datetime = None,
    ) -> QualityReport:
        """
        Assess overall data quality.

        Args:
            since: Start of assessment period
            until: End of assessment period

        Returns:
            QualityReport with scores and recommendations
        """
        # Get data for assessment
        records = await self._get_records(since, until)

        if not records:
            return QualityReport(
                overall_score=1.0,
                dimension_scores={},
                record_count=0,
                period_start=since,
                period_end=until,
            )

        # Calculate each dimension
        dimension_scores = {}

        # Completeness
        completeness = self._assess_completeness(records)
        dimension_scores[QualityDimension.COMPLETENESS.value] = completeness

        # Accuracy (via anomaly detection)
        accuracy = self._assess_accuracy(records)
        dimension_scores[QualityDimension.ACCURACY.value] = accuracy

        # Consistency
        consistency = self._assess_consistency(records)
        dimension_scores[QualityDimension.CONSISTENCY.value] = consistency

        # Timeliness
        timeliness = self._assess_timeliness(records)
        dimension_scores[QualityDimension.TIMELINESS.value] = timeliness

        # Uniqueness
        uniqueness = self._assess_uniqueness(records)
        dimension_scores[QualityDimension.UNIQUENESS.value] = uniqueness

        # Validity
        validity = self._assess_validity(records)
        dimension_scores[QualityDimension.VALIDITY.value] = validity

        # Calculate overall score (weighted average)
        weights = {
            QualityDimension.COMPLETENESS.value: 0.20,
            QualityDimension.ACCURACY.value: 0.20,
            QualityDimension.CONSISTENCY.value: 0.15,
            QualityDimension.TIMELINESS.value: 0.15,
            QualityDimension.UNIQUENESS.value: 0.15,
            QualityDimension.VALIDITY.value: 0.15,
        }

        overall_score = sum(
            dimension_scores[dim].score * weights.get(dim, 0.1)
            for dim in dimension_scores
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(dimension_scores)

        return QualityReport(
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            record_count=len(records),
            period_start=since,
            period_end=until,
            recommendations=recommendations,
        )

    # =========================================================================
    # DIMENSION ASSESSMENTS
    # =========================================================================

    def _assess_completeness(self, records: List[Dict]) -> DimensionScore:
        """Assess data completeness"""
        if not records:
            return DimensionScore(
                dimension=QualityDimension.COMPLETENESS,
                score=1.0,
                sample_size=0,
            )

        total_fields = len(self.REQUIRED_FIELDS) + len(self.EXPECTED_FIELDS)
        total_checks = len(records) * total_fields
        missing_count = 0

        field_missing: Dict[str, int] = {}

        for record in records:
            for field_name in self.REQUIRED_FIELDS + self.EXPECTED_FIELDS:
                value = record.get(field_name)
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    missing_count += 1
                    field_missing[field_name] = field_missing.get(field_name, 0) + 1

        completeness_score = 1.0 - (missing_count / total_checks) if total_checks > 0 else 1.0

        return DimensionScore(
            dimension=QualityDimension.COMPLETENESS,
            score=completeness_score,
            sample_size=len(records),
            issues=missing_count,
            details={
                "missing_by_field": field_missing,
                "total_missing": missing_count,
            },
        )

    def _assess_accuracy(self, records: List[Dict]) -> DimensionScore:
        """Assess data accuracy via anomaly detection"""
        if not records:
            return DimensionScore(
                dimension=QualityDimension.ACCURACY,
                score=1.0,
                sample_size=0,
            )

        results, counts = self._anomaly_detector.check_batch(records)

        # Count records with anomalies
        anomaly_count = sum(1 for r in results if r.has_anomalies)
        accuracy_score = 1.0 - (anomaly_count / len(records))

        return DimensionScore(
            dimension=QualityDimension.ACCURACY,
            score=accuracy_score,
            sample_size=len(records),
            issues=anomaly_count,
            details={
                "anomaly_counts": counts,
                "anomalous_records": anomaly_count,
            },
        )

    def _assess_consistency(self, records: List[Dict]) -> DimensionScore:
        """Assess data consistency (no contradictions)"""
        if not records:
            return DimensionScore(
                dimension=QualityDimension.CONSISTENCY,
                score=1.0,
                sample_size=0,
            )

        inconsistencies = 0

        for record in records:
            # Check outcome vs pnl_pct consistency
            outcome = record.get("outcome")
            pnl_pct = record.get("pnl_pct")

            if pnl_pct is not None and outcome:
                if outcome == "win" and pnl_pct < 0:
                    inconsistencies += 1
                elif outcome == "loss" and pnl_pct > 0:
                    inconsistencies += 1
                elif outcome == "break_even" and abs(pnl_pct) > 0.01:
                    inconsistencies += 1

            # Check side consistency
            side = record.get("side")
            if side and side not in ["buy", "sell", ""]:
                inconsistencies += 1

        consistency_score = 1.0 - (inconsistencies / len(records))

        return DimensionScore(
            dimension=QualityDimension.CONSISTENCY,
            score=consistency_score,
            sample_size=len(records),
            issues=inconsistencies,
            details={
                "inconsistent_records": inconsistencies,
            },
        )

    def _assess_timeliness(self, records: List[Dict]) -> DimensionScore:
        """Assess data timeliness (freshness)"""
        if not records:
            return DimensionScore(
                dimension=QualityDimension.TIMELINESS,
                score=1.0,
                sample_size=0,
            )

        now = datetime.now(timezone.utc)
        stale_threshold = timedelta(days=7)  # Records older than 7 days are "stale"
        very_stale_threshold = timedelta(days=30)

        stale_count = 0
        very_stale_count = 0

        for record in records:
            collected_at = record.get("collected_at")
            if collected_at:
                try:
                    collected = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
                    age = now - collected

                    if age > very_stale_threshold:
                        very_stale_count += 1
                    elif age > stale_threshold:
                        stale_count += 1
                except (ValueError, TypeError):
                    pass

        # Weight very stale records more heavily
        timeliness_penalty = (stale_count * 0.5 + very_stale_count * 1.0) / len(records)
        timeliness_score = max(0.0, 1.0 - timeliness_penalty)

        return DimensionScore(
            dimension=QualityDimension.TIMELINESS,
            score=timeliness_score,
            sample_size=len(records),
            issues=stale_count + very_stale_count,
            details={
                "stale_records": stale_count,
                "very_stale_records": very_stale_count,
            },
        )

    def _assess_uniqueness(self, records: List[Dict]) -> DimensionScore:
        """Assess data uniqueness (no duplicates)"""
        if not records:
            return DimensionScore(
                dimension=QualityDimension.UNIQUENESS,
                score=1.0,
                sample_size=0,
            )

        # Create fingerprints for duplicate detection
        fingerprints = set()
        duplicates = 0

        for record in records:
            # Create fingerprint from key fields
            fingerprint = (
                record.get("user_hash", ""),
                record.get("time_bucket", ""),
                record.get("token_mint", ""),
                record.get("side", ""),
                str(record.get("amount_bucket", "")),
            )

            if fingerprint in fingerprints:
                duplicates += 1
            else:
                fingerprints.add(fingerprint)

        uniqueness_score = 1.0 - (duplicates / len(records))

        return DimensionScore(
            dimension=QualityDimension.UNIQUENESS,
            score=uniqueness_score,
            sample_size=len(records),
            issues=duplicates,
            details={
                "duplicate_records": duplicates,
                "unique_records": len(fingerprints),
            },
        )

    def _assess_validity(self, records: List[Dict]) -> DimensionScore:
        """Assess data validity via validation rules"""
        if not records:
            return DimensionScore(
                dimension=QualityDimension.VALIDITY,
                score=1.0,
                sample_size=0,
            )

        results, validity_rate = self._validator.validate_batch(records, "trade")

        invalid_count = sum(1 for r in results if not r.is_valid)
        summary = self._validator.get_issues_summary(results)

        return DimensionScore(
            dimension=QualityDimension.VALIDITY,
            score=validity_rate,
            sample_size=len(records),
            issues=summary.get("total_issues", 0),
            details=summary,
        )

    # =========================================================================
    # RECOMMENDATIONS
    # =========================================================================

    def _generate_recommendations(
        self,
        scores: Dict[str, DimensionScore],
    ) -> List[str]:
        """Generate recommendations based on scores"""
        recommendations = []

        for dim_name, score in scores.items():
            if score.score < 0.8:
                if dim_name == QualityDimension.COMPLETENESS.value:
                    missing_fields = score.details.get("missing_by_field", {})
                    if missing_fields:
                        top_missing = sorted(
                            missing_fields.items(),
                            key=lambda x: -x[1]
                        )[:3]
                        fields = ", ".join(f[0] for f in top_missing)
                        recommendations.append(
                            f"Improve data collection for fields: {fields}"
                        )

                elif dim_name == QualityDimension.ACCURACY.value:
                    recommendations.append(
                        "Review data collection sources for accuracy issues"
                    )

                elif dim_name == QualityDimension.CONSISTENCY.value:
                    recommendations.append(
                        "Add validation rules to ensure outcome matches P&L"
                    )

                elif dim_name == QualityDimension.TIMELINESS.value:
                    stale = score.details.get("very_stale_records", 0)
                    if stale > 0:
                        recommendations.append(
                            f"Archive or remove {stale} very stale records"
                        )

                elif dim_name == QualityDimension.UNIQUENESS.value:
                    dupes = score.details.get("duplicate_records", 0)
                    if dupes > 0:
                        recommendations.append(
                            f"Investigate and remove {dupes} duplicate records"
                        )

                elif dim_name == QualityDimension.VALIDITY.value:
                    issues = score.details.get("issues_by_rule", {})
                    if issues:
                        top_rule = list(issues.keys())[0]
                        recommendations.append(
                            f"Fix validation issues for rule: {top_rule}"
                        )

        return recommendations

    # =========================================================================
    # DATA ACCESS
    # =========================================================================

    async def _get_records(
        self,
        since: datetime = None,
        until: datetime = None,
    ) -> List[Dict]:
        """Get records for assessment"""
        if not os.path.exists(self.db_path):
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM anonymized_trades WHERE 1=1"
        params = []

        if since:
            query += " AND collected_at >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND collected_at <= ?"
            params.append(until.isoformat())

        query += " ORDER BY collected_at DESC LIMIT 10000"  # Limit for performance

        try:
            cursor.execute(query, params)
            columns = [d[0] for d in cursor.description]
            records = [dict(zip(columns, row)) for row in cursor.fetchall()]
        except sqlite3.Error:
            records = []

        conn.close()
        return records

    # =========================================================================
    # HISTORICAL TRACKING
    # =========================================================================

    async def save_report(self, report: QualityReport):
        """Save quality report for historical tracking"""
        metrics_db = os.getenv("METRICS_DB", "data/metrics.db")
        os.makedirs(os.path.dirname(metrics_db), exist_ok=True)

        conn = sqlite3.connect(metrics_db)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                overall_score REAL NOT NULL,
                record_count INTEGER,
                period_start TEXT,
                period_end TEXT,
                scores_json TEXT,
                recommendations_json TEXT
            )
        """)

        cursor.execute("""
            INSERT INTO quality_reports
            (timestamp, overall_score, record_count, period_start, period_end,
             scores_json, recommendations_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            report.timestamp.isoformat(),
            report.overall_score,
            report.record_count,
            report.period_start.isoformat() if report.period_start else None,
            report.period_end.isoformat() if report.period_end else None,
            json.dumps({
                dim: {
                    "score": score.score,
                    "issues": score.issues,
                    "sample_size": score.sample_size,
                }
                for dim, score in report.dimension_scores.items()
            }),
            json.dumps(report.recommendations),
        ))

        conn.commit()
        conn.close()

    async def get_quality_trend(
        self,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get quality score trend over time"""
        metrics_db = os.getenv("METRICS_DB", "data/metrics.db")

        if not os.path.exists(metrics_db):
            return []

        conn = sqlite3.connect(metrics_db)
        cursor = conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT timestamp, overall_score, record_count, scores_json
            FROM quality_reports
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (since,))

        trend = []
        for row in cursor.fetchall():
            trend.append({
                "timestamp": row[0],
                "overall_score": row[1],
                "record_count": row[2],
                "scores": json.loads(row[3]) if row[3] else {},
            })

        conn.close()
        return trend


# =============================================================================
# SINGLETON
# =============================================================================

_quality_metrics: Optional[QualityMetrics] = None


def get_quality_metrics() -> QualityMetrics:
    """Get or create the quality metrics singleton"""
    global _quality_metrics
    if _quality_metrics is None:
        _quality_metrics = QualityMetrics()
    return _quality_metrics
