"""
DSPy Strategy Classification Module
====================================

Uses DSPy (Declarative Self-improving Python) from Stanford NLP
to optimize strategy classification, risk analysis, and patch proposals.

Works with local Ollama models (preferred) or cloud providers.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Try to import DSPy, graceful fallback if not installed
try:
    import dspy
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    log.warning("DSPy not installed. Run: pip install dspy-ai")

ROOT = Path(__file__).resolve().parents[1]
TRAINING_DATA_PATH = ROOT / "data" / "dspy_training.json"


# =============================================================================
# Strategy Categories
# =============================================================================

class StrategyCategory(Enum):
    ARBITRAGE = "arbitrage"
    MARKET_NEUTRAL = "market_neutral"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    AI_ADAPTIVE = "ai_adaptive"
    UNKNOWN = "unknown"


# =============================================================================
# DSPy Signatures (Class-Based for Complex Tasks)
# =============================================================================

if DSPY_AVAILABLE:
    
    class ClassifyStrategy(dspy.Signature):
        """Classify a trading strategy into categories based on its description."""
        
        description: str = dspy.InputField(
            desc="Description of the trading strategy, including entry/exit conditions"
        )
        
        category: str = dspy.OutputField(
            desc="One of: arbitrage, market_neutral, momentum, mean_reversion, ai_adaptive"
        )
        subcategory: str = dspy.OutputField(
            desc="Specific subcategory like 'triangular_arb', 'grid_trading', 'rsi_bollinger'"
        )
        confidence: float = dspy.OutputField(
            desc="Confidence score from 0.0 to 1.0"
        )
    
    
    class AnalyzeStrategyRisk(dspy.Signature):
        """Analyze failure modes and risk controls for a trading strategy."""
        
        strategy_name: str = dspy.InputField(desc="Name of the strategy")
        strategy_description: str = dspy.InputField(desc="Description of strategy logic")
        
        failure_modes: str = dspy.OutputField(
            desc="Comma-separated list of failure modes like: 'slippage, flash crash, exchange downtime'"
        )
        recommended_controls: str = dspy.OutputField(
            desc="Comma-separated risk controls like: 'max position size, stop loss, circuit breaker'"
        )
        risk_score: int = dspy.OutputField(
            desc="Risk score from 1 (low) to 10 (high)"
        )
    
    
    class ProposePatch(dspy.Signature):
        """Propose a code patch to fix an issue or improve code."""
        
        error_description: str = dspy.InputField(desc="Description of the error or improvement needed")
        relevant_code: str = dspy.InputField(desc="The code section to modify (100 lines max)")
        
        patch_explanation: str = dspy.OutputField(desc="Explanation of what the patch does")
        patch_diff: str = dspy.OutputField(desc="Unified diff format patch")
        risk_level: int = dspy.OutputField(desc="Risk level 1-10 of applying this patch")
    
    
    class GenerateTestCase(dspy.Signature):
        """Generate a pytest test case for a trading strategy."""
        
        strategy_name: str = dspy.InputField(desc="Name of the strategy to test")
        strategy_code: str = dspy.InputField(desc="Python code of the strategy")
        
        test_code: str = dspy.OutputField(desc="Complete pytest test function")
        edge_cases: str = dspy.OutputField(desc="Comma-separated list of edge cases tested")


# =============================================================================
# DSPy Modules (Composable Programs)
# =============================================================================

if DSPY_AVAILABLE:
    
    class StrategyClassifier(dspy.Module):
        """DSPy module to classify trading strategies."""
        
        def __init__(self):
            super().__init__()
            self.classify = dspy.Predict(ClassifyStrategy)
        
        def forward(self, description: str) -> Dict[str, Any]:
            """Classify a strategy description."""
            result = self.classify(description=description)
            return {
                "category": getattr(result, "category", "unknown"),
                "subcategory": getattr(result, "subcategory", "unknown"),
                "confidence": float(getattr(result, "confidence", 0.5)),
            }
    
    
    class RiskAnalyzer(dspy.Module):
        """DSPy module to analyze strategy risks."""
        
        def __init__(self):
            super().__init__()
            self.analyze = dspy.Predict(AnalyzeStrategyRisk)
        
        def forward(self, name: str, description: str) -> Dict[str, Any]:
            """Analyze risks of a strategy."""
            result = self.analyze(strategy_name=name, strategy_description=description)
            return {
                "failure_modes": [s.strip() for s in getattr(result, "failure_modes", "").split(",")],
                "recommended_controls": [s.strip() for s in getattr(result, "recommended_controls", "").split(",")],
                "risk_score": int(getattr(result, "risk_score", 5)),
            }
    
    
    class PatchProposer(dspy.Module):
        """DSPy module to propose code patches."""
        
        def __init__(self):
            super().__init__()
            self.propose = dspy.Predict(ProposePatch)
        
        def forward(self, error: str, code: str) -> Dict[str, Any]:
            """Propose a patch for an error."""
            result = self.propose(error_description=error, relevant_code=code[:3000])
            return {
                "explanation": getattr(result, "patch_explanation", ""),
                "diff": getattr(result, "patch_diff", ""),
                "risk_level": int(getattr(result, "risk_level", 5)),
            }


# =============================================================================
# Training Examples
# =============================================================================

TRAINING_EXAMPLES = [
    {
        "description": "Buy when RSI < 30 and price below lower Bollinger Band, sell when RSI > 70 or price above upper band",
        "category": "mean_reversion",
        "subcategory": "rsi_bollinger",
        "confidence": 0.95
    },
    {
        "description": "Execute simultaneous buy/sell across three trading pairs to exploit price discrepancies in cross-rates",
        "category": "arbitrage",
        "subcategory": "triangular_arb",
        "confidence": 0.98
    },
    {
        "description": "Buy when short-term moving average crosses above long-term moving average (golden cross)",
        "category": "momentum",
        "subcategory": "ma_crossover",
        "confidence": 0.92
    },
    {
        "description": "Place grid of buy orders below current price and sell orders above, capturing range-bound volatility",
        "category": "market_neutral",
        "subcategory": "grid_trading",
        "confidence": 0.95
    },
    {
        "description": "Use RandomForest classifier to detect market regime (trending/ranging) and switch strategies accordingly",
        "category": "ai_adaptive",
        "subcategory": "ml_regime_switching",
        "confidence": 0.88
    },
    {
        "description": "Buy assets at regular intervals regardless of price to average cost over time",
        "category": "market_neutral",
        "subcategory": "dca",
        "confidence": 0.90
    },
    {
        "description": "Monitor mempool for large trades, insert transaction before them to profit from price impact",
        "category": "arbitrage",
        "subcategory": "mev_frontrun",
        "confidence": 0.85
    },
    {
        "description": "Provide liquidity by placing limit orders on both sides, profit from bid-ask spread",
        "category": "market_neutral",
        "subcategory": "market_making",
        "confidence": 0.93
    },
]


# =============================================================================
# LM Configuration
# =============================================================================

def configure_ollama(model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434") -> bool:
    """Configure DSPy to use local Ollama model."""
    if not DSPY_AVAILABLE:
        log.error("DSPy not available")
        return False
    
    try:
        lm = dspy.LM(
            model=f"ollama_chat/{model}",
            api_base=base_url,
            temperature=0.7,
        )
        dspy.configure(lm=lm)
        log.info(f"Configured DSPy with Ollama: {model}")
        return True
    except Exception as e:
        log.error(f"Failed to configure Ollama: {e}")
        return False


def configure_groq(model: str = "llama-3.3-70b-versatile") -> bool:
    """Configure DSPy to use Groq (fast inference)."""
    if not DSPY_AVAILABLE:
        return False
    
    import os
    from core import secrets
    
    api_key = os.environ.get("GROQ_API_KEY") or secrets.get_groq_key()
    if not api_key:
        log.error("GROQ_API_KEY not found")
        return False
    
    try:
        lm = dspy.LM(
            model=f"groq/{model}",
            api_key=api_key,
            temperature=0.7,
        )
        dspy.configure(lm=lm)
        log.info(f"Configured DSPy with Groq: {model}")
        return True
    except Exception as e:
        log.error(f"Failed to configure Groq: {e}")
        return False


# =============================================================================
# High-Level API
# =============================================================================

_classifier: Optional["StrategyClassifier"] = None
_risk_analyzer: Optional["RiskAnalyzer"] = None
_patch_proposer: Optional["PatchProposer"] = None


def classify_strategy(description: str) -> Dict[str, Any]:
    """
    Classify a trading strategy description.
    
    Returns:
        {"category": str, "subcategory": str, "confidence": float}
    """
    if not DSPY_AVAILABLE:
        return {"category": "unknown", "subcategory": "unknown", "confidence": 0.0, "error": "DSPy not installed"}
    
    global _classifier
    if _classifier is None:
        _classifier = StrategyClassifier()
    
    try:
        return _classifier.forward(description)
    except Exception as e:
        log.error(f"Classification failed: {e}")
        return {"category": "unknown", "subcategory": "unknown", "confidence": 0.0, "error": str(e)}


def analyze_risk(strategy_name: str, description: str) -> Dict[str, Any]:
    """
    Analyze risks of a trading strategy.
    
    Returns:
        {"failure_modes": list, "recommended_controls": list, "risk_score": int}
    """
    if not DSPY_AVAILABLE:
        return {"failure_modes": [], "recommended_controls": [], "risk_score": 5, "error": "DSPy not installed"}
    
    global _risk_analyzer
    if _risk_analyzer is None:
        _risk_analyzer = RiskAnalyzer()
    
    try:
        return _risk_analyzer.forward(strategy_name, description)
    except Exception as e:
        log.error(f"Risk analysis failed: {e}")
        return {"failure_modes": [], "recommended_controls": [], "risk_score": 5, "error": str(e)}


def propose_patch(error_description: str, code: str) -> Dict[str, Any]:
    """
    Propose a patch for an error or improvement.
    
    Returns:
        {"explanation": str, "diff": str, "risk_level": int}
    """
    if not DSPY_AVAILABLE:
        return {"explanation": "", "diff": "", "risk_level": 5, "error": "DSPy not installed"}
    
    global _patch_proposer
    if _patch_proposer is None:
        _patch_proposer = PatchProposer()
    
    try:
        return _patch_proposer.forward(error_description, code)
    except Exception as e:
        log.error(f"Patch proposal failed: {e}")
        return {"explanation": "", "diff": "", "risk_level": 5, "error": str(e)}


def save_training_data(examples: Optional[List[Dict]] = None) -> Path:
    """Save training examples to JSON file."""
    data = examples or TRAINING_EXAMPLES
    TRAINING_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with open(TRAINING_DATA_PATH, "w") as f:
        json.dump({"examples": data}, f, indent=2)
    
    log.info(f"Saved {len(data)} training examples to {TRAINING_DATA_PATH}")
    return TRAINING_DATA_PATH


def load_training_data() -> List[Dict]:
    """Load training examples from JSON file."""
    if not TRAINING_DATA_PATH.exists():
        return TRAINING_EXAMPLES
    
    try:
        with open(TRAINING_DATA_PATH) as f:
            data = json.load(f)
            return data.get("examples", TRAINING_EXAMPLES)
    except Exception as e:
        log.warning(f"Failed to load training data: {e}")
        return TRAINING_EXAMPLES


# =============================================================================
# Optimization (BootstrapFewShot)
# =============================================================================

def optimize_classifier(
    training_examples: Optional[List[Dict]] = None,
    metric_threshold: float = 0.8
) -> Optional["StrategyClassifier"]:
    """
    Optimize the strategy classifier using DSPy BootstrapFewShot.
    
    This finds optimal few-shot examples to improve classification accuracy.
    """
    if not DSPY_AVAILABLE:
        log.error("DSPy not available for optimization")
        return None
    
    from dspy.teleprompt import BootstrapFewShot
    
    examples = training_examples or load_training_data()
    
    # Create DSPy examples
    trainset = []
    for ex in examples:
        trainset.append(dspy.Example(
            description=ex["description"],
            category=ex["category"],
            subcategory=ex["subcategory"],
            confidence=str(ex["confidence"])
        ).with_inputs("description"))
    
    def metric(pred, gold):
        """Score prediction against gold label."""
        score = 0.0
        
        # Category match (50%)
        if getattr(pred, "category", "") == gold.category:
            score += 0.5
        
        # Subcategory match (30%)
        if getattr(pred, "subcategory", "") == gold.subcategory:
            score += 0.3
        
        # Confidence calibration (20%)
        try:
            pred_conf = float(getattr(pred, "confidence", 0.5))
            gold_conf = float(gold.confidence)
            conf_error = abs(pred_conf - gold_conf)
            score += 0.2 * (1 - min(conf_error, 0.5) / 0.5)
        except (ValueError, TypeError):
            pass
        
        return score >= metric_threshold
    
    # Optimize
    optimizer = BootstrapFewShot(
        metric=metric,
        max_bootstrapped_demos=4,
        max_labeled_demos=8,
    )
    
    classifier = StrategyClassifier()
    optimized = optimizer.compile(classifier, trainset=trainset)
    
    log.info("Classifier optimization complete")
    return optimized


# =============================================================================
# Demo / Test
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("=== DSPy Strategy Classification Demo ===\n")
    
    if not DSPY_AVAILABLE:
        print("❌ DSPy not installed. Run: pip install dspy-ai")
        sys.exit(1)
    
    # Try to configure Ollama
    print("Configuring Ollama...")
    if not configure_ollama():
        print("⚠ Ollama not available, trying Groq...")
        if not configure_groq():
            print("❌ No LM provider available")
            sys.exit(1)
    
    print("\n--- Testing Strategy Classification ---")
    test_descriptions = [
        "Buy when RSI drops below 25 and sell when it rises above 75",
        "Monitor price differences between Binance and Coinbase, arbitrage when spread > 0.5%",
        "Train a neural network on historical price patterns to predict next hour's direction",
    ]
    
    for desc in test_descriptions:
        print(f"\nInput: {desc[:60]}...")
        result = classify_strategy(desc)
        print(f"  Category: {result['category']}")
        print(f"  Subcategory: {result['subcategory']}")
        print(f"  Confidence: {result['confidence']:.2f}")
    
    print("\n--- Testing Risk Analysis ---")
    result = analyze_risk(
        "GridTrader",
        "Places buy orders below and sell orders above current price in a grid pattern"
    )
    print(f"Failure modes: {result['failure_modes']}")
    print(f"Controls: {result['recommended_controls']}")
    print(f"Risk score: {result['risk_score']}/10")
    
    print("\n=== Demo Complete ===")
