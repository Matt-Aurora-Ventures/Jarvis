"""
Provenance Tracking

Tracks the origin and transformation history of all data flowing through the AI system.
"""
import logging
from typing import List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class ProvenanceRecord:
    """A single provenance record tracking data origin and transformations."""

    data_id: str
    source: str
    component: str
    timestamp: datetime
    transformations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_transformation(self, transformation: str, by_component: str):
        """Record a transformation applied to this data."""
        self.transformations.append(
            f"{datetime.utcnow().isoformat()} - {by_component}: {transformation}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "data_id": self.data_id,
            "source": self.source,
            "component": self.component,
            "timestamp": self.timestamp.isoformat(),
            "transformations": self.transformations,
            "metadata": self.metadata,
        }


class ProvenanceTracker:
    """
    Tracks data provenance throughout the AI system.

    Ensures we can always trace back where data came from and
    how it was transformed.
    """

    def __init__(self):
        self._records: Dict[str, ProvenanceRecord] = {}

    def create_record(
        self,
        data_id: str,
        source: str,
        component: str,
        metadata: Dict[str, Any] = None,
    ) -> ProvenanceRecord:
        """Create a new provenance record."""
        record = ProvenanceRecord(
            data_id=data_id,
            source=source,
            component=component,
            timestamp=datetime.utcnow(),
            metadata=metadata or {},
        )
        self._records[data_id] = record
        logger.debug(f"Created provenance record for {data_id} from {source}")
        return record

    def get_record(self, data_id: str) -> ProvenanceRecord:
        """Get provenance record for data."""
        return self._records.get(data_id)

    def add_transformation(
        self, data_id: str, transformation: str, by_component: str
    ) -> bool:
        """Record a transformation on existing data."""
        record = self._records.get(data_id)
        if record:
            record.add_transformation(transformation, by_component)
            return True
        else:
            logger.warning(f"No provenance record found for {data_id}")
            return False

    def get_audit_trail(self, data_id: str) -> Dict[str, Any]:
        """Get complete audit trail for data."""
        record = self._records.get(data_id)
        if record:
            return record.to_dict()
        return {}

    def export_records(self, since: datetime = None) -> List[Dict[str, Any]]:
        """Export all provenance records, optionally filtered by time."""
        records = []
        for record in self._records.values():
            if since is None or record.timestamp >= since:
                records.append(record.to_dict())
        return records
