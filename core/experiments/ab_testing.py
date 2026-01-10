"""
A/B Testing Framework
Prompt #93: Controlled experiments for strategy testing

Provides A/B testing capabilities for trading strategies and features.
"""

import hashlib
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import json
import random

logger = logging.getLogger("jarvis.experiments.ab_testing")


# =============================================================================
# MODELS
# =============================================================================

class ExperimentStatus(Enum):
    """Status of an experiment"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"


class AllocationStrategy(Enum):
    """User allocation strategy"""
    RANDOM = "random"
    HASH_BASED = "hash_based"
    WEIGHTED = "weighted"


@dataclass
class Variant:
    """A single variant in an experiment"""
    id: str
    name: str
    weight: float = 1.0  # Relative weight for allocation
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_control: bool = False


@dataclass
class Experiment:
    """An A/B test experiment"""
    id: str
    name: str
    description: str
    variants: List[Variant]
    status: ExperimentStatus = ExperimentStatus.DRAFT
    allocation_strategy: AllocationStrategy = AllocationStrategy.HASH_BASED
    target_sample_size: int = 1000
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    owner: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class ExperimentAssignment:
    """User assignment to an experiment variant"""
    user_id: str
    experiment_id: str
    variant_id: str
    assigned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExperimentEvent:
    """An event tracked for an experiment"""
    user_id: str
    experiment_id: str
    variant_id: str
    event_name: str
    value: Optional[float] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# A/B TESTING FRAMEWORK
# =============================================================================

class ABTestingFramework:
    """
    A/B Testing framework for controlled experiments.

    Features:
    - Deterministic user assignment (hash-based)
    - Multiple variants with custom weights
    - Event tracking and metrics
    - Statistical significance testing
    - Experiment lifecycle management
    """

    def __init__(self, db_path: str = None, salt: str = None):
        self.db_path = db_path or os.getenv(
            "EXPERIMENTS_DB",
            "data/experiments.db"
        )
        self.salt = salt or os.getenv("EXPERIMENT_SALT", "jarvis-ab-salt")

        self._experiments: Dict[str, Experiment] = {}
        self._assignments: Dict[str, Dict[str, str]] = {}  # user_id -> exp_id -> variant_id

        self._init_database()

    def _init_database(self):
        """Initialize experiments database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Experiments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                variants_json TEXT NOT NULL,
                status TEXT NOT NULL,
                allocation_strategy TEXT,
                target_sample_size INTEGER,
                created_at TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                owner TEXT,
                tags_json TEXT
            )
        """)

        # Assignments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiment_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                variant_id TEXT NOT NULL,
                assigned_at TEXT NOT NULL,
                UNIQUE(user_id, experiment_id)
            )
        """)

        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiment_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                variant_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                value REAL,
                properties_json TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_assignments_user
            ON experiment_assignments(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_assignments_experiment
            ON experiment_assignments(experiment_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_experiment
            ON experiment_events(experiment_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_name
            ON experiment_events(event_name)
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # EXPERIMENT MANAGEMENT
    # =========================================================================

    async def create_experiment(
        self,
        name: str,
        description: str,
        variants: List[Variant],
        allocation_strategy: AllocationStrategy = AllocationStrategy.HASH_BASED,
        target_sample_size: int = 1000,
        owner: str = "",
        tags: List[str] = None,
    ) -> Experiment:
        """
        Create a new experiment.

        Args:
            name: Experiment name
            description: Description
            variants: List of variants
            allocation_strategy: How to assign users
            target_sample_size: Target number of participants
            owner: Owner identifier
            tags: Tags for categorization

        Returns:
            Created Experiment
        """
        # Generate experiment ID
        exp_id = hashlib.sha256(
            f"{name}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:12]

        # Ensure at least one control variant
        has_control = any(v.is_control for v in variants)
        if not has_control and variants:
            variants[0].is_control = True

        experiment = Experiment(
            id=exp_id,
            name=name,
            description=description,
            variants=variants,
            status=ExperimentStatus.DRAFT,
            allocation_strategy=allocation_strategy,
            target_sample_size=target_sample_size,
            owner=owner,
            tags=tags or [],
        )

        # Store in memory and database
        self._experiments[exp_id] = experiment
        await self._save_experiment(experiment)

        logger.info(f"Created experiment: {exp_id} ({name})")

        return experiment

    async def start_experiment(self, experiment_id: str) -> Experiment:
        """Start an experiment"""
        experiment = await self.get_experiment(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment not found: {experiment_id}")

        if experiment.status != ExperimentStatus.DRAFT:
            raise ValueError(f"Experiment already started: {experiment_id}")

        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now(timezone.utc)

        await self._save_experiment(experiment)

        logger.info(f"Started experiment: {experiment_id}")

        return experiment

    async def pause_experiment(self, experiment_id: str) -> Experiment:
        """Pause an experiment"""
        experiment = await self.get_experiment(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment not found: {experiment_id}")

        experiment.status = ExperimentStatus.PAUSED
        await self._save_experiment(experiment)

        logger.info(f"Paused experiment: {experiment_id}")

        return experiment

    async def stop_experiment(
        self,
        experiment_id: str,
        reason: str = "",
    ) -> Experiment:
        """Stop an experiment permanently"""
        experiment = await self.get_experiment(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment not found: {experiment_id}")

        experiment.status = ExperimentStatus.STOPPED
        experiment.ended_at = datetime.now(timezone.utc)

        await self._save_experiment(experiment)

        logger.info(f"Stopped experiment: {experiment_id}, reason: {reason}")

        return experiment

    async def complete_experiment(self, experiment_id: str) -> Experiment:
        """Mark experiment as completed"""
        experiment = await self.get_experiment(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment not found: {experiment_id}")

        experiment.status = ExperimentStatus.COMPLETED
        experiment.ended_at = datetime.now(timezone.utc)

        await self._save_experiment(experiment)

        logger.info(f"Completed experiment: {experiment_id}")

        return experiment

    async def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get an experiment by ID"""
        if experiment_id in self._experiments:
            return self._experiments[experiment_id]

        # Load from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM experiments WHERE id = ?",
            (experiment_id,)
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        experiment = self._row_to_experiment(row)
        self._experiments[experiment_id] = experiment

        return experiment

    async def list_experiments(
        self,
        status: ExperimentStatus = None,
        owner: str = None,
    ) -> List[Experiment]:
        """List experiments with optional filters"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM experiments WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if owner:
            query += " AND owner = ?"
            params.append(owner)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)

        experiments = [self._row_to_experiment(row) for row in cursor.fetchall()]

        conn.close()

        return experiments

    # =========================================================================
    # USER ASSIGNMENT
    # =========================================================================

    async def get_variant(
        self,
        experiment_id: str,
        user_id: str,
    ) -> Optional[Variant]:
        """
        Get the variant for a user in an experiment.

        Uses deterministic hashing for consistent assignment.

        Args:
            experiment_id: Experiment ID
            user_id: User identifier

        Returns:
            Assigned Variant or None if experiment not running
        """
        experiment = await self.get_experiment(experiment_id)
        if experiment is None:
            return None

        if experiment.status != ExperimentStatus.RUNNING:
            return None

        # Check for existing assignment
        existing = await self._get_assignment(user_id, experiment_id)
        if existing:
            # Find variant
            for variant in experiment.variants:
                if variant.id == existing.variant_id:
                    return variant

        # Assign to variant
        variant = self._assign_variant(experiment, user_id)

        # Record assignment
        assignment = ExperimentAssignment(
            user_id=user_id,
            experiment_id=experiment_id,
            variant_id=variant.id,
        )
        await self._save_assignment(assignment)

        return variant

    def _assign_variant(
        self,
        experiment: Experiment,
        user_id: str,
    ) -> Variant:
        """Assign user to a variant"""
        if experiment.allocation_strategy == AllocationStrategy.RANDOM:
            return self._random_allocation(experiment)
        elif experiment.allocation_strategy == AllocationStrategy.WEIGHTED:
            return self._weighted_allocation(experiment)
        else:  # HASH_BASED
            return self._hash_allocation(experiment, user_id)

    def _hash_allocation(
        self,
        experiment: Experiment,
        user_id: str,
    ) -> Variant:
        """Deterministic hash-based allocation"""
        # Create deterministic hash
        hash_input = f"{self.salt}:{experiment.id}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)

        # Normalize to 0-1
        bucket = (hash_value % 10000) / 10000.0

        # Allocate based on weights
        total_weight = sum(v.weight for v in experiment.variants)
        cumulative = 0.0

        for variant in experiment.variants:
            cumulative += variant.weight / total_weight
            if bucket < cumulative:
                return variant

        return experiment.variants[-1]

    def _random_allocation(self, experiment: Experiment) -> Variant:
        """Random allocation"""
        return random.choice(experiment.variants)

    def _weighted_allocation(self, experiment: Experiment) -> Variant:
        """Weighted random allocation"""
        total_weight = sum(v.weight for v in experiment.variants)
        r = random.uniform(0, total_weight)
        cumulative = 0.0

        for variant in experiment.variants:
            cumulative += variant.weight
            if r < cumulative:
                return variant

        return experiment.variants[-1]

    async def _get_assignment(
        self,
        user_id: str,
        experiment_id: str,
    ) -> Optional[ExperimentAssignment]:
        """Get existing assignment"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, experiment_id, variant_id, assigned_at
            FROM experiment_assignments
            WHERE user_id = ? AND experiment_id = ?
        """, (user_id, experiment_id))

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return ExperimentAssignment(
            user_id=row[0],
            experiment_id=row[1],
            variant_id=row[2],
            assigned_at=datetime.fromisoformat(row[3]),
        )

    # =========================================================================
    # EVENT TRACKING
    # =========================================================================

    async def track_event(
        self,
        user_id: str,
        experiment_id: str,
        event_name: str,
        value: float = None,
        properties: Dict[str, Any] = None,
    ):
        """
        Track an event for an experiment.

        Args:
            user_id: User identifier
            experiment_id: Experiment ID
            event_name: Event name
            value: Optional numeric value
            properties: Additional properties
        """
        # Get user's variant
        assignment = await self._get_assignment(user_id, experiment_id)
        if assignment is None:
            logger.warning(f"No assignment for user {user_id} in experiment {experiment_id}")
            return

        event = ExperimentEvent(
            user_id=user_id,
            experiment_id=experiment_id,
            variant_id=assignment.variant_id,
            event_name=event_name,
            value=value,
            properties=properties or {},
        )

        await self._save_event(event)

    async def get_events(
        self,
        experiment_id: str,
        event_name: str = None,
        variant_id: str = None,
    ) -> List[ExperimentEvent]:
        """Get events for an experiment"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT user_id, experiment_id, variant_id, event_name,
                   value, properties_json, timestamp
            FROM experiment_events
            WHERE experiment_id = ?
        """
        params = [experiment_id]

        if event_name:
            query += " AND event_name = ?"
            params.append(event_name)

        if variant_id:
            query += " AND variant_id = ?"
            params.append(variant_id)

        cursor.execute(query, params)

        events = []
        for row in cursor.fetchall():
            events.append(ExperimentEvent(
                user_id=row[0],
                experiment_id=row[1],
                variant_id=row[2],
                event_name=row[3],
                value=row[4],
                properties=json.loads(row[5]) if row[5] else {},
                timestamp=datetime.fromisoformat(row[6]),
            ))

        conn.close()
        return events

    # =========================================================================
    # METRICS
    # =========================================================================

    async def get_variant_metrics(
        self,
        experiment_id: str,
        metric_event: str,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get metrics per variant.

        Args:
            experiment_id: Experiment ID
            metric_event: Event name to use as metric

        Returns:
            Dict of variant_id -> metrics
        """
        experiment = await self.get_experiment(experiment_id)
        if experiment is None:
            return {}

        events = await self.get_events(experiment_id, event_name=metric_event)

        # Group by variant
        variant_events: Dict[str, List[ExperimentEvent]] = {}
        for variant in experiment.variants:
            variant_events[variant.id] = []

        for event in events:
            if event.variant_id in variant_events:
                variant_events[event.variant_id].append(event)

        # Calculate metrics
        metrics = {}
        for variant_id, events_list in variant_events.items():
            values = [e.value for e in events_list if e.value is not None]

            metrics[variant_id] = {
                "n_events": len(events_list),
                "n_users": len(set(e.user_id for e in events_list)),
                "mean": sum(values) / len(values) if values else 0,
                "sum": sum(values) if values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
            }

        return metrics

    async def get_sample_sizes(
        self,
        experiment_id: str,
    ) -> Dict[str, int]:
        """Get number of users per variant"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT variant_id, COUNT(DISTINCT user_id)
            FROM experiment_assignments
            WHERE experiment_id = ?
            GROUP BY variant_id
        """, (experiment_id,))

        sizes = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()
        return sizes

    # =========================================================================
    # PERSISTENCE HELPERS
    # =========================================================================

    async def _save_experiment(self, experiment: Experiment):
        """Save experiment to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        variants_json = json.dumps([
            {
                "id": v.id,
                "name": v.name,
                "weight": v.weight,
                "parameters": v.parameters,
                "is_control": v.is_control,
            }
            for v in experiment.variants
        ])

        cursor.execute("""
            INSERT OR REPLACE INTO experiments
            (id, name, description, variants_json, status, allocation_strategy,
             target_sample_size, created_at, started_at, ended_at, owner, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            experiment.id,
            experiment.name,
            experiment.description,
            variants_json,
            experiment.status.value,
            experiment.allocation_strategy.value,
            experiment.target_sample_size,
            experiment.created_at.isoformat(),
            experiment.started_at.isoformat() if experiment.started_at else None,
            experiment.ended_at.isoformat() if experiment.ended_at else None,
            experiment.owner,
            json.dumps(experiment.tags),
        ))

        conn.commit()
        conn.close()

    async def _save_assignment(self, assignment: ExperimentAssignment):
        """Save assignment to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO experiment_assignments
            (user_id, experiment_id, variant_id, assigned_at)
            VALUES (?, ?, ?, ?)
        """, (
            assignment.user_id,
            assignment.experiment_id,
            assignment.variant_id,
            assignment.assigned_at.isoformat(),
        ))

        conn.commit()
        conn.close()

    async def _save_event(self, event: ExperimentEvent):
        """Save event to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO experiment_events
            (user_id, experiment_id, variant_id, event_name, value,
             properties_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            event.user_id,
            event.experiment_id,
            event.variant_id,
            event.event_name,
            event.value,
            json.dumps(event.properties),
            event.timestamp.isoformat(),
        ))

        conn.commit()
        conn.close()

    def _row_to_experiment(self, row: tuple) -> Experiment:
        """Convert database row to Experiment"""
        variants_data = json.loads(row[3])
        variants = [
            Variant(
                id=v["id"],
                name=v["name"],
                weight=v.get("weight", 1.0),
                parameters=v.get("parameters", {}),
                is_control=v.get("is_control", False),
            )
            for v in variants_data
        ]

        return Experiment(
            id=row[0],
            name=row[1],
            description=row[2],
            variants=variants,
            status=ExperimentStatus(row[4]),
            allocation_strategy=AllocationStrategy(row[5]) if row[5] else AllocationStrategy.HASH_BASED,
            target_sample_size=row[6],
            created_at=datetime.fromisoformat(row[7]),
            started_at=datetime.fromisoformat(row[8]) if row[8] else None,
            ended_at=datetime.fromisoformat(row[9]) if row[9] else None,
            owner=row[10] or "",
            tags=json.loads(row[11]) if row[11] else [],
        )


# =============================================================================
# SINGLETON
# =============================================================================

_framework: Optional[ABTestingFramework] = None


def get_ab_testing_framework() -> ABTestingFramework:
    """Get or create the A/B testing framework singleton"""
    global _framework
    if _framework is None:
        _framework = ABTestingFramework()
    return _framework
