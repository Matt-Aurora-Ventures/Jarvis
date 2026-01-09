"""
Enhanced Paper Trading System.

Features:
- Realistic paper wallet with balance tracking
- Simulated slippage and fees
- Trade history and analytics
- Telegram bot integration
- Performance tracking
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "paper_trading"
WALLET_FILE = DATA_DIR / "wallet.json"
TRADES_FILE = DATA_DIR / "trades.jsonl"
SETTINGS_FILE = DATA_DIR / "settings.json"


@dataclass
class PaperWallet:
    """Simulated trading wallet."""
    balance_usd: float = 1000.0
    initial_balance: float = 1000.0
    total_deposited: float = 1000.0
    total_withdrawn: float = 0.0
    total_fees_paid: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0
    current_position: Optional[Dict[str, Any]] = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaperWallet":
        # Handle current_position separately since it's Optional[Dict]
        pos = data.pop("current_position", None)
        wallet = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        wallet.current_position = pos
        return wallet


@dataclass
class PaperTrade:
    """A completed paper trade."""
    id: str
    symbol: str
    mint: str
    side: str  # "buy" or "sell"
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    position_usd: float
    fee_usd: float
    slippage_usd: float
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    entry_time: str = ""
    exit_time: Optional[str] = None
    exit_reason: Optional[str] = None
    status: str = "open"  # "open", "closed"
    strategy: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaperTrade":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PaperSettings:
    """Paper trading configuration."""
    default_position_size_pct: float = 10.0  # % of balance per trade
    max_position_size_pct: float = 25.0  # Max % of balance per trade
    fee_bps: float = 30.0  # 0.3% fee
    slippage_bps: float = 50.0  # 0.5% slippage
    default_stop_loss_pct: float = 10.0  # -10% stop loss
    default_take_profit_pct: float = 25.0  # +25% take profit
    max_open_positions: int = 3
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaperSettings":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class PaperTradingEngine:
    """
    Paper trading engine with realistic simulation.

    Features:
    - Balance tracking with fees and slippage
    - Multiple position support
    - Trade history logging
    - Performance analytics
    """

    def __init__(self):
        self._wallet: Optional[PaperWallet] = None
        self._settings: Optional[PaperSettings] = None
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """Load wallet and settings from disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Load wallet
        if WALLET_FILE.exists():
            try:
                data = json.loads(WALLET_FILE.read_text(encoding="utf-8"))
                self._wallet = PaperWallet.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load wallet: {e}")
                self._wallet = PaperWallet()
        else:
            self._wallet = PaperWallet()

        # Load settings
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                self._settings = PaperSettings.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load settings: {e}")
                self._settings = PaperSettings()
        else:
            self._settings = PaperSettings()

    def _save_wallet(self) -> None:
        """Save wallet to disk."""
        if self._wallet:
            self._wallet.updated_at = datetime.now(timezone.utc).isoformat()
            try:
                WALLET_FILE.write_text(
                    json.dumps(self._wallet.to_dict(), indent=2),
                    encoding="utf-8"
                )
            except Exception as e:
                logger.error(f"Failed to save wallet: {e}")

    def _save_settings(self) -> None:
        """Save settings to disk."""
        if self._settings:
            try:
                SETTINGS_FILE.write_text(
                    json.dumps(self._settings.to_dict(), indent=2),
                    encoding="utf-8"
                )
            except Exception as e:
                logger.error(f"Failed to save settings: {e}")

    def _log_trade(self, trade: PaperTrade) -> None:
        """Append trade to history file."""
        try:
            with open(TRADES_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(trade.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")

    def get_wallet(self) -> PaperWallet:
        """Get current wallet state."""
        with self._lock:
            return self._wallet

    def get_settings(self) -> PaperSettings:
        """Get current settings."""
        return self._settings

    def update_settings(self, **kwargs) -> PaperSettings:
        """Update paper trading settings."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._settings, key):
                    setattr(self._settings, key, value)
            self._save_settings()
            return self._settings

    def reset_wallet(self, initial_balance: float = 1000.0) -> PaperWallet:
        """Reset wallet to initial state."""
        with self._lock:
            self._wallet = PaperWallet(
                balance_usd=initial_balance,
                initial_balance=initial_balance,
                total_deposited=initial_balance,
            )
            self._save_wallet()
            logger.info(f"Wallet reset with ${initial_balance}")
            return self._wallet

    def deposit(self, amount: float) -> PaperWallet:
        """Deposit funds to paper wallet."""
        with self._lock:
            self._wallet.balance_usd += amount
            self._wallet.total_deposited += amount
            self._save_wallet()
            logger.info(f"Deposited ${amount} - New balance: ${self._wallet.balance_usd}")
            return self._wallet

    def withdraw(self, amount: float) -> PaperWallet:
        """Withdraw funds from paper wallet."""
        with self._lock:
            if amount > self._wallet.balance_usd:
                raise ValueError(f"Insufficient balance: ${self._wallet.balance_usd}")
            self._wallet.balance_usd -= amount
            self._wallet.total_withdrawn += amount
            self._save_wallet()
            logger.info(f"Withdrew ${amount} - New balance: ${self._wallet.balance_usd}")
            return self._wallet

    def open_position(
        self,
        symbol: str,
        mint: str,
        price: float,
        position_size_pct: Optional[float] = None,
        position_usd: Optional[float] = None,
        strategy: str = "",
        notes: str = "",
    ) -> PaperTrade:
        """
        Open a paper position.

        Args:
            symbol: Token symbol
            mint: Token mint address
            price: Entry price
            position_size_pct: Position size as % of balance (optional)
            position_usd: Fixed position size in USD (optional)
            strategy: Strategy name
            notes: Optional notes

        Returns:
            The opened trade
        """
        with self._lock:
            if self._wallet.current_position:
                raise ValueError("Already have an open position")

            if not self._settings.enabled:
                raise ValueError("Paper trading is disabled")

            # Calculate position size
            if position_usd:
                size_usd = min(
                    position_usd,
                    self._wallet.balance_usd * (self._settings.max_position_size_pct / 100)
                )
            else:
                pct = position_size_pct or self._settings.default_position_size_pct
                size_usd = self._wallet.balance_usd * (pct / 100)

            if size_usd > self._wallet.balance_usd:
                raise ValueError(f"Insufficient balance: ${self._wallet.balance_usd}")

            # Calculate fees and slippage
            fee_usd = size_usd * (self._settings.fee_bps / 10000)
            slippage_usd = size_usd * (self._settings.slippage_bps / 10000)
            total_cost = size_usd + fee_usd + slippage_usd

            if total_cost > self._wallet.balance_usd:
                raise ValueError(f"Insufficient balance for trade with fees")

            # Adjust entry price for slippage (buying at slightly higher price)
            adjusted_price = price * (1 + self._settings.slippage_bps / 10000)
            quantity = size_usd / adjusted_price

            # Create trade
            trade = PaperTrade(
                id=f"paper_{int(time.time())}_{symbol}",
                symbol=symbol,
                mint=mint,
                side="buy",
                entry_price=adjusted_price,
                exit_price=None,
                quantity=quantity,
                position_usd=size_usd,
                fee_usd=fee_usd,
                slippage_usd=slippage_usd,
                entry_time=datetime.now(timezone.utc).isoformat(),
                status="open",
                strategy=strategy,
                notes=notes,
            )

            # Update wallet
            self._wallet.balance_usd -= total_cost
            self._wallet.total_fees_paid += fee_usd
            self._wallet.current_position = trade.to_dict()
            self._save_wallet()
            self._log_trade(trade)

            logger.info(
                f"Opened paper position: {symbol} @ ${adjusted_price:.8f} "
                f"(${size_usd:.2f}, fee: ${fee_usd:.2f})"
            )

            return trade

    def close_position(
        self,
        price: float,
        exit_reason: str = "MANUAL_EXIT",
    ) -> Optional[PaperTrade]:
        """
        Close the current paper position.

        Args:
            price: Exit price
            exit_reason: Reason for exit

        Returns:
            The closed trade or None if no position
        """
        with self._lock:
            if not self._wallet.current_position:
                return None

            pos = self._wallet.current_position
            entry_price = pos["entry_price"]
            quantity = pos["quantity"]
            position_usd = pos["position_usd"]

            # Calculate fees and slippage on exit
            exit_fee_usd = position_usd * (self._settings.fee_bps / 10000)
            exit_slippage_usd = position_usd * (self._settings.slippage_bps / 10000)

            # Adjust exit price for slippage (selling at slightly lower price)
            adjusted_price = price * (1 - self._settings.slippage_bps / 10000)

            # Calculate P&L
            gross_pnl = (adjusted_price - entry_price) * quantity
            net_pnl = gross_pnl - exit_fee_usd - exit_slippage_usd
            pnl_pct = (adjusted_price - entry_price) / entry_price * 100

            # Create closed trade record
            trade = PaperTrade(
                id=pos["id"],
                symbol=pos["symbol"],
                mint=pos["mint"],
                side="sell",
                entry_price=entry_price,
                exit_price=adjusted_price,
                quantity=quantity,
                position_usd=position_usd,
                fee_usd=pos["fee_usd"] + exit_fee_usd,
                slippage_usd=pos["slippage_usd"] + exit_slippage_usd,
                pnl_usd=net_pnl,
                pnl_pct=pnl_pct,
                entry_time=pos["entry_time"],
                exit_time=datetime.now(timezone.utc).isoformat(),
                exit_reason=exit_reason,
                status="closed",
                strategy=pos.get("strategy", ""),
                notes=pos.get("notes", ""),
            )

            # Update wallet
            exit_value = position_usd + gross_pnl - exit_fee_usd - exit_slippage_usd
            self._wallet.balance_usd += exit_value
            self._wallet.total_fees_paid += exit_fee_usd
            self._wallet.total_trades += 1
            self._wallet.total_pnl += net_pnl

            if net_pnl > 0:
                self._wallet.winning_trades += 1
                self._wallet.best_trade_pnl = max(self._wallet.best_trade_pnl, net_pnl)
            else:
                self._wallet.losing_trades += 1
                self._wallet.worst_trade_pnl = min(self._wallet.worst_trade_pnl, net_pnl)

            self._wallet.current_position = None
            self._save_wallet()
            self._log_trade(trade)

            logger.info(
                f"Closed paper position: {trade.symbol} @ ${adjusted_price:.8f} "
                f"P&L: ${net_pnl:+.2f} ({pnl_pct:+.2f}%)"
            )

            return trade

    def get_trade_history(self, limit: int = 50) -> List[PaperTrade]:
        """Get recent trade history."""
        trades = []
        if TRADES_FILE.exists():
            try:
                with open(TRADES_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                trades.append(PaperTrade.from_dict(json.loads(line)))
                            except (json.JSONDecodeError, TypeError):
                                continue
            except Exception as e:
                logger.warning(f"Failed to load trade history: {e}")

        # Return most recent trades
        return list(reversed(trades[-limit:]))

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        wallet = self.get_wallet()
        roi = (
            (wallet.balance_usd - wallet.initial_balance) / wallet.initial_balance * 100
            if wallet.initial_balance > 0 else 0
        )
        win_rate = (
            wallet.winning_trades / wallet.total_trades * 100
            if wallet.total_trades > 0 else 0
        )

        return {
            "balance_usd": wallet.balance_usd,
            "initial_balance": wallet.initial_balance,
            "total_pnl": wallet.total_pnl,
            "roi_pct": roi,
            "total_trades": wallet.total_trades,
            "winning_trades": wallet.winning_trades,
            "losing_trades": wallet.losing_trades,
            "win_rate": win_rate,
            "total_fees_paid": wallet.total_fees_paid,
            "best_trade": wallet.best_trade_pnl,
            "worst_trade": wallet.worst_trade_pnl,
            "has_position": wallet.current_position is not None,
            "current_position": wallet.current_position,
        }


# Global instance
_engine: Optional[PaperTradingEngine] = None
_lock = threading.Lock()


def get_engine() -> PaperTradingEngine:
    """Get the global paper trading engine."""
    global _engine
    with _lock:
        if _engine is None:
            _engine = PaperTradingEngine()
        return _engine


# Convenience functions
def get_wallet() -> PaperWallet:
    return get_engine().get_wallet()


def get_settings() -> PaperSettings:
    return get_engine().get_settings()


def open_position(**kwargs) -> PaperTrade:
    return get_engine().open_position(**kwargs)


def close_position(price: float, reason: str = "MANUAL_EXIT") -> Optional[PaperTrade]:
    return get_engine().close_position(price, reason)


def get_performance() -> Dict[str, Any]:
    return get_engine().get_performance_summary()


def reset_wallet(initial_balance: float = 1000.0) -> PaperWallet:
    return get_engine().reset_wallet(initial_balance)
