"""
Instrumented Jupiter Client

Wraps JupiterClient with execution metrics tracking.
Automatically captures:
- Quote latency
- Execution time
- Slippage
- Fill rates
- Gas costs

Usage:
    from core.trading.instrumented_jupiter import InstrumentedJupiterClient

    jupiter = InstrumentedJupiterClient(rpc_url="...")
    result = await jupiter.execute_swap(quote, wallet)
    # Metrics automatically recorded
"""

import asyncio
import logging
import time
from typing import Optional, Any

from bots.treasury.jupiter import JupiterClient, SwapQuote, SwapResult
from core.trading.execution_metrics import (
    get_execution_metrics_tracker,
    ExecutionStatus,
    ExecutionMetricsTracker
)

logger = logging.getLogger(__name__)


class InstrumentedJupiterClient(JupiterClient):
    """
    Jupiter client with built-in execution metrics tracking.

    Extends JupiterClient to automatically capture performance metrics
    for all swap operations.
    """

    def __init__(self, rpc_url: str = None, metrics_tracker: Optional[ExecutionMetricsTracker] = None):
        """
        Initialize instrumented Jupiter client.

        Args:
            rpc_url: Solana RPC URL
            metrics_tracker: Optional custom metrics tracker (uses singleton if None)
        """
        super().__init__(rpc_url)
        self.metrics = metrics_tracker or get_execution_metrics_tracker()
        logger.info("Initialized InstrumentedJupiterClient with metrics tracking")

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
        mode: str = "ExactIn"
    ) -> Optional[SwapQuote]:
        """
        Get quote with latency tracking.

        Wraps parent get_quote and tracks quote retrieval time.
        """
        start_time = time.time()

        quote = await super().get_quote(input_mint, output_mint, amount, slippage_bps, mode)

        elapsed = time.time() - start_time

        if quote:
            # Store quote time for later use in execute_swap
            quote._metrics_quote_time = elapsed
            logger.debug(f"Quote retrieved in {elapsed:.3f}s")

        return quote

    async def execute_swap(
        self,
        quote: SwapQuote,
        wallet,
        simulate_first: bool = True,
        priority_fee: int = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        position_id: Optional[str] = None,
        direction: str = "BUY"
    ) -> SwapResult:
        """
        Execute swap with comprehensive metrics tracking.

        Args:
            quote: Quote from get_quote()
            wallet: SecureWallet instance
            simulate_first: Simulate before executing
            priority_fee: Priority fee in micro lamports
            max_retries: Maximum retry attempts
            retry_delay: Retry delay in seconds
            position_id: Optional position ID to link metrics
            direction: Trade direction (BUY/SELL)

        Returns:
            SwapResult with execution details
        """
        # Get token info for metrics
        input_info = await self.get_token_info(quote.input_mint)
        output_info = await self.get_token_info(quote.output_mint)

        token_symbol = output_info.symbol if output_info else 'UNKNOWN'
        token_mint = quote.output_mint

        # Start metrics tracking
        metric_id = self.metrics.start_execution(
            token_symbol=token_symbol,
            token_mint=token_mint,
            direction=direction,
            requested_amount=quote.output_amount_ui,
            position_id=position_id
        )

        # Record quote time if available
        quote_time = getattr(quote, '_metrics_quote_time', 0.0)
        if quote_time > 0:
            self.metrics.record_quote_time(metric_id, quote_time)

        # Track execution timing
        exec_start = time.time()

        # Determine priority fee
        if priority_fee is None:
            priority_fee = await self.get_dynamic_priority_fee()

        # Execute swap with parent method
        result = await super().execute_swap(
            quote=quote,
            wallet=wallet,
            simulate_first=simulate_first,
            priority_fee=priority_fee,
            max_retries=max_retries,
            retry_delay=retry_delay
        )

        exec_time = time.time() - exec_start

        # Determine execution status
        if result.success:
            status = ExecutionStatus.SUCCESS
            error_type = None
            error_message = None
        else:
            # Categorize error type
            error_msg = result.error.lower() if result.error else ""

            if "timeout" in error_msg:
                status = ExecutionStatus.TIMEOUT
                error_type = "timeout"
            elif "simulation" in error_msg or "simulate" in error_msg:
                status = ExecutionStatus.SIMULATED
                error_type = "simulation_failed"
            elif "blockhash" in error_msg or "expired" in error_msg:
                status = ExecutionStatus.FAILED
                error_type = "blockhash_expired"
            elif "slippage" in error_msg:
                status = ExecutionStatus.FAILED
                error_type = "slippage_exceeded"
            elif "balance" in error_msg or "insufficient" in error_msg:
                status = ExecutionStatus.FAILED
                error_type = "insufficient_balance"
            else:
                status = ExecutionStatus.FAILED
                error_type = "unknown"

            error_message = result.error

        # Calculate actual slippage
        expected_output = quote.output_amount_ui
        actual_output = result.output_amount if result.success else 0.0

        # Record execution metrics
        self.metrics.record_execution_result(
            metric_id=metric_id,
            status=status,
            tx_signature=result.signature if result.success else None,
            expected_output=expected_output,
            actual_output=actual_output,
            filled_amount=actual_output,  # Full fill on success, 0 on failure
            execution_time=exec_time,
            confirmation_time=0.0,  # Jupiter doesn't wait for confirmation
            priority_fee_lamports=priority_fee,
            jupiter_fee_usd=quote.fees_usd,
            price_impact_pct=quote.price_impact_pct,
            retry_count=max_retries if not result.success else 0,
            error_type=error_type,
            error_message=error_message
        )

        # Log summary
        if result.success:
            logger.info(
                f"Swap executed: {result.input_amount} {result.input_symbol} → "
                f"{result.output_amount} {result.output_symbol} "
                f"(slippage: {((expected_output - actual_output) / expected_output * 100):.2f}%, "
                f"latency: {exec_time:.2f}s)"
            )
        else:
            logger.error(
                f"Swap failed: {token_symbol} - {result.error} "
                f"(latency: {exec_time:.2f}s)"
            )

        return result

    async def execute_swap_with_confirmation(
        self,
        quote: SwapQuote,
        wallet,
        simulate_first: bool = True,
        priority_fee: int = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        position_id: Optional[str] = None,
        direction: str = "BUY",
        confirm_timeout: int = 30
    ) -> SwapResult:
        """
        Execute swap and wait for confirmation with metrics.

        Similar to execute_swap but waits for on-chain confirmation
        and tracks confirmation time.

        Args:
            Same as execute_swap plus:
            confirm_timeout: Seconds to wait for confirmation

        Returns:
            SwapResult with execution details
        """
        # Get token info
        input_info = await self.get_token_info(quote.input_mint)
        output_info = await self.get_token_info(quote.output_mint)

        token_symbol = output_info.symbol if output_info else 'UNKNOWN'
        token_mint = quote.output_mint

        # Start metrics
        metric_id = self.metrics.start_execution(
            token_symbol=token_symbol,
            token_mint=token_mint,
            direction=direction,
            requested_amount=quote.output_amount_ui,
            position_id=position_id
        )

        # Record quote time
        quote_time = getattr(quote, '_metrics_quote_time', 0.0)
        if quote_time > 0:
            self.metrics.record_quote_time(metric_id, quote_time)

        # Execute
        exec_start = time.time()

        if priority_fee is None:
            priority_fee = await self.get_dynamic_priority_fee()

        result = await super().execute_swap(
            quote, wallet, simulate_first, priority_fee, max_retries, retry_delay
        )

        exec_time = time.time() - exec_start

        # Wait for confirmation if successful
        confirm_time = 0.0
        if result.success and result.signature:
            confirm_start = time.time()

            try:
                confirmed = await self._wait_for_confirmation(
                    result.signature,
                    timeout=confirm_timeout
                )
                confirm_time = time.time() - confirm_start
                if confirmed and confirm_time <= 0:
                    confirm_time = 0.001

                if not confirmed:
                    logger.warning(f"Transaction {result.signature} not confirmed within {confirm_timeout}s")

            except Exception as e:
                logger.error(f"Error waiting for confirmation: {e}")
                confirm_time = time.time() - confirm_start

        # Determine status
        if result.success:
            status = ExecutionStatus.SUCCESS
            error_type = None
            error_message = None
        else:
            error_msg = result.error.lower() if result.error else ""
            if "timeout" in error_msg:
                status = ExecutionStatus.TIMEOUT
                error_type = "timeout"
            elif "simulation" in error_msg:
                status = ExecutionStatus.SIMULATED
                error_type = "simulation_failed"
            else:
                status = ExecutionStatus.FAILED
                error_type = "unknown"
            error_message = result.error

        # Record metrics
        self.metrics.record_execution_result(
            metric_id=metric_id,
            status=status,
            tx_signature=result.signature if result.success else None,
            expected_output=quote.output_amount_ui,
            actual_output=result.output_amount if result.success else 0.0,
            filled_amount=result.output_amount if result.success else 0.0,
            execution_time=exec_time,
            confirmation_time=confirm_time,
            priority_fee_lamports=priority_fee,
            jupiter_fee_usd=quote.fees_usd,
            price_impact_pct=quote.price_impact_pct,
            retry_count=max_retries if not result.success else 0,
            error_type=error_type,
            error_message=error_message
        )

        return result

    async def _wait_for_confirmation(self, signature: str, timeout: int = 30) -> bool:
        """
        Wait for transaction confirmation.

        Args:
            signature: Transaction signature
            timeout: Timeout in seconds

        Returns:
            True if confirmed, False if timeout
        """
        session = await self._get_session()
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                async with session.post(self.rpc_url, json={
                    'jsonrpc': '2.0',
                    'id': 1,
                    'method': 'getSignatureStatuses',
                    'params': [[signature], {'searchTransactionHistory': True}]
                }) as resp:
                    data = await resp.json()

                    if 'result' in data and data['result']['value']:
                        status = data['result']['value'][0]
                        if status and status.get('confirmationStatus') in ['confirmed', 'finalized']:
                            return True

                await asyncio.sleep(1)

            except Exception as e:
                logger.debug(f"Confirmation check error: {e}")
                await asyncio.sleep(1)

        return False

    def get_metrics_stats(self, hours: int = 24):
        """Get execution metrics statistics"""
        return self.metrics.get_stats(hours=hours)

    def get_optimization_insights(self, hours: int = 24):
        """Get optimization insights from metrics"""
        return self.metrics.get_optimization_insights(hours=hours)


# Convenience function
def create_instrumented_jupiter(rpc_url: str = None) -> InstrumentedJupiterClient:
    """Create an instrumented Jupiter client"""
    return InstrumentedJupiterClient(rpc_url=rpc_url)
