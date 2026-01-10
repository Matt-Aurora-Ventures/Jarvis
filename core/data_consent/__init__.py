"""
Data Consent & Collection System.

Manages user consent for data collection and usage:

Consent Tiers:
- TIER_0: No data collection (opt-out completely)
- TIER_1: Anonymous improvement data (helps improve the system)
- TIER_2: Marketplace participation (earn from your data)

Key Principles:
- Explicit opt-in required
- Easy opt-out at any time
- Full transparency on what's collected
- Data deletion on request (GDPR compliant)

Usage:
    from core.data_consent import (
        get_consent_manager,
        ConsentTier,
        check_consent,
        record_consent,
    )

    # Check user's consent level
    tier = await check_consent(user_id)

    # Update consent
    await record_consent(user_id, ConsentTier.TIER_1)
"""

from core.data_consent.manager import (
    ConsentManager,
    get_consent_manager,
)
from core.data_consent.models import (
    ConsentTier,
    ConsentRecord,
    DataCategory,
)
from core.data_consent.collector import (
    DataCollector,
    AnonymizedData,
)

__all__ = [
    # Manager
    "ConsentManager",
    "get_consent_manager",
    # Models
    "ConsentTier",
    "ConsentRecord",
    "DataCategory",
    # Collector
    "DataCollector",
    "AnonymizedData",
]
