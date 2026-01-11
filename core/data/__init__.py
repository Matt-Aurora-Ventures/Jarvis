"""
Data Collection System

GDPR-compliant data collection, anonymization, and management.
"""

from core.data.anonymizer import DataAnonymizer, AnonymizationConfig
from core.data.collector import TradeDataCollector
from core.data.deletion import DataDeletionService, DeletionScope
from core.data.retention import RetentionManager, RetentionPolicy
from core.data.validation import DataValidator, ValidationResult
from core.data.anomaly import AnomalyDetector, Anomaly, AnomalyType
from core.data.quality import QualityMetrics, QualityReport
from core.data.metrics import DataCollectionMonitor, get_data_collection_monitor

__all__ = [
    # Anonymization
    "DataAnonymizer",
    "AnonymizationConfig",
    # Collection
    "TradeDataCollector",
    # Deletion
    "DataDeletionService",
    "DeletionScope",
    # Retention
    "RetentionManager",
    "RetentionPolicy",
    # Validation
    "DataValidator",
    "ValidationResult",
    # Anomaly Detection
    "AnomalyDetector",
    "Anomaly",
    "AnomalyType",
    # Quality
    "QualityMetrics",
    "QualityReport",
    # Metrics
    "DataCollectionMonitor",
    "get_data_collection_monitor",
]
