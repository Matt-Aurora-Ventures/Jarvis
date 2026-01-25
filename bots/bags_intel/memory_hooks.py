"""
Bags Intel memory hooks for graduation pattern tracking and outcome prediction.

Integrates with core memory system to:
- Store graduation events with outcomes
- Recall similar past graduations for pattern matching
- Calculate historical success rates
- Predict graduation success probability
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

from core.async_utils import fire_and_forget, TaskTracker
from core.memory import retain_fact, recall

logger = logging.getLogger(__name__)

# Module-level task tracker
_memory_tracker = TaskTracker("bags_intel_memory")

# Environment variable to enable/disable memory operations
BAGS_INTEL_MEMORY_ENABLED = os.getenv("BAGS_INTEL_MEMORY_ENABLED", "true").lower() == "true"


async def store_graduation_outcome(
    token_symbol: str,
    token_mint: str,
    graduation_score: float,  # 0-100 from intel_service
    price_at_graduation: float,
    price_24h_later: Optional[float] = None,
    price_7d_later: Optional[float] = None,
    outcome: Optional[str] = None,  # success, failure, pending
    creator_twitter: Optional[str] = None,
    bonding_curve_data: Optional[Dict] = None,
) -> int:
    """
    Store graduation event and outcome in memory.

    Args:
        token_symbol: Token ticker symbol
        token_mint: Token mint address
        graduation_score: Overall score from intel service (0-100)
        price_at_graduation: Price at graduation time
        price_24h_later: Price 24h after graduation (if known)
        price_7d_later: Price 7d after graduation (if known)
        outcome: "success", "failure", or "pending"
        creator_twitter: Creator's Twitter handle
        bonding_curve_data: Additional bonding curve metrics

    Returns:
        Fact ID from memory system

    Example:
        fact_id = await store_graduation_outcome(
            token_symbol="TEST",
            token_mint="test123...",
            graduation_score=75.5,
            price_at_graduation=0.001,
            outcome="pending"
        )
    """
    if not BAGS_INTEL_MEMORY_ENABLED:
        logger.debug("Bags Intel memory disabled, skipping graduation storage")
        return -1

    try:
        # Calculate price changes if available
        price_change_24h = None
        price_change_7d = None

        if price_24h_later and price_at_graduation > 0:
            price_change_24h = ((price_24h_later - price_at_graduation) / price_at_graduation) * 100

        if price_7d_later and price_at_graduation > 0:
            price_change_7d = ((price_7d_later - price_at_graduation) / price_at_graduation) * 100

        # Build entities
        entities = [f"@{token_symbol}"]
        if creator_twitter:
            entities.append(f"@{creator_twitter}")

        # Build summary
        summary = (
            f"bags.fm graduation: {token_symbol}\n"
            f"Score: {graduation_score:.1f}/100\n"
            f"Price at graduation: ${price_at_graduation:.6f}"
        )

        if price_change_24h is not None:
            summary += f"\n24h change: {price_change_24h:+.1f}%"

        if price_change_7d is not None:
            summary += f"\n7d change: {price_change_7d:+.1f}%"

        if outcome:
            summary += f"\nOutcome: {outcome}"

        if creator_twitter:
            summary += f"\nCreator: @{creator_twitter}"

        # Add bonding curve highlights
        if bonding_curve_data:
            duration = bonding_curve_data.get("duration_seconds", 0)
            volume = bonding_curve_data.get("total_volume_sol", 0)
            buyers = bonding_curve_data.get("unique_buyers", 0)

            if duration:
                summary += f"\nBonding duration: {duration}s"
            if volume:
                summary += f", Volume: {volume:.1f} SOL"
            if buyers:
                summary += f", Buyers: {buyers}"

        # Build context with score tier
        if graduation_score >= 80:
            tier = "exceptional"
        elif graduation_score >= 65:
            tier = "strong"
        elif graduation_score >= 50:
            tier = "average"
        else:
            tier = "weak"

        outcome_status = outcome or "pending"

        # Store in memory (retain_fact is sync - run in thread pool)
        fact_id = await asyncio.to_thread(
            retain_fact,
            content=summary,
            context=f"graduation_outcome|{token_mint[:12]}|score:{graduation_score:.1f}|tier:{tier}|outcome:{outcome_status}",
            source="bags_intel",
            entities=entities,
            confidence=1.0,
        )

        logger.debug(f"Stored graduation for {token_symbol} (fact_id={fact_id})")
        return fact_id

    except Exception as e:
        logger.error(f"Failed to store graduation outcome: {e}")
        return -1


async def recall_similar_graduations(
    score_range: Tuple[float, float] = (0, 100),
    creator_twitter: Optional[str] = None,
    k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Recall similar past graduations for pattern matching.

    Args:
        score_range: (min_score, max_score) to filter by
        creator_twitter: Filter by creator's Twitter handle
        k: Maximum results to return

    Returns:
        List of similar graduations sorted by relevance

    Example:
        similar = await recall_similar_graduations(
            score_range=(70, 80),
            k=5
        )
        for grad in similar:
            print(f"Token: {grad['content'][:50]}...")
    """
    if not BAGS_INTEL_MEMORY_ENABLED:
        logger.debug("Bags Intel memory disabled, returning empty results")
        return []

    try:
        # Build query
        query_parts = ["bags.fm graduation", "score"]

        if creator_twitter:
            query_parts.append(f"@{creator_twitter}")

        query = " ".join(query_parts)

        # Recall from memory
        results = await recall(
            query=query,
            k=k * 2,  # Get more for filtering
            source_filter="bags_intel",
            context_filter="graduation_outcome",
            time_filter="month",  # Last month
        )

        # Filter by score range
        min_score, max_score = score_range
        filtered = []

        for result in results:
            context_str = result.get("context", "")

            try:
                # Extract score from context (format: "...score:{score}...")
                if "score:" in context_str:
                    score_str = context_str.split("score:")[1].split("|")[0]
                    score = float(score_str)

                    if min_score <= score <= max_score:
                        result["graduation_score"] = score

                        # Extract tier
                        if "tier:" in context_str:
                            tier = context_str.split("tier:")[1].split("|")[0]
                            result["tier"] = tier

                        # Extract outcome
                        if "outcome:" in context_str:
                            outcome = context_str.split("outcome:")[1].split("|")[0]
                            result["outcome"] = outcome

                        filtered.append(result)
            except (ValueError, IndexError):
                continue

        # Sort by score descending
        filtered.sort(key=lambda x: x.get("graduation_score", 0), reverse=True)

        return filtered[:k]

    except Exception as e:
        logger.error(f"Failed to recall similar graduations: {e}")
        return []


async def get_graduation_success_rate(
    score_threshold: float = 70,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Calculate historical success rate for high-score graduations.

    Args:
        score_threshold: Minimum score to consider
        days: Lookback period in days

    Returns:
        {
            "total_graduations": int,
            "successful": int,
            "failed": int,
            "pending": int,
            "success_rate": float,
            "avg_score_successful": float,
            "avg_score_failed": float,
        }

    Example:
        stats = await get_graduation_success_rate(score_threshold=75)
        print(f"Success rate for 75+ scores: {stats['success_rate']:.1f}%")
    """
    if not BAGS_INTEL_MEMORY_ENABLED:
        logger.debug("Bags Intel memory disabled, returning empty stats")
        return {
            "total_graduations": 0,
            "successful": 0,
            "failed": 0,
            "pending": 0,
            "success_rate": 0.0,
            "avg_score_successful": 0.0,
            "avg_score_failed": 0.0,
        }

    try:
        # Get graduations above threshold
        graduations = await recall_similar_graduations(
            score_range=(score_threshold, 100),
            k=100,  # Get recent 100
        )

        # Categorize by outcome
        successful = []
        failed = []
        pending = []

        for grad in graduations:
            outcome = grad.get("outcome", "pending")
            score = grad.get("graduation_score", 0)

            if outcome == "success":
                successful.append(score)
            elif outcome == "failure":
                failed.append(score)
            else:
                pending.append(score)

        # Calculate stats
        total = len(graduations)
        success_count = len(successful)
        fail_count = len(failed)
        pending_count = len(pending)

        success_rate = (success_count / total * 100) if total > 0 else 0.0
        avg_score_success = sum(successful) / len(successful) if successful else 0.0
        avg_score_fail = sum(failed) / len(failed) if failed else 0.0

        return {
            "total_graduations": total,
            "successful": success_count,
            "failed": fail_count,
            "pending": pending_count,
            "success_rate": success_rate,
            "avg_score_successful": avg_score_success,
            "avg_score_failed": avg_score_fail,
        }

    except Exception as e:
        logger.error(f"Failed to get graduation success rate: {e}")
        return {
            "total_graduations": 0,
            "successful": 0,
            "failed": 0,
            "pending": 0,
            "success_rate": 0.0,
            "avg_score_successful": 0.0,
            "avg_score_failed": 0.0,
        }


async def predict_graduation_success(
    score: float,
    creator_twitter: Optional[str] = None,
) -> Tuple[float, str]:
    """
    Predict success probability based on historical patterns.

    Args:
        score: Graduation score for new token
        creator_twitter: Creator's Twitter handle (if known)

    Returns:
        (probability, reasoning) tuple

    Example:
        prob, reason = await predict_graduation_success(score=78.5)
        print(f"Success probability: {prob:.1f}%")
        print(f"Reasoning: {reason}")
    """
    if not BAGS_INTEL_MEMORY_ENABLED:
        logger.debug("Bags Intel memory disabled, returning default prediction")
        return (50.0, "Memory system disabled")

    try:
        # Get success rate for similar score range
        score_range = (score - 5, score + 5)  # ±5 points
        similar = await recall_similar_graduations(
            score_range=score_range,
            creator_twitter=creator_twitter,
            k=20,
        )

        if not similar:
            # No similar graduations - use general stats
            general_stats = await get_graduation_success_rate(score_threshold=score)
            probability = general_stats["success_rate"]
            reasoning = (
                f"No similar graduations in score range {score_range[0]:.0f}-{score_range[1]:.0f}. "
                f"Based on general {score:.0f}+ score success rate: {probability:.1f}%"
            )
            return (probability, reasoning)

        # Calculate success rate from similar graduations
        successful = sum(1 for g in similar if g.get("outcome") == "success")
        failed = sum(1 for g in similar if g.get("outcome") == "failure")
        total_decided = successful + failed

        if total_decided == 0:
            probability = 50.0
            reasoning = (
                f"Found {len(similar)} similar graduations but all pending. "
                f"Defaulting to 50% probability."
            )
        else:
            probability = (successful / total_decided) * 100
            reasoning = (
                f"Based on {len(similar)} similar graduations (score {score_range[0]:.0f}-{score_range[1]:.0f}): "
                f"{successful} successful, {failed} failed. "
                f"Success rate: {probability:.1f}%"
            )

        # Adjust for creator if known
        if creator_twitter:
            creator_grads = [g for g in similar if f"@{creator_twitter}" in g.get("content", "")]
            if creator_grads:
                creator_success = sum(1 for g in creator_grads if g.get("outcome") == "success")
                creator_total = sum(1 for g in creator_grads if g.get("outcome") in ("success", "failure"))

                if creator_total > 0:
                    creator_rate = (creator_success / creator_total) * 100
                    # Weighted average: 70% similar scores, 30% creator history
                    probability = (probability * 0.7) + (creator_rate * 0.3)
                    reasoning += f"\nCreator @{creator_twitter} history: {creator_rate:.1f}% success"

        return (probability, reasoning)

    except Exception as e:
        logger.error(f"Failed to predict graduation success: {e}")
        return (50.0, f"Error in prediction: {e}")
