"""
Model Registry for Version Control and Management.

Tracks ML model versions with:
- Training metadata
- Performance metrics
- Git commit hash (reproducibility)
- Easy rollback to previous versions

Usage:
    from core.ml.model_registry import ModelRegistry

    registry = ModelRegistry()

    # Register a new model version
    version = registry.register(
        model_name="sentiment_classifier",
        model_object=trained_model,
        metrics={"accuracy": 0.85}
    )

    # Load the active version
    model = registry.load("sentiment_classifier")

    # Rollback if needed
    registry.rollback("sentiment_classifier", version_id="v1")
"""

import hashlib
import json
import logging
import pickle
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """Represents a specific version of a model."""
    version_id: str
    model_name: str
    timestamp: str
    metrics: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    git_commit: Optional[str] = None
    file_path: Optional[str] = None
    is_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "model_name": self.model_name,
            "timestamp": self.timestamp,
            "metrics": self.metrics,
            "metadata": self.metadata,
            "git_commit": self.git_commit,
            "file_path": self.file_path,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelVersion":
        return cls(
            version_id=data["version_id"],
            model_name=data["model_name"],
            timestamp=data["timestamp"],
            metrics=data.get("metrics", {}),
            metadata=data.get("metadata", {}),
            git_commit=data.get("git_commit"),
            file_path=data.get("file_path"),
            is_active=data.get("is_active", False),
        )


class ModelRegistry:
    """
    Registry for ML model version control.

    Features:
    - Store multiple versions of each model
    - Track training metrics and metadata
    - Automatic git commit tracking
    - Load active version or specific version
    - Rollback to previous versions
    """

    def __init__(
        self,
        registry_dir: Optional[Path] = None,
    ):
        """
        Initialize model registry.

        Args:
            registry_dir: Directory for storing models and metadata
        """
        self.registry_dir = registry_dir or Path(__file__).parent.parent.parent / "data" / "ml" / "models"
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        self._registry_file = self.registry_dir / "registry.json"
        self._registry: Dict[str, List[ModelVersion]] = {}
        self._active_versions: Dict[str, str] = {}  # model_name -> version_id

        self._load_registry()

    def _load_registry(self):
        """Load registry from disk."""
        if self._registry_file.exists():
            try:
                with open(self._registry_file, "r") as f:
                    data = json.load(f)

                self._registry = {}
                for model_name, versions in data.get("models", {}).items():
                    self._registry[model_name] = [ModelVersion.from_dict(v) for v in versions]

                self._active_versions = data.get("active_versions", {})

                logger.info(f"Loaded registry with {len(self._registry)} models")
            except Exception as e:
                logger.warning(f"Failed to load registry: {e}")
                self._registry = {}
                self._active_versions = {}

    def _save_registry(self):
        """Save registry to disk."""
        try:
            data = {
                "models": {
                    model_name: [v.to_dict() for v in versions]
                    for model_name, versions in self._registry.items()
                },
                "active_versions": self._active_versions,
                "updated": datetime.now(timezone.utc).isoformat(),
            }

            with open(self._registry_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug("Saved registry")
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()[:8]  # Short hash
        except Exception:
            pass
        return None

    def _generate_version_id(self, model_name: str) -> str:
        """Generate a unique version ID."""
        # Count existing versions
        existing = len(self._registry.get(model_name, []))
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"v{existing + 1}_{timestamp}"

    def register(
        self,
        model_name: str,
        model_object: Any,
        metrics: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
        set_active: bool = True,
    ) -> ModelVersion:
        """
        Register a new model version.

        Args:
            model_name: Name of the model
            model_object: The model object to save
            metrics: Performance metrics
            metadata: Additional metadata (training params, etc.)
            set_active: Whether to set this as the active version

        Returns:
            ModelVersion object for the registered model
        """
        version_id = self._generate_version_id(model_name)
        timestamp = datetime.now(timezone.utc).isoformat()

        # Create version directory
        version_dir = self.registry_dir / model_name
        version_dir.mkdir(parents=True, exist_ok=True)

        # Save model file
        model_file = version_dir / f"{version_id}.pkl"
        try:
            with open(model_file, "wb") as f:
                pickle.dump(model_object, f)
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
            raise

        # Get git commit
        git_commit = self._get_git_commit()

        # Create version entry
        version = ModelVersion(
            version_id=version_id,
            model_name=model_name,
            timestamp=timestamp,
            metrics=metrics,
            metadata=metadata or {},
            git_commit=git_commit,
            file_path=str(model_file),
            is_active=set_active,
        )

        # Add to registry
        if model_name not in self._registry:
            self._registry[model_name] = []

        # Mark all previous versions as inactive if setting active
        if set_active:
            for v in self._registry[model_name]:
                v.is_active = False
            self._active_versions[model_name] = version_id

        self._registry[model_name].append(version)

        # Save registry
        self._save_registry()

        logger.info(f"Registered model {model_name} version {version_id}")

        return version

    def load(
        self,
        model_name: str,
        version_id: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Load a model from the registry.

        Args:
            model_name: Name of the model
            version_id: Specific version to load (None = active version)

        Returns:
            Loaded model object, or None if not found
        """
        if model_name not in self._registry:
            logger.warning(f"Model {model_name} not found in registry")
            return None

        # Find the version
        if version_id is None:
            version_id = self._active_versions.get(model_name)

        if version_id is None:
            # Use most recent
            versions = self._registry[model_name]
            if versions:
                version_id = versions[-1].version_id

        if version_id is None:
            logger.warning(f"No version found for model {model_name}")
            return None

        # Find version entry
        version = None
        for v in self._registry[model_name]:
            if v.version_id == version_id:
                version = v
                break

        if version is None or version.file_path is None:
            logger.warning(f"Version {version_id} not found for model {model_name}")
            return None

        # Load model file
        try:
            with open(version.file_path, "rb") as f:
                model = pickle.load(f)
            logger.info(f"Loaded model {model_name} version {version_id}")
            return model
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return None

    def rollback(
        self,
        model_name: str,
        version_id: str,
    ) -> bool:
        """
        Rollback to a previous model version.

        Args:
            model_name: Name of the model
            version_id: Version to rollback to

        Returns:
            True if successful
        """
        if model_name not in self._registry:
            logger.warning(f"Model {model_name} not found in registry")
            return False

        # Find the version
        found = False
        for v in self._registry[model_name]:
            if v.version_id == version_id:
                found = True
                v.is_active = True
                self._active_versions[model_name] = version_id
            else:
                v.is_active = False

        if found:
            self._save_registry()
            logger.info(f"Rolled back {model_name} to version {version_id}")
            return True
        else:
            logger.warning(f"Version {version_id} not found for model {model_name}")
            return False

    def get_active_version(self, model_name: str) -> Optional[ModelVersion]:
        """Get the currently active version of a model."""
        if model_name not in self._registry:
            return None

        active_id = self._active_versions.get(model_name)
        if active_id is None:
            return None

        for v in self._registry[model_name]:
            if v.version_id == active_id:
                return v

        return None

    def list_versions(self, model_name: str) -> List[ModelVersion]:
        """List all versions of a model."""
        return self._registry.get(model_name, [])

    def list_models(self) -> List[str]:
        """List all registered models."""
        return list(self._registry.keys())

    def get_version_metrics(
        self,
        model_name: str,
        version_id: Optional[str] = None,
    ) -> Optional[Dict[str, float]]:
        """Get metrics for a specific version."""
        if model_name not in self._registry:
            return None

        if version_id is None:
            version_id = self._active_versions.get(model_name)

        for v in self._registry[model_name]:
            if v.version_id == version_id:
                return v.metrics

        return None

    def compare_versions(
        self,
        model_name: str,
        version_ids: List[str],
    ) -> Dict[str, Dict[str, float]]:
        """
        Compare metrics across multiple versions.

        Returns:
            Dict mapping version_id to metrics
        """
        results = {}
        for v in self._registry.get(model_name, []):
            if v.version_id in version_ids:
                results[v.version_id] = v.metrics
        return results

    def get_best_version(
        self,
        model_name: str,
        metric: str = "accuracy",
        higher_is_better: bool = True,
    ) -> Optional[ModelVersion]:
        """
        Get the best performing version based on a metric.

        Args:
            model_name: Name of the model
            metric: Metric to compare
            higher_is_better: True if higher values are better

        Returns:
            Best performing version
        """
        versions = self._registry.get(model_name, [])
        if not versions:
            return None

        best = None
        best_value = None

        for v in versions:
            value = v.metrics.get(metric)
            if value is None:
                continue

            if best is None:
                best = v
                best_value = value
            elif higher_is_better and value > best_value:
                best = v
                best_value = value
            elif not higher_is_better and value < best_value:
                best = v
                best_value = value

        return best

    def delete_version(
        self,
        model_name: str,
        version_id: str,
    ) -> bool:
        """
        Delete a specific version (cannot delete active version).

        Args:
            model_name: Name of the model
            version_id: Version to delete

        Returns:
            True if deleted successfully
        """
        if model_name not in self._registry:
            return False

        # Check if it's the active version
        if self._active_versions.get(model_name) == version_id:
            logger.warning("Cannot delete active version")
            return False

        # Find and remove
        versions = self._registry[model_name]
        for i, v in enumerate(versions):
            if v.version_id == version_id:
                # Delete file
                if v.file_path:
                    try:
                        Path(v.file_path).unlink()
                    except Exception:
                        pass

                # Remove from registry
                versions.pop(i)
                self._save_registry()
                logger.info(f"Deleted version {version_id} of model {model_name}")
                return True

        return False

    def cleanup_old_versions(
        self,
        model_name: str,
        keep_n: int = 5,
    ) -> int:
        """
        Clean up old versions, keeping the N most recent.

        Args:
            model_name: Name of the model
            keep_n: Number of versions to keep

        Returns:
            Number of versions deleted
        """
        versions = self._registry.get(model_name, [])
        if len(versions) <= keep_n:
            return 0

        # Sort by timestamp
        versions.sort(key=lambda v: v.timestamp)

        # Keep the most recent N
        to_delete = versions[:-keep_n]
        active_id = self._active_versions.get(model_name)

        deleted = 0
        for v in to_delete:
            if v.version_id != active_id:
                if self.delete_version(model_name, v.version_id):
                    deleted += 1

        return deleted

    def generate_report(self, model_name: str) -> str:
        """Generate a report for a model's versions."""
        versions = self._registry.get(model_name, [])

        lines = [
            f"Model Registry Report: {model_name}",
            "=" * 50,
            f"Total versions: {len(versions)}",
            f"Active version: {self._active_versions.get(model_name, 'None')}",
            "",
            "Versions:",
            "-" * 50,
        ]

        for v in reversed(versions):  # Most recent first
            active_marker = " [ACTIVE]" if v.is_active else ""
            metrics_str = ", ".join(f"{k}={v:.3f}" for k, v in v.metrics.items())
            lines.append(f"  {v.version_id}{active_marker}")
            lines.append(f"    Timestamp: {v.timestamp}")
            lines.append(f"    Metrics: {metrics_str}")
            if v.git_commit:
                lines.append(f"    Git commit: {v.git_commit}")
            lines.append("")

        return "\n".join(lines)
