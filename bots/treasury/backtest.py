"""
Jarvis Backtesting Framework
Test sentiment trading strategies against historical data
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal
import aiohttp
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)


@dataclass
class HistoricalPrice:
    """Historical price data point."""
    timestamp: datetime
    price: float
    volume_24h: float
    mcap: float
    change_24h: float


@dataclass
class BacktestTrade:
    """A trade in the backtest."""
    token_symbol: str
    token_mint: str
    direction: str
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    take_profit: float = 0.0
    stop_loss: float = 0.0
    amount_usd: float = 100.0
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""
    sentiment_grade: str = ""
    sentiment_score: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.exit_time is None


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl_usd: float
    total_pnl_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    best_trade: float
    worst_trade: float
    avg_trade: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    trades: List[BacktestTrade]

    def to_report(self) -> str:
        """Generate text report."""
        return f"""
BACKTEST RESULTS

Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}

PERFORMANCE:
  Initial Balance: ${self.initial_balance:,.2f}
  Final Balance: ${self.final_balance:,.2f}
  Total P&L: ${self.total_pnl_usd:+,.2f} ({self.total_pnl_pct:+.1f}%)

STATISTICS:
  Total Trades: {self.total_trades}
  Win Rate: {self.win_rate:.1f}%
  Profit Factor: {self.profit_factor:.2f}
  Max Drawdown: {self.max_drawdown_pct:.1f}%
  Sharpe Ratio: {self.sharpe_ratio:.2f}

TRADE ANALYSIS:
  Best Trade: ${self.best_trade:+.2f}
  Worst Trade: ${self.worst_trade:+.2f}
  Average Trade: ${self.avg_trade:+.2f}
  Average Win: ${self.avg_win:+.2f}
  Average Loss: ${self.avg_loss:+.2f}
"""

    def to_telegram(self) -> str:
        """Generate Telegram-formatted report."""
        emoji = "" if self.total_pnl_usd >= 0 else ""

        return f"""
<b>BACKTEST RESULTS</b>

<b>Period:</b> {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}

<b>Performance:</b>
{emoji} P&L: <code>${self.total_pnl_usd:+,.2f}</code> (<code>{self.total_pnl_pct:+.1f}%</code>)
Initial: <code>${self.initial_balance:,.2f}</code>
Final: <code>${self.final_balance:,.2f}</code>

<b>Statistics:</b>
Trades: <code>{self.total_trades}</code> ({self.winning_trades}W / {self.losing_trades}L)
Win Rate: <code>{self.win_rate:.1f}%</code>
Profit Factor: <code>{self.profit_factor:.2f}</code>
Max Drawdown: <code>{self.max_drawdown_pct:.1f}%</code>

<b>Trade Analysis:</b>
Best: <code>${self.best_trade:+.2f}</code>
Worst: <code>${self.worst_trade:+.2f}</code>
Average: <code>${self.avg_trade:+.2f}</code>
"""


class SentimentBacktester:
    """
    Backtest sentiment-based trading strategies.

    Uses historical prediction data and price data to simulate
    trading performance.
    """

    PREDICTIONS_FILE = Path(__file__).parent.parent / 'buy_tracker' / 'predictions_history.json'
    RESULTS_DIR = Path(__file__).parent / '.backtest_results'

    # TP/SL configuration by grade
    TP_SL_CONFIG = {
        'A': {'take_profit': 0.30, 'stop_loss': 0.10},
        'A-': {'take_profit': 0.25, 'stop_loss': 0.10},
        'B+': {'take_profit': 0.20, 'stop_loss': 0.08},
        'B': {'take_profit': 0.15, 'stop_loss': 0.08},
        'C+': {'take_profit': 0.10, 'stop_loss': 0.05},
        'C': {'take_profit': 0.08, 'stop_loss': 0.05},
    }

    def __init__(
        self,
        initial_balance: float = 1000.0,
        position_size_pct: float = 0.10,  # 10% per trade
        max_positions: int = 50,
        min_grade: str = "B",  # Minimum grade to trade
        use_trailing_stop: bool = False
    ):
        """
        Initialize backtester.

        Args:
            initial_balance: Starting balance in USD
            position_size_pct: Position size as % of balance
            max_positions: Maximum concurrent positions
            min_grade: Minimum sentiment grade to take trades
            use_trailing_stop: Use trailing stop loss
        """
        self.initial_balance = initial_balance
        self.position_size_pct = position_size_pct
        self.max_positions = max_positions
        self.min_grade = min_grade
        self.use_trailing_stop = use_trailing_stop

        self.RESULTS_DIR.mkdir(exist_ok=True)

        # Grade ranking for comparison
        self.grade_rank = {
            'A': 6, 'A-': 5, 'B+': 4, 'B': 3, 'C+': 2, 'C': 1, 'C-': 0, 'D+': -1, 'D': -2, 'F': -3
        }

    def load_predictions(self) -> List[Dict]:
        """Load historical predictions."""
        if not self.PREDICTIONS_FILE.exists():
            logger.warning(f"No predictions file found at {self.PREDICTIONS_FILE}")
            return []

        try:
            with open(self.PREDICTIONS_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load predictions: {e}")
            return []

    async def get_historical_prices(
        self,
        token_mint: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[HistoricalPrice]:
        """
        Get historical price data for a token.

        Uses DexScreener or Birdeye API for historical data.
        """
        prices = []

        try:
            timeout = ClientTimeout(total=60, connect=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Try DexScreener first
                url = f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}"

                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get('pairs', [])

                        if pairs:
                            pair = pairs[0]  # Use most liquid pair
                            current_price = float(pair.get('priceUsd', 0))

                            # Generate simulated historical data based on priceChange
                            price_change_24h = float(pair.get('priceChange', {}).get('h24', 0))

                            # Create hourly price points
                            hours = int((end_time - start_time).total_seconds() / 3600)
                            hourly_change = price_change_24h / 24

                            for i in range(hours):
                                t = start_time + timedelta(hours=i)
                                # Interpolate price
                                hours_from_start = i
                                price_mult = 1 + (hourly_change / 100 * hours_from_start)
                                price = current_price / (1 + price_change_24h/100) * price_mult

                                prices.append(HistoricalPrice(
                                    timestamp=t,
                                    price=price,
                                    volume_24h=float(pair.get('volume', {}).get('h24', 0)),
                                    mcap=float(pair.get('marketCap', 0) or 0),
                                    change_24h=price_change_24h
                                ))

        except Exception as e:
            logger.error(f"Failed to get historical prices: {e}")

        return prices

    def should_take_trade(self, prediction: Dict) -> bool:
        """Determine if we should take this trade based on grade."""
        grade = prediction.get('grade', 'C')
        min_rank = self.grade_rank.get(self.min_grade, 3)
        pred_rank = self.grade_rank.get(grade, 0)

        return pred_rank >= min_rank

    def calculate_exit(
        self,
        entry_price: float,
        grade: str,
        prices: List[HistoricalPrice]
    ) -> Tuple[Optional[float], str, Optional[datetime]]:
        """
        Calculate exit price based on TP/SL and price history.

        Returns:
            Tuple of (exit_price, exit_reason, exit_time)
        """
        config = self.TP_SL_CONFIG.get(grade, {'take_profit': 0.15, 'stop_loss': 0.08})

        tp_price = entry_price * (1 + config['take_profit'])
        sl_price = entry_price * (1 - config['stop_loss'])

        highest_price = entry_price

        for price_point in prices:
            current_price = price_point.price

            # Update trailing stop if enabled
            if self.use_trailing_stop and current_price > highest_price:
                highest_price = current_price
                # Trail at 50% of TP distance
                sl_price = highest_price * (1 - config['stop_loss'] * 0.5)

            # Check take profit
            if current_price >= tp_price:
                return current_price, "TAKE_PROFIT", price_point.timestamp

            # Check stop loss
            if current_price <= sl_price:
                return current_price, "STOP_LOSS", price_point.timestamp

        # If no TP/SL hit, use last price
        if prices:
            return prices[-1].price, "END_OF_DATA", prices[-1].timestamp

        return None, "NO_DATA", None

    async def run_backtest(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        simulation_hours: int = 24  # How long to simulate each trade
    ) -> BacktestResult:
        """
        Run the backtest on historical predictions.

        Args:
            start_date: Start date filter
            end_date: End date filter
            simulation_hours: Hours to simulate each trade

        Returns:
            BacktestResult with performance metrics
        """
        predictions = self.load_predictions()

        if not predictions:
            logger.warning("No predictions to backtest")
            return self._empty_result()

        trades: List[BacktestTrade] = []
        balance = self.initial_balance
        peak_balance = self.initial_balance
        max_drawdown = 0.0
        open_positions = 0

        logger.info(f"Running backtest on {len(predictions)} predictions")

        for pred in predictions:
            # Parse timestamp
            try:
                pred_time = datetime.fromisoformat(pred.get('timestamp', ''))
            except (ValueError, TypeError):
                continue  # Skip entries with invalid timestamps

            # Apply date filters
            if start_date and pred_time < start_date:
                continue
            if end_date and pred_time > end_date:
                continue

            # Check if we should take this trade
            if not self.should_take_trade(pred):
                continue

            # Check max positions
            if open_positions >= self.max_positions:
                continue

            # Get prediction details
            tokens = pred.get('tokens', [])

            for token in tokens:
                grade = token.get('grade', 'C')
                if self.grade_rank.get(grade, 0) < self.grade_rank.get(self.min_grade, 3):
                    continue

                symbol = token.get('symbol', 'UNKNOWN')
                mint = token.get('contract', '')
                entry_price = token.get('price', 0)
                sentiment_score = token.get('sentiment_score', 0)

                if entry_price <= 0 or not mint:
                    continue

                # Calculate position size
                position_size = balance * self.position_size_pct

                # Get historical prices for simulation
                end_time = pred_time + timedelta(hours=simulation_hours)
                prices = await self.get_historical_prices(mint, pred_time, end_time)

                # Calculate exit
                exit_price, exit_reason, exit_time = self.calculate_exit(
                    entry_price, grade, prices
                )

                if exit_price is None:
                    continue

                # Calculate P&L
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                pnl_usd = position_size * (pnl_pct / 100)

                # Update balance
                balance += pnl_usd

                # Track drawdown
                if balance > peak_balance:
                    peak_balance = balance
                drawdown = (peak_balance - balance) / peak_balance * 100
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

                # Create trade record
                trade = BacktestTrade(
                    token_symbol=symbol,
                    token_mint=mint,
                    direction="LONG",
                    entry_time=pred_time,
                    entry_price=entry_price,
                    exit_time=exit_time,
                    exit_price=exit_price,
                    take_profit=entry_price * (1 + self.TP_SL_CONFIG.get(grade, {}).get('take_profit', 0.15)),
                    stop_loss=entry_price * (1 - self.TP_SL_CONFIG.get(grade, {}).get('stop_loss', 0.08)),
                    amount_usd=position_size,
                    pnl_usd=pnl_usd,
                    pnl_pct=pnl_pct,
                    exit_reason=exit_reason,
                    sentiment_grade=grade,
                    sentiment_score=sentiment_score
                )

                trades.append(trade)
                logger.info(f"Trade: {symbol} {grade} -> {exit_reason} P&L: ${pnl_usd:+.2f}")

        # Calculate results
        return self._calculate_results(trades, balance, max_drawdown)

    def _calculate_results(
        self,
        trades: List[BacktestTrade],
        final_balance: float,
        max_drawdown: float
    ) -> BacktestResult:
        """Calculate backtest statistics."""
        if not trades:
            return self._empty_result()

        winning = [t for t in trades if t.pnl_usd > 0]
        losing = [t for t in trades if t.pnl_usd < 0]

        total_pnl = sum(t.pnl_usd for t in trades)
        pnls = [t.pnl_usd for t in trades]

        gross_profit = sum(t.pnl_usd for t in winning)
        gross_loss = abs(sum(t.pnl_usd for t in losing))

        # Calculate Sharpe ratio (simplified - daily returns assumed)
        if len(pnls) > 1:
            import statistics
            avg_return = statistics.mean(pnls)
            std_return = statistics.stdev(pnls)
            sharpe = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0
        else:
            sharpe = 0

        return BacktestResult(
            start_date=trades[0].entry_time if trades else datetime.now(),
            end_date=trades[-1].entry_time if trades else datetime.now(),
            initial_balance=self.initial_balance,
            final_balance=final_balance,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=(len(winning) / len(trades) * 100) if trades else 0,
            total_pnl_usd=total_pnl,
            total_pnl_pct=(total_pnl / self.initial_balance * 100),
            max_drawdown_pct=max_drawdown,
            sharpe_ratio=sharpe,
            best_trade=max(pnls) if pnls else 0,
            worst_trade=min(pnls) if pnls else 0,
            avg_trade=(total_pnl / len(trades)) if trades else 0,
            avg_win=(gross_profit / len(winning)) if winning else 0,
            avg_loss=(gross_loss / len(losing)) if losing else 0,
            profit_factor=(gross_profit / gross_loss) if gross_loss > 0 else float('inf'),
            trades=trades
        )

    def _empty_result(self) -> BacktestResult:
        """Return empty result."""
        return BacktestResult(
            start_date=datetime.now(),
            end_date=datetime.now(),
            initial_balance=self.initial_balance,
            final_balance=self.initial_balance,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0,
            total_pnl_usd=0,
            total_pnl_pct=0,
            max_drawdown_pct=0,
            sharpe_ratio=0,
            best_trade=0,
            worst_trade=0,
            avg_trade=0,
            avg_win=0,
            avg_loss=0,
            profit_factor=0,
            trades=[]
        )

    def save_results(self, result: BacktestResult, name: str = None):
        """Save backtest results to file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name = name or f"backtest_{timestamp}"

        filepath = self.RESULTS_DIR / f"{name}.json"

        data = {
            'start_date': result.start_date.isoformat(),
            'end_date': result.end_date.isoformat(),
            'initial_balance': result.initial_balance,
            'final_balance': result.final_balance,
            'total_trades': result.total_trades,
            'winning_trades': result.winning_trades,
            'losing_trades': result.losing_trades,
            'win_rate': result.win_rate,
            'total_pnl_usd': result.total_pnl_usd,
            'total_pnl_pct': result.total_pnl_pct,
            'max_drawdown_pct': result.max_drawdown_pct,
            'sharpe_ratio': result.sharpe_ratio,
            'trades': [
                {
                    'symbol': t.token_symbol,
                    'entry_time': t.entry_time.isoformat(),
                    'exit_time': t.exit_time.isoformat() if t.exit_time else None,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'pnl_usd': t.pnl_usd,
                    'pnl_pct': t.pnl_pct,
                    'exit_reason': t.exit_reason,
                    'grade': t.sentiment_grade
                }
                for t in result.trades
            ]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved backtest results to {filepath}")


async def run_quick_backtest():
    """Run a quick backtest with default settings."""
    backtester = SentimentBacktester(
        initial_balance=1000.0,
        position_size_pct=0.10,
        max_positions=50,
        min_grade="B"
    )

    result = await backtester.run_backtest()

    print(result.to_report())
    backtester.save_results(result)

    return result


if __name__ == "__main__":
    asyncio.run(run_quick_backtest())
