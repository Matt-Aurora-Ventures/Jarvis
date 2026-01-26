"""
Opportunity Strategy Integration

Connects opportunity_engine.py detection with trading_decision_matrix.py strategy selection
and trading_operations.py execution.

Integration Flow:
    opportunity_engine.detect()
    -> decision_matrix.evaluate_opportunity()
    -> strategy = match_opportunity_to_strategy()
    -> if confidence > threshold and risk_ok:
        -> trading_operations.execute_trade()
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.trading_decision_matrix import (
    get_decision_matrix,
    StrategyCategory,
    MarketRegime,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Defaults
# =============================================================================

DEFAULT_CONFIG = {
    "min_confidence": 0.55,
    "min_edge_to_cost_ratio": 2.0,
    "approval_threshold_usd": 100.0,
    "max_concurrent_positions": 10,
    "risk_limits": {
        "crypto": {
            "max_position_usd": 500.0,
            "max_daily_loss_usd": 500.0,
            "max_portfolio_allocation_pct": 0.10,
        },
        "tokenized_equity": {
            "max_position_usd": 300.0,
            "max_daily_loss_usd": 300.0,
            "max_portfolio_allocation_pct": 0.08,
        },
    },
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class EvaluationResult:
    """Result of evaluating an opportunity."""
    approved: bool
    strategy: Optional[str]
    confidence: float
    recommended_size_usd: float
    requires_approval: bool
    auto_execute_eligible: bool
    rejection_reason: str
    approval_reason: str
    timestamp: str
    symbol: str
    opportunity_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "strategy": self.strategy,
            "confidence": self.confidence,
            "recommended_size_usd": self.recommended_size_usd,
            "requires_approval": self.requires_approval,
            "auto_execute_eligible": self.auto_execute_eligible,
            "rejection_reason": self.rejection_reason,
            "approval_reason": self.approval_reason,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "opportunity_id": self.opportunity_id,
        }


# =============================================================================
# Main Integration Class
# =============================================================================

class OpportunityStrategyIntegration:
    """
    Integration layer connecting opportunity detection to strategy execution.

    This class:
    1. Maps opportunities to appropriate trading strategies
    2. Applies confidence thresholds for quality control
    3. Enforces risk limits per opportunity type
    4. Implements approval gates for high-value trades
    5. Integrates with trading operations for execution
    """

    def __init__(
        self,
        min_confidence: float = None,
        min_edge_to_cost_ratio: float = None,
        approval_threshold_usd: float = None,
        max_concurrent_positions: int = None,
        risk_limits: Dict[str, Dict[str, float]] = None,
    ):
        """
        Initialize the integration layer.

        Args:
            min_confidence: Minimum confidence score to approve (default: 0.55)
            approval_threshold_usd: Trades above this require manual approval (default: 100)
            max_concurrent_positions: Maximum open positions allowed (default: 10)
            risk_limits: Risk limits per asset type
        """
        self.min_confidence = min_confidence if min_confidence is not None else DEFAULT_CONFIG["min_confidence"]
        self.min_edge_to_cost_ratio = min_edge_to_cost_ratio if min_edge_to_cost_ratio is not None else DEFAULT_CONFIG["min_edge_to_cost_ratio"]
        self.approval_threshold_usd = approval_threshold_usd if approval_threshold_usd is not None else DEFAULT_CONFIG["approval_threshold_usd"]
        self.max_concurrent_positions = max_concurrent_positions if max_concurrent_positions is not None else DEFAULT_CONFIG["max_concurrent_positions"]
        self.risk_limits = risk_limits if risk_limits is not None else DEFAULT_CONFIG["risk_limits"].copy()

        self._decision_matrix = get_decision_matrix()
        self._evaluation_history: List[Dict[str, Any]] = []

    def evaluate_opportunity(
        self,
        opportunity: Dict[str, Any],
        requested_size_usd: float = None,
        portfolio_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate an opportunity and determine if it should be traded.

        Args:
            opportunity: Opportunity dict from opportunity_engine
            requested_size_usd: Requested position size in USD
            portfolio_context: Current portfolio state (daily loss, etc.)

        Returns:
            Evaluation result dict with approval status, strategy, sizing
        """
        symbol = opportunity.get("symbol", "UNKNOWN")
        asset_type = opportunity.get("asset_type", "crypto")
        scores = opportunity.get("scores", {})
        signal = opportunity.get("signal", {})
        costs = opportunity.get("costs", {})

        # Extract key metrics
        confidence = signal.get("confidence", scores.get("opportunity", 0.0))
        sentiment = scores.get("sentiment", 0.5)
        momentum = scores.get("momentum", 0.5)
        opportunity_score = scores.get("opportunity", 0.0)
        expected_edge_pct = signal.get("expected_edge_pct", 0.0)
        cost_pct = costs.get("total_pct", 0.03)

        # Calculate edge-to-cost ratio
        edge_to_cost = expected_edge_pct / cost_pct if cost_pct > 0 else 0

        # Default result
        result = EvaluationResult(
            approved=False,
            strategy=None,
            confidence=confidence,
            recommended_size_usd=0.0,
            requires_approval=False,
            auto_execute_eligible=False,
            rejection_reason="",
            approval_reason="",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            symbol=symbol,
            opportunity_id=str(uuid.uuid4())[:8],
        )

        # Check 1: Confidence threshold
        if confidence < self.min_confidence:
            result.rejection_reason = f"Confidence {confidence:.2f} below threshold {self.min_confidence}"
            self._log_evaluation(result)
            return result.to_dict()

        # Check 2: Edge-to-cost ratio
        if edge_to_cost < self.min_edge_to_cost_ratio:
            result.rejection_reason = f"Edge-to-cost ratio {edge_to_cost:.2f} below minimum {self.min_edge_to_cost_ratio}"
            self._log_evaluation(result)
            return result.to_dict()

        # Check 3: Daily loss limit
        if portfolio_context:
            daily_loss = portfolio_context.get("daily_loss_usd", 0)
            daily_limit = portfolio_context.get("daily_loss_limit_usd", self.risk_limits.get(asset_type, {}).get("max_daily_loss_usd", 500))
            remaining_risk_budget = daily_limit - daily_loss

            if remaining_risk_budget <= 50:  # Less than or equal to $50 remaining risk budget
                result.rejection_reason = f"Daily loss limit nearly reached: ${daily_loss:.2f} of ${daily_limit:.2f}"
                self._log_evaluation(result)
                return result.to_dict()

        # Select strategy based on opportunity characteristics
        strategy = self._select_strategy(opportunity)
        result.strategy = strategy

        # Calculate recommended position size
        risk_limits = self.get_risk_limits(asset_type)
        max_position = risk_limits.get("max_position_usd", 500.0)

        if requested_size_usd is not None:
            result.recommended_size_usd = min(requested_size_usd, max_position)
        else:
            # Scale position by confidence
            base_size = max_position * 0.5  # Start at 50% of max
            confidence_multiplier = (confidence - self.min_confidence) / (1.0 - self.min_confidence)
            result.recommended_size_usd = min(base_size * (1 + confidence_multiplier * 0.5), max_position)

        # Apply daily loss limit constraint
        if portfolio_context:
            remaining_risk = portfolio_context.get("daily_loss_limit_usd", 500) - portfolio_context.get("daily_loss_usd", 0)
            result.recommended_size_usd = min(result.recommended_size_usd, remaining_risk)

        # Check if approval required
        if result.recommended_size_usd > self.approval_threshold_usd:
            result.requires_approval = True
            result.approval_reason = "amount_exceeds_threshold"
            result.auto_execute_eligible = False
        else:
            result.requires_approval = False
            result.auto_execute_eligible = True

        # Approved!
        result.approved = True

        self._log_evaluation(result)
        return result.to_dict()

    def _select_strategy(self, opportunity: Dict[str, Any]) -> str:
        """
        Select the best strategy for an opportunity.

        Uses decision matrix and opportunity characteristics.
        """
        signal = opportunity.get("signal", {})
        scores = opportunity.get("scores", {})
        asset_type = opportunity.get("asset_type", "crypto")

        # Check for explicit strategy hint
        strategy_hint = signal.get("strategy_hint", "")
        if strategy_hint:
            if strategy_hint == "mean_reversion":
                return "MeanReversion"
            elif strategy_hint == "momentum":
                return "TrendFollower"
            elif strategy_hint == "arbitrage":
                return "ArbitrageScanner"

        # Analyze scores to determine regime
        momentum = scores.get("momentum", 0.5)
        sentiment = scores.get("sentiment", 0.5)

        # For tokenized equities, prefer safer strategies (check FIRST before regime)
        if asset_type == "tokenized_equity":
            if momentum > 0.5:
                return "TrendFollower"
            else:
                return "DCABot"

        # Determine market regime from opportunity characteristics for crypto
        # High momentum + high sentiment = trending market
        if momentum > 0.7 and sentiment > 0.6:
            # For trending markets with high momentum, use TrendFollower or BreakoutTrader
            return "TrendFollower"
        elif momentum < 0.3:
            # Low momentum = choppy/ranging market
            return "MeanReversion"
        elif momentum > 0.6:
            # Moderate-high momentum but lower sentiment = volatile
            return "BreakoutTrader"
        else:
            # Calm market
            return "GridTrader"

    def get_risk_limits(self, asset_type: str) -> Dict[str, float]:
        """
        Get risk limits for an asset type.

        Args:
            asset_type: "crypto" or "tokenized_equity"

        Returns:
            Dict with max_position_usd, max_daily_loss_usd, etc.
        """
        return self.risk_limits.get(asset_type, self.risk_limits.get("crypto", DEFAULT_CONFIG["risk_limits"]["crypto"]))

    def _log_evaluation(self, result: EvaluationResult) -> None:
        """Log evaluation to history."""
        self._evaluation_history.append(result.to_dict())

        if result.approved:
            logger.info(
                f"Opportunity APPROVED: {result.symbol} | "
                f"Strategy: {result.strategy} | "
                f"Confidence: {result.confidence:.2f} | "
                f"Size: ${result.recommended_size_usd:.2f}"
            )
        else:
            logger.info(
                f"Opportunity REJECTED: {result.symbol} | "
                f"Reason: {result.rejection_reason}"
            )

    def get_evaluation_history(self) -> List[Dict[str, Any]]:
        """Get history of evaluations."""
        return self._evaluation_history.copy()

    async def execute_opportunity(
        self,
        opportunity: Dict[str, Any],
        trading_engine: Any,
        size_usd: float,
        user_id: int,
        skip_approval: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute an approved opportunity.

        Args:
            opportunity: Opportunity dict
            trading_engine: Trading engine with open_position method
            size_usd: Position size in USD
            user_id: User ID for authorization
            skip_approval: Skip approval gate (for pre-approved trades)

        Returns:
            Execution result dict
        """
        # Evaluate the opportunity first
        evaluation = self.evaluate_opportunity(opportunity, requested_size_usd=size_usd)

        if not evaluation.get("approved"):
            return {
                "success": False,
                "reason": f"Opportunity not approved: {evaluation.get('rejection_reason')}",
                "evaluation": evaluation,
            }

        # Check approval gate
        if evaluation.get("requires_approval") and not skip_approval:
            return {
                "success": False,
                "requires_approval": True,
                "reason": "Trade requires manual approval",
                "evaluation": evaluation,
            }

        # Extract trade parameters
        symbol = opportunity.get("symbol", "UNKNOWN")
        mint_address = opportunity.get("mint_address", "")
        strategy = evaluation.get("strategy")
        recommended_size = evaluation.get("recommended_size_usd", size_usd)

        # Determine sentiment grade from confidence
        confidence = evaluation.get("confidence", 0.55)
        if confidence >= 0.8:
            sentiment_grade = "A"
        elif confidence >= 0.7:
            sentiment_grade = "B"
        elif confidence >= 0.6:
            sentiment_grade = "C"
        else:
            sentiment_grade = "C"

        try:
            # Import TradeDirection
            from bots.treasury.trading.types import TradeDirection

            success, message, position = await trading_engine.open_position(
                token_mint=mint_address,
                token_symbol=symbol,
                direction=TradeDirection.LONG,
                amount_usd=recommended_size,
                sentiment_grade=sentiment_grade,
                sentiment_score=confidence,
                user_id=user_id,
            )

            return {
                "success": success,
                "message": message,
                "position": position,
                "strategy": strategy,
                "evaluation": evaluation,
            }

        except Exception as e:
            logger.error(f"Failed to execute opportunity: {e}")
            return {
                "success": False,
                "reason": f"Execution error: {str(e)}",
                "evaluation": evaluation,
            }

    def evaluate_engine_output(
        self,
        engine_output: Dict[str, Any],
        current_positions: int = 0,
    ) -> Dict[str, Any]:
        """
        Evaluate all opportunities from opportunity_engine output.

        Args:
            engine_output: Output from opportunity_engine.run_engine()
            current_positions: Number of currently open positions

        Returns:
            Dict with approved_opportunities and rejected_opportunities
        """
        ranked = engine_output.get("ranked", [])
        trade_intents = engine_output.get("trade_intents", [])

        # Build lookup for tradable status
        tradable_lookup = {
            ti.get("symbol"): ti.get("tradable", True)
            for ti in trade_intents
        }

        approved = []
        rejected = []

        # How many more positions can we open?
        available_slots = self.max_concurrent_positions - current_positions

        for opportunity in ranked:
            symbol = opportunity.get("symbol", "")

            # Check if tradable
            if not tradable_lookup.get(symbol, True):
                rejected.append({
                    "opportunity": opportunity,
                    "reason": "Not tradable",
                })
                continue

            # Evaluate
            evaluation = self.evaluate_opportunity(opportunity)

            if evaluation.get("approved"):
                if len(approved) < available_slots:
                    approved.append({
                        "opportunity": opportunity,
                        "evaluation": evaluation,
                    })
                else:
                    rejected.append({
                        "opportunity": opportunity,
                        "reason": "Position limit reached",
                    })
            else:
                rejected.append({
                    "opportunity": opportunity,
                    "reason": evaluation.get("rejection_reason"),
                })

        return {
            "approved_opportunities": approved,
            "rejected_opportunities": rejected,
            "total_evaluated": len(ranked),
            "available_slots": available_slots,
        }


# =============================================================================
# Module-level convenience functions
# =============================================================================

_integration_instance: Optional[OpportunityStrategyIntegration] = None


def get_integration() -> OpportunityStrategyIntegration:
    """Get or create the singleton integration instance."""
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = OpportunityStrategyIntegration()
    return _integration_instance


def evaluate_opportunity(opportunity: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Convenience function to evaluate an opportunity."""
    return get_integration().evaluate_opportunity(opportunity, **kwargs)


async def execute_opportunity(
    opportunity: Dict[str, Any],
    trading_engine: Any,
    size_usd: float,
    user_id: int,
    **kwargs
) -> Dict[str, Any]:
    """Convenience function to execute an opportunity."""
    return await get_integration().execute_opportunity(
        opportunity, trading_engine, size_usd, user_id, **kwargs
    )
