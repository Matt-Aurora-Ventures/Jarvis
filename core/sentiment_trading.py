"""Sentiment-triggered trading with @xinsanityo signals."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SIGNALS_DIR = ROOT / "data" / "trader" / "sentiment_signals"
CONFIG_PATH = ROOT / "data" / "trader" / "sentiment_config.json"


@dataclass
class SentimentTradeConfig:
    """Configuration for sentiment-based trading."""
    
    # Risk parameters - LOOSER for vetted social signals
    capital_usd: float = 10.0
    risk_per_trade: float = 0.10  # 10% per trade (higher for conviction)
    max_position_pct: float = 0.50  # 50% max position
    stop_loss_pct: float = 0.15  # 15% stop loss (wider for volatile memes)
    take_profit_pct: float = 0.50  # 50% take profit (memes can run)
    trailing_stop_pct: float = 0.20  # 20% trailing stop after profit
    
    # Safety filters - LOOSER for vetted accounts
    min_liquidity_usd: float = 10000.0  # Lower threshold (was 50k)
    min_volume_24h_usd: float = 5000.0  # Lower threshold (was 50k)
    require_locked_lp: bool = False  # Don't require locked LP
    min_locked_pct: float = 0.0  # No minimum
    require_revoked_authorities: bool = False  # Don't require
    max_transfer_fee_bps: float = 100.0  # Allow up to 1% fee
    
    # Execution
    fee_bps: float = 50.0  # Higher fees for meme tokens
    slippage_bps: float = 100.0  # 1% slippage (memes are volatile)
    max_slippage_bps: float = 500.0  # 5% absolute max
    
    # Signal source
    trusted_handles: List[str] = None
    
    def __post_init__(self):
        if self.trusted_handles is None:
            self.trusted_handles = ["xinsanityo"]


@dataclass 
class SentimentSignal:
    """A trading signal from social sentiment."""
    
    handle: str
    token_symbol: str
    token_address: Optional[str]
    signal_type: str  # "bullish", "bearish", "watch"
    conviction: str  # "high", "medium", "low"
    source_url: Optional[str]
    timestamp: float
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_default_config() -> SentimentTradeConfig:
    """Get default sentiment trading config."""
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
            return SentimentTradeConfig(**data)
        except (json.JSONDecodeError, TypeError):
            pass
    return SentimentTradeConfig()


def save_config(config: SentimentTradeConfig) -> None:
    """Save sentiment trading config."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(config), indent=2))


def log_signal(signal: SentimentSignal) -> None:
    """Log a sentiment signal for tracking."""
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Append to daily log
    date_str = time.strftime("%Y-%m-%d")
    log_path = SIGNALS_DIR / f"signals_{date_str}.jsonl"
    
    with open(log_path, "a") as f:
        f.write(json.dumps(signal.to_dict()) + "\n")


def load_recent_signals(days: int = 7) -> List[SentimentSignal]:
    """Load recent sentiment signals."""
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    signals = []
    
    cutoff = time.time() - (days * 86400)
    
    for path in sorted(SIGNALS_DIR.glob("signals_*.jsonl")):
        try:
            with open(path) as f:
                for line in f:
                    data = json.loads(line.strip())
                    if data.get("timestamp", 0) >= cutoff:
                        signals.append(SentimentSignal(**data))
        except (json.JSONDecodeError, TypeError):
            continue
    
    return sorted(signals, key=lambda s: s.timestamp, reverse=True)


def evaluate_signal_for_trade(
    signal: SentimentSignal,
    config: Optional[SentimentTradeConfig] = None,
) -> Dict[str, Any]:
    """
    Evaluate if a signal should trigger a trade.
    
    Returns assessment with:
        - should_trade: bool
        - position_size_pct: float
        - stop_loss: float
        - take_profit: float
        - warnings: list
    """
    if config is None:
        config = get_default_config()
    
    warnings = []
    should_trade = False
    position_size = 0.0
    
    # Check if handle is trusted
    if signal.handle not in config.trusted_handles:
        warnings.append(f"Handle @{signal.handle} not in trusted list")
        return {
            "should_trade": False,
            "position_size_pct": 0,
            "warnings": warnings,
        }
    
    # Only trade bullish signals
    if signal.signal_type != "bullish":
        warnings.append(f"Signal type '{signal.signal_type}' not tradeable")
        return {
            "should_trade": False,
            "position_size_pct": 0,
            "warnings": warnings,
        }
    
    # Position sizing based on conviction
    conviction_multipliers = {
        "high": 1.0,
        "medium": 0.6,
        "low": 0.3,
    }
    multiplier = conviction_multipliers.get(signal.conviction, 0.3)
    position_size = config.max_position_pct * multiplier
    
    # Determine if we should trade
    if signal.token_address:
        should_trade = True
    else:
        warnings.append("No token address - need to look up manually")
        should_trade = False
    
    # Add warning if no address
    if not signal.token_address:
        warnings.append("Token address missing - search required")
    
    return {
        "should_trade": should_trade,
        "position_size_pct": position_size,
        "stop_loss_pct": config.stop_loss_pct,
        "take_profit_pct": config.take_profit_pct,
        "trailing_stop_pct": config.trailing_stop_pct,
        "max_slippage_bps": config.max_slippage_bps,
        "warnings": warnings,
        "config": asdict(config),
    }


def format_trade_plan(
    signal: SentimentSignal,
    evaluation: Dict[str, Any],
    current_price: Optional[float] = None,
) -> str:
    """Format a trade plan for display."""
    lines = [
        "=" * 50,
        "SENTIMENT TRADE PLAN",
        "=" * 50,
        f"Source: @{signal.handle}",
        f"Token: {signal.token_symbol}",
        f"Address: {signal.token_address or 'UNKNOWN'}",
        f"Signal: {signal.signal_type.upper()}",
        f"Conviction: {signal.conviction.upper()}",
        "",
    ]
    
    if evaluation["should_trade"]:
        lines.extend([
            "TRADE PARAMETERS:",
            f"  Position Size: {evaluation['position_size_pct']*100:.1f}% of capital",
            f"  Stop Loss: {evaluation['stop_loss_pct']*100:.1f}%",
            f"  Take Profit: {evaluation['take_profit_pct']*100:.1f}%",
            f"  Trailing Stop: {evaluation['trailing_stop_pct']*100:.1f}%",
            f"  Max Slippage: {evaluation['max_slippage_bps']/100:.1f}%",
        ])
        
        if current_price:
            config = evaluation.get("config", {})
            capital = config.get("capital_usd", 10.0)
            position_usd = capital * evaluation["position_size_pct"]
            lines.extend([
                "",
                "EXECUTION:",
                f"  Entry: ~${current_price:.6f}",
                f"  Position: ${position_usd:.2f}",
                f"  Stop: ~${current_price * (1 - evaluation['stop_loss_pct']):.6f}",
                f"  Target: ~${current_price * (1 + evaluation['take_profit_pct']):.6f}",
            ])
    else:
        lines.append("DO NOT TRADE - See warnings below")
    
    if evaluation["warnings"]:
        lines.extend(["", "WARNINGS:"])
        for w in evaluation["warnings"]:
            lines.append(f"  - {w}")
    
    lines.append("=" * 50)
    return "\n".join(lines)


# Initialize default config
if not CONFIG_PATH.exists():
    save_config(SentimentTradeConfig())


if __name__ == "__main__":
    # Example usage
    config = get_default_config()
    print("Sentiment Trading Config:")
    print(json.dumps(asdict(config), indent=2))
    
    # Example signal
    signal = SentimentSignal(
        handle="xinsanityo",
        token_symbol="HORSE",
        token_address=None,  # Would need to look up
        signal_type="bullish",
        conviction="medium",
        source_url="https://x.com/xinsanityo/status/123",
        timestamp=time.time(),
        notes="Horse meta for 2026",
    )
    
    evaluation = evaluate_signal_for_trade(signal, config)
    print("\n" + format_trade_plan(signal, evaluation))
