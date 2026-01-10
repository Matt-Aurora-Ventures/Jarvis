"""
Statistical Analysis for A/B Testing
Prompt #93: Statistical significance testing for experiments

Provides statistical analysis for experiment results.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import statistics

logger = logging.getLogger("jarvis.experiments.analysis")


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class VariantStats:
    """Statistics for a single variant"""
    variant_id: str
    n: int  # Sample size
    mean: float
    std: float
    se: float  # Standard error
    ci_lower: float  # 95% CI lower bound
    ci_upper: float  # 95% CI upper bound


@dataclass
class ComparisonResult:
    """Result of comparing two variants"""
    control_id: str
    treatment_id: str
    control_mean: float
    treatment_mean: float
    absolute_difference: float
    relative_difference: float  # Percentage lift
    t_statistic: float
    p_value: float
    is_significant: bool
    significance_level: float
    confidence_interval: Tuple[float, float]
    required_sample_size: int
    statistical_power: float


@dataclass
class ExperimentAnalysis:
    """Complete analysis of an experiment"""
    experiment_id: str
    metric_name: str
    variant_stats: Dict[str, VariantStats]
    comparisons: List[ComparisonResult]
    winner: Optional[str]
    recommendation: str
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# STATISTICAL ANALYZER
# =============================================================================

class StatisticalAnalyzer:
    """
    Provides statistical analysis for A/B test experiments.

    Features:
    - T-test for significance
    - Confidence intervals
    - Effect size calculation
    - Power analysis
    - Sample size estimation
    """

    # Default configuration
    DEFAULT_ALPHA = 0.05  # Significance level
    DEFAULT_POWER = 0.8   # Statistical power
    Z_ALPHA = 1.96        # Z-score for 95% CI

    def __init__(
        self,
        alpha: float = None,
        target_power: float = None,
    ):
        self.alpha = alpha or self.DEFAULT_ALPHA
        self.target_power = target_power or self.DEFAULT_POWER

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    async def analyze_experiment(
        self,
        experiment_id: str,
        variant_data: Dict[str, List[float]],
        control_variant_id: str,
    ) -> ExperimentAnalysis:
        """
        Analyze an experiment's results.

        Args:
            experiment_id: Experiment ID
            variant_data: Dict of variant_id -> list of metric values
            control_variant_id: ID of the control variant

        Returns:
            ExperimentAnalysis with all statistical results
        """
        # Calculate variant statistics
        variant_stats = {}
        for variant_id, values in variant_data.items():
            if values:
                stats = self._calculate_stats(variant_id, values)
                variant_stats[variant_id] = stats

        # Compare each treatment to control
        comparisons = []
        control_values = variant_data.get(control_variant_id, [])

        for variant_id, values in variant_data.items():
            if variant_id == control_variant_id:
                continue

            if control_values and values:
                comparison = self._compare_variants(
                    control_variant_id, variant_id,
                    control_values, values
                )
                comparisons.append(comparison)

        # Determine winner
        winner = None
        significant_improvements = [
            c for c in comparisons
            if c.is_significant and c.relative_difference > 0
        ]

        if significant_improvements:
            # Best improvement
            best = max(significant_improvements, key=lambda c: c.relative_difference)
            winner = best.treatment_id

        # Generate recommendation
        recommendation = self._generate_recommendation(
            comparisons, control_variant_id, variant_stats
        )

        return ExperimentAnalysis(
            experiment_id=experiment_id,
            metric_name="metric",  # Can be parameterized
            variant_stats=variant_stats,
            comparisons=comparisons,
            winner=winner,
            recommendation=recommendation,
        )

    def _calculate_stats(
        self,
        variant_id: str,
        values: List[float],
    ) -> VariantStats:
        """Calculate statistics for a variant"""
        n = len(values)
        mean = statistics.mean(values)
        std = statistics.stdev(values) if n > 1 else 0
        se = std / math.sqrt(n) if n > 0 else 0

        # 95% confidence interval
        margin = self.Z_ALPHA * se
        ci_lower = mean - margin
        ci_upper = mean + margin

        return VariantStats(
            variant_id=variant_id,
            n=n,
            mean=mean,
            std=std,
            se=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
        )

    def _compare_variants(
        self,
        control_id: str,
        treatment_id: str,
        control_values: List[float],
        treatment_values: List[float],
    ) -> ComparisonResult:
        """Compare two variants using t-test"""
        # Calculate statistics
        n1 = len(control_values)
        n2 = len(treatment_values)

        mean1 = statistics.mean(control_values)
        mean2 = statistics.mean(treatment_values)

        std1 = statistics.stdev(control_values) if n1 > 1 else 0
        std2 = statistics.stdev(treatment_values) if n2 > 1 else 0

        # Absolute and relative difference
        abs_diff = mean2 - mean1
        rel_diff = (abs_diff / mean1 * 100) if mean1 != 0 else 0

        # Welch's t-test (unequal variances)
        se1 = std1 / math.sqrt(n1) if n1 > 0 else 0
        se2 = std2 / math.sqrt(n2) if n2 > 0 else 0
        se_diff = math.sqrt(se1**2 + se2**2) if (se1 > 0 or se2 > 0) else 0

        t_stat = abs_diff / se_diff if se_diff > 0 else 0

        # Degrees of freedom (Welch-Satterthwaite)
        if se1 > 0 or se2 > 0:
            df_num = (se1**2 + se2**2)**2
            df_denom = (se1**4 / (n1 - 1) if n1 > 1 else 0) + (se2**4 / (n2 - 1) if n2 > 1 else 0)
            df = df_num / df_denom if df_denom > 0 else 1
        else:
            df = 1

        # P-value (two-tailed)
        p_value = self._t_distribution_pvalue(abs(t_stat), df)

        # Is significant?
        is_significant = p_value < self.alpha

        # Confidence interval for difference
        margin = self._t_critical(df, self.alpha) * se_diff
        ci = (abs_diff - margin, abs_diff + margin)

        # Required sample size
        pooled_std = math.sqrt((std1**2 + std2**2) / 2)
        effect_size = abs(abs_diff) / pooled_std if pooled_std > 0 else 0
        required_n = self._calculate_required_sample_size(effect_size)

        # Statistical power
        power = self._calculate_power(n1, n2, effect_size)

        return ComparisonResult(
            control_id=control_id,
            treatment_id=treatment_id,
            control_mean=mean1,
            treatment_mean=mean2,
            absolute_difference=abs_diff,
            relative_difference=rel_diff,
            t_statistic=t_stat,
            p_value=p_value,
            is_significant=is_significant,
            significance_level=self.alpha,
            confidence_interval=ci,
            required_sample_size=required_n,
            statistical_power=power,
        )

    # =========================================================================
    # STATISTICAL FUNCTIONS
    # =========================================================================

    def _t_distribution_pvalue(self, t: float, df: float) -> float:
        """
        Approximate p-value from t-distribution.

        Using approximation since we don't have scipy.
        """
        if df <= 0:
            return 1.0

        # Use normal approximation for large df
        if df > 100:
            return 2 * (1 - self._normal_cdf(abs(t)))

        # Simple approximation using beta function relationship
        x = df / (df + t**2)

        # Beta incomplete function approximation
        # For t-test, P(T > t) = 0.5 * I_x(df/2, 0.5)
        a = df / 2
        b = 0.5

        # Use Lentz's continued fraction for incomplete beta
        # Simplified approximation
        if x > (a + 1) / (a + b + 2):
            p = 1 - self._incomplete_beta(1 - x, b, a)
        else:
            p = self._incomplete_beta(x, a, b)

        return 2 * min(p, 1 - p)  # Two-tailed

    def _normal_cdf(self, x: float) -> float:
        """Standard normal CDF approximation"""
        # Abramowitz and Stegun approximation
        a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
        p = 0.3275911

        sign = 1 if x >= 0 else -1
        x = abs(x) / math.sqrt(2)

        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

        return 0.5 * (1.0 + sign * y)

    def _incomplete_beta(self, x: float, a: float, b: float) -> float:
        """Incomplete beta function approximation"""
        if x <= 0:
            return 0
        if x >= 1:
            return 1

        # Simple numerical integration (trapezoidal)
        n_steps = 100
        dx = x / n_steps
        total = 0

        for i in range(n_steps):
            t = (i + 0.5) * dx
            if t > 0 and t < 1:
                total += t**(a-1) * (1-t)**(b-1) * dx

        # Normalize by beta function
        beta_ab = math.gamma(a) * math.gamma(b) / math.gamma(a + b)

        return total / beta_ab if beta_ab > 0 else 0

    def _t_critical(self, df: float, alpha: float) -> float:
        """Approximate t critical value"""
        # Use normal approximation for large df
        if df > 100:
            return self.Z_ALPHA

        # Approximation for smaller df
        # t ~ z * (1 + 1/(4*df))
        return self.Z_ALPHA * (1 + 1 / (4 * max(df, 1)))

    def _calculate_required_sample_size(self, effect_size: float) -> int:
        """Calculate required sample size per group"""
        if effect_size <= 0:
            return 10000  # Default large number

        # Formula: n = 2 * ((z_alpha + z_beta) / d)^2
        z_alpha = self.Z_ALPHA
        z_beta = 0.84  # For 80% power

        n = 2 * ((z_alpha + z_beta) / effect_size) ** 2

        return max(int(math.ceil(n)), 10)

    def _calculate_power(
        self,
        n1: int,
        n2: int,
        effect_size: float,
    ) -> float:
        """Calculate statistical power"""
        if effect_size <= 0 or n1 <= 0 or n2 <= 0:
            return 0

        # Harmonic mean of sample sizes
        n = 2 * n1 * n2 / (n1 + n2) if (n1 + n2) > 0 else 0

        # Non-centrality parameter
        ncp = effect_size * math.sqrt(n / 2)

        # Power = P(T > t_crit | H1)
        # Approximate using normal
        power = 1 - self._normal_cdf(self.Z_ALPHA - ncp)

        return min(max(power, 0), 1)

    # =========================================================================
    # RECOMMENDATIONS
    # =========================================================================

    def _generate_recommendation(
        self,
        comparisons: List[ComparisonResult],
        control_id: str,
        variant_stats: Dict[str, VariantStats],
    ) -> str:
        """Generate recommendation based on analysis"""
        if not comparisons:
            return "Insufficient data for comparison."

        significant_winners = [
            c for c in comparisons
            if c.is_significant and c.relative_difference > 0
        ]

        significant_losers = [
            c for c in comparisons
            if c.is_significant and c.relative_difference < 0
        ]

        if significant_winners:
            best = max(significant_winners, key=lambda c: c.relative_difference)
            return (
                f"Implement {best.treatment_id}. "
                f"Shows {best.relative_difference:.1f}% improvement over control "
                f"(p={best.p_value:.4f}, power={best.statistical_power:.1%})."
            )

        if significant_losers:
            return (
                f"Keep control ({control_id}). "
                f"All treatments show worse performance."
            )

        # Check if underpowered
        low_power = [c for c in comparisons if c.statistical_power < 0.8]
        if low_power:
            needed = max(c.required_sample_size for c in low_power)
            return (
                f"Continue experiment. Need {needed} samples per variant "
                f"for 80% power. Current power: {min(c.statistical_power for c in low_power):.1%}."
            )

        return (
            "No significant difference detected. "
            "Consider implementing the simpler option or continuing the experiment."
        )

    # =========================================================================
    # UTILITIES
    # =========================================================================

    async def calculate_minimum_detectable_effect(
        self,
        baseline_conversion: float,
        sample_size_per_variant: int,
    ) -> float:
        """
        Calculate minimum detectable effect size.

        Args:
            baseline_conversion: Baseline conversion rate (0-1)
            sample_size_per_variant: Sample size per variant

        Returns:
            Minimum detectable effect as relative change
        """
        if baseline_conversion <= 0 or sample_size_per_variant <= 0:
            return float('inf')

        # For proportions, SE = sqrt(p(1-p)/n)
        p = baseline_conversion
        se = math.sqrt(p * (1 - p) / sample_size_per_variant)

        # MDE = (z_alpha + z_beta) * sqrt(2) * SE / p
        z_alpha = self.Z_ALPHA
        z_beta = 0.84

        mde = (z_alpha + z_beta) * math.sqrt(2) * se / p

        return mde * 100  # Return as percentage

    async def calculate_sample_size_for_mde(
        self,
        baseline_rate: float,
        mde_percent: float,
    ) -> int:
        """
        Calculate sample size needed to detect a given effect.

        Args:
            baseline_rate: Baseline conversion/metric rate
            mde_percent: Minimum detectable effect as percentage

        Returns:
            Required sample size per variant
        """
        if baseline_rate <= 0 or mde_percent <= 0:
            return 10000

        # Effect size
        effect = mde_percent / 100 * baseline_rate
        pooled_std = math.sqrt(baseline_rate * (1 - baseline_rate))
        d = abs(effect) / pooled_std if pooled_std > 0 else 0

        return self._calculate_required_sample_size(d)


# =============================================================================
# SINGLETON
# =============================================================================

_analyzer: Optional[StatisticalAnalyzer] = None


def get_statistical_analyzer() -> StatisticalAnalyzer:
    """Get or create the statistical analyzer singleton"""
    global _analyzer
    if _analyzer is None:
        _analyzer = StatisticalAnalyzer()
    return _analyzer
