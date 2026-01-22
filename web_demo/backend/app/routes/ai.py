"""
AI Analysis Routes
Self-correcting AI endpoints for token analysis and recommendations.
"""

from fastapi import APIRouter, HTTPException, Security, Request, status
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, Dict, Any, Literal
from datetime import datetime
import logging

from ..services.self_correcting_ai import (
    get_ai_service,
    TradeOutcome,
    AIRecommendation
)
from ..services.supervisor_bridge import get_supervisor_bridge
from ..security import get_current_user
from ..middleware.security_validator import (
    security_monitor,
    sanitize_error_message,
    log_security_event,
    validate_ai_configuration
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI Analysis"])


class TokenAnalysisRequest(BaseModel):
    """Request for AI token analysis."""
    token_address: str = Field(..., description="Token mint address")
    token_symbol: str = Field(..., description="Token symbol")
    liquidity_usd: float = Field(default=0, description="Liquidity in USD")
    volume_24h: float = Field(default=0, description="24h volume in USD")
    holder_count: int = Field(default=0, description="Number of holders")
    age_days: int = Field(default=0, description="Token age in days")
    price_change_24h_pct: float = Field(default=0, description="24h price change %")
    has_twitter: bool = Field(default=False, description="Has Twitter account")
    has_website: bool = Field(default=False, description="Has website")
    has_telegram: bool = Field(default=False, description="Has Telegram")
    use_ai: bool = Field(default=True, description="Use AI vs rule-based")


class OutcomeReport(BaseModel):
    """Report actual trading outcome for learning."""
    token_address: str
    token_symbol: str
    action: Literal["buy", "sell", "hold", "skip"]
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    profit_loss_pct: Optional[float] = None
    outcome: Optional[Literal["profit", "loss", "pending"]] = None
    notes: str = ""


@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_token(
    req: Request,
    request: TokenAnalysisRequest,
    current_user: Dict = Security(get_current_user)
):
    """
    Analyze a token using self-correcting AI.

    Returns recommendation with action, confidence, and reasoning.
    The AI learns from past outcomes to improve accuracy over time.

    Security: Rate limited, input validated, errors sanitized.
    """
    # Validate AI configuration on first use
    await validate_ai_configuration(req)

    ai_service = get_ai_service()

    try:
        # Build token data
        token_data = {
            "address": request.token_address,
            "symbol": request.token_symbol,
            "liquidity_usd": request.liquidity_usd,
            "volume_24h": request.volume_24h,
            "holder_count": request.holder_count,
            "age_days": request.age_days,
            "price_change_24h_pct": request.price_change_24h_pct,
            "has_twitter": request.has_twitter,
            "has_website": request.has_website,
            "has_telegram": request.has_telegram
        }

        # Get AI recommendation
        recommendation = await ai_service.analyze_token(
            token_data=token_data,
            use_ai=request.use_ai
        )

        # Log successful analysis
        await log_security_event(
            event_type="ai_analysis_success",
            severity="info",
            details={
                "token": request.token_symbol,
                "action": recommendation.action,
                "confidence": recommendation.confidence
            },
            request=req
        )

        # Share with supervisor
        bridge = get_supervisor_bridge()
        bridge.publish_event(
            event_type="ai_recommendation",
            data={
                "token_address": recommendation.token_address,
                "token_symbol": recommendation.token_symbol,
                "action": recommendation.action,
                "confidence": recommendation.confidence,
                "score": recommendation.score,
                "user_id": current_user["user_id"]
            }
        )

        return {
            "token_address": recommendation.token_address,
            "token_symbol": recommendation.token_symbol,
            "action": recommendation.action,
            "confidence": recommendation.confidence,
            "reasoning": recommendation.reasoning,
            "score": recommendation.score,
            "timestamp": recommendation.timestamp.isoformat(),
            "model_used": ai_service.preferred_model,
            "prediction_accuracy": ai_service.prediction_accuracy
        }

    except ValidationError as e:
        # Log validation failure
        security_monitor.log_validation_failure(
            endpoint="/api/v1/ai/analyze",
            error=str(e),
            client_ip=req.client.host
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid request data"
        )
    except Exception as e:
        # Log error and sanitize message
        logger.error(f"AI analysis error: {e}", exc_info=True)
        await log_security_event(
            event_type="ai_analysis_error",
            severity="error",
            details={"error_type": type(e).__name__},
            request=req
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=sanitize_error_message(e)
        )


@router.post("/record-outcome")
async def record_outcome(
    req: Request,
    outcome: OutcomeReport,
    current_user: Dict = Security(get_current_user)
):
    """
    Record actual trading outcome for AI to learn from.

    This completes the feedback loop and enables self-correction.

    Security: Input validated, outcomes logged for audit trail.
    """
    ai_service = get_ai_service()

    try:
        trade_outcome = TradeOutcome(
            token_address=outcome.token_address,
            token_symbol=outcome.token_symbol,
            action=outcome.action,
            entry_price=outcome.entry_price,
            exit_price=outcome.exit_price,
            profit_loss_pct=outcome.profit_loss_pct,
            outcome=outcome.outcome,
            notes=outcome.notes
        )

        await ai_service.record_outcome(trade_outcome)

        # Log outcome recording
        await log_security_event(
            event_type="trade_outcome_recorded",
            severity="info",
            details={
                "token": outcome.token_symbol,
                "action": outcome.action,
                "outcome": outcome.outcome,
                "profit_loss_pct": outcome.profit_loss_pct
            },
            request=req
        )

        # Share learning with supervisor
        bridge = get_supervisor_bridge()
        bridge.publish_event(
            event_type="trade_outcome",
            data={
                "token_address": outcome.token_address,
                "token_symbol": outcome.token_symbol,
                "action": outcome.action,
                "outcome": outcome.outcome,
                "profit_loss_pct": outcome.profit_loss_pct,
                "user_id": current_user["user_id"]
            }
        )

        # If we learned something significant, share it
        if outcome.outcome in ["profit", "loss"]:
            if outcome.outcome == "loss" and outcome.profit_loss_pct and outcome.profit_loss_pct < -20:
                bridge.share_learning(
                    insight=f"{outcome.token_symbol} lost {outcome.profit_loss_pct:.1f}% - pattern to avoid in future",
                    category="risk",
                    confidence=0.7
                )

        return {
            "status": "recorded",
            "prediction_accuracy": ai_service.prediction_accuracy,
            "total_predictions": ai_service.total_predictions,
            "message": "Outcome recorded. AI will learn from this result."
        }

    except ValidationError as e:
        security_monitor.log_validation_failure(
            endpoint="/api/v1/ai/record-outcome",
            error=str(e),
            client_ip=req.client.host
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid outcome data"
        )
    except Exception as e:
        logger.error(f"Record outcome error: {e}", exc_info=True)
        await log_security_event(
            event_type="record_outcome_error",
            severity="error",
            details={"error_type": type(e).__name__},
            request=req
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=sanitize_error_message(e)
        )


@router.get("/stats")
async def get_ai_stats(current_user: Dict = Security(get_current_user)):
    """Get AI service statistics and performance metrics."""
    ai_service = get_ai_service()
    bridge = get_supervisor_bridge()

    ai_stats = ai_service.get_stats()
    bridge_stats = bridge.get_stats()

    return {
        "ai": ai_stats,
        "supervisor": bridge_stats,
        "integration": {
            "shared_learnings": len(bridge.get_learnings()),
            "high_confidence_learnings": len(
                bridge.get_learnings(min_confidence=0.7)
            ),
            "recent_events": len(bridge.get_events(limit=100))
        }
    }


@router.get("/learnings")
async def get_learnings(
    category: Optional[str] = None,
    min_confidence: float = 0.0,
    current_user: Dict = Security(get_current_user)
):
    """
    Get AI learnings from across the Jarvis ecosystem.

    These are insights shared by all components (web demo, treasury, twitter, etc.)
    that help improve future predictions.
    """
    bridge = get_supervisor_bridge()
    learnings = bridge.get_learnings(
        category=category,
        min_confidence=min_confidence
    )

    return {
        "total": len(learnings),
        "category": category or "all",
        "min_confidence": min_confidence,
        "learnings": learnings
    }
