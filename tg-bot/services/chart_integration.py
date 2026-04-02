"""
Chart Integration with Treasury Dashboard

Seamlessly integrate chart generation with dashboard display.
"""

import asyncio
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from io import BytesIO

from telegram import InputMediaPhoto
from telegram.ext import ContextTypes

from .chart_generator import ChartGenerator

logger = logging.getLogger(__name__)


class ChartIntegration:
    """Integration layer for charts with Treasury Dashboard."""

    def __init__(self, trader_instance, dashboard):
        """
        Initialize chart integration.

        Args:
            trader_instance: TreasuryTrader or TradingEngine
            dashboard: TreasuryDashboard instance
        """
        self.trader = trader_instance
        self.dashboard = dashboard
        self.chart_gen = ChartGenerator()

    # ==================== DASHBOARD WITH CHARTS ====================

    async def send_dashboard_with_charts(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
    ) -> Dict[str, Any]:
        """
        Send dashboard with charts as album.

        Returns:
            Dict with message_ids of all sent messages
        """
        try:
            # Update position prices
            try:
                await self.trader.update_positions()
            except Exception as e:
                logger.warning(f"Failed to update positions: {e}")

            # Build text dashboard
            dashboard_text = self.dashboard.build_portfolio_dashboard(include_positions=True)

            # Send main dashboard text
            text_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=dashboard_text,
                parse_mode='HTML',
            )

            message_ids = {'text': text_msg.message_id}

            # Generate and send charts
            await asyncio.sleep(0.5)  # Rate limiting

            # Portfolio performance chart
            try:
                portfolio_chart = await self._generate_portfolio_chart_data()
                if portfolio_chart:
                    msg = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=portfolio_chart,
                        caption='<b>Portfolio Performance</b>',
                        parse_mode='HTML',
                    )
                    message_ids['portfolio'] = msg.message_id
                    await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"Failed to generate portfolio chart: {e}")

            # Position allocation chart
            try:
                allocation_chart = await self._generate_allocation_chart_data()
                if allocation_chart:
                    msg = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=allocation_chart,
                        caption='<b>Position Allocation</b>',
                        parse_mode='HTML',
                    )
                    message_ids['allocation'] = msg.message_id
                    await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"Failed to generate allocation chart: {e}")

            # Drawdown chart
            try:
                drawdown_chart = await self._generate_drawdown_chart_data()
                if drawdown_chart:
                    msg = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=drawdown_chart,
                        caption='<b>Drawdown Analysis</b>',
                        parse_mode='HTML',
                    )
                    message_ids['drawdown'] = msg.message_id
                    await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"Failed to generate drawdown chart: {e}")

            return message_ids

        except Exception as e:
            logger.error(f"Dashboard with charts error: {e}")
            raise

    # ==================== POSITION CHARTS ====================

    async def send_position_analysis(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        symbol: str,
    ) -> Dict[str, Any]:
        """
        Send detailed analysis for a single position.

        Includes:
        - Price action chart
        - Current metrics
        - Entry/exit levels
        """
        try:
            positions = self.trader.get_open_positions()
            position = next((p for p in positions if p.token_symbol == symbol), None)

            if not position:
                raise ValueError(f"Position {symbol} not found")

            # Build text info
            info_text = f"""
📊 <b>{symbol} Position Analysis</b>

<b>Entry Details:</b>
  • Price: <code>${position.entry_price:.6f}</code>
  • Time: {position.entry_time.strftime('%Y-%m-%d %H:%M')}
  • Size: <code>{position.amount:.2f} tokens</code>
  • Value: <code>${position.entry_price * position.amount:,.2f}</code>

<b>Current Status:</b>
  • Price: <code>${position.current_price:.6f}</code>
  • Value: <code>${position.current_value_usd:,.2f}</code>
  • P&L: <code>${position.unrealized_pnl_usd:+,.2f}</code> ({position.unrealized_pnl_pct:+.2f}%)
  • Duration: {self.dashboard._format_duration(datetime.utcnow() - position.entry_time)}

<b>Risk Management:</b>
  • TP: <code>${position.take_profit_price:.6f}</code> if set
  • SL: <code>${position.stop_loss_price:.6f}</code> if set
  • Risk/Reward: N/A

<i>Real-time monitoring active</i>
"""

            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=info_text,
                parse_mode='HTML',
            )

            message_ids = {'info': msg.message_id}

            # Generate price chart
            try:
                # TODO: Fetch historical price data
                price_chart = await self._generate_position_chart_data(symbol)
                if price_chart:
                    msg = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=price_chart,
                        caption=f'<b>{symbol} Price Action</b>',
                        parse_mode='HTML',
                    )
                    message_ids['chart'] = msg.message_id
            except Exception as e:
                logger.warning(f"Failed to generate position chart: {e}")

            return message_ids

        except Exception as e:
            logger.error(f"Position analysis error: {e}")
            raise

    # ==================== PERFORMANCE REPORTS ====================

    async def send_performance_report(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        period_days: int = 7,
    ) -> Dict[str, Any]:
        """Send comprehensive performance report with charts."""
        try:
            # Build text report
            report_text = self.dashboard.build_performance_report(period_days)

            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=report_text,
                parse_mode='HTML',
            )

            message_ids = {'report': msg.message_id}

            await asyncio.sleep(0.3)

            # Trade distribution chart
            try:
                trade_dist = await self._generate_trade_distribution_data()
                if trade_dist:
                    msg = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=trade_dist,
                        caption='<b>Trade P&L Distribution</b>',
                        parse_mode='HTML',
                    )
                    message_ids['trades'] = msg.message_id
                    await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"Failed to generate trade distribution: {e}")

            # Risk/return plot
            try:
                risk_return = await self._generate_risk_return_data()
                if risk_return:
                    msg = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=risk_return,
                        caption='<b>Risk/Return Profile</b>',
                        parse_mode='HTML',
                    )
                    message_ids['risk_return'] = msg.message_id
            except Exception as e:
                logger.warning(f"Failed to generate risk/return plot: {e}")

            return message_ids

        except Exception as e:
            logger.error(f"Performance report error: {e}")
            raise

    # ==================== SENTIMENT VISUALIZATION ====================

    async def send_sentiment_analysis(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
    ) -> Optional[int]:
        """Send sentiment analysis heatmap."""
        try:
            # TODO: Get sentiment data from aggregator
            sentiment_data = {
                'SOL': {'grok': 75, 'twitter': 68, 'news': 72},
                'BTC': {'grok': 82, 'twitter': 71, 'news': 78},
                'ETH': {'grok': 68, 'twitter': 65, 'news': 70},
            }

            # Generate heatmap
            heatmap = self.chart_gen.generate_sentiment_heatmap(
                symbols=list(sentiment_data.keys()),
                sentiment_scores=sentiment_data,
                time_period="24h",
            )

            msg = await context.bot.send_photo(
                chat_id=chat_id,
                photo=heatmap,
                caption='<b>Sentiment Analysis Heatmap</b>\n\n<i>Scores: 0-100 (Red=Bearish, Green=Bullish)</i>',
                parse_mode='HTML',
            )

            return msg.message_id

        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return None

    # ==================== CHART DATA GENERATORS ====================

    async def _generate_portfolio_chart_data(self) -> Optional[BytesIO]:
        """Generate portfolio performance chart data."""
        try:
            # TODO: Fetch actual portfolio history
            dates = [datetime.utcnow() - timedelta(days=i) for i in range(30, 0, -1)]
            values = [10000 + i * 150 for i in range(30)]

            return self.chart_gen.generate_portfolio_chart(values, dates)
        except Exception as e:
            logger.warning(f"Portfolio chart generation failed: {e}")
            return None

    async def _generate_allocation_chart_data(self) -> Optional[BytesIO]:
        """Generate position allocation chart."""
        try:
            positions = self.trader.get_open_positions()
            total_value = sum(p.current_value_usd for p in positions) if positions else 1

            allocation = {
                p.token_symbol: (p.current_value_usd / total_value * 100)
                for p in positions
            }

            if not allocation:
                return None

            return self.chart_gen.generate_position_allocation(allocation)
        except Exception as e:
            logger.warning(f"Allocation chart generation failed: {e}")
            return None

    async def _generate_drawdown_chart_data(self) -> Optional[BytesIO]:
        """Generate drawdown analysis chart."""
        try:
            # TODO: Fetch actual portfolio history
            dates = [datetime.utcnow() - timedelta(days=i) for i in range(30, 0, -1)]
            values = [10000 + i * 150 for i in range(30)]

            return self.chart_gen.generate_drawdown_chart(values, dates)
        except Exception as e:
            logger.warning(f"Drawdown chart generation failed: {e}")
            return None

    async def _generate_position_chart_data(self, symbol: str) -> Optional[BytesIO]:
        """Generate individual position price chart."""
        try:
            # TODO: Fetch price history for symbol
            times = [datetime.utcnow() - timedelta(hours=i) for i in range(24, 0, -1)]
            prices = [100 + i * 0.5 for i in range(24)]

            position = next((p for p in self.trader.get_open_positions() if p.token_symbol == symbol), None)
            if not position:
                return None

            return self.chart_gen.generate_price_chart(
                symbol=symbol,
                prices=prices,
                times=times,
                entry_price=position.entry_price,
                exit_price=position.take_profit_price,
            )
        except Exception as e:
            logger.warning(f"Position chart generation failed: {e}")
            return None

    async def _generate_trade_distribution_data(self) -> Optional[BytesIO]:
        """Generate trade P&L distribution chart."""
        try:
            # TODO: Fetch closed trades
            pnl_values = [100, 250, -50, 120, 300, -75, 85, 220, -30, 150]

            return self.chart_gen.generate_trade_distribution(pnl_values)
        except Exception as e:
            logger.warning(f"Trade distribution chart generation failed: {e}")
            return None

    async def _generate_risk_return_data(self) -> Optional[BytesIO]:
        """Generate risk/return scatter plot."""
        try:
            positions = self.trader.get_open_positions()
            if not positions:
                return None

            position_data = [
                {
                    'symbol': p.token_symbol,
                    'return': p.unrealized_pnl_pct,
                    'volatility': 20.0,  # TODO: Calculate actual volatility
                    'allocation': (p.current_value_usd / sum(pos.current_value_usd for pos in positions) * 100),
                }
                for p in positions
            ]

            return self.chart_gen.generate_risk_return_plot(position_data)
        except Exception as e:
            logger.warning(f"Risk/return chart generation failed: {e}")
            return None
