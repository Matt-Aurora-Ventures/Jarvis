"""
Example: Integrating ConfidenceScorer with DexterAgent

This example demonstrates how to integrate the enhanced confidence
scoring system with the Dexter ReAct agent.
"""

import asyncio
from datetime import datetime, timezone
from core.dexter.agent import DexterAgent
from core.dexter.confidence_scorer import (
    ConfidenceScorer,
    ConfidenceThresholds
)


async def example_integration():
    """Example of using ConfidenceScorer with DexterAgent."""

    # Initialize confidence scorer with custom thresholds
    thresholds = ConfidenceThresholds(
        buy_threshold=75.0,  # Higher threshold for BUY
        sell_threshold=70.0,  # Standard threshold for SELL
        buy_high_confidence=85.0,  # Aggressive BUY threshold
        absolute_minimum=65.0  # Never trade below this
    )

    confidence_scorer = ConfidenceScorer(
        data_dir="data/dexter/confidence",
        thresholds=thresholds
    )

    # Initialize Dexter agent
    agent = DexterAgent(config={
        "model": "grok-3",
        "max_iterations": 15,
        "min_confidence": 70.0
    })

    # Analyze a token
    symbol = "SOL"
    result = await agent.analyze_token(symbol)

    # Score and calibrate confidence
    raw_confidence = result.get("confidence", 70.0)
    decision = result.get("action", "HOLD")

    calibrated_confidence, note = confidence_scorer.score_confidence(
        raw_confidence=raw_confidence,
        decision=decision,
        symbol=symbol,
        grok_sentiment=75.0,  # From result
        iterations=5,
        tools_used=["market_data", "sentiment"]
    )

    print(f"\nDecision Analysis for {symbol}")
    print(f"="*50)
    print(f"Raw Confidence: {raw_confidence:.1f}%")
    print(f"Calibrated Confidence: {calibrated_confidence:.1f}%")
    print(f"Calibration Note: {note}")

    # Check if action should be taken
    should_act = confidence_scorer.should_take_action(
        calibrated_confidence,
        decision
    )

    is_high_conf = confidence_scorer.is_high_confidence(
        calibrated_confidence,
        decision
    )

    print(f"\nShould Take Action: {should_act}")
    print(f"High Confidence: {is_high_conf}")

    # Record decision for future calibration
    decision_id = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    confidence_scorer.record_decision(
        decision_id=decision_id,
        symbol=symbol,
        decision=decision,
        confidence=calibrated_confidence,
        grok_sentiment=75.0,
        iterations=5,
        tools_used=["market_data", "sentiment"]
    )

    print(f"\nRecorded decision: {decision_id}")

    # Later: Update with actual outcome (e.g., after 1 hour)
    # confidence_scorer.update_outcome(
    #     decision_id=decision_id,
    #     actual_accuracy_1h=True,  # Was the prediction correct?
    #     pnl_pct_1h=2.5  # Actual P&L
    # )

    # Check temporal decay
    print(f"\nTemporal Decay Examples:")
    for age_hours in [0.1, 0.5, 2.0, 12.0, 24.0]:
        decayed = confidence_scorer.apply_temporal_decay(
            calibrated_confidence,
            age_hours
        )
        print(f"  After {age_hours:.1f}h: {decayed:.1f}%")

    # Get calibration statistics
    stats = confidence_scorer.get_calibration_stats()

    print(f"\nCalibration Statistics:")
    print(f"  Total Decisions: {stats.total_decisions}")
    print(f"  Avg Predicted: {stats.avg_predicted_confidence:.1f}%")
    print(f"  Avg Actual (1h): {stats.avg_actual_accuracy_1h:.1f}%")
    print(f"  Calibration Error: {stats.calibration_error_1h:.1f} points")
    print(f"  Status: {stats.calibration_status_1h}")

    # Generate full calibration report
    report = confidence_scorer.generate_calibration_report()
    print(f"\n{report}")

    # Save calibration data
    calibration_file = confidence_scorer.save_calibration()
    print(f"Calibration saved to: {calibration_file}")


def example_usage_pattern():
    """
    Example usage pattern for production code.

    Shows how to integrate confidence scoring into the trading workflow.
    """

    code_example = '''
# In your trading bot:

from core.dexter.agent import DexterAgent
from core.dexter.confidence_scorer import ConfidenceScorer, ConfidenceThresholds

class TradingBot:
    def __init__(self):
        # Initialize components
        self.agent = DexterAgent()

        # Custom thresholds for your risk tolerance
        thresholds = ConfidenceThresholds(
            buy_threshold=75.0,
            sell_threshold=70.0,
            absolute_minimum=65.0
        )

        self.confidence_scorer = ConfidenceScorer(
            data_dir="data/dexter/confidence",
            thresholds=thresholds
        )

    async def analyze_and_trade(self, symbol: str):
        # Get Dexter's analysis
        result = await self.agent.analyze_token(symbol)

        # Calibrate confidence
        calibrated, note = self.confidence_scorer.score_confidence(
            raw_confidence=result["confidence"],
            decision=result["action"],
            symbol=symbol,
            iterations=result.get("iterations", 0)
        )

        # Check if confidence meets threshold
        if not self.confidence_scorer.should_take_action(calibrated, result["action"]):
            print(f"Confidence {calibrated:.1f}% too low, holding")
            return

        # Record decision
        decision_id = self.confidence_scorer.record_decision(
            decision_id=f"{symbol}_{int(datetime.now().timestamp())}",
            symbol=symbol,
            decision=result["action"],
            confidence=calibrated
        )

        # Execute trade (if confidence is high enough)
        if result["action"] == "BUY":
            await self.execute_buy(symbol, calibrated)
        elif result["action"] == "SELL":
            await self.execute_sell(symbol, calibrated)

        # Schedule outcome update (after 1 hour)
        asyncio.create_task(self.update_outcome_later(decision_id, symbol))

    async def update_outcome_later(self, decision_id: str, symbol: str):
        # Wait 1 hour
        await asyncio.sleep(3600)

        # Check actual outcome
        entry_price = self.get_entry_price(decision_id)
        current_price = await self.get_current_price(symbol)

        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        was_accurate = pnl_pct > 0

        # Update confidence scorer
        self.confidence_scorer.update_outcome(
            decision_id=decision_id,
            actual_accuracy_1h=was_accurate,
            pnl_pct_1h=pnl_pct
        )

        # Save calibration data
        self.confidence_scorer.save_calibration()
'''

    print(code_example)


if __name__ == "__main__":
    print("=" * 70)
    print("Dexter Confidence Scorer Integration Example")
    print("=" * 70)

    # Run integration example
    asyncio.run(example_integration())

    print("\n" + "=" * 70)
    print("Production Usage Pattern")
    print("=" * 70)
    example_usage_pattern()
