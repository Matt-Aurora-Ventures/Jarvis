"""
Feature Importance Analyzer for ML Models.

Analyzes which features contribute most to model predictions using:
- Permutation importance
- SHAP values (if available)
- Coefficient analysis for linear models

Usage:
    from core.ml.feature_importance import FeatureImportanceAnalyzer

    analyzer = FeatureImportanceAnalyzer()

    importance = analyzer.analyze(feature_data, labels)
    for item in importance:
        print(f"{item['feature']}: {item['importance']:.4f}")
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# Optional ML imports
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    from sklearn.inspection import permutation_importance
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False


@dataclass
class FeatureImportanceResult:
    """Result of feature importance analysis."""
    feature: str
    importance: float
    std: float = 0.0  # Standard deviation for permutation importance
    method: str = "permutation"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature,
            "importance": round(self.importance, 4),
            "std": round(self.std, 4),
            "method": self.method,
        }


class FeatureImportanceAnalyzer:
    """
    Analyze feature importance for ML models.

    Methods:
    1. Permutation importance: Measure accuracy drop when feature is shuffled
    2. SHAP values: Game-theoretic approach to feature attribution
    3. Coefficient analysis: For linear models
    """

    def __init__(self):
        """Initialize feature importance analyzer."""
        self._shap_explainer: Optional[Any] = None

    def supports_shap(self) -> bool:
        """Check if SHAP is available."""
        return HAS_SHAP

    def analyze(
        self,
        feature_data: Union[Dict[str, List[float]], List[List[float]]],
        labels: List[int],
        feature_names: Optional[List[str]] = None,
        method: str = "permutation",
    ) -> List[Dict[str, Any]]:
        """
        Analyze feature importance.

        Args:
            feature_data: Either dict of {feature_name: values} or 2D list
            labels: Target labels
            feature_names: Feature names (required if feature_data is 2D list)
            method: "permutation", "shap", or "coefficient"

        Returns:
            List of dicts with feature name and importance, sorted by importance
        """
        if not HAS_SKLEARN or not HAS_NUMPY:
            return self._analyze_simple(feature_data, labels, feature_names)

        # Convert dict to array if needed
        if isinstance(feature_data, dict):
            feature_names = list(feature_data.keys())
            X = np.array([feature_data[f] for f in feature_names]).T
        else:
            X = np.array(feature_data)
            if feature_names is None:
                feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        y = np.array(labels)

        if method == "shap" and HAS_SHAP:
            return self._analyze_shap(X, y, feature_names)
        elif method == "coefficient":
            return self._analyze_coefficient(X, y, feature_names)
        else:
            return self._analyze_permutation(X, y, feature_names)

    def _analyze_permutation(
        self,
        X: 'np.ndarray',
        y: 'np.ndarray',
        feature_names: List[str],
    ) -> List[Dict[str, Any]]:
        """Permutation importance analysis."""
        try:
            # Train a model
            model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
            model.fit(X, y)

            # Calculate permutation importance
            result = permutation_importance(
                model, X, y,
                n_repeats=10,
                random_state=42,
                n_jobs=-1,
            )

            # Build results
            importance_list = []
            for i, name in enumerate(feature_names):
                importance_list.append({
                    "feature": name,
                    "importance": float(result.importances_mean[i]),
                    "std": float(result.importances_std[i]),
                    "method": "permutation",
                })

            # Sort by importance descending
            importance_list.sort(key=lambda x: abs(x["importance"]), reverse=True)

            return importance_list

        except Exception as e:
            logger.warning(f"Permutation importance failed: {e}")
            return self._analyze_simple_array(X, y, feature_names)

    def _analyze_shap(
        self,
        X: 'np.ndarray',
        y: 'np.ndarray',
        feature_names: List[str],
    ) -> List[Dict[str, Any]]:
        """SHAP value analysis."""
        if not HAS_SHAP:
            logger.warning("SHAP not installed, falling back to permutation importance")
            return self._analyze_permutation(X, y, feature_names)

        try:
            # Train a model
            model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
            model.fit(X, y)

            # Create SHAP explainer
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X)

            # Handle binary classification (shap_values may be list)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]  # Use positive class

            # Calculate mean absolute SHAP values
            mean_shap = np.abs(shap_values).mean(axis=0)

            # Build results
            importance_list = []
            for i, name in enumerate(feature_names):
                importance_list.append({
                    "feature": name,
                    "importance": float(mean_shap[i]),
                    "std": float(np.abs(shap_values[:, i]).std()),
                    "method": "shap",
                })

            importance_list.sort(key=lambda x: x["importance"], reverse=True)

            return importance_list

        except Exception as e:
            logger.warning(f"SHAP analysis failed: {e}")
            return self._analyze_permutation(X, y, feature_names)

    def _analyze_coefficient(
        self,
        X: 'np.ndarray',
        y: 'np.ndarray',
        feature_names: List[str],
    ) -> List[Dict[str, Any]]:
        """Coefficient analysis for linear models."""
        try:
            from sklearn.linear_model import LogisticRegression

            # Scale features for fair comparison
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Train logistic regression
            model = LogisticRegression(max_iter=1000, random_state=42)
            model.fit(X_scaled, y)

            # Get coefficients
            coef = model.coef_[0]

            # Build results
            importance_list = []
            for i, name in enumerate(feature_names):
                importance_list.append({
                    "feature": name,
                    "importance": float(abs(coef[i])),
                    "std": 0.0,  # No std for coefficients
                    "method": "coefficient",
                    "direction": "positive" if coef[i] > 0 else "negative",
                })

            importance_list.sort(key=lambda x: x["importance"], reverse=True)

            return importance_list

        except Exception as e:
            logger.warning(f"Coefficient analysis failed: {e}")
            return self._analyze_permutation(X, y, feature_names)

    def _analyze_simple(
        self,
        feature_data: Union[Dict[str, List[float]], List[List[float]]],
        labels: List[int],
        feature_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Simple correlation-based importance (fallback when sklearn not available)."""
        if isinstance(feature_data, dict):
            feature_names = list(feature_data.keys())
            features = {name: values for name, values in feature_data.items()}
        else:
            if feature_names is None:
                feature_names = [f"feature_{i}" for i in range(len(feature_data[0]))]
            features = {name: [row[i] for row in feature_data] for i, name in enumerate(feature_names)}

        importance_list = []
        for name, values in features.items():
            # Simple correlation with labels
            correlation = self._simple_correlation(values, labels)
            importance_list.append({
                "feature": name,
                "importance": abs(correlation),
                "std": 0.0,
                "method": "correlation",
            })

        importance_list.sort(key=lambda x: x["importance"], reverse=True)

        return importance_list

    def _analyze_simple_array(
        self,
        X: 'np.ndarray',
        y: 'np.ndarray',
        feature_names: List[str],
    ) -> List[Dict[str, Any]]:
        """Simple correlation-based importance from numpy arrays."""
        importance_list = []
        for i, name in enumerate(feature_names):
            correlation = np.corrcoef(X[:, i], y)[0, 1]
            if np.isnan(correlation):
                correlation = 0.0

            importance_list.append({
                "feature": name,
                "importance": abs(float(correlation)),
                "std": 0.0,
                "method": "correlation",
            })

        importance_list.sort(key=lambda x: x["importance"], reverse=True)

        return importance_list

    def _simple_correlation(self, x: List[float], y: List[int]) -> float:
        """Calculate simple Pearson correlation."""
        n = len(x)
        if n < 2:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator = (
            sum((x[i] - mean_x) ** 2 for i in range(n)) ** 0.5 *
            sum((y[i] - mean_y) ** 2 for i in range(n)) ** 0.5
        )

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def get_top_features(
        self,
        feature_data: Union[Dict[str, List[float]], List[List[float]]],
        labels: List[int],
        top_k: int = 5,
        method: str = "permutation",
    ) -> List[str]:
        """
        Get the top K most important features.

        Args:
            feature_data: Feature data
            labels: Target labels
            top_k: Number of top features to return
            method: Importance calculation method

        Returns:
            List of top feature names
        """
        importance = self.analyze(feature_data, labels, method=method)
        return [item["feature"] for item in importance[:top_k]]

    def generate_report(
        self,
        feature_data: Union[Dict[str, List[float]], List[List[float]]],
        labels: List[int],
        feature_names: Optional[List[str]] = None,
    ) -> str:
        """
        Generate a human-readable feature importance report.

        Returns:
            Formatted string report
        """
        importance = self.analyze(feature_data, labels, feature_names)

        lines = [
            "Feature Importance Report",
            "=" * 40,
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Method: {importance[0]['method'] if importance else 'N/A'}",
            f"Features analyzed: {len(importance)}",
            "",
            "Ranking:",
            "-" * 40,
        ]

        for i, item in enumerate(importance, 1):
            bar_length = int(item["importance"] * 20)
            bar = "#" * bar_length + "-" * (20 - bar_length)
            lines.append(f"{i:2}. {item['feature']:<20} [{bar}] {item['importance']:.4f}")

        lines.append("")
        lines.append("Recommendation:")

        if importance:
            top_features = [item["feature"] for item in importance[:3]]
            bottom_features = [item["feature"] for item in importance[-3:] if item["importance"] < 0.01]

            lines.append(f"  - Keep: {', '.join(top_features)}")
            if bottom_features:
                lines.append(f"  - Consider dropping: {', '.join(bottom_features)}")

        return "\n".join(lines)
