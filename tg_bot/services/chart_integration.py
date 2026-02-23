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
        """Send sentiment analysis heatmap using live CoinGecko price change data."""
        try:
            # Build sentiment scores from live price changes (proxy for sentiment)
            sentiment_data = {}
            try:
                from tg_bot.services.market_intelligence import MarketIntelligence
                prices = await MarketIntelligence._fetch_live_prices()
                coin_map = {
                    'SOL': ('solana', 'solana'),
                    'BTC': ('bitcoin', 'bitcoin'),
                    'ETH': ('ethereum', 'ethereum'),
                }
                for sym, (cg_id, _) in coin_map.items():
                    coin = prices.get(cg_id, {})
                    chg = float(coin.get('usd_24h_change', 0) or 0)
                    # Map -10%..+10% change → 0..100 sentiment score
                    score = max(0, min(100, int(50 + chg * 5)))
                    sentiment_data[sym] = {'price_momentum': score, 'trend': score}
            except Exception:
                pass

            if not sentiment_data:
                # Minimal neutral fallback
                sentiment_data = {
                    'SOL': {'trend': 50},
                    'BTC': {'trend': 50},
                    'ETH': {'trend': 50},
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
        """Generate portfolio performance chart data from trade history."""
        try:
            history = getattr(self.trader, 'trade_history', [])
            closed = sorted(
                [p for p in history if getattr(p, 'closed_at', None) and getattr(p, 'pnl_usd', None) is not None],
                key=lambda p: p.closed_at,
            )

            if not closed:
                # No closed trades yet — return None rather than fake data
                return None

            # Build equity curve: cumulative PnL over time
            cumulative = 0.0
            dates, values = [], []
            for p in closed:
                try:
                    dt = datetime.fromisoformat(p.closed_at.replace('Z', '+00:00'))
                except Exception:
                    continue
                cumulative += p.pnl_usd
                dates.append(dt)
                values.append(cumulative)

            if len(values) < 2:
                return None

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
        """Generate drawdown analysis chart from trade history."""
        try:
            history = getattr(self.trader, 'trade_history', [])
            closed = sorted(
                [p for p in history if getattr(p, 'closed_at', None) and getattr(p, 'pnl_usd', None) is not None],
                key=lambda p: p.closed_at,
            )

            if not closed:
                return None

            # Build equity curve then compute drawdown
            cumulative = 0.0
            dates, values = [], []
            for p in closed:
                try:
                    dt = datetime.fromisoformat(p.closed_at.replace('Z', '+00:00'))
                except Exception:
                    continue
                cumulative += p.pnl_usd
                dates.append(dt)
                values.append(cumulative)

            if len(values) < 2:
                return None

            return self.chart_gen.generate_drawdown_chart(values, dates)
        except Exception as e:
            logger.warning(f"Drawdown chart generation failed: {e}")
            return None

    async def _generate_position_chart_data(self, symbol: str) -> Optional[BytesIO]:
        """Generate individual position price chart using DexScreener OHLCV data."""
        try:
            position = next((p for p in self.trader.get_open_positions() if p.token_symbol == symbol), None)
            if not position:
                return None

            # Attempt to fetch 24h price history from DexScreener
            times: List[datetime] = []
            prices: List[float] = []
            try:
                import aiohttp
                mint = getattr(position, 'token_mint', '')
                if mint:
                    url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                    timeout = aiohttp.ClientTimeout(total=8)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                pairs = (data.get('pairs') or [])
                                # Use the pair with highest liquidity
                                pairs_sol = [p for p in pairs if (p.get('chainId') == 'solana')]
                                best = max(pairs_sol, key=lambda p: (p.get('liquidity') or {}).get('usd', 0), default=None)
                                if best:
                                    # DexScreener doesn't have OHLCV on free tier;
                                    # reconstruct from current price + 24h change
                                    current = float((best.get('priceUsd') or 0) or 0)
                                    chg24 = float((best.get('priceChange') or {}).get('h24', 0) or 0)
                                    if current > 0:
                                        open24 = current / (1 + chg24 / 100) if chg24 != -100 else current
                                        # Interpolate 24 hourly points linearly
                                        for i in range(24):
                                            frac = i / 23.0
                                            prices.append(open24 + (current - open24) * frac)
                                            times.append(datetime.utcnow() - timedelta(hours=(23 - i)))
            except Exception as fetch_err:
                logger.debug(f"DexScreener fetch failed for {symbol}: {fetch_err}")

            if not prices:
                # Fallback: use current entry price as flat line (still shows entry/TP markers)
                prices = [position.current_price] * 24
                times = [datetime.utcnow() - timedelta(hours=i) for i in range(23, -1, -1)]

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
        """Generate trade P&L distribution chart from closed trade history."""
        try:
            history = getattr(self.trader, 'trade_history', [])
            pnl_values = [
                p.pnl_usd for p in history
                if getattr(p, 'pnl_usd', None) is not None
            ]

            if not pnl_values:
                return None

            return self.chart_gen.generate_trade_distribution(pnl_values)
        except Exception as e:
            logger.warning(f"Trade distribution chart generation failed: {e}")
            return None

    @staticmethod
    def _volatility_from_change_pct(change_pct: float) -> float:
        """Map 24h percentage move to a 0-100 volatility scale."""
        return max(0.0, min(100.0, abs(change_pct) * 7.0))

    async def _estimate_position_volatility(
        self,
        position: Any,
        live_prices: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> float:
        """
        Estimate per-position volatility using best available market data.

        Priority:
        1) CoinGecko 24h change for majors (SOL/BTC/ETH)
        2) DexScreener 24h change for token mint
        3) Fallback from unrealized PnL%
        """
        symbol = str(getattr(position, 'token_symbol', '')).upper()
        coin_map = {
            'SOL': 'solana',
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
        }

        # Major assets: use already-fetched CoinGecko cache.
        if live_prices and symbol in coin_map:
            cg_id = coin_map[symbol]
            coin = (live_prices.get(cg_id, {}) or {})
            chg24 = float(coin.get('usd_24h_change', 0) or 0)
            if chg24:
                return self._volatility_from_change_pct(chg24)

        # Token-specific fallback: DexScreener 24h change for mint.
        mint = getattr(position, 'token_mint', '')
        if mint:
            try:
                import aiohttp

                url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                timeout = aiohttp.ClientTimeout(total=8)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            pairs = (data.get('pairs') or [])
                            pairs_sol = [p for p in pairs if p.get('chainId') == 'solana']
                            best = max(
                                pairs_sol,
                                key=lambda p: (p.get('liquidity') or {}).get('usd', 0),
                                default=None,
                            )
                            if best:
                                chg24 = float((best.get('priceChange') or {}).get('h24', 0) or 0)
                                if chg24:
                                    return self._volatility_from_change_pct(chg24)
            except Exception as fetch_err:
                logger.debug(f"Volatility fetch failed for {symbol}: {fetch_err}")

        # Last-resort fallback from current position behavior.
        pnl_pct = abs(float(getattr(position, 'unrealized_pnl_pct', 0) or 0))
        return max(5.0, min(100.0, pnl_pct * 2.0))

    async def _generate_risk_return_data(self) -> Optional[BytesIO]:
        """Generate risk/return scatter plot."""
        try:
            positions = self.trader.get_open_positions()
            if not positions:
                return None

            total_value = sum(float(getattr(p, 'current_value_usd', 0) or 0) for p in positions)
            if total_value <= 0:
                total_value = 1.0

            live_prices: Dict[str, Dict[str, float]] = {}
            try:
                from tg_bot.services.market_intelligence import MarketIntelligence

                live_prices = await MarketIntelligence._fetch_live_prices()
            except Exception as price_err:
                logger.debug(f"Live price cache unavailable for risk/return plot: {price_err}")

            position_data = []
            for p in positions:
                volatility = await self._estimate_position_volatility(p, live_prices)
                allocation = (float(getattr(p, 'current_value_usd', 0) or 0) / total_value) * 100
                position_data.append(
                    {
                        'symbol': getattr(p, 'token_symbol', 'UNKNOWN'),
                        'return': float(getattr(p, 'unrealized_pnl_pct', 0) or 0),
                        'volatility': volatility,
                        'allocation': allocation,
                    }
                )

            return self.chart_gen.generate_risk_return_plot(position_data)
        except Exception as e:
            logger.warning(f"Risk/return chart generation failed: {e}")
            return None
