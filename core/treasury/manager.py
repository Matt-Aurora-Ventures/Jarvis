"""
Treasury Manager - Central orchestration for treasury operations.

Coordinates:
- Wallet management
- Risk controls
- Autonomous trading
- Profit distribution

Usage:
    from core.treasury import get_treasury

    treasury = get_treasury()

    # Check balances
    status = await treasury.get_status()

    # Execute trade (with risk checks)
    result = await treasury.execute_trade(
        token_mint="...",
        side="buy",
        amount=1_000_000_000,
    )

    # Distribute profits
    distribution = await treasury.distribute_profits()
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.treasury.wallet import (
    WalletManager,
    WalletType,
    TreasuryWallet,
    WalletAllocation,
    DEFAULT_ALLOCATIONS,
)
from core.treasury.risk import (
    RiskManager,
    RiskLimits,
)
from core.treasury.distribution import (
    ProfitDistributor,
    DistributionConfig,
)

logger = logging.getLogger("jarvis.treasury")


@dataclass
class TreasuryConfig:
    """Treasury system configuration."""

    # Wallet addresses
    reserve_wallet: str = ""
    active_wallet: str = ""
    profit_wallet: str = ""
    staking_pool_wallet: str = ""
    operations_wallet: str = ""
    development_wallet: str = ""

    # Keypair paths (hot wallets only)
    active_keypair_path: str = ""
    profit_keypair_path: str = ""

    # RPC
    rpc_url: str = ""

    # Risk limits
    risk_limits: RiskLimits = None

    # Distribution config
    distribution_config: DistributionConfig = None

    @classmethod
    def from_env(cls) -> "TreasuryConfig":
        """Load configuration from environment variables."""
        return cls(
            reserve_wallet=os.getenv("TREASURY_RESERVE_WALLET", ""),
            active_wallet=os.getenv("TREASURY_ACTIVE_WALLET", ""),
            profit_wallet=os.getenv("TREASURY_PROFIT_WALLET", ""),
            staking_pool_wallet=os.getenv("STAKING_POOL_WALLET", ""),
            operations_wallet=os.getenv("OPERATIONS_WALLET", ""),
            development_wallet=os.getenv("DEVELOPMENT_WALLET", ""),
            active_keypair_path=os.getenv("TREASURY_ACTIVE_KEYPAIR", ""),
            profit_keypair_path=os.getenv("TREASURY_PROFIT_KEYPAIR", ""),
            rpc_url=os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"),
        )


class TreasuryManager:
    """
    Central manager for all treasury operations.

    Responsibilities:
    - Initialize and coordinate sub-systems
    - Execute trades with risk validation
    - Handle profit distribution
    - Provide unified status/reporting
    """

    def __init__(self, config: TreasuryConfig = None):
        """
        Initialize treasury manager.

        Args:
            config: Treasury configuration (loads from env if not provided)
        """
        self.config = config or TreasuryConfig.from_env()

        # Initialize wallet manager
        self.wallet_manager = WalletManager(
            allocations=DEFAULT_ALLOCATIONS,
            rpc_url=self.config.rpc_url,
        )

        # Set up wallets
        self._setup_wallets()

        # Initialize risk manager
        self.risk_manager = RiskManager(
            limits=self.config.risk_limits or RiskLimits(),
        )

        # Initialize distributor
        dist_config = self.config.distribution_config or DistributionConfig(
            staking_pool_wallet=self.config.staking_pool_wallet,
            operations_wallet=self.config.operations_wallet,
            development_wallet=self.config.development_wallet,
        )
        self.distributor = ProfitDistributor(
            config=dist_config,
            wallet_manager=self.wallet_manager,
        )

        # State
        self._initialized = False
        self._running = False
        self._trade_router = None

        logger.info("Treasury manager initialized")

    def _setup_wallets(self):
        """Configure wallets from config."""
        if self.config.reserve_wallet:
            self.wallet_manager.add_wallet(TreasuryWallet(
                wallet_type=WalletType.RESERVE,
                address=self.config.reserve_wallet,
                label="Reserve Vault",
                is_multisig=True,
            ))

        if self.config.active_wallet:
            self.wallet_manager.add_wallet(TreasuryWallet(
                wallet_type=WalletType.ACTIVE,
                address=self.config.active_wallet,
                label="Active Trading",
                keypair_path=self.config.active_keypair_path,
            ))

        if self.config.profit_wallet:
            self.wallet_manager.add_wallet(TreasuryWallet(
                wallet_type=WalletType.PROFIT,
                address=self.config.profit_wallet,
                label="Profit Buffer",
                keypair_path=self.config.profit_keypair_path,
            ))

    async def initialize(self):
        """Initialize treasury system."""
        if self._initialized:
            return

        # Fetch initial balances
        await self.wallet_manager.get_all_balances()

        # Set starting balances for P&L tracking
        active_balance = await self.wallet_manager.get_balance(WalletType.ACTIVE)
        if active_balance:
            self.risk_manager.set_starting_balance(active_balance.sol_balance, "daily")
            self.risk_manager.set_starting_balance(active_balance.sol_balance, "weekly")
            self.risk_manager.set_starting_balance(active_balance.sol_balance, "monthly")

        self._initialized = True
        logger.info("Treasury system initialized")

    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive treasury status."""
        await self.initialize()

        return {
            "wallets": self.wallet_manager.get_wallet_status(),
            "risk": self.risk_manager.get_risk_status(),
            "distribution": self.distributor.get_status(),
            "running": self._running,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_total_balance(self) -> int:
        """Get total SOL across all wallets."""
        return await self.wallet_manager.get_total_balance()

    async def get_trading_balance(self) -> int:
        """Get balance available for trading."""
        balance = await self.wallet_manager.get_balance(WalletType.ACTIVE)
        return balance.sol_balance if balance else 0

    # =========================================================================
    # Trading Operations
    # =========================================================================

    async def execute_trade(
        self,
        token_mint: str,
        side: str,
        amount: int,
        max_slippage_bps: int = 100,
    ) -> Dict[str, Any]:
        """
        Execute a trade with risk validation.

        Args:
            token_mint: Token to trade
            side: "buy" or "sell"
            amount: Amount in lamports
            max_slippage_bps: Maximum slippage

        Returns:
            Trade result
        """
        await self.initialize()

        # Get current balance
        current_balance = await self.get_trading_balance()

        # Validate against risk limits
        is_valid, reason = self.risk_manager.validate_trade(
            token_mint=token_mint,
            side=side,
            amount=amount,
            current_balance=current_balance,
        )

        if not is_valid:
            return {
                "success": False,
                "error": reason,
                "risk_rejected": True,
            }

        # Execute via trade router
        try:
            if self._trade_router is None:
                from integrations.bags import get_trade_router
                self._trade_router = get_trade_router(paper_mode=False)

            from integrations.bags.trade_router import TradeIntent, SOL_MINT

            # Determine mints based on side
            if side == "buy":
                input_mint = SOL_MINT
                output_mint = token_mint
            else:
                input_mint = token_mint
                output_mint = SOL_MINT

            result = await self._trade_router.execute(TradeIntent(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                max_slippage_bps=max_slippage_bps,
                user_id="treasury",
                metadata={"treasury": True},
            ))

            # Record in risk manager
            self.risk_manager.record_trade(
                token_mint=token_mint,
                side=side,
                amount_in=result.input_amount,
                amount_out=result.output_amount,
                success=result.success,
                signature=result.signature,
            )

            return result.to_dict()

        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def close_position(self, token_mint: str) -> Dict[str, Any]:
        """
        Close a position by selling all holdings.

        Args:
            token_mint: Token to sell

        Returns:
            Trade result
        """
        # Get current position
        position = self.risk_manager._active_positions.get(token_mint, 0)
        if position <= 0:
            return {"success": False, "error": "No position to close"}

        return await self.execute_trade(
            token_mint=token_mint,
            side="sell",
            amount=position,
        )

    async def close_all_positions(self) -> List[Dict[str, Any]]:
        """Close all open positions."""
        results = []

        for token_mint in list(self.risk_manager._active_positions.keys()):
            result = await self.close_position(token_mint)
            results.append({
                "token": token_mint,
                "result": result,
            })

        return results

    # =========================================================================
    # Profit Distribution
    # =========================================================================

    async def distribute_profits(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Distribute profits to stakers.

        Args:
            dry_run: If True, simulate without transfers

        Returns:
            Distribution result
        """
        await self.initialize()

        try:
            distribution = await self.distributor.execute_distribution(dry_run=dry_run)
            return distribution.to_dict()
        except Exception as e:
            logger.error(f"Distribution error: {e}")
            return {"success": False, "error": str(e)}

    async def check_distribution_due(self) -> bool:
        """Check if weekly distribution is due."""
        return self.distributor.is_distribution_due()

    # =========================================================================
    # Rebalancing
    # =========================================================================

    async def check_rebalance_needed(self) -> bool:
        """Check if wallet rebalancing is needed."""
        return await self.wallet_manager.needs_rebalance()

    async def rebalance(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """
        Rebalance wallets to target allocations.

        Args:
            dry_run: If True, return planned transfers without execution

        Returns:
            List of transfer results
        """
        await self.initialize()

        transfers = await self.wallet_manager.calculate_rebalance()

        if dry_run:
            return transfers

        results = []
        for transfer in transfers:
            if transfer.get("requires_multisig"):
                logger.info(f"Multisig transfer required: {transfer}")
                results.append({**transfer, "status": "requires_approval"})
            else:
                # Execute transfer
                sig = await self.wallet_manager.execute_transfer(
                    from_wallet=WalletType(transfer["from_wallet"]),
                    to_address=transfer["to_address"],
                    amount_lamports=transfer["amount_lamports"],
                )
                results.append({**transfer, "signature": sig, "status": "completed"})

        return results

    # =========================================================================
    # Risk Controls
    # =========================================================================

    def emergency_stop(self, reason: str = "Manual stop"):
        """Trigger emergency stop - halt all trading."""
        self.risk_manager.emergency_stop(reason)
        logger.critical(f"TREASURY EMERGENCY STOP: {reason}")

    def resume_trading(self, override: bool = False):
        """Resume trading after emergency stop."""
        self.risk_manager.resume_trading(override)

    def is_trading_allowed(self) -> bool:
        """Check if trading is currently allowed."""
        return self.risk_manager.circuit_breaker.is_trading_allowed()

    # =========================================================================
    # Reporting
    # =========================================================================

    def get_pnl_report(self) -> Dict[str, Any]:
        """Get P&L report for all periods."""
        return {
            "daily": self.risk_manager.get_pnl("daily"),
            "weekly": self.risk_manager.get_pnl("weekly"),
            "monthly": self.risk_manager.get_pnl("monthly"),
        }

    def get_distribution_history(self, limit: int = 12) -> List[Dict[str, Any]]:
        """Get recent distribution history."""
        distributions = self.distributor.get_distribution_history(limit=limit)
        return [d.to_dict() for d in distributions]


# =============================================================================
# Singleton
# =============================================================================

_treasury: Optional[TreasuryManager] = None


def get_treasury() -> TreasuryManager:
    """Get or create the singleton treasury manager."""
    global _treasury

    if _treasury is None:
        _treasury = TreasuryManager()

    return _treasury


async def initialize_treasury() -> TreasuryManager:
    """Initialize and return treasury manager."""
    treasury = get_treasury()
    await treasury.initialize()
    return treasury
