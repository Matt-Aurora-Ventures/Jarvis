import math

def wilson_lower_bound(wins: int, total_trials: int, confidence: float = 0.95) -> float:
    """
    Calculates the Wilson Confidence Interval lower bound.
    Used for discounting heuristics that have a high hit rate but low sample sizes.
    Defaults to 95% confidence (Z = 1.96).
    """
    if total_trials == 0:
        return 0.0

    z = 1.96  # 95% confidence
    if confidence == 0.99:
        z = 2.58
    elif confidence == 0.90:
        z = 1.645

    phat = 1.0 * wins / total_trials

    # Calculate wilson score
    numerator = phat + z * z / (2 * total_trials) - z * math.sqrt((phat * (1 - phat) + z * z / (4 * total_trials)) / total_trials)
    denominator = 1 + z * z / total_trials

    return max(0.0, numerator / denominator)

if __name__ == "__main__":
    # Smoke test locally
    low_sample_high_win = wilson_lower_bound(1, 1)
    high_sample_high_win = wilson_lower_bound(95, 100)
    print(f"1/1  Lower Bound: {low_sample_high_win:.4f}")
    print(f"95/100 Lower Bound: {high_sample_high_win:.4f}")
