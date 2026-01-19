"""
Model Evaluation Framework for ML Models.

Provides comprehensive evaluation metrics:
- Classification: accuracy, precision, recall, F1, AUC-ROC
- Regression: MAE, RMSE, R2
- Cross-validation with k-fold
- Hyperparameter tuning with grid search

Usage:
    from core.ml.model_evaluator import ModelEvaluator

    evaluator = ModelEvaluator()

    # Classification metrics
    metrics = evaluator.evaluate_classification(y_true, y_pred)

    # Regression metrics
    metrics = evaluator.evaluate_regression(y_true, y_pred)

    # Cross-validation
    cv_results = evaluator.cross_validate(model, X, y, k=5)
"""

import logging
import math
from dataclasses import dataclass, field
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
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        roc_auc_score, confusion_matrix, classification_report,
        mean_absolute_error, mean_squared_error, r2_score,
    )
    from sklearn.model_selection import cross_val_score, GridSearchCV, KFold
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


@dataclass
class EvaluationResult:
    """Result of model evaluation."""
    metrics: Dict[str, float]
    model_type: str
    evaluation_time: str = ""
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.evaluation_time:
            self.evaluation_time = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": {k: round(v, 4) if isinstance(v, float) else v for k, v in self.metrics.items()},
            "model_type": self.model_type,
            "evaluation_time": self.evaluation_time,
            "additional_info": self.additional_info,
        }


class ModelEvaluator:
    """
    Comprehensive model evaluation framework.

    Supports:
    - Classification metrics (binary and multiclass)
    - Regression metrics
    - Cross-validation
    - Hyperparameter tuning
    - Performance tracking over time
    """

    def __init__(self):
        """Initialize model evaluator."""
        self._evaluation_history: List[EvaluationResult] = []

    def evaluate_classification(
        self,
        y_true: List[int],
        y_pred: List[int],
        y_prob: Optional[List[float]] = None,
        average: str = "weighted",
    ) -> Dict[str, Any]:
        """
        Evaluate classification model.

        Args:
            y_true: True labels
            y_pred: Predicted labels
            y_prob: Predicted probabilities (for AUC calculation)
            average: Averaging method for multiclass ("weighted", "macro", "micro")

        Returns:
            Dictionary of metrics
        """
        if HAS_SKLEARN and HAS_NUMPY:
            return self._evaluate_classification_sklearn(y_true, y_pred, y_prob, average)
        return self._evaluate_classification_simple(y_true, y_pred)

    def _evaluate_classification_sklearn(
        self,
        y_true: List[int],
        y_pred: List[int],
        y_prob: Optional[List[float]],
        average: str,
    ) -> Dict[str, Any]:
        """Classification evaluation using sklearn."""
        y_true = np.array(y_true)
        y_pred = np.array(y_pred)

        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, average=average, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, average=average, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, average=average, zero_division=0)),
        }

        # AUC-ROC if probabilities provided (binary classification)
        if y_prob is not None and len(set(y_true)) == 2:
            try:
                metrics["auc_roc"] = float(roc_auc_score(y_true, y_prob))
            except Exception:
                pass

        # Confusion matrix
        try:
            cm = confusion_matrix(y_true, y_pred)
            metrics["confusion_matrix"] = cm.tolist()
        except Exception:
            pass

        return metrics

    def _evaluate_classification_simple(
        self,
        y_true: List[int],
        y_pred: List[int],
    ) -> Dict[str, Any]:
        """Simple classification evaluation without sklearn."""
        n = len(y_true)
        if n == 0:
            return {"accuracy": 0, "precision": 0, "recall": 0, "f1": 0}

        # Accuracy
        correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        accuracy = correct / n

        # For binary classification (positive class = 1)
        true_positives = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        false_positives = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
        false_negatives = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

        # Precision
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0

        # Recall
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0

        # F1
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    def evaluate_regression(
        self,
        y_true: List[float],
        y_pred: List[float],
    ) -> Dict[str, Any]:
        """
        Evaluate regression model.

        Args:
            y_true: True values
            y_pred: Predicted values

        Returns:
            Dictionary of metrics
        """
        if HAS_SKLEARN and HAS_NUMPY:
            return self._evaluate_regression_sklearn(y_true, y_pred)
        return self._evaluate_regression_simple(y_true, y_pred)

    def _evaluate_regression_sklearn(
        self,
        y_true: List[float],
        y_pred: List[float],
    ) -> Dict[str, Any]:
        """Regression evaluation using sklearn."""
        y_true = np.array(y_true)
        y_pred = np.array(y_pred)

        return {
            "mae": float(mean_absolute_error(y_true, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "mse": float(mean_squared_error(y_true, y_pred)),
            "r2": float(r2_score(y_true, y_pred)),
        }

    def _evaluate_regression_simple(
        self,
        y_true: List[float],
        y_pred: List[float],
    ) -> Dict[str, Any]:
        """Simple regression evaluation without sklearn."""
        n = len(y_true)
        if n == 0:
            return {"mae": 0, "rmse": 0, "r2": 0}

        # MAE
        mae = sum(abs(t - p) for t, p in zip(y_true, y_pred)) / n

        # RMSE
        mse = sum((t - p) ** 2 for t, p in zip(y_true, y_pred)) / n
        rmse = math.sqrt(mse)

        # R2
        mean_true = sum(y_true) / n
        ss_tot = sum((t - mean_true) ** 2 for t in y_true)
        ss_res = sum((t - p) ** 2 for t, p in zip(y_true, y_pred))
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "mae": mae,
            "rmse": rmse,
            "mse": mse,
            "r2": r2,
        }

    def cross_validate(
        self,
        model: Any,
        X: Union[List[List[float]], 'np.ndarray'],
        y: Union[List[int], 'np.ndarray'],
        k: int = 5,
        scoring: str = "accuracy",
    ) -> Dict[str, Any]:
        """
        Perform k-fold cross-validation.

        Args:
            model: Model with fit/predict methods
            X: Feature matrix
            y: Target values
            k: Number of folds
            scoring: Scoring metric

        Returns:
            Cross-validation results
        """
        if HAS_SKLEARN and HAS_NUMPY:
            return self._cross_validate_sklearn(model, X, y, k, scoring)
        return self._cross_validate_simple(model, X, y, k)

    def _cross_validate_sklearn(
        self,
        model: Any,
        X: Union[List[List[float]], 'np.ndarray'],
        y: Union[List[int], 'np.ndarray'],
        k: int,
        scoring: str,
    ) -> Dict[str, Any]:
        """Cross-validation using sklearn."""
        X = np.array(X)
        y = np.array(y)

        try:
            scores = cross_val_score(model, X, y, cv=k, scoring=scoring)

            return {
                "mean_score": float(scores.mean()),
                "std_score": float(scores.std()),
                "fold_scores": scores.tolist(),
                "k_folds": k,
                "scoring": scoring,
            }
        except Exception as e:
            logger.warning(f"Cross-validation failed: {e}")
            return {
                "mean_score": 0,
                "std_score": 0,
                "fold_scores": [],
                "k_folds": k,
                "error": str(e),
            }

    def _cross_validate_simple(
        self,
        model: Any,
        X: Union[List[List[float]], 'np.ndarray'],
        y: Union[List[int], 'np.ndarray'],
        k: int,
    ) -> Dict[str, Any]:
        """Simple cross-validation without sklearn."""
        if isinstance(X, list):
            X = [list(x) for x in X]
        else:
            X = [list(x) for x in X]

        y = list(y)
        n = len(X)
        fold_size = n // k

        scores = []

        for i in range(k):
            # Split data
            start = i * fold_size
            end = start + fold_size if i < k - 1 else n

            X_test = X[start:end]
            y_test = y[start:end]
            X_train = X[:start] + X[end:]
            y_train = y[:start] + y[end:]

            try:
                # Train and predict
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)

                # Calculate accuracy
                correct = sum(1 for t, p in zip(y_test, y_pred) if t == p)
                accuracy = correct / len(y_test) if y_test else 0
                scores.append(accuracy)
            except Exception:
                scores.append(0)

        mean_score = sum(scores) / len(scores) if scores else 0
        std_score = (sum((s - mean_score) ** 2 for s in scores) / len(scores)) ** 0.5 if scores else 0

        return {
            "mean_score": mean_score,
            "std_score": std_score,
            "fold_scores": scores,
            "k_folds": k,
        }

    def grid_search(
        self,
        model: Any,
        X: Union[List[List[float]], 'np.ndarray'],
        y: Union[List[int], 'np.ndarray'],
        param_grid: Dict[str, List[Any]],
        cv: int = 5,
        scoring: str = "accuracy",
    ) -> Dict[str, Any]:
        """
        Hyperparameter tuning with grid search.

        Args:
            model: Base model
            X: Feature matrix
            y: Target values
            param_grid: Dictionary of parameter names to lists of values
            cv: Number of cross-validation folds
            scoring: Scoring metric

        Returns:
            Best parameters and scores
        """
        if not HAS_SKLEARN or not HAS_NUMPY:
            return {"error": "scikit-learn required for grid search"}

        X = np.array(X)
        y = np.array(y)

        try:
            grid_search = GridSearchCV(
                model, param_grid,
                cv=cv,
                scoring=scoring,
                n_jobs=-1,
                return_train_score=True,
            )
            grid_search.fit(X, y)

            return {
                "best_params": grid_search.best_params_,
                "best_score": float(grid_search.best_score_),
                "cv_results": {
                    "mean_test_score": grid_search.cv_results_["mean_test_score"].tolist(),
                    "std_test_score": grid_search.cv_results_["std_test_score"].tolist(),
                    "params": [str(p) for p in grid_search.cv_results_["params"]],
                },
            }
        except Exception as e:
            logger.error(f"Grid search failed: {e}")
            return {"error": str(e)}

    def track_performance(
        self,
        model_name: str,
        metrics: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Track model performance over time.

        Args:
            model_name: Name of the model
            metrics: Performance metrics
            metadata: Additional metadata
        """
        result = EvaluationResult(
            metrics=metrics,
            model_type=model_name,
            additional_info=metadata or {},
        )
        self._evaluation_history.append(result)

    def get_performance_trend(
        self,
        model_name: str,
        metric: str = "accuracy",
    ) -> List[Tuple[str, float]]:
        """
        Get performance trend for a model over time.

        Args:
            model_name: Name of the model
            metric: Metric to track

        Returns:
            List of (timestamp, metric_value) tuples
        """
        trend = []
        for result in self._evaluation_history:
            if result.model_type == model_name and metric in result.metrics:
                trend.append((result.evaluation_time, result.metrics[metric]))
        return trend

    def detect_drift(
        self,
        model_name: str,
        metric: str = "accuracy",
        threshold: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Detect if model performance is drifting.

        Args:
            model_name: Name of the model
            metric: Metric to monitor
            threshold: Drift threshold (fraction of initial performance)

        Returns:
            Drift detection result
        """
        trend = self.get_performance_trend(model_name, metric)

        if len(trend) < 5:
            return {"drift_detected": False, "reason": "Insufficient data"}

        # Compare recent to initial performance
        initial_avg = sum(v for _, v in trend[:3]) / 3
        recent_avg = sum(v for _, v in trend[-3:]) / 3

        drift_magnitude = (initial_avg - recent_avg) / initial_avg if initial_avg > 0 else 0

        return {
            "drift_detected": drift_magnitude > threshold,
            "drift_magnitude": drift_magnitude,
            "initial_performance": initial_avg,
            "recent_performance": recent_avg,
            "threshold": threshold,
        }

    def generate_report(
        self,
        y_true: List[int],
        y_pred: List[int],
        model_name: str = "Model",
    ) -> str:
        """
        Generate a human-readable evaluation report.

        Args:
            y_true: True labels
            y_pred: Predicted labels
            model_name: Name of the model

        Returns:
            Formatted report string
        """
        metrics = self.evaluate_classification(y_true, y_pred)

        lines = [
            f"Evaluation Report: {model_name}",
            "=" * 40,
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "Classification Metrics:",
            "-" * 40,
            f"  Accuracy:  {metrics['accuracy']:.4f}",
            f"  Precision: {metrics['precision']:.4f}",
            f"  Recall:    {metrics['recall']:.4f}",
            f"  F1 Score:  {metrics['f1']:.4f}",
        ]

        if "auc_roc" in metrics:
            lines.append(f"  AUC-ROC:   {metrics['auc_roc']:.4f}")

        if "confusion_matrix" in metrics:
            lines.extend([
                "",
                "Confusion Matrix:",
                str(metrics["confusion_matrix"]),
            ])

        return "\n".join(lines)
