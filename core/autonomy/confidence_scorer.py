"""
Confidence Scorer
Rate predictions and track accuracy over time
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "predictions"
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Prediction:
    """A prediction/call made by Jarvis"""
    prediction_id: str
    created_at: str
    prediction_type: str  # price, sentiment, trend, event
    subject: str  # token or topic
    prediction: str  # the actual prediction
    confidence: float  # 1-10
    timeframe: str  # 1h, 4h, 1d, 1w
    entry_price: float = 0.0
    target_price: float = 0.0
    invalidation_price: float = 0.0
    outcome: str = "pending"  # pending, correct, incorrect, partial
    outcome_notes: str = ""
    resolved_at: str = ""
    tweet_id: str = ""


class ConfidenceScorer:
    """
    Rate own predictions with confidence scores.
    Track accuracy over time.
    """
    
    def __init__(self):
        self.predictions_file = DATA_DIR / "predictions.json"
        self.predictions: List[Prediction] = []
        self._load_data()
    
    def _load_data(self):
        """Load prediction history"""
        try:
            if self.predictions_file.exists():
                data = json.loads(self.predictions_file.read_text())
                self.predictions = [Prediction(**p) for p in data]
        except Exception as e:
            logger.error(f"Error loading predictions: {e}")
    
    def _save_data(self):
        """Save prediction data"""
        try:
            self.predictions_file.write_text(json.dumps(
                [asdict(p) for p in self.predictions[-500:]],
                indent=2
            ))
        except Exception as e:
            logger.error(f"Error saving predictions: {e}")
    
    def _generate_id(self) -> str:
        """Generate unique prediction ID"""
        import hashlib
        timestamp = datetime.utcnow().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:12]
    
    def calculate_confidence(
        self,
        signal_strength: float,  # 0-1, how strong the signal
        data_quality: float,  # 0-1, how much/good data we have
        market_conditions: str,  # trending, ranging, volatile
        alignment_count: int = 0  # how many indicators agree
    ) -> float:
        """
        Calculate confidence score 1-10 based on factors.
        """
        base = 5.0
        
        # Signal strength (±2)
        base += (signal_strength - 0.5) * 4
        
        # Data quality (±1.5)
        base += (data_quality - 0.5) * 3
        
        # Market conditions
        if market_conditions == "trending":
            base += 0.5  # Easier to predict in trends
        elif market_conditions == "volatile":
            base -= 1.0  # Harder in volatility
        
        # Indicator alignment bonus
        base += min(alignment_count * 0.3, 1.5)
        
        # Clamp to 1-10
        return max(1.0, min(10.0, round(base, 1)))
    
    def record_prediction(
        self,
        prediction_type: str,
        subject: str,
        prediction: str,
        confidence: float,
        timeframe: str = "1d",
        entry_price: float = 0.0,
        target_price: float = 0.0,
        invalidation_price: float = 0.0,
        tweet_id: str = ""
    ) -> Prediction:
        """Record a new prediction"""
        pred = Prediction(
            prediction_id=self._generate_id(),
            created_at=datetime.utcnow().isoformat(),
            prediction_type=prediction_type,
            subject=subject,
            prediction=prediction,
            confidence=confidence,
            timeframe=timeframe,
            entry_price=entry_price,
            target_price=target_price,
            invalidation_price=invalidation_price,
            tweet_id=tweet_id
        )
        self.predictions.append(pred)
        self._save_data()
        logger.info(f"Recorded prediction: {subject} - {prediction} (confidence: {confidence})")
        return pred
    
    def resolve_prediction(
        self,
        prediction_id: str,
        outcome: str,
        notes: str = ""
    ):
        """Resolve a prediction outcome"""
        for pred in self.predictions:
            if pred.prediction_id == prediction_id:
                pred.outcome = outcome
                pred.outcome_notes = notes
                pred.resolved_at = datetime.utcnow().isoformat()
                self._save_data()
                logger.info(f"Resolved prediction {prediction_id}: {outcome}")
                return pred
        return None
    
    async def auto_resolve_predictions(self, price_fetcher) -> int:
        """Auto-resolve predictions based on price data"""
        resolved = 0
        now = datetime.utcnow()
        
        for pred in self.predictions:
            if pred.outcome != "pending":
                continue
            
            # Check if timeframe has passed
            created = datetime.fromisoformat(pred.created_at)
            timeframe_hours = {
                "1h": 1, "4h": 4, "1d": 24, "1w": 168
            }.get(pred.timeframe, 24)
            
            if (now - created).total_seconds() / 3600 < timeframe_hours:
                continue  # Not yet time to resolve
            
            # Try to get current price
            try:
                if pred.entry_price > 0:
                    current_price = await price_fetcher(pred.subject)
                    if current_price:
                        # Check outcome
                        if pred.target_price > 0:
                            if pred.target_price > pred.entry_price:  # Bullish
                                if current_price >= pred.target_price:
                                    self.resolve_prediction(pred.prediction_id, "correct", f"Hit target {pred.target_price}")
                                elif pred.invalidation_price > 0 and current_price <= pred.invalidation_price:
                                    self.resolve_prediction(pred.prediction_id, "incorrect", f"Hit invalidation {pred.invalidation_price}")
                                else:
                                    # Partial - moved in right direction
                                    if current_price > pred.entry_price:
                                        self.resolve_prediction(pred.prediction_id, "partial", f"Right direction, didn't hit target")
                                    else:
                                        self.resolve_prediction(pred.prediction_id, "incorrect", f"Wrong direction")
                            else:  # Bearish
                                if current_price <= pred.target_price:
                                    self.resolve_prediction(pred.prediction_id, "correct", f"Hit target {pred.target_price}")
                                else:
                                    self.resolve_prediction(pred.prediction_id, "incorrect", f"Didn't hit target")
                        resolved += 1
            except Exception as e:
                logger.debug(f"Could not auto-resolve {pred.prediction_id}: {e}")
        
        return resolved
    
    def get_accuracy_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get accuracy statistics"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        recent = [p for p in self.predictions 
                  if p.outcome != "pending" and 
                  datetime.fromisoformat(p.created_at) > cutoff]
        
        if not recent:
            return {"total": 0, "accuracy": 0, "message": "Not enough data"}
        
        correct = len([p for p in recent if p.outcome == "correct"])
        partial = len([p for p in recent if p.outcome == "partial"])
        incorrect = len([p for p in recent if p.outcome == "incorrect"])
        total = correct + partial + incorrect
        
        # Accuracy: correct + 0.5*partial
        accuracy = ((correct + 0.5 * partial) / total * 100) if total > 0 else 0
        
        # Accuracy by confidence level
        high_conf = [p for p in recent if p.confidence >= 7]
        high_conf_correct = len([p for p in high_conf if p.outcome == "correct"])
        high_conf_accuracy = (high_conf_correct / len(high_conf) * 100) if high_conf else 0
        
        return {
            "total": total,
            "correct": correct,
            "partial": partial,
            "incorrect": incorrect,
            "accuracy": round(accuracy, 1),
            "high_confidence_accuracy": round(high_conf_accuracy, 1),
            "avg_confidence": round(sum(p.confidence for p in recent) / len(recent), 1) if recent else 0,
            "message": f"{accuracy:.0f}% accuracy over {days} days ({total} predictions)"
        }
    
    def get_accuracy_by_type(self) -> Dict[str, float]:
        """Get accuracy breakdown by prediction type"""
        types = {}
        
        for pred in self.predictions:
            if pred.outcome == "pending":
                continue
            
            if pred.prediction_type not in types:
                types[pred.prediction_type] = {"correct": 0, "total": 0}
            
            types[pred.prediction_type]["total"] += 1
            if pred.outcome == "correct":
                types[pred.prediction_type]["correct"] += 1
        
        return {
            t: round(v["correct"] / v["total"] * 100, 1) if v["total"] > 0 else 0
            for t, v in types.items()
        }
    
    def should_be_conservative(self) -> bool:
        """Check if recent accuracy suggests being more conservative"""
        stats = self.get_accuracy_stats(7)  # Last week
        return stats["accuracy"] < 50 and stats["total"] >= 5
    
    def get_confidence_adjustment(self) -> float:
        """Get adjustment factor based on recent performance"""
        stats = self.get_accuracy_stats(14)
        if stats["total"] < 5:
            return 1.0  # Not enough data
        
        if stats["accuracy"] >= 70:
            return 1.1  # Slightly more confident
        elif stats["accuracy"] < 40:
            return 0.8  # Be more conservative
        return 1.0
    
    def format_track_record(self) -> str:
        """Format track record for display"""
        stats = self.get_accuracy_stats(30)
        if stats["total"] == 0:
            return "no track record yet. building it."
        
        return f"{stats['accuracy']:.0f}% accuracy ({stats['correct']}/{stats['total']} calls). transparent about the misses too."


# Singleton
_scorer: Optional[ConfidenceScorer] = None

def get_confidence_scorer() -> ConfidenceScorer:
    global _scorer
    if _scorer is None:
        _scorer = ConfidenceScorer()
    return _scorer
