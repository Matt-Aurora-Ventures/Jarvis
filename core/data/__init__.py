"""
Data Collection System
Prompts #87-91: Anonymous data collection, validation, deletion, and aggregation

Provides:
- Consent-based data collection (Prompt #87)
- Anonymous trade data collection (Prompt #88)
- GDPR-compliant data deletion (Prompt #89)
- Data quality validation (Prompt #90)
- Trade outcome aggregation (Prompt #91)
"""

from core.data.anonymizer import DataAnonymizer, get_anonymizer
from core.data.collector import TradeDataCollector, get_trade_collector
from core.data.deletion import DataDeletionService, get_deletion_service
from core.data.validation import DataValidator, get_data_validator
from core.data.aggregator import TradeAggregator, get_trade_aggregator

__all__ = [
    "DataAnonymizer",
    "get_anonymizer",
    "TradeDataCollector",
    "get_trade_collector",
    "DataDeletionService",
    "get_deletion_service",
    "DataValidator",
    "get_data_validator",
    "TradeAggregator",
    "get_trade_aggregator",
]
