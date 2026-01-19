"""
Arbitrage Strategy - Identifies price discrepancies across exchanges.

Detects opportunities to buy low on one exchange and sell high on another.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class PricePoint:
    """Price data from an exchange."""
    exchange: str
    price: float
    timestamp: datetime
    liquidity: float = 0.0  # Available liquidity in USD
    volume_24h: float = 0.0  # 24h volume in USD


@dataclass
class ArbitrageConfig:
    """Configuration for arbitrage strategy."""
    min_spread_pct: float = 2.0  # Minimum profitable spread
    max_latency_seconds: int = 30  # Max allowed price latency
    min_liquidity_usd: float = 10000.0  # Minimum liquidity required
    max_position_size_usd: float = 5000.0  # Max arb position size
    fee_per_trade_pct: float = 0.5  # Trading fee per leg
    slippage_pct: float = 1.0  # Expected slippage


class ArbitrageStrategy:
    """Implements arbitrage opportunity detection."""

    def __init__(self, config: Optional[ArbitrageConfig] = None):
        """Initialize arbitrage strategy.

        Args:
            config: Strategy configuration
        """
        self.config = config or ArbitrageConfig()
        self.exchange_prices = {}  # symbol -> {exchange -> PricePoint}
        self.opportunities = {}  # symbol -> list of opportunities
        self.executed_arbs = []  # History of executed arbitrage trades

    def update_price(self, symbol: str, exchange: str, price: float,
                     liquidity: float = 0.0, volume_24h: float = 0.0) -> None:
        """Update price data from an exchange.

        Args:
            symbol: Token symbol
            exchange: Exchange name (e.g., 'jupiter', 'raydium')
            price: Current price
            liquidity: Available liquidity in USD
            volume_24h: 24h trading volume in USD
        """
        if symbol not in self.exchange_prices:
            self.exchange_prices[symbol] = {}

        self.exchange_prices[symbol][exchange] = PricePoint(
            exchange=exchange,
            price=price,
            timestamp=datetime.utcnow(),
            liquidity=liquidity,
            volume_24h=volume_24h,
        )

    def find_opportunities(self, symbol: str) -> List[Dict[str, Any]]:
        """Find arbitrage opportunities for a symbol.

        Args:
            symbol: Token symbol

        Returns:
            List of profitable arbitrage opportunities
        """
        if symbol not in self.exchange_prices or len(self.exchange_prices[symbol]) < 2:
            return []

        exchanges_data = self.exchange_prices[symbol]
        opportunities = []
        now = datetime.utcnow()

        # Get all valid price points
        valid_prices = []
        for exchange, price_point in exchanges_data.items():
            # Check if price is recent enough
            age_seconds = (now - price_point.timestamp).total_seconds()

            if age_seconds <= self.config.max_latency_seconds:
                valid_prices.append(price_point)

        if len(valid_prices) < 2:
            logger.debug(f"Not enough recent prices for {symbol}")
            return []

        # Find all price pairs and calculate spreads
        for i in range(len(valid_prices)):
            for j in range(i + 1, len(valid_prices)):
                buy_point = valid_prices[i]
                sell_point = valid_prices[j]

                # Calculate if profitable
                spread_pct = ((sell_point.price - buy_point.price) / buy_point.price) * 100

                # Account for fees and slippage
                net_profit_pct = spread_pct - (2 * self.config.fee_per_trade_pct) - (2 * self.config.slippage_pct)

                if net_profit_pct >= self.config.min_spread_pct:
                    # Calculate position size based on liquidity
                    buy_liquidity = buy_point.liquidity
                    sell_liquidity = sell_point.liquidity
                    available_size = min(
                        buy_liquidity,
                        sell_liquidity,
                        self.config.max_position_size_usd,
                    )

                    if available_size >= 1000:  # Minimum $1000 position
                        profit_usd = (available_size * net_profit_pct) / 100

                        opportunity = {
                            'symbol': symbol,
                            'buy_exchange': buy_point.exchange,
                            'sell_exchange': sell_point.exchange,
                            'buy_price': buy_point.price,
                            'sell_price': sell_point.price,
                            'spread_pct': spread_pct,
                            'net_profit_pct': net_profit_pct,
                            'position_size_usd': available_size,
                            'estimated_profit_usd': profit_usd,
                            'buy_liquidity': buy_liquidity,
                            'sell_liquidity': sell_liquidity,
                            'timestamp': now.isoformat(),
                            'profitable': True,
                        }

                        opportunities.append(opportunity)

                        logger.info(
                            f"Arbitrage opportunity for {symbol}: "
                            f"Buy {buy_point.exchange} @ {buy_point.price}, "
                            f"Sell {sell_point.exchange} @ {sell_point.price}, "
                            f"Net profit: {net_profit_pct:.2f}% (~${profit_usd:.2f})"
                        )

        # Sort by profitability
        opportunities.sort(key=lambda x: x['estimated_profit_usd'], reverse=True)
        self.opportunities[symbol] = opportunities

        return opportunities

    def get_best_opportunity(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the most profitable arbitrage opportunity.

        Args:
            symbol: Token symbol

        Returns:
            Best opportunity or None
        """
        if symbol in self.opportunities and len(self.opportunities[symbol]) > 0:
            return self.opportunities[symbol][0]

        return None

    def execute_arbitrage(self, symbol: str, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """Record execution of an arbitrage trade.

        Args:
            symbol: Token symbol
            opportunity: Opportunity details

        Returns:
            Execution record
        """
        execution = {
            'symbol': symbol,
            'opportunity': opportunity,
            'executed_at': datetime.utcnow().isoformat(),
            'buy_exchange': opportunity['buy_exchange'],
            'sell_exchange': opportunity['sell_exchange'],
            'position_size_usd': opportunity['position_size_usd'],
            'estimated_profit_usd': opportunity['estimated_profit_usd'],
        }

        self.executed_arbs.append(execution)

        logger.info(
            f"Executed arbitrage for {symbol}: "
            f"{opportunity['buy_exchange']} -> {opportunity['sell_exchange']}, "
            f"profit: ${opportunity['estimated_profit_usd']:.2f}"
        )

        return execution

    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get history of executed arbitrage trades.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of execution records
        """
        return self.executed_arbs[-limit:]

    def get_total_profit(self, symbol: Optional[str] = None) -> float:
        """Calculate total profit from arbitrage trades.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            Total profit in USD
        """
        total = 0.0

        for execution in self.executed_arbs:
            if symbol is None or execution['symbol'] == symbol:
                total += execution['estimated_profit_usd']

        return total

    def scan_all_symbols(self) -> Dict[str, List[Dict[str, Any]]]:
        """Scan all tracked symbols for opportunities.

        Returns:
            Dictionary of opportunities by symbol
        """
        all_opportunities = {}

        for symbol in self.exchange_prices.keys():
            opps = self.find_opportunities(symbol)
            if opps:
                all_opportunities[symbol] = opps

        return all_opportunities

    def get_statistics(self) -> Dict[str, Any]:
        """Get arbitrage trading statistics.

        Returns:
            Statistics summary
        """
        if not self.executed_arbs:
            return {
                'total_trades': 0,
                'total_profit_usd': 0.0,
                'average_profit_usd': 0.0,
            }

        total_profit = sum(ex['estimated_profit_usd'] for ex in self.executed_arbs)
        avg_profit = total_profit / len(self.executed_arbs)

        return {
            'total_trades': len(self.executed_arbs),
            'total_profit_usd': total_profit,
            'average_profit_usd': avg_profit,
            'max_profit_trade': max((ex['estimated_profit_usd'] for ex in self.executed_arbs), default=0),
            'min_profit_trade': min((ex['estimated_profit_usd'] for ex in self.executed_arbs), default=0),
        }


__all__ = ["ArbitrageStrategy", "ArbitrageConfig", "PricePoint"]
