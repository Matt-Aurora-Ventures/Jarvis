"""
A/B Testing and Experimentation Framework

Provides controlled experiments for strategy and feature testing.
"""

from core.experiments.ab_testing import ABTestingFramework, Experiment, Variant
from core.experiments.analysis import StatisticalAnalyzer, ExperimentAnalysis

__all__ = [
    "ABTestingFramework",
    "Experiment",
    "Variant",
    "StatisticalAnalyzer",
    "ExperimentAnalysis",
]
