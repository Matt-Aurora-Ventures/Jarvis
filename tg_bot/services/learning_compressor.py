"""
Learning Compressor - US-003 AI Learning System

Hourly background service that processes observations into actionable insights.

Architecture:
- Runs every hour in supervisor
- Reads observations from demo_observations.jsonl
- Analyzes patterns using Grok AI
- Generates insights with confidence scores
- Stores compressed learnings in demo_learnings.json

Learning Types:
- Win rate patterns: "A+ tokens have 67% win rate"
- Behavior patterns: "You buy too early, wait for dips"
- Timing patterns: "Best results when holding 2-4 hours"
- Risk patterns: "Your SL is too tight, increase to 25%"

Data Flow:
1. Load observations since last compression
2. Calculate statistics (win rate, avg PnL, hold duration)
3. Send to Grok for insight generation
4. Store insights with confidence scores

Storage: ~/.lifeos/trading/demo_learnings.json
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import traceback

logger = logging.getLogger(__name__)

# File paths
LEARNINGS_FILE = Path.home() / ".lifeos" / "trading" / "demo_learnings.json"
OBSERVATIONS_FILE = Path.home() / ".lifeos" / "trading" / "demo_observations.jsonl"


# =============================================================================
# Statistics Calculator
# =============================================================================

def calculate_trade_statistics(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate trading statistics from observations.

    Args:
        observations: List of observation events

    Returns:
        Statistics dict with win rates, avg PnL, patterns
    """
    try:
        # Filter by event type
        buys = [o for o in observations if o.get("event_type") == "buy_executed"]
        sells = [o for o in observations if o.get("event_type") == "sell_executed"]
        picks_shown = [o for o in observations if o.get("event_type") == "grok_pick_shown"]
        picks_ignored = [o for o in observations if o.get("event_type") == "pick_ignored"]

        # Calculate win rate
        wins = [s for s in sells if s.get("data", {}).get("success", False)]
        losses = [s for s in sells if not s.get("data", {}).get("success", False)]
        win_rate = (len(wins) / len(sells) * 100) if sells else 0.0

        # Calculate average PnL
        pnls = [s.get("data", {}).get("pnl_pct", 0) for s in sells]
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0.0

        # Calculate average hold duration
        hold_durations = [
            s.get("data", {}).get("hold_duration_minutes", 0)
            for s in sells
            if s.get("data", {}).get("hold_duration_minutes")
        ]
        avg_hold_minutes = sum(hold_durations) / len(hold_durations) if hold_durations else 0.0

        # Grade-based win rates
        grade_outcomes = {}
        for buy in buys:
            grade = buy.get("data", {}).get("grok_grade")
            if not grade:
                continue

            # Find corresponding sell
            token_address = buy.get("data", {}).get("token_address")
            matching_sells = [
                s for s in sells
                if s.get("data", {}).get("token_address") == token_address
            ]

            if matching_sells:
                sell = matching_sells[0]
                success = sell.get("data", {}).get("success", False)

                if grade not in grade_outcomes:
                    grade_outcomes[grade] = {"wins": 0, "losses": 0}

                if success:
                    grade_outcomes[grade]["wins"] += 1
                else:
                    grade_outcomes[grade]["losses"] += 1

        # Calculate grade win rates
        grade_win_rates = {}
        for grade, outcomes in grade_outcomes.items():
            total = outcomes["wins"] + outcomes["losses"]
            grade_win_rates[grade] = (outcomes["wins"] / total * 100) if total > 0 else 0.0

        # Exit reason breakdown
        exit_reasons = {}
        for sell in sells:
            reason = sell.get("data", {}).get("exit_reason", "unknown")
            if reason not in exit_reasons:
                exit_reasons[reason] = {"count": 0, "avg_pnl": 0, "pnls": []}

            exit_reasons[reason]["count"] += 1
            pnl = sell.get("data", {}).get("pnl_pct", 0)
            exit_reasons[reason]["pnls"].append(pnl)

        # Calculate avg PnL per exit reason
        for reason, data in exit_reasons.items():
            data["avg_pnl"] = sum(data["pnls"]) / len(data["pnls"]) if data["pnls"] else 0.0
            del data["pnls"]  # Remove raw data

        # Pick conversion rate
        picks_bought = len([b for b in buys if b.get("data", {}).get("source") == "grok_pick"])
        pick_conversion_rate = (picks_bought / len(picks_shown) * 100) if picks_shown else 0.0

        return {
            "total_buys": len(buys),
            "total_sells": len(sells),
            "total_picks_shown": len(picks_shown),
            "total_picks_ignored": len(picks_ignored),
            "win_rate": win_rate,
            "avg_pnl_pct": avg_pnl,
            "avg_hold_minutes": avg_hold_minutes,
            "grade_win_rates": grade_win_rates,
            "exit_reasons": exit_reasons,
            "pick_conversion_rate": pick_conversion_rate,
        }

    except Exception as e:
        logger.error(f"Failed to calculate statistics: {e}")
        logger.error(traceback.format_exc())
        return {
            "total_buys": 0,
            "total_sells": 0,
            "win_rate": 0.0,
            "avg_pnl_pct": 0.0,
        }


# =============================================================================
# Grok AI Insight Generator
# =============================================================================

async def generate_insights_with_grok(
    stats: Dict[str, Any],
    xai_api_key: str
) -> List[Dict[str, Any]]:
    """
    Use Grok AI to generate actionable insights from statistics.

    Args:
        stats: Trading statistics
        xai_api_key: XAI API key

    Returns:
        List of insights with text, type, confidence
    """
    try:
        import aiohttp

        if not xai_api_key:
            logger.warning("No XAI_API_KEY provided, skipping Grok insights")
            return []

        # Build prompt for Grok
        prompt = f"""You are an AI trading coach analyzing user trading behavior.

Here are the statistics from recent trades:

Total Trades: {stats.get('total_buys', 0)} buys, {stats.get('total_sells', 0)} sells
Win Rate: {stats.get('win_rate', 0):.1f}%
Average PnL: {stats.get('avg_pnl_pct', 0):+.1f}%
Average Hold Time: {stats.get('avg_hold_minutes', 0):.0f} minutes

Grade-Based Win Rates:
{json.dumps(stats.get('grade_win_rates', {}), indent=2)}

Exit Reasons:
{json.dumps(stats.get('exit_reasons', {}), indent=2)}

Grok Pick Conversion: {stats.get('pick_conversion_rate', 0):.1f}%

Generate 3-5 actionable insights for the trader. For each insight:
1. Identify a clear pattern or problem
2. Provide specific, actionable advice
3. Assign a confidence level (high/medium/low)

Format your response as JSON array:
[
  {{
    "text": "Your insight here",
    "type": "win_rate" | "behavior" | "timing" | "risk" | "picks",
    "confidence": "high" | "medium" | "low",
    "action": "What user should do differently"
  }}
]

Focus on:
- Grade patterns (which grades perform best?)
- Exit strategy (are TPs/SLs working?)
- Hold duration (holding too long or too short?)
- Pick conversion (ignoring good picks? buying bad ones?)
"""

        # Call Grok API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {xai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-2-1212",
                    "messages": [
                        {"role": "system", "content": "You are a trading coach AI that generates concise, actionable insights."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1000,
                },
                timeout=30,
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Grok API error: {resp.status}")
                    return []

                data = await resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Parse JSON response
                try:
                    # Extract JSON array from response (might have markdown code blocks)
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()

                    insights = json.loads(content)

                    if not isinstance(insights, list):
                        logger.warning("Grok response is not a list")
                        return []

                    # Add timestamp to each insight
                    for insight in insights:
                        insight["generated_at"] = datetime.now(timezone.utc).isoformat()

                    logger.info(f"Generated {len(insights)} insights from Grok")
                    return insights

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Grok JSON response: {e}")
                    logger.debug(f"Raw response: {content}")
                    return []

    except Exception as e:
        logger.error(f"Failed to generate Grok insights: {e}")
        logger.error(traceback.format_exc())
        return []


# =============================================================================
# Learning Storage
# =============================================================================

def load_learnings() -> Dict[str, Any]:
    """Load existing learnings from disk."""
    if not LEARNINGS_FILE.exists():
        return {
            "insights": [],
            "statistics": {},
            "last_compressed": None,
        }

    try:
        with open(LEARNINGS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load learnings: {e}")
        return {
            "insights": [],
            "statistics": {},
            "last_compressed": None,
        }


def save_learnings(learnings: Dict[str, Any]):
    """Save learnings to disk."""
    try:
        LEARNINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(LEARNINGS_FILE, 'w') as f:
            json.dump(learnings, f, indent=2)

        logger.debug(f"Saved learnings ({len(learnings.get('insights', []))} insights)")

    except Exception as e:
        logger.error(f"Failed to save learnings: {e}")


# =============================================================================
# Learning Compressor Service
# =============================================================================

class LearningCompressor:
    """
    Background service that compresses observations into insights every hour.

    Usage:
        compressor = LearningCompressor()
        await compressor.start()  # Runs forever
    """

    def __init__(self, compression_interval: int = 60 * 60):
        """
        Initialize learning compressor.

        Args:
            compression_interval: Seconds between compressions (default 1 hour)
        """
        self.compression_interval = compression_interval
        self.running = False
        self.xai_api_key = os.getenv("XAI_API_KEY", "")

    async def start(self):
        """Start the compression loop (runs forever)."""
        self.running = True
        logger.info(f"🧠 Learning compressor started (compressing every {self.compression_interval // 60} minutes)")

        while self.running:
            try:
                await self.compress_observations()

            except Exception as e:
                logger.error(f"Learning compressor error: {e}")
                logger.error(traceback.format_exc())

            # Wait for next compression
            await asyncio.sleep(self.compression_interval)

    async def compress_observations(self):
        """Compress observations into insights."""
        logger.info("Compressing observations into insights...")

        try:
            # Load observations
            from tg_bot.services.observation_collector import load_observations

            learnings = load_learnings()
            last_compressed = learnings.get("last_compressed")

            # Get observations since last compression
            observations = load_observations(since_timestamp=last_compressed)

            if not observations:
                logger.info("No new observations to compress")
                return

            logger.info(f"Processing {len(observations)} new observations")

            # Calculate statistics
            stats = calculate_trade_statistics(observations)

            # Generate insights with Grok
            insights = await generate_insights_with_grok(stats, self.xai_api_key)

            # Update learnings
            learnings["statistics"] = stats
            learnings["insights"] = insights
            learnings["last_compressed"] = datetime.now(timezone.utc).isoformat()
            learnings["observation_count"] = len(observations)

            # Save to disk
            save_learnings(learnings)

            logger.info(
                f"✅ Compressed {len(observations)} observations → {len(insights)} insights "
                f"(Win rate: {stats.get('win_rate', 0):.1f}%)"
            )

        except Exception as e:
            logger.error(f"Compression failed: {e}")
            logger.error(traceback.format_exc())

    def stop(self):
        """Stop the compression loop."""
        self.running = False
        logger.info("Learning compressor stopped")


# =============================================================================
# Singleton Instance
# =============================================================================

_compressor_instance: Optional[LearningCompressor] = None


def get_learning_compressor() -> LearningCompressor:
    """Get singleton learning compressor instance."""
    global _compressor_instance
    if _compressor_instance is None:
        _compressor_instance = LearningCompressor()
    return _compressor_instance


async def start_learning_compressor():
    """Start the learning compressor service (for use in supervisor)."""
    compressor = get_learning_compressor()
    await compressor.start()


# =============================================================================
# Insight Query API (for demo.py to show warnings)
# =============================================================================

def get_latest_insights(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get latest insights for display in UI.

    Args:
        limit: Max number of insights to return

    Returns:
        List of insights sorted by confidence
    """
    learnings = load_learnings()
    insights = learnings.get("insights", [])

    # Sort by confidence (high > medium > low)
    confidence_order = {"high": 3, "medium": 2, "low": 1}
    insights.sort(
        key=lambda x: confidence_order.get(x.get("confidence", "low"), 0),
        reverse=True
    )

    return insights[:limit]


def get_statistics() -> Dict[str, Any]:
    """
    Get latest trading statistics.

    Returns:
        Statistics dict with win rates, avg PnL, etc.
    """
    learnings = load_learnings()
    return learnings.get("statistics", {})


# =============================================================================
# Manual Testing
# =============================================================================

if __name__ == "__main__":
    # Test the learning compressor
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    async def test():
        """Test learning compressor."""
        compressor = LearningCompressor(compression_interval=30)  # 30 seconds for testing

        print("Starting learning compressor test...")
        print("Add some observations to demo_observations.jsonl to see compression in action")
        print("Press Ctrl+C to stop\n")

        try:
            await compressor.start()
        except KeyboardInterrupt:
            print("\nStopping...")
            compressor.stop()

    asyncio.run(test())
