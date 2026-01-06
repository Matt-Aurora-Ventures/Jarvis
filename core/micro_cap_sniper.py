"""
Micro-Cap Sniper Strategy for Small Capital
============================================

PURPOSE: Grow $4 → $1K through aggressive memecoin momentum plays.
TARGET: 25% gains per trade on new Solana tokens.
RISK: HIGH - This strategy is designed for small speculative capital only.

MATH:
- $4 @ 25% compounded ~25 times = $1K
- Win rate needed: ~50% with 2:1 R:R (25% TP, 12% SL)

FLOW:
1. Scan for new tokens with momentum (BirdEye, DexScreener, GeckoTerminal)
2. Filter: liquidity > $50K, volume > $100K, age < 24h
3. Entry: On momentum spike (volume surge + price break)
4. Exit: 25% take profit or 12% stop loss
5. Reinvest all gains into next trade

SAFETY:
- Paper mode by default
- Live mode requires explicit approval
- Never risk more than 100% of allocated capital
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
SNIPER_DIR = ROOT / "data" / "sniper"
STATE_FILE = SNIPER_DIR / "sniper_state.json"
TRADE_LOG = SNIPER_DIR / "trade_log.jsonl"


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class SniperConfig:
    """Configuration for micro-cap sniper strategy."""
    
    # Capital
    starting_capital_usd: float = 4.0
    target_capital_usd: float = 1000.0
    
    # Trade Parameters
    take_profit_pct: float = 0.25      # 25% TP
    stop_loss_pct: float = 0.12        # 12% SL (2:1 R:R)
    max_hold_minutes: int = 90         # Time stop: 90 min
    
    # Token Filters
    min_liquidity_usd: float = 50_000
    max_liquidity_usd: float = 2_000_000  # Avoid too established
    min_volume_24h_usd: float = 100_000
    max_token_age_hours: int = 24
    min_price_change_1h: float = 0.05  # 5% pump in last hour
    
    # Entry Signals
    volume_spike_multiplier: float = 2.0  # Volume 2x average
    momentum_confirmation: bool = True
    
    # Safety
    is_paper: bool = True
    require_approval: bool = True
    max_consecutive_losses: int = 3
    cooldown_after_loss_minutes: int = 30
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "starting_capital_usd": self.starting_capital_usd,
            "target_capital_usd": self.target_capital_usd,
            "take_profit_pct": self.take_profit_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "max_hold_minutes": self.max_hold_minutes,
            "min_liquidity_usd": self.min_liquidity_usd,
            "min_volume_24h_usd": self.min_volume_24h_usd,
            "max_token_age_hours": self.max_token_age_hours,
            "is_paper": self.is_paper,
        }


# =============================================================================
# Token Candidate
# =============================================================================

@dataclass
class TokenCandidate:
    """A token identified as potential snipe target."""
    
    mint: str
    symbol: str
    name: str
    price_usd: float
    
    # Metrics
    liquidity_usd: float = 0.0
    volume_24h_usd: float = 0.0
    volume_1h_usd: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    
    # Scoring
    momentum_score: float = 0.0
    risk_score: float = 0.0
    composite_score: float = 0.0
    
    # Metadata
    age_hours: float = 0.0
    holder_count: int = 0
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mint": self.mint,
            "symbol": self.symbol,
            "name": self.name,
            "price_usd": self.price_usd,
            "liquidity_usd": self.liquidity_usd,
            "volume_24h_usd": self.volume_24h_usd,
            "price_change_1h": self.price_change_1h,
            "momentum_score": self.momentum_score,
            "composite_score": self.composite_score,
            "age_hours": self.age_hours,
        }


# =============================================================================
# Sniper State
# =============================================================================

@dataclass  
class SniperState:
    """Persistent state for sniper strategy."""
    
    current_capital_usd: float = 4.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_usd: float = 0.0
    consecutive_losses: int = 0
    last_trade_time: float = 0.0
    active_position: Optional[Dict[str, Any]] = None
    is_paused: bool = False
    pause_reason: str = ""
    
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_capital_usd": self.current_capital_usd,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl_usd": self.total_pnl_usd,
            "consecutive_losses": self.consecutive_losses,
            "win_rate": round(self.win_rate(), 3),
            "active_position": self.active_position,
            "is_paused": self.is_paused,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SniperState":
        return cls(
            current_capital_usd=data.get("current_capital_usd", 4.0),
            total_trades=data.get("total_trades", 0),
            winning_trades=data.get("winning_trades", 0),
            losing_trades=data.get("losing_trades", 0),
            total_pnl_usd=data.get("total_pnl_usd", 0.0),
            consecutive_losses=data.get("consecutive_losses", 0),
            last_trade_time=data.get("last_trade_time", 0.0),
            active_position=data.get("active_position"),
            is_paused=data.get("is_paused", False),
            pause_reason=data.get("pause_reason", ""),
        )


# =============================================================================
# Micro-Cap Sniper
# =============================================================================

class MicroCapSniper:
    """
    Aggressive micro-cap token sniper for small capital growth.
    
    STRATEGY:
    1. Scan for new tokens with strong momentum signals
    2. Enter on volume spike + price breakout
    3. Exit at 25% profit or 12% stop loss
    4. Compound all gains
    
    RISK WARNING:
    This is a HIGH RISK strategy for speculative capital only.
    Most trades will be volatile memecoins with high failure rates.
    Only use capital you can afford to lose entirely.
    """
    
    def __init__(self, config: Optional[SniperConfig] = None):
        self.config = config or SniperConfig()
        self.state = self._load_state()
        SNIPER_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_state(self) -> SniperState:
        """Load persistent state from disk."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    return SniperState.from_dict(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
        return SniperState(current_capital_usd=self.config.starting_capital_usd)
    
    def _save_state(self) -> None:
        """Save state to disk."""
        SNIPER_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)
    
    def _log_trade(self, trade: Dict[str, Any]) -> None:
        """Append trade to log file."""
        with open(TRADE_LOG, "a") as f:
            f.write(json.dumps(trade) + "\n")
    
    # =========================================================================
    # Scanning
    # =========================================================================
    
    def scan_candidates(self) -> List[TokenCandidate]:
        """
        Scan for potential snipe targets from multiple sources.
        
        Returns candidates sorted by composite score (best first).
        """
        candidates: List[TokenCandidate] = []
        
        # Try trending aggregator
        try:
            from core.trending_aggregator import fetch_trending_all_sources
            trending = fetch_trending_all_sources(limit=100)
            
            for token in trending:
                candidate = TokenCandidate(
                    mint=token.mint,
                    symbol=token.symbol,
                    name=token.name,
                    price_usd=token.price_usd,
                    liquidity_usd=token.liquidity_usd,
                    volume_24h_usd=token.volume_24h_usd,
                    price_change_24h=token.price_change_24h,
                    momentum_score=token.velocity,
                    source="trending_aggregator",
                )
                candidates.append(candidate)
        except Exception as e:
            logger.warning(f"Trending aggregator failed: {e}")
        
        # Try DexScreener for newer tokens
        try:
            from core.dexscreener import get_boosted_tokens
            boosted = get_boosted_tokens()
            
            for token in boosted:
                if token.get("chainId") != "solana":
                    continue
                candidate = TokenCandidate(
                    mint=token.get("tokenAddress", ""),
                    symbol=token.get("symbol", ""),
                    name=token.get("name", ""),
                    price_usd=float(token.get("priceUsd", 0)),
                    liquidity_usd=float(token.get("liquidity", {}).get("usd", 0)),
                    volume_24h_usd=float(token.get("volume", {}).get("h24", 0)),
                    source="dexscreener",
                )
                candidates.append(candidate)
        except Exception as e:
            logger.debug(f"DexScreener fallback: {e}")
        
        # Filter and score candidates
        filtered = self._filter_candidates(candidates)
        scored = self._score_candidates(filtered)
        
        return sorted(scored, key=lambda c: c.composite_score, reverse=True)
    
    def _filter_candidates(
        self, 
        candidates: List[TokenCandidate]
    ) -> List[TokenCandidate]:
        """Filter candidates by configuration thresholds."""
        filtered = []
        
        for c in candidates:
            # Liquidity filter
            if c.liquidity_usd < self.config.min_liquidity_usd:
                continue
            if c.liquidity_usd > self.config.max_liquidity_usd:
                continue
            
            # Volume filter  
            if c.volume_24h_usd < self.config.min_volume_24h_usd:
                continue
            
            # Age filter (if available)
            if c.age_hours > 0 and c.age_hours > self.config.max_token_age_hours:
                continue
            
            # Momentum filter
            if c.price_change_1h < self.config.min_price_change_1h:
                # Allow if 24h change is strong
                if c.price_change_24h < 0.20:  # 20%
                    continue
            
            filtered.append(c)
        
        return filtered
    
    def _score_candidates(
        self, 
        candidates: List[TokenCandidate]
    ) -> List[TokenCandidate]:
        """Score candidates for ranking."""
        for c in candidates:
            # Momentum score (40%)
            momentum = min(c.price_change_1h / 0.10, 1.0) * 0.4  # Normalize to 10%
            
            # Volume/Liquidity ratio (30%) - higher = more active
            if c.liquidity_usd > 0:
                vol_ratio = min(c.volume_24h_usd / c.liquidity_usd, 5.0) / 5.0
            else:
                vol_ratio = 0
            volume = vol_ratio * 0.3
            
            # Freshness score (30%) - newer = better
            if c.age_hours > 0:
                freshness = max(0, 1 - c.age_hours / 24) * 0.3
            else:
                freshness = 0.15  # Default if unknown
            
            c.composite_score = momentum + volume + freshness
            c.momentum_score = momentum
        
        return candidates
    
    # =========================================================================
    # Entry Logic
    # =========================================================================
    
    def should_enter(self, candidate: TokenCandidate) -> Tuple[bool, str]:
        """
        Determine if we should enter a position.
        
        Returns (should_enter, reason).
        """
        # Check if paused
        if self.state.is_paused:
            return False, f"Paused: {self.state.pause_reason}"
        
        # Check if already in position
        if self.state.active_position:
            return False, "Already in position"
        
        # Check consecutive loss cooldown
        if self.state.consecutive_losses >= self.config.max_consecutive_losses:
            cooldown_elapsed = time.time() - self.state.last_trade_time
            if cooldown_elapsed < self.config.cooldown_after_loss_minutes * 60:
                return False, f"Cooldown: {self.config.cooldown_after_loss_minutes}min after losses"
        
        # Check minimum score
        if candidate.composite_score < 0.5:
            return False, f"Score too low: {candidate.composite_score:.2f}"
        
        # TODO: Add more sophisticated entry signals
        # - Volume spike detection
        # - Price breakout confirmation
        # - Holder count growth
        
        return True, f"Score: {candidate.composite_score:.2f}, Momentum: +{candidate.price_change_1h*100:.1f}%"
    
    def calculate_position(self, candidate: TokenCandidate) -> Dict[str, Any]:
        """Calculate position size and exit levels."""
        capital = self.state.current_capital_usd
        entry_price = candidate.price_usd
        
        # Position: Use entire capital (aggressive for small amounts)
        position_usd = capital
        quantity = position_usd / entry_price if entry_price > 0 else 0
        
        # Exit levels
        take_profit_price = entry_price * (1 + self.config.take_profit_pct)
        stop_loss_price = entry_price * (1 - self.config.stop_loss_pct)
        
        return {
            "mint": candidate.mint,
            "symbol": candidate.symbol,
            "entry_price": entry_price,
            "quantity": quantity,
            "position_usd": position_usd,
            "take_profit_price": take_profit_price,
            "stop_loss_price": stop_loss_price,
            "entry_time": time.time(),
            "max_hold_until": time.time() + (self.config.max_hold_minutes * 60),
            "is_paper": self.config.is_paper,
        }
    
    # =========================================================================
    # Exit Logic
    # =========================================================================
    
    def check_exit(self, current_price: float) -> Tuple[bool, str, float]:
        """
        Check if position should be exited.
        
        Returns (should_exit, reason, pnl_pct).
        """
        pos = self.state.active_position
        if not pos:
            return False, "No position", 0.0
        
        entry = pos["entry_price"]
        pnl_pct = (current_price - entry) / entry if entry > 0 else 0
        
        # Take profit
        if current_price >= pos["take_profit_price"]:
            return True, "TAKE_PROFIT", pnl_pct
        
        # Stop loss
        if current_price <= pos["stop_loss_price"]:
            return True, "STOP_LOSS", pnl_pct
        
        # Time stop
        if time.time() >= pos["max_hold_until"]:
            return True, "TIME_STOP", pnl_pct
        
        return False, "HOLD", pnl_pct
    
    def record_exit(self, reason: str, exit_price: float) -> Dict[str, Any]:
        """Record position exit and update state."""
        pos = self.state.active_position
        if not pos:
            return {}
        
        entry = pos["entry_price"]
        quantity = pos["quantity"]
        pnl_usd = (exit_price - entry) * quantity
        pnl_pct = (exit_price - entry) / entry if entry > 0 else 0
        
        # Update state
        self.state.total_trades += 1
        self.state.total_pnl_usd += pnl_usd
        
        if pnl_usd > 0:
            self.state.winning_trades += 1
            self.state.consecutive_losses = 0
        else:
            self.state.losing_trades += 1
            self.state.consecutive_losses += 1
        
        # Update capital
        self.state.current_capital_usd += pnl_usd
        self.state.last_trade_time = time.time()
        
        # Clear position
        trade_record = {
            "mint": pos["mint"],
            "symbol": pos["symbol"],
            "entry_price": entry,
            "exit_price": exit_price,
            "quantity": quantity,
            "pnl_usd": round(pnl_usd, 4),
            "pnl_pct": round(pnl_pct, 4),
            "reason": reason,
            "is_paper": pos["is_paper"],
            "timestamp": time.time(),
        }
        
        self.state.active_position = None
        self._log_trade(trade_record)
        self._save_state()
        
        return trade_record
    
    # =========================================================================
    # Main Loop
    # =========================================================================
    
    def run_scan_cycle(self) -> Dict[str, Any]:
        """
        Run one complete scan cycle.
        
        Returns summary of actions taken.
        """
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "capital": self.state.current_capital_usd,
            "candidates_found": 0,
            "action": "none",
            "details": {},
        }
        
        # Check if we've hit target
        if self.state.current_capital_usd >= self.config.target_capital_usd:
            result["action"] = "TARGET_REACHED"
            result["details"] = {"message": "🎉 Target capital reached!"}
            return result
        
        # Scan for candidates
        candidates = self.scan_candidates()
        result["candidates_found"] = len(candidates)
        
        if not candidates:
            result["action"] = "no_candidates"
            return result
        
        # Check top candidate
        best = candidates[0]
        should_enter, reason = self.should_enter(best)
        
        if should_enter:
            position = self.calculate_position(best)
            
            if self.config.is_paper:
                # Paper trade - just record it
                self.state.active_position = position
                self._save_state()
                result["action"] = "PAPER_ENTRY"
                result["details"] = position
            else:
                # Live trade - would execute here
                result["action"] = "LIVE_ENTRY_PENDING"
                result["details"] = {
                    "message": "Live entry requires approval",
                    "position": position,
                }
        else:
            result["action"] = "skip"
            result["details"] = {"reason": reason, "best_candidate": best.to_dict()}
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get current sniper status."""
        progress = self.state.current_capital_usd / self.config.target_capital_usd
        trades_needed = 0
        if self.state.current_capital_usd < self.config.target_capital_usd:
            import math
            trades_needed = int(math.ceil(
                math.log(self.config.target_capital_usd / max(self.state.current_capital_usd, 0.01)) 
                / math.log(1 + self.config.take_profit_pct)
            ))
        
        return {
            "strategy": "MicroCapSniper",
            "mode": "PAPER" if self.config.is_paper else "LIVE",
            "current_capital": f"${self.state.current_capital_usd:.2f}",
            "target_capital": f"${self.config.target_capital_usd:.2f}",
            "progress": f"{progress*100:.1f}%",
            "trades_to_target": trades_needed,
            "total_trades": self.state.total_trades,
            "win_rate": f"{self.state.win_rate()*100:.1f}%",
            "total_pnl": f"${self.state.total_pnl_usd:.2f}",
            "active_position": bool(self.state.active_position),
            "is_paused": self.state.is_paused,
        }


# =============================================================================
# Entry Points
# =============================================================================

_sniper: Optional[MicroCapSniper] = None


def get_sniper(config: Optional[SniperConfig] = None) -> MicroCapSniper:
    """Get global sniper instance."""
    global _sniper
    if _sniper is None:
        _sniper = MicroCapSniper(config)
    return _sniper


def run_sniper_cycle() -> Dict[str, Any]:
    """Run one sniper scan cycle."""
    sniper = get_sniper()
    return sniper.run_scan_cycle()


def get_sniper_status() -> Dict[str, Any]:
    """Get sniper status."""
    sniper = get_sniper()
    return sniper.get_status()


# =============================================================================
# Self-Test
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🎯 Micro-Cap Sniper Status")
    print("=" * 40)
    
    sniper = MicroCapSniper(SniperConfig(
        starting_capital_usd=4.0,
        is_paper=True,
    ))
    
    status = sniper.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print("\n🔍 Scanning for candidates...")
    result = sniper.run_scan_cycle()
    
    print(f"\n  Found: {result['candidates_found']} candidates")
    print(f"  Action: {result['action']}")
    if result.get("details"):
        print(f"  Details: {result['details']}")
