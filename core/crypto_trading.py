"""
Crypto Trading Research and Automation for Jarvis.
Researches trading strategies, analyzes markets, and builds trading tools.
"""

import json
import math
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import config, learning_validator, notes_manager, providers, research_engine

ROOT = Path(__file__).resolve().parents[1]
CRYPTO_PATH = ROOT / "data" / "crypto_trading"
CRYPTO_LOG_PATH = ROOT / "data" / "crypto_trading.log"
HFT_BACKLOG_PATH = CRYPTO_PATH / "hft_backlog.json"
HFT_HISTORY_PATH = CRYPTO_PATH / "hft_history.jsonl"
LOW_FEE_CHAINS = ["Solana", "Base", "Arbitrum", "Optimism", "Polygon", "BSC"]
DEFAULT_PAIRS = ["SOL/USDC", "PYTH/SOL", "JUP/USDC", "WIF/SOL", "BONK/SOL", "AERO/USDC"]


class CryptoTrading:
    """Manages crypto trading research and automation."""
    
    def __init__(self):
        self.trading_db = CRYPTO_PATH / "trading_data.json"
        self.strategies_db = CRYPTO_PATH / "strategies.json"
        self._ensure_directories()
        self._load_trading_data()
        self._load_hft_backlog()
    
    def _ensure_directories(self):
        """Ensure data directories exist."""
        CRYPTO_PATH.mkdir(parents=True, exist_ok=True)
        
    def _load_trading_data(self):
        """Load trading data and strategies."""
        if self.trading_db.exists():
            with open(self.trading_db, "r") as f:
                self.trading_data = json.load(f)
        else:
            self.trading_data = {
                "market_data": {},
                "research_findings": [],
                "strategies_tested": [],
                "performance_metrics": {},
                "exchanges": []
            }
    
    def _load_hft_backlog(self):
        if HFT_BACKLOG_PATH.exists():
            with open(HFT_BACKLOG_PATH, "r", encoding="utf-8") as handle:
                self.hft_backlog = json.load(handle)
        else:
            self.hft_backlog = []
        
        if self.strategies_db.exists():
            with open(self.strategies_db, "r") as f:
                self.strategies = json.load(f)
        else:
            self.strategies = {
                "discovered": [],
                "evaluated": [],
                "implemented": [],
                "profitable": []
            }
    
    def _save_trading_data(self):
        """Save trading data."""
        with open(self.trading_db, "w") as f:
            json.dump(self.trading_data, f, indent=2)
        with open(self.strategies_db, "w") as f:
            json.dump(self.strategies, f, indent=2)
    
    def _log_trading(self, action: str, details: Dict[str, Any]):
        """Log trading activity."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        
        with open(CRYPTO_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def research_trading_strategies(self) -> List[Dict[str, Any]]:
        """Research crypto trading strategies."""
        strategies = []
        
        research_queries = [
            "profitable crypto trading strategies 2024",
            "automated trading bot algorithms",
            "technical analysis indicators crypto",
            "arbitrage trading opportunities",
            "DeFi yield farming strategies",
            "AI machine learning trading",
            "grid trading bot strategies",
            "scalping techniques crypto",
            "market making algorithms",
            "momentum trading strategies"
        ]
        
        engine = research_engine.get_research_engine()
        
        for query in research_queries:
            try:
                results = engine.search_web(query, max_results=5)
                
                for result in results:
                    strategy = {
                        "query": query,
                        "title": result["title"],
                        "url": result["url"],
                        "snippet": result["snippet"],
                        "researched_at": datetime.now().isoformat()
                    }
                    strategies.append(strategy)
                    self.strategies["discovered"].append(strategy)
                    
            except Exception as e:
                self._log_trading("research_error", {"query": query, "error": str(e)})
        
        self._save_trading_data()
        self._log_trading("strategies_researched", {"count": len(strategies)})
        
        return strategies
    
    def evaluate_trading_strategy(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a trading strategy for viability."""
        evaluation_prompt = f"""Evaluate this crypto trading strategy:

Title: {strategy['title']}
Description: {strategy['snippet']}
Source: {strategy['url']}

Consider:
1. Profitability potential (1-10)
2. Risk level (1-10, lower is better)
3. Technical complexity (1-10, lower is better)
4. Automation feasibility (1-10)
5. Market conditions needed

Provide:
- Overall rating (1-10)
- Risk assessment
- Implementation difficulty
- Recommended for automation (yes/no)"""
        
        try:
            response = providers.generate_text(evaluation_prompt, max_output_tokens=400)
            
            if response:
                # Extract rating
                rating = 5
                for word in response.split():
                    if word.isdigit() and 1 <= int(word) <= 10:
                        rating = int(word)
                        break
                
                # Check if recommended for automation
                automation_recommended = "yes" in response.lower()
                
                evaluated_strategy = {
                    **strategy,
                    "evaluation": response,
                    "rating": rating,
                    "automation_recommended": automation_recommended,
                    "evaluated_at": datetime.now().isoformat()
                }
                
                self.strategies["evaluated"].append(evaluated_strategy)
                self._save_trading_data()
                
                return evaluated_strategy
                
        except Exception as e:
            self._log_trading("evaluation_error", {
                "strategy": strategy["title"],
                "error": str(e)
            })
        
        return strategy
    
    def create_trading_bot_code(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Create trading bot code for a strategy."""
        code_prompt = f"""Create Python code for an automated trading bot based on this strategy:

Strategy: {strategy['title']}
Description: {strategy['snippet']}
Evaluation: {strategy.get('evaluation', '')}

Requirements:
1. Use common libraries (ccxt, pandas, numpy)
2. Include proper error handling
3. Add logging for trades
4. Implement risk management
5. Include position sizing
6. Add stop-loss and take-profit

Focus on practical, implementable code."""
        
        try:
            response = providers.generate_text(code_prompt, max_output_tokens=800)
            
            if response:
                bot_code = {
                    "strategy_title": strategy["title"],
                    "code": response,
                    "created_at": datetime.now().isoformat(),
                    "language": "python"
                }
                
                # Save code to file
                code_file = CRYPTO_PATH / f"bot_{hash(strategy['title'])}.py"
                with open(code_file, "w") as f:
                    f.write(f"""
# Trading Bot for: {strategy['title']}
# Generated: {datetime.now().isoformat()}
# Source: {strategy.get('url', 'Unknown')}

{response}
""")
                
                bot_code["file_path"] = str(code_file)
                self.strategies["implemented"].append(bot_code)
                self._save_trading_data()
                
                self._log_trading("bot_created", {
                    "strategy": strategy["title"],
                    "file": str(code_file)
                })
                
                return bot_code
                
        except Exception as e:
            self._log_trading("bot_creation_error", {
                "strategy": strategy["title"],
                "error": str(e)
            })
        
        return {"error": "Failed to create bot code"}
    
    def research_crypto_exchanges(self) -> List[Dict[str, Any]]:
        """Research crypto exchanges and their APIs."""
        exchanges = []
        
        exchange_info = [
            {"name": "Binance", "api": "REST/WebSocket", "fees": "0.1%", "features": "spot, futures, margin"},
            {"name": "Coinbase", "api": "REST", "fees": "0.5%", "features": "spot, pro"},
            {"name": "Kraken", "api": "REST/WebSocket", "fees": "0.26%", "features": "spot, futures"},
            {"name": "Bybit", "api": "REST/WebSocket", "fees": "0.1%", "features": "spot, derivatives"},
            {"name": "KuCoin", "api": "REST/WebSocket", "fees": "0.1%", "features": "spot, futures, margin"}
        ]
        
        for exchange in exchange_info:
            # Research API documentation and capabilities
            try:
                engine = research_engine.get_research_engine()
                results = engine.search_web(
                    f"{exchange['name']} API documentation trading bot",
                    max_results=3
                )
                
                exchange["research_results"] = results
                exchange["researched_at"] = datetime.now().isoformat()
                exchanges.append(exchange)
                
            except Exception as e:
                self._log_trading("exchange_research_error", {
                    "exchange": exchange["name"],
                    "error": str(e)
                })
        
        self.trading_data["exchanges"] = exchanges
        self._save_trading_data()
        
        return exchanges
    
    def analyze_market_trends(self) -> Dict[str, Any]:
        """Analyze current market trends."""
        trend_analysis = {
            "timestamp": datetime.now().isoformat(),
            "trends": [],
            "sentiment": "neutral"
        }
        
        # Research current market trends
        trend_queries = [
            "bitcoin price analysis today",
            "ethereum market trends",
            "crypto market sentiment",
            "altcoin performance",
            "DeFi market trends"
        ]
        
        engine = research_engine.get_research_engine()
        
        for query in trend_queries:
            try:
                results = engine.search_web(query, max_results=3)
                
                for result in results:
                    trend = {
                        "query": query,
                        "title": result["title"],
                        "snippet": result["snippet"],
                        "url": result["url"]
                    }
                    trend_analysis["trends"].append(trend)
                    
            except Exception as e:
                self._log_trading("trend_analysis_error", {
                    "query": query,
                    "error": str(e)
                })
        
        # Analyze sentiment
        if trend_analysis["trends"]:
            sentiment_prompt = f"""Analyze market sentiment from these crypto news headlines:

{json.dumps([t['title'] + ': ' + t['snippet'] for t in trend_analysis['trends'][:5]], indent=2)}

Is the overall sentiment bullish, bearish, or neutral? Provide brief reasoning."""
            
            try:
                response = providers.generate_text(sentiment_prompt, max_output_tokens=200)
                if response:
                    if "bullish" in response.lower():
                        trend_analysis["sentiment"] = "bullish"
                    elif "bearish" in response.lower():
                        trend_analysis["sentiment"] = "bearish"
                    else:
                        trend_analysis["sentiment"] = "neutral"
                    
                    trend_analysis["sentiment_analysis"] = response
            except Exception as e:
                pass
        
        self.trading_data["market_data"]["latest_trends"] = trend_analysis
        self._save_trading_data()
        
        return trend_analysis
    
    def create_knowledge_base(self) -> Dict[str, Any]:
        """Create organized knowledge base for crypto trading."""
        knowledge_base = {
            "created_at": datetime.now().isoformat(),
            "categories": {
                "strategies": [],
                "technical_analysis": [],
                "risk_management": [],
                "exchanges": [],
                "tools": []
            },
            "prompts": {
                "strategy_research": "Research profitable crypto trading strategies focusing on automation potential",
                "market_analysis": "Analyze current crypto market trends and identify trading opportunities",
                "risk_assessment": "Evaluate risk management techniques for crypto trading",
                "bot_development": "Create automated trading bot code with proper risk controls"
            },
            "best_practices": []
        }
        
        # Organize existing research
        for strategy in self.strategies.get("evaluated", []):
            if strategy.get("rating", 0) >= 7:
                knowledge_base["categories"]["strategies"].append({
                    "title": strategy["title"],
                    "rating": strategy["rating"],
                    "automation": strategy.get("automation_recommended", False)
                })
        
        # Add best practices
        best_practices = [
            "Always use stop-loss orders to limit downside risk",
            "Never risk more than 2% of portfolio on single trade",
            "Diversify across multiple cryptocurrencies",
            "Use proper position sizing based on volatility",
            "Keep detailed trading records for analysis",
            "Test strategies with paper trading before real money",
            "Monitor market conditions 24/7 for automated bots",
            "Implement proper error handling in trading code"
        ]
        
        knowledge_base["best_practices"] = best_practices
        
        # Save knowledge base
        kb_file = CRYPTO_PATH / "knowledge_base.json"
        with open(kb_file, "w") as f:
            json.dump(knowledge_base, f, indent=2)
        
        self._log_trading("knowledge_base_created", {"categories": len(knowledge_base["categories"])})
        
        return knowledge_base

    # === HFT sandbox helpers ===

    def _save_hft_backlog(self) -> None:
        HFT_BACKLOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(HFT_BACKLOG_PATH, "w", encoding="utf-8") as handle:
            json.dump(self.hft_backlog, handle, indent=2)

    def _record_hft_history(self, result: Dict[str, Any]) -> None:
        HFT_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(HFT_HISTORY_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(result) + "\n")

    def enqueue_hft_strategy(self, strategy: Dict[str, Any]) -> None:
        uid = f"{strategy.get('chain', 'chain')}-{strategy.get('pair', 'pair')}-{int(time.time())}"
        strategy.setdefault("id", uid)
        strategy.setdefault("created_at", datetime.now().isoformat())
        self.hft_backlog.append(strategy)
        self._save_hft_backlog()

    def seed_low_cap_backlog(self, max_new: int = 5) -> List[Dict[str, Any]]:
        added: List[Dict[str, Any]] = []
        existing_pairs = {item.get("pair") for item in self.hft_backlog}
        for chain in LOW_FEE_CHAINS:
            if len(added) >= max_new:
                break
            pair = random.choice(DEFAULT_PAIRS)
            if pair in existing_pairs:
                continue
            strategy = {
                "chain": chain,
                "pair": pair,
                "entry_capital": random.choice([100, 250, 500]),
                "latency_target_ms": random.choice([50, 80, 120]),
                "liquidity_source": random.choice(["Jupiter", "Orca", "Phoenix", "Raydium"]),
                "objective": random.choice(["scalp", "arbitrage", "market-making"]),
            }
            self.enqueue_hft_strategy(strategy)
            added.append(strategy)
        return added

    def _pop_next_hft_strategy(self) -> Optional[Dict[str, Any]]:
        if not self.hft_backlog:
            return None
        strategy = self.hft_backlog.pop(0)
        self._save_hft_backlog()
        return strategy

    def _simulate_price_series(
        self, ticks: int = 400, base_price: float = 1.0, volatility: float = 0.015
    ) -> List[float]:
        prices = [base_price]
        for i in range(1, ticks):
            noise = random.gauss(0, volatility)
            drift = math.sin(i / 25.0) * volatility * 0.5
            prices.append(max(0.0001, prices[-1] * (1 + noise + drift)))
        return prices

    def run_hft_simulation(
        self,
        strategy: Dict[str, Any],
        capital: float = 200.0,
        ticks: int = 400,
    ) -> Dict[str, Any]:
        random.seed(hash(strategy.get("pair", "") + strategy.get("chain", "")))
        prices = self._simulate_price_series(ticks=ticks, base_price=random.uniform(0.5, 2.0))
        pnl = 0.0
        trades = 0
        wins = 0
        latency_ms = strategy.get("latency_target_ms", 80)
        for i in range(1, len(prices)):
            if i % 10 != 0:
                continue
            delta = prices[i] - prices[i - 1]
            edge = (0.003 - latency_ms / 10000)
            trades += 1
            if delta > edge:
                pnl += delta * capital * 0.1
                wins += 1
            else:
                pnl -= abs(delta) * capital * 0.05
        win_rate = wins / trades if trades else 0
        roi = pnl / capital if capital else 0
        result = {
            "strategy": strategy,
            "pnl": round(pnl, 2),
            "roi": round(roi, 4),
            "trades": trades,
            "win_rate": round(win_rate, 3),
            "simulated_at": datetime.now().isoformat(),
        }
        self._record_hft_history(result)
        return result

    def run_hft_sandbox_cycle(self) -> Optional[Dict[str, Any]]:
        if not self.hft_backlog:
            self.seed_low_cap_backlog(max_new=3)
        strategy = self._pop_next_hft_strategy()
        if not strategy:
            return None
        result = self.run_hft_simulation(strategy, capital=strategy.get("entry_capital", 200))
        summary_note = (
            f"# HFT Sandbox Simulation\n\n"
            f"- Chain: {strategy['chain']}\n"
            f"- Pair: {strategy['pair']}\n"
            f"- Objective: {strategy['objective']}\n"
            f"- Liquidity Source: {strategy['liquidity_source']}\n"
            f"- Trades: {result['trades']} | Win rate: {result['win_rate']}\n"
            f"- PnL: {result['pnl']} ({result['roi']*100:.2f}% of capital)\n"
        )
        notes_manager.save_note(
            topic="hft_sandbox",
            content=summary_note,
            fmt="md",
            tags=["crypto", "hft", "simulation"],
            source="crypto_trading.run_hft_sandbox_cycle",
            metadata={"strategy_id": strategy.get("id")},
        )
        self._log_trading(
            "hft_simulation",
            {"strategy": strategy, "pnl": result["pnl"], "roi": result["roi"], "trades": result["trades"]},
        )
        return result
    
    def run_trading_research_cycle(self) -> Dict[str, Any]:
        """Run complete trading research cycle."""
        cycle_start = datetime.now()
        
        self._log_trading("cycle_started", {})
        
        # Step 1: Research trading strategies
        strategies = self.research_trading_strategies()
        
        # Step 2: Evaluate top strategies
        evaluated = []
        for strategy in strategies[:10]:  # Limit to 10 per cycle
            evaluated_strategy = self.evaluate_trading_strategy(strategy)
            evaluated.append(evaluated_strategy)
        
        # Step 3: Create bot code for best strategies
        bots_created = 0
        for strategy in evaluated:
            if strategy.get("rating", 0) >= 7 and strategy.get("automation_recommended", False):
                bot = self.create_trading_bot_code(strategy)
                if "error" not in bot:
                    bots_created += 1
        
        # Step 4: Research exchanges
        exchanges = self.research_crypto_exchanges()
        
        # Step 5: Analyze market trends
        market_analysis = self.analyze_market_trends()
        
        # Step 6: Update knowledge base
        knowledge_base = self.create_knowledge_base()
        
        cycle_result = {
            "cycle_start": cycle_start.isoformat(),
            "cycle_end": datetime.now().isoformat(),
            "strategies_researched": len(strategies),
            "strategies_evaluated": len(evaluated),
            "bots_created": bots_created,
            "exchanges_researched": len(exchanges),
            "market_trends_analyzed": len(market_analysis.get("trends", [])),
            "knowledge_base_updated": True
        }
        
        self._log_trading("cycle_completed", cycle_result)
        
        return cycle_result
    
    def get_status(self) -> Dict[str, Any]:
        """Get trading research status."""
        return {
            "total_strategies": len(self.strategies.get("discovered", [])),
            "evaluated_strategies": len(self.strategies.get("evaluated", [])),
            "implemented_bots": len(self.strategies.get("implemented", [])),
            "exchanges_researched": len(self.trading_data.get("exchanges", [])),
            "latest_market_sentiment": self.trading_data.get("market_data", {}).get("latest_trends", {}).get("sentiment", "unknown")
        }


# Global crypto trading instance
_crypto_trading: Optional[CryptoTrading] = None


def get_crypto_trading() -> CryptoTrading:
    """Get the global crypto trading instance."""
    global _crypto_trading
    if not _crypto_trading:
        _crypto_trading = CryptoTrading()
    return _crypto_trading
