"""
Life OS Router - Hybrid AI Intelligence Engine
===============================================

Master routing layer for Life OS and Trading Bot that intelligently
switches between cloud (MiniMax M2.1) and local (Ollama) inference.

Features:
- Primary: MiniMax M2.1 via OpenRouter (cloud)
- Fallback: Llama 3.2 via Ollama (local)
- Beast Mode: Full model running locally (for high-end hardware)
- Cost tracking with daily spend limits
- Automatic failover on errors or cost limits

Usage:
    from core.life_os_router import MiniMaxRouter, MODE
    
    router = MiniMaxRouter()
    response = router.query("Analyze BTC/USDT trading opportunity")
    
    # Check status
    print(router.get_status())

Configuration:
    Set MODE = 'CLOUD' | 'LOCAL' | 'BEAST' at top of file
    Or use environment variable: ROUTER_MODE=CLOUD
"""

import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from core import secrets

# Lazy imports to avoid circular dependencies
if TYPE_CHECKING:
    from core.trading_strategies import BaseStrategy, TradeSignal, StrategyEnsemble
    from core.risk_manager import RiskManager, PositionSizer

# ============================================================================
# MODE SWITCH - Change this for different operation modes
# ============================================================================
# CLOUD  = MiniMax M2.1 via OpenRouter (default, cheapest cloud option)
# LOCAL  = Llama 3.2 via Ollama (free, runs on your machine)
# BEAST  = Full MiniMax model locally (requires high-end GPU)
# ============================================================================
MODE = os.environ.get("ROUTER_MODE", "CLOUD").upper()

# Cost tracking
DAILY_SPEND_LIMIT_USD = float(os.environ.get("DAILY_SPEND_LIMIT_USD", "5.00"))

# OpenRouter configuration
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "minimax/minimax-m2.1")
MINIMAX_CONTEXT_WINDOW = int(os.environ.get("MINIMAX_CONTEXT_WINDOW", "200000"))

# Ollama configuration (local fallback)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

# Beast mode configuration (local full model)
BEAST_MODEL = os.environ.get("BEAST_MODEL", "minimax-m2.1")  # Requires local setup


def _log(message: str) -> None:
    """Log to stderr for visibility."""
    print(f"[LifeOS Router] {message}", file=sys.stderr, flush=True)


@dataclass
class UsageStats:
    """Track daily API usage and costs."""
    date: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    estimated_cost_usd: float = 0.0
    
    # MiniMax M2.1 pricing via OpenRouter
    INPUT_COST_PER_M: float = 0.30   # $0.30 per 1M input tokens
    OUTPUT_COST_PER_M: float = 1.20  # $1.20 per 1M output tokens
    
    def add_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Record token usage and update cost estimate."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.requests += 1
        self.estimated_cost_usd = (
            (self.input_tokens / 1_000_000) * self.INPUT_COST_PER_M +
            (self.output_tokens / 1_000_000) * self.OUTPUT_COST_PER_M
        )
    
    def reset_if_new_day(self) -> None:
        """Reset stats if it's a new day."""
        today = date.today().isoformat()
        if self.date != today:
            self.date = today
            self.input_tokens = 0
            self.output_tokens = 0
            self.requests = 0
            self.estimated_cost_usd = 0.0


@dataclass
class RouterResponse:
    """Response from the router."""
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    fallback_used: bool = False


class MiniMaxRouter:
    """
    Hybrid router for Life OS intelligence.
    
    Automatically routes between cloud (MiniMax M2.1) and local (Ollama)
    based on availability, cost limits, and configured mode.
    """
    
    def __init__(self, mode: Optional[str] = None):
        self.mode = (mode or MODE).upper()
        self.stats = UsageStats()
        self.stats.reset_if_new_day()
        self._ollama_available: Optional[bool] = None
        self._last_ollama_check: float = 0.0
        
        _log(f"Initialized in {self.mode} mode")
        if self.mode == "CLOUD" and not OPENROUTER_API_KEY:
            _log("⚠ WARNING: OPENROUTER_API_KEY not set. Cloud mode will fail.")
    
    def _check_ollama_available(self) -> bool:
        """Check if Ollama is running locally."""
        # Cache check for 30 seconds
        now = time.time()
        if self._ollama_available is not None and (now - self._last_ollama_check) < 30:
            return self._ollama_available
        
        try:
            req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                self._ollama_available = resp.status == 200
        except Exception:
            self._ollama_available = False
        
        self._last_ollama_check = now
        return self._ollama_available
    
    def _should_use_fallback(self) -> bool:
        """Determine if we should fall back to local inference."""
        self.stats.reset_if_new_day()
        
        # Always use local in LOCAL mode
        if self.mode == "LOCAL":
            return True
        
        # Check daily spend limit
        if self.stats.estimated_cost_usd >= DAILY_SPEND_LIMIT_USD:
            _log(f"⚠ Daily spend limit reached (${self.stats.estimated_cost_usd:.2f}/${DAILY_SPEND_LIMIT_USD:.2f})")
            return True
        
        # Check if API key is configured
        if self.mode == "CLOUD" and not OPENROUTER_API_KEY:
            return True
        
        return False
    
    def _call_openrouter(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> RouterResponse:
        """Call MiniMax M2.1 via OpenRouter API."""
        start_time = time.time()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": MINIMAX_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://lifeos.aurora-ventures.ai",
            "X-Title": "Life OS Trading Bot",
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            data=data,
            headers=headers,
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"OpenRouter API error {e.code}: {error_body[:200]}")
        
        # Extract response
        choices = body.get("choices", [])
        if not choices:
            raise RuntimeError("Empty response from OpenRouter")
        
        text = choices[0].get("message", {}).get("content", "")
        if not text:
            raise RuntimeError("No content in OpenRouter response")
        
        # Extract usage stats
        usage = body.get("usage", {})
        input_tokens = usage.get("prompt_tokens", len(prompt) // 4)
        output_tokens = usage.get("completion_tokens", len(text) // 4)
        
        # Update stats
        self.stats.add_usage(input_tokens, output_tokens)
        
        latency_ms = int((time.time() - start_time) * 1000)
        cost_usd = (
            (input_tokens / 1_000_000) * UsageStats.INPUT_COST_PER_M +
            (output_tokens / 1_000_000) * UsageStats.OUTPUT_COST_PER_M
        )
        
        return RouterResponse(
            text=text,
            provider="openrouter",
            model=MINIMAX_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            fallback_used=False,
        )

    def _call_minimax_direct(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> RouterResponse:
        """Call MiniMax API directly."""
        start_time = time.time()
        api_key = secrets.get_minimax_key()
        
        if not api_key:
            raise RuntimeError("MiniMax Direct selected but no key found.")

        # MiniMax API endpoint (Abab6.5 assumed for M2.1 equivalent)
        url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
        model = "abab6.5-chat" 
        
        messages = []
        if system_prompt:
            messages.append({"sender_type": "BOT", "sender_name": "MM Intelligent Assistant", "text": system_prompt})
        messages.append({"sender_type": "USER", "sender_name": "User", "text": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "tokens_to_generate": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"MiniMax API error {e.code}: {error_body[:200]}")
            
        # Parse MiniMax response
        # Structure varies, but usually: check 'choices' or 'reply'
        choices = body.get("choices", [])
        if not choices:
            # Check for error msg
            if "base_resp" in body and body["base_resp"].get("status_msg"):
                 raise RuntimeError(f"MiniMax Error: {body['base_resp']['status_msg']}")
            raise RuntimeError("Empty response from MiniMax")
            
        text = choices[0].get("message", {}).get("text", "")
        if not text:
             # Try alternate structure just in case
             text = choices[0].get("text", "")
        
        usage = body.get("usage", {})
        input_tokens = usage.get("total_tokens", len(prompt)//4) # This might be total?
        # MiniMax usage structure is sometimes different, fallback to safe estimate
        
        # Approximate if needed
        output_tokens = len(text) // 4
        
        self.stats.add_usage(input_tokens, output_tokens)
        cost_usd = (input_tokens / 1_000_000 * 0.30) + (output_tokens / 1_000_000 * 1.20) # Approx M2.1 pricing
        latency_ms = int((time.time() - start_time) * 1000)

        return RouterResponse(
            text=text,
            provider="minimax_direct",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            fallback_used=False,
        )
    
    def _call_ollama(
        self,
        prompt: str,
        max_tokens: int = 2048,
        model: Optional[str] = None,
    ) -> RouterResponse:
        """Call local Ollama for inference."""
        start_time = time.time()
        
        model = model or OLLAMA_MODEL
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise RuntimeError(f"Ollama error: {e}")
        
        text = body.get("response", "")
        if not text:
            raise RuntimeError("Empty response from Ollama")
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return RouterResponse(
            text=text,
            provider="ollama",
            model=model,
            input_tokens=len(prompt) // 4,
            output_tokens=len(text) // 4,
            latency_ms=latency_ms,
            cost_usd=0.0,  # Local = free
            fallback_used=True,
        )
    
    def query(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        force_local: bool = False,
    ) -> RouterResponse:
        """
        Query the AI with automatic routing.
        
        Args:
            prompt: The user prompt
            max_tokens: Maximum output tokens
            temperature: Creativity (0.0-1.0)
            system_prompt: Optional system instruction
            force_local: Force local inference regardless of mode
        
        Returns:
            RouterResponse with the result
        """
        # BEAST mode - use local full model
        if self.mode == "BEAST":
            if self._check_ollama_available():
                return self._call_ollama(prompt, max_tokens, model=BEAST_MODEL)
            raise RuntimeError("BEAST mode requires Ollama with full model installed")
        
        # Check if we should use fallback
        use_fallback = force_local or self._should_use_fallback()
        
        if not use_fallback:
            # Try cloud first
            try:
                # Check for Direct MiniMax Key first
                if secrets.get_minimax_key():
                    return self._call_minimax_direct(prompt, max_tokens, temperature, system_prompt)
                
                # Fallback to OpenRouter
                return self._call_openrouter(prompt, max_tokens, temperature, system_prompt)
            except Exception as e:
                _log(f"⚠ Cloud failed: {e}. Falling back to local...")
                use_fallback = True
        
        # Use local fallback
        if self._check_ollama_available():
            return self._call_ollama(prompt, max_tokens)
        
        raise RuntimeError("No available inference providers. Check OPENROUTER_API_KEY, MINIMAX_API_KEY, or Ollama.")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current router status and stats."""
        self.stats.reset_if_new_day()
        return {
            "mode": self.mode,
            "cloud_configured": bool(OPENROUTER_API_KEY) or bool(secrets.get_minimax_key()),
            "direct_minimax": bool(secrets.get_minimax_key()),
            "ollama_available": self._check_ollama_available(),
            "daily_stats": {
                "date": self.stats.date,
                "requests": self.stats.requests,
                "input_tokens": self.stats.input_tokens,
                "output_tokens": self.stats.output_tokens,
                "estimated_cost_usd": round(self.stats.estimated_cost_usd, 4),
                "spend_limit_usd": DAILY_SPEND_LIMIT_USD,
                "limit_remaining_usd": round(DAILY_SPEND_LIMIT_USD - self.stats.estimated_cost_usd, 4),
            },
            "models": {
                "cloud": MINIMAX_MODEL,
                "local": OLLAMA_MODEL,
                "beast": BEAST_MODEL,
            },
        }
    
    # ========================================================================
    # Trading-Specific Methods
    # ========================================================================
    
    def analyze_trade(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a trading opportunity.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            market_data: Current market data dict
            strategy: Optional strategy name to apply
        
        Returns:
            Analysis dict with recommendation
        """
        system_prompt = """You are an expert crypto trading analyst. Analyze market data
and provide actionable trading recommendations. Be concise and data-driven.
Output JSON with: action (buy/sell/hold), confidence (0-100), reasoning, entry_price, 
stop_loss, take_profit."""
        
        prompt = f"""Analyze this trading opportunity:

Symbol: {symbol}
Strategy: {strategy or 'General Analysis'}
Market Data:
{json.dumps(market_data, indent=2)}

Provide your analysis as JSON."""
        
        response = self.query(prompt, max_tokens=1024, temperature=0.3, system_prompt=system_prompt)
        
        # Try to parse JSON from response
        try:
            # Find JSON in response
            text = response.text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                analysis = json.loads(text[start:end])
                analysis["_meta"] = {
                    "provider": response.provider,
                    "model": response.model,
                    "latency_ms": response.latency_ms,
                }
                return analysis
        except json.JSONDecodeError:
            pass
        
        return {
            "action": "hold",
            "confidence": 0,
            "reasoning": response.text,
            "error": "Could not parse structured response",
            "_meta": {
                "provider": response.provider,
                "model": response.model,
            },
        }
    
    def generate_strategy(self, description: str) -> Dict[str, Any]:
        """
        Generate a trading strategy from a description.
        
        Args:
            description: Natural language strategy description
        
        Returns:
            Structured strategy dict
        """
        system_prompt = """You are an expert quantitative trading strategist. 
Generate detailed, executable trading strategies. Output JSON with:
name, description, entry_conditions[], exit_conditions[], risk_management{},
timeframe, suitable_markets[], backtesting_params{}."""
        
        response = self.query(
            f"Create a trading strategy for: {description}",
            max_tokens=2048,
            temperature=0.5,
            system_prompt=system_prompt,
        )
        
        try:
            text = response.text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
        
        return {"raw_response": response.text, "error": "Could not parse strategy"}
    
    # ========================================================================
    # Strategy Module Integration
    # ========================================================================
    
    def execute_strategy(
        self,
        prices: List[float],
        symbol: str,
        strategy_name: str = "ensemble",
        capital: float = 10000.0,
    ) -> Dict[str, Any]:
        """
        Execute a trading strategy with risk management.
        
        Args:
            prices: Historical price data
            symbol: Trading pair
            strategy_name: Strategy to use (trend, mean_reversion, dca, ensemble)
            capital: Available trading capital
        
        Returns:
            Dict with signal, position sizing, and risk params
        """
        try:
            from core.trading_strategies import (
                TrendFollower, MeanReversion, DCABot, 
                StrategyEnsemble, create_default_ensemble
            )
            from core.risk_manager import get_risk_manager
        except ImportError as e:
            return {"error": f"Strategy modules not available: {e}"}
        
        # Select strategy
        if strategy_name == "trend":
            strategy = TrendFollower()
        elif strategy_name == "mean_reversion":
            strategy = MeanReversion()
        elif strategy_name == "dca":
            strategy = DCABot()
        else:
            strategy = create_default_ensemble()
        
        # Get signal
        signal = strategy.analyze(prices, symbol)
        
        # Check risk limits
        rm = get_risk_manager()
        can_trade = rm.can_trade()
        
        result = {
            "signal": signal.to_dict(),
            "risk_check": can_trade,
            "can_execute": can_trade["allowed"] and signal.action != "HOLD",
        }
        
        # Calculate position if actionable
        if result["can_execute"] and signal.action == "BUY":
            current_price = prices[-1]
            # Calculate stop-loss based on strategy
            stop_take = rm.sizer.calculate_stop_take(current_price, "LONG")
            position = rm.sizer.calculate_position(
                capital=capital,
                entry_price=current_price,
                stop_loss_price=stop_take["stop_loss"]
            )
            result["position"] = position
            result["stop_take"] = stop_take
        
        return result
    
    def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk management status."""
        try:
            from core.risk_manager import get_risk_manager
            rm = get_risk_manager()
            return {
                "stats": rm.get_stats(),
                "can_trade": rm.can_trade(),
                "open_trades": rm.get_open_trades(),
            }
        except ImportError:
            return {"error": "Risk manager not available"}
    
    def check_stops(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        Check all open positions against current prices.
        
        Args:
            current_prices: Dict of symbol -> current price
        
        Returns:
            Dict with any triggered stops
        """
        try:
            from core.risk_manager import get_risk_manager
            rm = get_risk_manager()
            closed = rm.check_stops(current_prices)
            return {
                "triggered": len(closed),
                "closed_trades": [t.to_dict() for t in closed]
            }
        except ImportError:
            return {"error": "Risk manager not available"}
    
    def scan_arbitrage(
        self,
        symbol: str,
        dex_prices: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Scan for arbitrage opportunities across DEXs.
        
        Args:
            symbol: Trading pair
            dex_prices: Dict of DEX name -> price
        
        Returns:
            Arbitrage opportunity details if found
        """
        try:
            from core.trading_strategies import ArbitrageScanner
            scanner = ArbitrageScanner()
            signal = scanner.scan_multi_dex(symbol, dex_prices)
            if signal:
                return {
                    "opportunity_found": True,
                    "signal": signal.to_dict()
                }
            return {"opportunity_found": False}
        except ImportError:
            return {"error": "Strategy modules not available"}


# ============================================================================
# Module-level convenience functions
# ============================================================================

_router: Optional[MiniMaxRouter] = None


def get_router() -> MiniMaxRouter:
    """Get or create the global router instance."""
    global _router
    if _router is None:
        _router = MiniMaxRouter()
    return _router


def query(prompt: str, **kwargs) -> RouterResponse:
    """Convenience function to query with default router."""
    return get_router().query(prompt, **kwargs)


def analyze_trade(symbol: str, market_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Convenience function for trade analysis."""
    return get_router().analyze_trade(symbol, market_data, **kwargs)


def get_status() -> Dict[str, Any]:
    """Convenience function to get router status."""
    return get_router().get_status()


# ============================================================================
# CLI for testing
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Life OS AI Router")
    parser.add_argument("--mode", choices=["CLOUD", "LOCAL", "BEAST"], help="Override mode")
    parser.add_argument("--status", action="store_true", help="Show router status")
    parser.add_argument("--prompt", type=str, help="Send a test prompt")
    parser.add_argument("--analyze", type=str, help="Analyze a trading pair (e.g., BTC/USDT)")
    
    args = parser.parse_args()
    
    if args.mode:
        router = MiniMaxRouter(mode=args.mode)
    else:
        router = get_router()
    
    if args.status:
        print(json.dumps(router.get_status(), indent=2))
    elif args.prompt:
        response = router.query(args.prompt)
        print(f"\n=== Response from {response.provider}/{response.model} ===")
        print(response.text)
        print(f"\n[Latency: {response.latency_ms}ms, Cost: ${response.cost_usd:.4f}]")
    elif args.analyze:
        # Mock market data for demo
        mock_data = {
            "price": 42500.00,
            "24h_change": 2.5,
            "volume": 1500000000,
            "rsi": 55,
            "macd": {"value": 150, "signal": 120, "histogram": 30},
        }
        result = router.analyze_trade(args.analyze, mock_data)
        print(json.dumps(result, indent=2))
    else:
        print("Life OS Router - Hybrid AI Intelligence Engine")
        print("=" * 50)
        print(json.dumps(router.get_status(), indent=2))
        print("\nUsage examples:")
        print("  python life_os_router.py --status")
        print("  python life_os_router.py --prompt 'Hello, test!'")
        print("  python life_os_router.py --analyze BTC/USDT")
        print("  python life_os_router.py --mode LOCAL --prompt 'Test local'")
