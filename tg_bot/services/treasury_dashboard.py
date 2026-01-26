"""
Stunning Telegram Treasury Dashboard

Features:
- Beautiful real-time portfolio metrics
- Comprehensive position analytics
- Trading history with detailed stats
- Performance reports with trend analysis
- Live market data integration
- Professional formatting with emojis and Unicode art
- Inline keyboard controls for easy navigation
- Auto-refreshing dashboard with live updates
"""

import asyncio
import logging
import statistics
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PerformanceTrend(Enum):
    """Performance trend indicators."""
    STRONG_UP = "📈📈 Strong Uptrend"
    UP = "📈 Uptrend"
    STABLE = "➡️ Stable"
    DOWN = "📉 Downtrend"
    STRONG_DOWN = "📉📉 Strong Downtrend"


@dataclass
class TrendData:
    """Trend analysis data."""
    current_pnl: float
    period_return: float  # Period return %
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float  # % of profitable trades
    avg_trade_duration: float  # hours


class TreasuryDashboard:
    """
    Professional Telegram dashboard for Treasury Bot.

    Generates beautifully formatted messages with:
    - Portfolio metrics (balance, PnL, ROI)
    - Position breakdown (open positions, entry/exit)
    - Performance analytics (win rate, Sharpe, drawdown)
    - Trading history (recent trades, cumulative returns)
    - Market insights (sentiment, liquidity, volatility)
    """

    # Unicode art borders and decorators
    BORDER_TOP = "╔═════════════════════════════════════╗"
    BORDER_MID = "╠═════════════════════════════════════╣"
    BORDER_BOT = "╚═════════════════════════════════════╝"
    SECTION_DIVIDER = "─" * 35

    # Performance indicators
    PERFECT_WIN_RATE = 75.0  # 75%+ win rate = 🏆
    GOOD_WIN_RATE = 55.0     # 55%+ = ✅

    EMOJI = {
        # Status indicators
        'active': '🟢',
        'paused': '🟡',
        'error': '🔴',
        'neutral': '⚪',

        # Market direction
        'bull': '🐮',
        'bear': '🐻',
        'neutral_market': '⏸️',

        # Performance
        'profit': '💰',
        'loss': '💸',
        'breakeven': '🔄',
        'win': '✅',
        'loss_cross': '❌',

        # Positions
        'long': '📈',
        'short': '📉',
        'closed': '🏁',
        'pending': '⏳',

        # UI elements
        'portfolio': '💼',
        'positions': '📊',
        'trades': '💹',
        'report': '📋',
        'settings': '⚙️',
        'refresh': '🔄',
        'chart': '📈',
        'warning': '⚠️',
        'info': 'ℹ️',
        'rocket': '🚀',
        'target': '🎯',
        'fire': '🔥',
        'crown': '👑',
        'diamond': '💎',
        'star': '⭐',
        'sunburst': '✨',
        'energy': '⚡',
    }

    def __init__(self, trader_instance):
        """
        Initialize dashboard.

        Args:
            trader_instance: TreasuryTrader or TradingEngine instance
        """
        self.trader = trader_instance

    # ==================== PORTFOLIO DASHBOARD ====================

    def build_portfolio_dashboard(self, include_positions: bool = True) -> str:
        """
        Build stunning portfolio dashboard.

        Returns:
            Formatted Telegram message (HTML)
        """
        positions = self.trader.get_open_positions() if include_positions else []

        # Header with status
        status = self._get_status_indicator()
        dashboard = f"""{self.EMOJI['portfolio']} <b>JARVIS TREASURY DASHBOARD</b> {self.EMOJI['crown']}
{status}

{self.SECTION_DIVIDER}
<b>PORTFOLIO METRICS</b>
{self.SECTION_DIVIDER}

"""

        # Portfolio overview
        portfolio_data = self._get_portfolio_overview()
        dashboard += f"""<b>Balance:</b> <code>${portfolio_data['total_balance']:,.2f}</code>
<b>Deployed:</b> <code>${portfolio_data['deployed']:,.2f}</code> ({portfolio_data['deployed_pct']:.1f}%)
<b>Available:</b> <code>${portfolio_data['available']:,.2f}</code> ({portfolio_data['available_pct']:.1f}%)

"""

        # PnL Section
        pnl_data = self._get_pnl_summary()
        pnl_emoji = self.EMOJI['profit'] if pnl_data['total_pnl'] >= 0 else self.EMOJI['loss']

        dashboard += f"""<b>Performance:</b>
  {pnl_emoji} <b>Total P&L:</b> <code>${pnl_data['total_pnl']:+,.2f}</code> ({pnl_data['total_pnl_pct']:+.2f}%)
  {self.EMOJI['star']} <b>24h Return:</b> <code>{pnl_data['return_24h']:+.2f}%</code>
  {self.EMOJI['chart']} <b>7d Return:</b> <code>{pnl_data['return_7d']:+.2f}%</code>

"""

        # Risk metrics
        risk_data = self._get_risk_metrics()
        dashboard += f"""<b>Risk Profile:</b>
  <b>Max Drawdown:</b> <code>{risk_data['max_drawdown']:.2f}%</code>
  <b>Volatility:</b> <code>{risk_data['volatility']:.2f}%</code>
  <b>Sharpe Ratio:</b> <code>{risk_data['sharpe_ratio']:.2f}</code>

"""

        # Open positions summary
        if positions:
            dashboard += f"""{self.SECTION_DIVIDER}
<b>OPEN POSITIONS ({len(positions)})</b>
{self.SECTION_DIVIDER}

"""
            for pos in positions[:5]:  # Show top 5
                pos_line = self._format_position_summary(pos)
                dashboard += pos_line + "\n"

            if len(positions) > 5:
                dashboard += f"\n<i>... and {len(positions) - 5} more positions</i>\n"

        dashboard += f"""\n{self.SECTION_DIVIDER}
<b>TRADING STATS</b>
{self.SECTION_DIVIDER}

"""

        # Trading statistics
        stats = self._get_trading_statistics()
        dashboard += f"""<b>Total Trades:</b> <code>{stats['total_trades']}</code>
  <b>Win Rate:</b> <code>{stats['win_rate']:.1f}%</code> {self._get_win_rate_emoji(stats['win_rate'])}
  <b>Avg Win:</b> <code>{stats['avg_win']:+.2f}%</code>
  <b>Avg Loss:</b> <code>{stats['avg_loss']:+.2f}%</code>
  <b>Profit Factor:</b> <code>{stats['profit_factor']:.2f}</code>

"""

        dashboard += f"<i>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"

        return dashboard

    # ==================== POSITION VIEWS ====================

    def build_detailed_positions(self) -> str:
        """Build detailed view of all open positions."""
        positions = self.trader.get_open_positions()

        if not positions:
            return f"{self.EMOJI['neutral_market']} <b>No open positions</b>"

        msg = f"""{self.EMOJI['positions']} <b>OPEN POSITIONS</b> ({len(positions)})
{self.SECTION_DIVIDER}

"""

        total_exposure = sum(p.current_value_usd for p in positions) if positions else 0

        for i, pos in enumerate(positions, 1):
            pnl_emoji = self.EMOJI['profit'] if pos.unrealized_pnl_usd >= 0 else self.EMOJI['loss']
            exposure_pct = (pos.current_value_usd / total_exposure * 100) if total_exposure > 0 else 0

            msg += f"""<b>{i}. {pos.token_symbol}</b>
  <b>Entry:</b> <code>${pos.entry_price:.6f}</code> • <b>Current:</b> <code>${pos.current_price:.6f}</code>
  {pnl_emoji} <b>P&L:</b> <code>${pos.unrealized_pnl_usd:+,.2f}</code> ({pos.unrealized_pnl_pct:+.2f}%)
  <b>Size:</b> <code>{pos.amount:.2f} tokens</code> • <b>Value:</b> <code>${pos.current_value_usd:,.2f}</code> ({exposure_pct:.1f}%)
  <b>Entry:</b> {pos.entry_time.strftime('%H:%M %Y-%m-%d')} • <b>Hold:</b> {self._format_duration(datetime.utcnow() - pos.entry_time)}
"""

            if pos.take_profit_price:
                distance_tp = ((pos.take_profit_price - pos.current_price) / pos.current_price * 100)
                msg += f"  <b>TP:</b> <code>${pos.take_profit_price:.6f}</code> ({distance_tp:+.1f}%)"

            if pos.stop_loss_price:
                distance_sl = ((pos.stop_loss_price - pos.current_price) / pos.current_price * 100)
                msg += f" • <b>SL:</b> <code>${pos.stop_loss_price:.6f}</code> ({distance_sl:+.1f}%)"

            msg += "\n\n"

        return msg

    # ==================== PERFORMANCE REPORTS ====================

    def build_performance_report(self, period_days: int = 7) -> str:
        """Build comprehensive performance report."""
        report_data = self._get_period_performance(period_days)
        trend = self._determine_trend(report_data)

        msg = f"""{self.EMOJI['report']} <b>PERFORMANCE REPORT</b> ({period_days}d)
{self.SECTION_DIVIDER}

"""

        # Trend indicator
        msg += f"<b>Trend:</b> {trend.value}\n\n"

        # Returns
        msg += f"""<b>Returns:</b>
  <b>Period Return:</b> <code>{report_data['period_return']:+.2f}%</code>
  <b>Annualized:</b> <code>{report_data['annualized_return']:+.2f}%</code>
  <b>Best Day:</b> <code>{report_data['best_day']:+.2f}%</code>
  <b>Worst Day:</b> <code>{report_data['worst_day']:+.2f}%</code>

"""

        # Risk metrics
        msg += f"""<b>Risk Metrics:</b>
  <b>Volatility:</b> <code>{report_data['volatility']:.2f}%</code>
  <b>Max Drawdown:</b> <code>{report_data['max_drawdown']:.2f}%</code>
  <b>Sharpe Ratio:</b> <code>{report_data['sharpe_ratio']:.2f}</code>
  <b>Sortino Ratio:</b> <code>{report_data['sortino_ratio']:.2f}</code>

"""

        # Trade statistics
        msg += f"""<b>Trade Stats:</b>
  <b>Trades:</b> <code>{report_data['total_trades']}</code>
  <b>Win Rate:</b> <code>{report_data['win_rate']:.1f}%</code> {self._get_win_rate_emoji(report_data['win_rate'])}
  <b>Profit Factor:</b> <code>{report_data['profit_factor']:.2f}</code>
  <b>Avg Duration:</b> <code>{report_data['avg_trade_duration']:.1f}h</code>

"""

        msg += f"<i>Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"

        return msg

    # ==================== TRADE HISTORY ====================

    def build_recent_trades(self, limit: int = 10) -> str:
        """Build recent trade history."""
        trades = self._get_recent_trades(limit)

        if not trades:
            return f"{self.EMOJI['neutral_market']} <b>No trade history</b>"

        msg = f"""{self.EMOJI['trades']} <b>RECENT TRADES</b> (Last {limit})
{self.SECTION_DIVIDER}

"""

        cumulative_pnl = 0
        for i, trade in enumerate(trades, 1):
            cumulative_pnl += trade['pnl']
            status_emoji = self.EMOJI['win'] if trade['pnl'] >= 0 else self.EMOJI['loss_cross']

            msg += f"""<b>{i}.</b> {status_emoji} {trade['symbol']}
  <b>Entry:</b> <code>${trade['entry_price']:.6f}</code> → <b>Exit:</b> <code>${trade['exit_price']:.6f}</code>
  <b>P&L:</b> <code>${trade['pnl']:+,.2f}</code> ({trade['pnl_pct']:+.2f}%)
  <b>Duration:</b> {self._format_duration(trade['duration'])} • <b>Time:</b> {trade['exit_time'].strftime('%Y-%m-%d %H:%M')}

"""

        msg += f"\n<b>Cumulative P&L:</b> <code>${cumulative_pnl:+,.2f}</code>"

        return msg

    # ==================== HELPER METHODS ====================

    def _get_status_indicator(self) -> str:
        """Get status indicator line."""
        is_live = not getattr(self.trader, 'dry_run', False)
        status = "🟢 LIVE" if is_live else "🟡 DRY RUN"
        max_pos = getattr(self.trader, 'max_positions', 50)
        positions = len(self.trader.get_open_positions())

        return f"<code>{status} | Positions: {positions}/{max_pos}</code>"

    def _get_portfolio_overview(self) -> Dict[str, float]:
        """Get portfolio overview metrics."""
        balance = getattr(self.trader, 'get_balance', lambda: {'total': 10000})()
        total = balance.get('total', 10000)

        positions = self.trader.get_open_positions()
        deployed = sum(p.current_value_usd for p in positions) if positions else 0
        available = total - deployed

        return {
            'total_balance': total,
            'deployed': deployed,
            'deployed_pct': (deployed / total * 100) if total > 0 else 0,
            'available': available,
            'available_pct': (available / total * 100) if total > 0 else 0,
        }

    def _get_pnl_summary(self) -> Dict[str, float]:
        """Get PnL summary."""
        positions = self.trader.get_open_positions()
        unrealized = sum(p.unrealized_pnl_usd for p in positions) if positions else 0

        # Get realized PnL from trade history
        realized = self._get_realized_pnl()
        total_pnl = realized + unrealized

        balance = self._get_portfolio_overview()['total_balance']
        total_pnl_pct = (total_pnl / balance * 100) if balance > 0 else 0

        # Calculate 24h and 7d returns from trade history
        return_24h = self._calculate_period_return(1)
        return_7d = self._calculate_period_return(7)

        return {
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'return_24h': return_24h,
            'return_7d': return_7d,
        }

    def _calculate_period_return(self, days: int) -> float:
        """Calculate return percentage for a given period."""
        trade_history = getattr(self.trader, 'trade_history', [])
        if not trade_history:
            return 0.0

        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)

        period_pnl = 0.0
        period_volume = 0.0

        for trade in trade_history:
            # Parse close time
            closed_at = getattr(trade, 'closed_at', None)
            if closed_at is None:
                continue

            if isinstance(closed_at, str):
                try:
                    close_time = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    continue
            elif isinstance(closed_at, datetime):
                close_time = closed_at
            else:
                continue

            # Only include trades within the period
            if close_time.replace(tzinfo=None) >= cutoff:
                pnl = getattr(trade, 'pnl_usd', None)
                if pnl is None:
                    pnl = getattr(trade, 'realized_pnl', 0.0)
                period_pnl += pnl or 0.0

                volume = getattr(trade, 'amount_usd', 0.0)
                period_volume += volume or 0.0

        if period_volume == 0:
            return 0.0

        return (period_pnl / period_volume) * 100

    def _get_risk_metrics(self) -> Dict[str, float]:
        """Get risk metrics."""
        trade_history = getattr(self.trader, 'trade_history', [])

        if not trade_history:
            return {
                'max_drawdown': 0.0,
                'volatility': 0.0,
                'sharpe_ratio': 0.0,
            }

        # Calculate returns from each trade
        returns = []
        for trade in trade_history:
            pnl_pct = getattr(trade, 'pnl_pct', None)
            if pnl_pct is None:
                entry_price = getattr(trade, 'entry_price', 0)
                exit_price = getattr(trade, 'exit_price', getattr(trade, 'current_price', 0))
                if entry_price > 0:
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                else:
                    pnl_pct = 0.0
            returns.append(pnl_pct or 0.0)

        if len(returns) < 2:
            return {
                'max_drawdown': 0.0,
                'volatility': 0.0,
                'sharpe_ratio': 0.0,
            }

        # Calculate max drawdown from cumulative returns
        max_drawdown = self._calculate_max_drawdown(returns)

        # Calculate volatility (standard deviation of returns)
        try:
            volatility = statistics.stdev(returns)
        except statistics.StatisticsError:
            volatility = 0.0

        # Calculate Sharpe ratio (assuming 2% risk-free rate annualized)
        sharpe_ratio = self._calculate_sharpe_ratio(returns, risk_free_rate=0.02)

        return {
            'max_drawdown': max_drawdown,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
        }

    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown from a series of returns."""
        if not returns:
            return 0.0

        # Calculate cumulative returns
        cumulative = []
        running_total = 0.0
        for r in returns:
            running_total += r
            cumulative.append(running_total)

        if len(cumulative) < 2:
            return 0.0

        # Find max drawdown
        peak = cumulative[0]
        max_dd = 0.0

        for value in cumulative:
            if value > peak:
                peak = value

            if peak != 0:
                drawdown = ((peak - value) / abs(peak)) * 100
                max_dd = max(max_dd, drawdown)

        return max_dd

    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio from returns."""
        if len(returns) < 2:
            return 0.0

        try:
            avg_return = statistics.mean(returns)
            std_dev = statistics.stdev(returns)
        except statistics.StatisticsError:
            return 0.0

        if std_dev == 0:
            return 0.0

        # Convert risk-free rate to per-trade basis (simplified)
        rf_per_trade = risk_free_rate * 100 / 365  # Daily risk-free rate in %

        # Sharpe ratio = (avg return - rf) / std_dev
        sharpe = (avg_return - rf_per_trade) / std_dev

        return sharpe

    def _get_trading_statistics(self) -> Dict[str, Any]:
        """Get trading statistics."""
        trade_history = getattr(self.trader, 'trade_history', [])

        if not trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
            }

        total_trades = len(trade_history)
        wins = []
        losses = []

        for trade in trade_history:
            pnl = getattr(trade, 'pnl_usd', None)
            if pnl is None:
                pnl = getattr(trade, 'realized_pnl', 0.0)
            pnl = pnl or 0.0

            pnl_pct = getattr(trade, 'pnl_pct', None)
            if pnl_pct is None:
                entry_price = getattr(trade, 'entry_price', 0)
                exit_price = getattr(trade, 'exit_price', getattr(trade, 'current_price', 0))
                if entry_price > 0:
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                else:
                    pnl_pct = 0.0
            pnl_pct = pnl_pct or 0.0

            if pnl > 0:
                wins.append({'pnl': pnl, 'pnl_pct': pnl_pct})
            elif pnl < 0:
                losses.append({'pnl': pnl, 'pnl_pct': pnl_pct})

        # Calculate win rate
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0.0

        # Calculate average win percentage
        avg_win = 0.0
        if wins:
            avg_win = sum(w['pnl_pct'] for w in wins) / len(wins)

        # Calculate average loss percentage
        avg_loss = 0.0
        if losses:
            avg_loss = sum(l['pnl_pct'] for l in losses) / len(losses)

        # Calculate profit factor (gross wins / gross losses)
        total_wins = sum(w['pnl'] for w in wins)
        total_losses = abs(sum(l['pnl'] for l in losses))
        profit_factor = 0.0
        if total_losses > 0:
            profit_factor = total_wins / total_losses
        elif total_wins > 0:
            profit_factor = float('inf')

        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor if profit_factor != float('inf') else 999.99,
        }

    def _format_position_summary(self, pos) -> str:
        """Format single position summary line."""
        pnl_emoji = self.EMOJI['profit'] if pos.unrealized_pnl_pct >= 0 else self.EMOJI['loss']
        return (
            f"  {pnl_emoji} <b>{pos.token_symbol}</b>: "
            f"<code>${pos.current_value_usd:,.0f}</code> "
            f"({pos.unrealized_pnl_pct:+.1f}%)"
        )

    def _get_win_rate_emoji(self, win_rate: float) -> str:
        """Get win rate emoji."""
        if win_rate >= self.PERFECT_WIN_RATE:
            return "🏆"
        elif win_rate >= self.GOOD_WIN_RATE:
            return "✅"
        elif win_rate >= 50:
            return "➖"
        else:
            return "📉"

    def _format_duration(self, duration: timedelta) -> str:
        """Format duration nicely."""
        total_seconds = int(duration.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def _determine_trend(self, data: Dict) -> PerformanceTrend:
        """Determine performance trend."""
        ret = data['period_return']
        dd = abs(data['max_drawdown'])

        if ret > 15 and dd < 5:
            return PerformanceTrend.STRONG_UP
        elif ret > 5 and dd < 10:
            return PerformanceTrend.UP
        elif -5 <= ret <= 5 and dd < 10:
            return PerformanceTrend.STABLE
        elif ret < -5 and dd > 10:
            return PerformanceTrend.DOWN
        else:
            return PerformanceTrend.STRONG_DOWN

    def _get_period_performance(self, days: int) -> Dict[str, Any]:
        """Get performance for a period."""
        trade_history = getattr(self.trader, 'trade_history', [])

        if not trade_history:
            return {
                'period_return': 0.0,
                'annualized_return': 0.0,
                'best_day': 0.0,
                'worst_day': 0.0,
                'volatility': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'avg_trade_duration': 0.0,
            }

        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)

        # Filter trades within the period
        period_trades = []
        for trade in trade_history:
            closed_at = getattr(trade, 'closed_at', None)
            if closed_at is None:
                continue

            if isinstance(closed_at, str):
                try:
                    close_time = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    continue
            elif isinstance(closed_at, datetime):
                close_time = closed_at
            else:
                continue

            if close_time.replace(tzinfo=None) >= cutoff:
                period_trades.append(trade)

        if not period_trades:
            return {
                'period_return': 0.0,
                'annualized_return': 0.0,
                'best_day': 0.0,
                'worst_day': 0.0,
                'volatility': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'avg_trade_duration': 0.0,
            }

        # Calculate returns for each trade
        returns = []
        durations = []
        daily_returns = {}  # Group returns by date

        for trade in period_trades:
            pnl_pct = getattr(trade, 'pnl_pct', None)
            if pnl_pct is None:
                entry_price = getattr(trade, 'entry_price', 0)
                exit_price = getattr(trade, 'exit_price', getattr(trade, 'current_price', 0))
                if entry_price > 0:
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                else:
                    pnl_pct = 0.0
            returns.append(pnl_pct or 0.0)

            # Calculate duration
            opened_at = getattr(trade, 'opened_at', None)
            if opened_at is None:
                opened_at = getattr(trade, 'entry_time', None)
            closed_at = getattr(trade, 'closed_at', None)

            if opened_at and closed_at:
                if isinstance(opened_at, str):
                    try:
                        entry_time = datetime.fromisoformat(opened_at.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        entry_time = None
                elif isinstance(opened_at, datetime):
                    entry_time = opened_at
                else:
                    entry_time = None

                if isinstance(closed_at, str):
                    try:
                        exit_time = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        exit_time = None
                elif isinstance(closed_at, datetime):
                    exit_time = closed_at
                else:
                    exit_time = None

                if entry_time and exit_time:
                    duration_hours = (exit_time - entry_time).total_seconds() / 3600
                    durations.append(duration_hours)

                    # Group by date for daily returns
                    date_key = exit_time.date().isoformat()
                    if date_key not in daily_returns:
                        daily_returns[date_key] = []
                    daily_returns[date_key].append(pnl_pct or 0.0)

        # Calculate period return
        period_return = sum(returns) if returns else 0.0

        # Calculate annualized return
        if days > 0 and period_return != 0:
            annualized_return = ((1 + period_return / 100) ** (365 / days) - 1) * 100
        else:
            annualized_return = 0.0

        # Calculate best/worst day
        if daily_returns:
            daily_totals = [sum(v) for v in daily_returns.values()]
            best_day = max(daily_totals) if daily_totals else 0.0
            worst_day = min(daily_totals) if daily_totals else 0.0
        else:
            best_day = max(returns) if returns else 0.0
            worst_day = min(returns) if returns else 0.0

        # Calculate volatility
        try:
            volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0
        except statistics.StatisticsError:
            volatility = 0.0

        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(returns)

        # Calculate Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio(returns)

        # Calculate Sortino ratio (uses only downside deviation)
        sortino_ratio = self._calculate_sortino_ratio(returns)

        # Calculate trading statistics
        total_trades = len(period_trades)
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]

        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0.0

        # Profit factor
        win_pnl = sum(getattr(t, 'pnl_usd', 0) or getattr(t, 'realized_pnl', 0) or 0 for t in period_trades if (getattr(t, 'pnl_usd', 0) or getattr(t, 'realized_pnl', 0) or 0) > 0)
        loss_pnl = abs(sum(getattr(t, 'pnl_usd', 0) or getattr(t, 'realized_pnl', 0) or 0 for t in period_trades if (getattr(t, 'pnl_usd', 0) or getattr(t, 'realized_pnl', 0) or 0) < 0))
        profit_factor = (win_pnl / loss_pnl) if loss_pnl > 0 else (999.99 if win_pnl > 0 else 0.0)

        # Average trade duration
        avg_trade_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            'period_return': period_return,
            'annualized_return': annualized_return,
            'best_day': best_day,
            'worst_day': worst_day,
            'volatility': volatility,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_trade_duration': avg_trade_duration,
        }

    def _calculate_sortino_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio using only downside deviation."""
        if len(returns) < 2:
            return 0.0

        try:
            avg_return = statistics.mean(returns)
        except statistics.StatisticsError:
            return 0.0

        # Calculate downside deviation (only negative returns)
        rf_per_trade = risk_free_rate * 100 / 365
        downside_returns = [min(0, r - rf_per_trade) ** 2 for r in returns]

        if not downside_returns or sum(downside_returns) == 0:
            return 0.0

        downside_dev = (sum(downside_returns) / len(downside_returns)) ** 0.5

        if downside_dev == 0:
            return 0.0

        sortino = (avg_return - rf_per_trade) / downside_dev
        return sortino

    def _get_realized_pnl(self) -> float:
        """Get realized PnL from closed trades."""
        trade_history = getattr(self.trader, 'trade_history', [])
        if not trade_history:
            return 0.0

        realized = 0.0
        for trade in trade_history:
            # Support different attribute names for PnL
            pnl = getattr(trade, 'pnl_usd', None)
            if pnl is None:
                pnl = getattr(trade, 'realized_pnl', 0.0)
            realized += pnl or 0.0

        return realized

    def _get_recent_trades(self, limit: int) -> List[Dict]:
        """Get recent closed trades."""
        trade_history = getattr(self.trader, 'trade_history', [])
        if not trade_history:
            return []

        # Convert trades to dictionaries and sort by exit time
        trades = []
        for trade in trade_history:
            # Parse exit time
            closed_at = getattr(trade, 'closed_at', None)
            if closed_at is None:
                continue

            if isinstance(closed_at, str):
                try:
                    exit_time = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    exit_time = datetime.utcnow()
            elif isinstance(closed_at, datetime):
                exit_time = closed_at
            else:
                exit_time = datetime.utcnow()

            # Parse entry time for duration
            opened_at = getattr(trade, 'opened_at', None)
            if opened_at is None:
                opened_at = getattr(trade, 'entry_time', None)

            if isinstance(opened_at, str):
                try:
                    entry_time = datetime.fromisoformat(opened_at.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    entry_time = exit_time - timedelta(hours=1)
            elif isinstance(opened_at, datetime):
                entry_time = opened_at
            else:
                entry_time = exit_time - timedelta(hours=1)

            duration = exit_time - entry_time

            # Get PnL values
            pnl = getattr(trade, 'pnl_usd', None)
            if pnl is None:
                pnl = getattr(trade, 'realized_pnl', 0.0)

            pnl_pct = getattr(trade, 'pnl_pct', None)
            if pnl_pct is None:
                pnl_pct = getattr(trade, 'realized_pnl_pct', 0.0)

            trades.append({
                'symbol': getattr(trade, 'token_symbol', 'UNKNOWN'),
                'entry_price': getattr(trade, 'entry_price', 0.0),
                'exit_price': getattr(trade, 'exit_price', getattr(trade, 'current_price', 0.0)),
                'pnl': pnl or 0.0,
                'pnl_pct': pnl_pct or 0.0,
                'duration': duration,
                'exit_time': exit_time,
            })

        # Sort by exit time (most recent first) and limit
        trades.sort(key=lambda t: t['exit_time'], reverse=True)
        return trades[:limit]
