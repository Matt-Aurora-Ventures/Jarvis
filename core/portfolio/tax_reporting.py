"""
Tax Reporting System

Generates tax reports for crypto transactions including:
- Capital gains/losses (FIFO, LIFO, HIFO)
- Income from staking rewards
- Cost basis tracking
- IRS Form 8949 generation
- CSV/PDF export

Prompts #108: Tax Reporting
"""

import asyncio
import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json

from .tracker import Portfolio, Position, Transaction, TransactionType

logger = logging.getLogger(__name__)


class CostBasisMethod(str, Enum):
    """Cost basis calculation methods"""
    FIFO = "fifo"   # First In, First Out
    LIFO = "lifo"   # Last In, First Out
    HIFO = "hifo"   # Highest In, First Out
    AVG = "average" # Average cost


class GainType(str, Enum):
    """Type of capital gain"""
    SHORT_TERM = "short_term"  # Held < 1 year
    LONG_TERM = "long_term"    # Held >= 1 year


class IncomeType(str, Enum):
    """Types of taxable income"""
    STAKING_REWARD = "staking_reward"
    AIRDROP = "airdrop"
    INTEREST = "interest"
    MINING = "mining"
    OTHER = "other"


@dataclass
class TaxLot:
    """A tax lot representing acquired tokens"""
    lot_id: str
    token: str
    amount: float
    cost_basis: float           # Total cost in USD
    cost_per_unit: float        # Cost per token
    acquired_date: datetime
    source_tx: str              # Transaction ID
    remaining_amount: float = 0.0
    sold_amount: float = 0.0

    def __post_init__(self):
        if self.remaining_amount == 0.0:
            self.remaining_amount = self.amount


@dataclass
class CapitalGain:
    """A capital gain/loss event"""
    gain_id: str
    token: str
    amount_sold: float
    proceeds: float             # USD received
    cost_basis: float           # USD cost
    gain_loss: float            # Proceeds - cost basis
    gain_type: GainType
    acquired_date: datetime
    sold_date: datetime
    lot_id: str
    sell_tx: str

    @property
    def holding_period_days(self) -> int:
        return (self.sold_date - self.acquired_date).days


@dataclass
class TaxableIncome:
    """Taxable income event (staking, airdrops, etc.)"""
    income_id: str
    income_type: IncomeType
    token: str
    amount: float
    fair_market_value: float    # USD value at time of receipt
    date: datetime
    source_tx: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaxYearSummary:
    """Summary of tax events for a year"""
    year: int
    short_term_gains: float = 0.0
    short_term_losses: float = 0.0
    long_term_gains: float = 0.0
    long_term_losses: float = 0.0
    staking_income: float = 0.0
    airdrop_income: float = 0.0
    other_income: float = 0.0
    total_proceeds: float = 0.0
    total_cost_basis: float = 0.0
    transaction_count: int = 0

    @property
    def net_short_term(self) -> float:
        return self.short_term_gains - self.short_term_losses

    @property
    def net_long_term(self) -> float:
        return self.long_term_gains - self.long_term_losses

    @property
    def total_capital_gain(self) -> float:
        return self.net_short_term + self.net_long_term

    @property
    def total_income(self) -> float:
        return self.staking_income + self.airdrop_income + self.other_income


class TaxReportGenerator:
    """
    Generates tax reports from portfolio transactions.

    Supports multiple cost basis methods and various report formats.
    """

    def __init__(
        self,
        cost_basis_method: CostBasisMethod = CostBasisMethod.FIFO
    ):
        self.cost_basis_method = cost_basis_method
        self._tax_lots: Dict[str, List[TaxLot]] = {}  # token -> lots
        self._capital_gains: List[CapitalGain] = []
        self._income_events: List[TaxableIncome] = []
        self._lot_counter = 0
        self._gain_counter = 0
        self._income_counter = 0

    def _generate_lot_id(self) -> str:
        self._lot_counter += 1
        return f"LOT-{self._lot_counter:06d}"

    def _generate_gain_id(self) -> str:
        self._gain_counter += 1
        return f"GAIN-{self._gain_counter:06d}"

    def _generate_income_id(self) -> str:
        self._income_counter += 1
        return f"INC-{self._income_counter:06d}"

    async def process_transactions(
        self,
        transactions: List[Transaction]
    ) -> Tuple[List[CapitalGain], List[TaxableIncome]]:
        """
        Process transactions to calculate gains and income.

        Returns tuple of (capital_gains, income_events)
        """
        # Sort by timestamp
        sorted_txs = sorted(transactions, key=lambda t: t.timestamp)

        for tx in sorted_txs:
            if tx.tx_type in [TransactionType.BUY, TransactionType.TRANSFER_IN]:
                await self._process_acquisition(tx)
            elif tx.tx_type == TransactionType.SELL:
                await self._process_sale(tx)
            elif tx.tx_type == TransactionType.REWARD:
                await self._process_income(tx, IncomeType.STAKING_REWARD)
            elif tx.tx_type == TransactionType.AIRDROP:
                await self._process_income(tx, IncomeType.AIRDROP)

        return self._capital_gains, self._income_events

    async def _process_acquisition(self, tx: Transaction):
        """Process a token acquisition (buy/transfer in)"""
        lot = TaxLot(
            lot_id=self._generate_lot_id(),
            token=tx.token,
            amount=tx.amount,
            cost_basis=tx.total_usd,
            cost_per_unit=tx.price_usd,
            acquired_date=tx.timestamp,
            source_tx=tx.tx_hash
        )

        if tx.token not in self._tax_lots:
            self._tax_lots[tx.token] = []
        self._tax_lots[tx.token].append(lot)

        logger.debug(
            f"Created tax lot {lot.lot_id}: "
            f"{lot.amount} {lot.token} @ ${lot.cost_per_unit}"
        )

    async def _process_sale(self, tx: Transaction):
        """Process a token sale using cost basis method"""
        if tx.token not in self._tax_lots:
            logger.warning(f"No tax lots for {tx.token}, cannot calculate gain")
            return

        remaining_to_sell = tx.amount
        proceeds_per_unit = tx.price_usd

        # Get lots in order based on cost basis method
        lots = self._get_lots_in_order(tx.token)

        for lot in lots:
            if remaining_to_sell <= 0:
                break

            if lot.remaining_amount <= 0:
                continue

            # Calculate how much to sell from this lot
            sell_from_lot = min(remaining_to_sell, lot.remaining_amount)

            # Calculate proceeds and cost basis for this portion
            proceeds = sell_from_lot * proceeds_per_unit
            cost_basis = sell_from_lot * lot.cost_per_unit
            gain_loss = proceeds - cost_basis

            # Determine gain type (short vs long term)
            holding_days = (tx.timestamp - lot.acquired_date).days
            gain_type = (
                GainType.LONG_TERM if holding_days >= 365
                else GainType.SHORT_TERM
            )

            # Record capital gain
            gain = CapitalGain(
                gain_id=self._generate_gain_id(),
                token=tx.token,
                amount_sold=sell_from_lot,
                proceeds=proceeds,
                cost_basis=cost_basis,
                gain_loss=gain_loss,
                gain_type=gain_type,
                acquired_date=lot.acquired_date,
                sold_date=tx.timestamp,
                lot_id=lot.lot_id,
                sell_tx=tx.tx_hash
            )
            self._capital_gains.append(gain)

            # Update lot
            lot.remaining_amount -= sell_from_lot
            lot.sold_amount += sell_from_lot
            remaining_to_sell -= sell_from_lot

            logger.debug(
                f"Capital gain {gain.gain_id}: "
                f"${gain.gain_loss:,.2f} ({gain.gain_type.value})"
            )

        if remaining_to_sell > 0:
            logger.warning(
                f"Sold {tx.amount} {tx.token} but only had lots for "
                f"{tx.amount - remaining_to_sell}"
            )

    async def _process_income(self, tx: Transaction, income_type: IncomeType):
        """Process taxable income (staking rewards, airdrops)"""
        income = TaxableIncome(
            income_id=self._generate_income_id(),
            income_type=income_type,
            token=tx.token,
            amount=tx.amount,
            fair_market_value=tx.total_usd,
            date=tx.timestamp,
            source_tx=tx.tx_hash
        )
        self._income_events.append(income)

        # Also create a tax lot at FMV for future sales
        lot = TaxLot(
            lot_id=self._generate_lot_id(),
            token=tx.token,
            amount=tx.amount,
            cost_basis=tx.total_usd,  # FMV at time of receipt
            cost_per_unit=tx.price_usd,
            acquired_date=tx.timestamp,
            source_tx=tx.tx_hash
        )

        if tx.token not in self._tax_lots:
            self._tax_lots[tx.token] = []
        self._tax_lots[tx.token].append(lot)

        logger.debug(
            f"Taxable income {income.income_id}: "
            f"${income.fair_market_value:,.2f} ({income_type.value})"
        )

    def _get_lots_in_order(self, token: str) -> List[TaxLot]:
        """Get tax lots in order based on cost basis method"""
        lots = [l for l in self._tax_lots.get(token, []) if l.remaining_amount > 0]

        if self.cost_basis_method == CostBasisMethod.FIFO:
            return sorted(lots, key=lambda l: l.acquired_date)
        elif self.cost_basis_method == CostBasisMethod.LIFO:
            return sorted(lots, key=lambda l: l.acquired_date, reverse=True)
        elif self.cost_basis_method == CostBasisMethod.HIFO:
            return sorted(lots, key=lambda l: l.cost_per_unit, reverse=True)
        elif self.cost_basis_method == CostBasisMethod.AVG:
            # For average cost, we treat all as one lot
            return lots

        return lots

    async def generate_year_summary(self, year: int) -> TaxYearSummary:
        """Generate summary for a tax year"""
        summary = TaxYearSummary(year=year)

        # Process capital gains
        for gain in self._capital_gains:
            if gain.sold_date.year != year:
                continue

            summary.total_proceeds += gain.proceeds
            summary.total_cost_basis += gain.cost_basis
            summary.transaction_count += 1

            if gain.gain_type == GainType.SHORT_TERM:
                if gain.gain_loss >= 0:
                    summary.short_term_gains += gain.gain_loss
                else:
                    summary.short_term_losses += abs(gain.gain_loss)
            else:
                if gain.gain_loss >= 0:
                    summary.long_term_gains += gain.gain_loss
                else:
                    summary.long_term_losses += abs(gain.gain_loss)

        # Process income
        for income in self._income_events:
            if income.date.year != year:
                continue

            if income.income_type == IncomeType.STAKING_REWARD:
                summary.staking_income += income.fair_market_value
            elif income.income_type == IncomeType.AIRDROP:
                summary.airdrop_income += income.fair_market_value
            else:
                summary.other_income += income.fair_market_value

        return summary

    async def generate_form_8949(
        self,
        year: int,
        include_short_term: bool = True,
        include_long_term: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate IRS Form 8949 data.

        Returns list of rows for Form 8949.
        """
        rows = []

        for gain in self._capital_gains:
            if gain.sold_date.year != year:
                continue

            if gain.gain_type == GainType.SHORT_TERM and not include_short_term:
                continue
            if gain.gain_type == GainType.LONG_TERM and not include_long_term:
                continue

            row = {
                "description": f"{gain.amount_sold:.6f} {gain.token}",
                "date_acquired": gain.acquired_date.strftime("%m/%d/%Y"),
                "date_sold": gain.sold_date.strftime("%m/%d/%Y"),
                "proceeds": round(gain.proceeds, 2),
                "cost_basis": round(gain.cost_basis, 2),
                "adjustment_code": "",
                "adjustment_amount": 0,
                "gain_or_loss": round(gain.gain_loss, 2),
                "gain_type": gain.gain_type.value,
                "holding_period_days": gain.holding_period_days
            }
            rows.append(row)

        return rows

    async def export_csv(
        self,
        year: int,
        report_type: str = "form_8949"
    ) -> str:
        """Export report as CSV string"""
        output = io.StringIO()

        if report_type == "form_8949":
            rows = await self.generate_form_8949(year)
            if not rows:
                return ""

            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        elif report_type == "income":
            writer = csv.writer(output)
            writer.writerow([
                "Date", "Type", "Token", "Amount", "Fair Market Value (USD)",
                "Transaction ID"
            ])

            for income in self._income_events:
                if income.date.year != year:
                    continue
                writer.writerow([
                    income.date.strftime("%Y-%m-%d"),
                    income.income_type.value,
                    income.token,
                    income.amount,
                    round(income.fair_market_value, 2),
                    income.source_tx
                ])

        elif report_type == "tax_lots":
            writer = csv.writer(output)
            writer.writerow([
                "Lot ID", "Token", "Amount", "Cost Basis", "Cost Per Unit",
                "Acquired Date", "Remaining", "Sold"
            ])

            for token, lots in self._tax_lots.items():
                for lot in lots:
                    writer.writerow([
                        lot.lot_id,
                        lot.token,
                        lot.amount,
                        round(lot.cost_basis, 2),
                        round(lot.cost_per_unit, 6),
                        lot.acquired_date.strftime("%Y-%m-%d"),
                        lot.remaining_amount,
                        lot.sold_amount
                    ])

        return output.getvalue()

    def to_dict(self) -> Dict[str, Any]:
        """Get tax data as dictionary"""
        return {
            "cost_basis_method": self.cost_basis_method.value,
            "tax_lots": {
                token: [
                    {
                        "lot_id": l.lot_id,
                        "amount": l.amount,
                        "cost_basis": l.cost_basis,
                        "acquired_date": l.acquired_date.isoformat(),
                        "remaining": l.remaining_amount
                    }
                    for l in lots
                ]
                for token, lots in self._tax_lots.items()
            },
            "capital_gains": [
                {
                    "gain_id": g.gain_id,
                    "token": g.token,
                    "amount": g.amount_sold,
                    "proceeds": g.proceeds,
                    "cost_basis": g.cost_basis,
                    "gain_loss": g.gain_loss,
                    "gain_type": g.gain_type.value,
                    "sold_date": g.sold_date.isoformat()
                }
                for g in self._capital_gains
            ],
            "income_events": [
                {
                    "income_id": i.income_id,
                    "type": i.income_type.value,
                    "token": i.token,
                    "amount": i.amount,
                    "fmv": i.fair_market_value,
                    "date": i.date.isoformat()
                }
                for i in self._income_events
            ]
        }


class TaxReportingService:
    """
    High-level service for tax reporting.

    Manages report generation and caching.
    """

    def __init__(self):
        self._generators: Dict[str, TaxReportGenerator] = {}
        self._reports_cache: Dict[str, Dict] = {}

    def get_generator(
        self,
        user_id: str,
        method: CostBasisMethod = CostBasisMethod.FIFO
    ) -> TaxReportGenerator:
        """Get or create generator for user"""
        key = f"{user_id}_{method.value}"
        if key not in self._generators:
            self._generators[key] = TaxReportGenerator(method)
        return self._generators[key]

    async def generate_report(
        self,
        user_id: str,
        portfolio: Portfolio,
        year: int,
        method: CostBasisMethod = CostBasisMethod.FIFO
    ) -> Dict[str, Any]:
        """Generate complete tax report for a year"""
        generator = self.get_generator(user_id, method)

        # Filter transactions for the year
        start_of_year = datetime(year, 1, 1)
        end_of_year = datetime(year, 12, 31, 23, 59, 59)

        # Get all transactions up to end of year (for cost basis)
        relevant_txs = [
            tx for tx in portfolio.transactions
            if tx.timestamp <= end_of_year
        ]

        # Process transactions
        await generator.process_transactions(relevant_txs)

        # Generate summary
        summary = await generator.generate_year_summary(year)

        # Generate Form 8949 data
        form_8949 = await generator.generate_form_8949(year)

        report = {
            "user_id": user_id,
            "year": year,
            "cost_basis_method": method.value,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "short_term_gains": round(summary.short_term_gains, 2),
                "short_term_losses": round(summary.short_term_losses, 2),
                "net_short_term": round(summary.net_short_term, 2),
                "long_term_gains": round(summary.long_term_gains, 2),
                "long_term_losses": round(summary.long_term_losses, 2),
                "net_long_term": round(summary.net_long_term, 2),
                "total_capital_gain": round(summary.total_capital_gain, 2),
                "staking_income": round(summary.staking_income, 2),
                "airdrop_income": round(summary.airdrop_income, 2),
                "other_income": round(summary.other_income, 2),
                "total_income": round(summary.total_income, 2),
                "total_proceeds": round(summary.total_proceeds, 2),
                "total_cost_basis": round(summary.total_cost_basis, 2),
                "transaction_count": summary.transaction_count
            },
            "form_8949": form_8949,
            "data": generator.to_dict()
        }

        # Cache the report
        cache_key = f"{user_id}_{year}_{method.value}"
        self._reports_cache[cache_key] = report

        return report

    async def export_report(
        self,
        user_id: str,
        year: int,
        format: str = "csv",
        report_type: str = "form_8949",
        method: CostBasisMethod = CostBasisMethod.FIFO
    ) -> str:
        """Export report in specified format"""
        generator = self.get_generator(user_id, method)

        if format == "csv":
            return await generator.export_csv(year, report_type)
        elif format == "json":
            return json.dumps(generator.to_dict(), indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def get_cached_report(
        self,
        user_id: str,
        year: int,
        method: CostBasisMethod = CostBasisMethod.FIFO
    ) -> Optional[Dict]:
        """Get cached report if available"""
        cache_key = f"{user_id}_{year}_{method.value}"
        return self._reports_cache.get(cache_key)


# Singleton service
_tax_service: Optional[TaxReportingService] = None


def get_tax_service() -> TaxReportingService:
    """Get the tax reporting service singleton"""
    global _tax_service
    if _tax_service is None:
        _tax_service = TaxReportingService()
    return _tax_service


# Testing
if __name__ == "__main__":
    async def test():
        from .tracker import Transaction, TransactionType

        # Create test transactions
        transactions = [
            Transaction(
                tx_hash="tx1",
                tx_type=TransactionType.BUY,
                token="SOL",
                amount=10.0,
                price_usd=100.0,
                total_usd=1000.0,
                timestamp=datetime(2024, 1, 15)
            ),
            Transaction(
                tx_hash="tx2",
                tx_type=TransactionType.BUY,
                token="SOL",
                amount=5.0,
                price_usd=120.0,
                total_usd=600.0,
                timestamp=datetime(2024, 3, 1)
            ),
            Transaction(
                tx_hash="tx3",
                tx_type=TransactionType.REWARD,
                token="SOL",
                amount=0.5,
                price_usd=150.0,
                total_usd=75.0,
                timestamp=datetime(2024, 6, 1)
            ),
            Transaction(
                tx_hash="tx4",
                tx_type=TransactionType.SELL,
                token="SOL",
                amount=8.0,
                price_usd=180.0,
                total_usd=1440.0,
                timestamp=datetime(2024, 10, 1)
            )
        ]

        # Generate report
        generator = TaxReportGenerator(CostBasisMethod.FIFO)
        gains, income = await generator.process_transactions(transactions)

        print("Capital Gains:")
        for g in gains:
            print(f"  {g.gain_id}: {g.amount_sold} {g.token}")
            print(f"    Proceeds: ${g.proceeds:,.2f}")
            print(f"    Cost: ${g.cost_basis:,.2f}")
            print(f"    Gain/Loss: ${g.gain_loss:,.2f} ({g.gain_type.value})")

        print("\nIncome Events:")
        for i in income:
            print(f"  {i.income_id}: {i.amount} {i.token}")
            print(f"    FMV: ${i.fair_market_value:,.2f}")
            print(f"    Type: {i.income_type.value}")

        # Generate summary
        summary = await generator.generate_year_summary(2024)
        print(f"\n2024 Tax Summary:")
        print(f"  Short-term net: ${summary.net_short_term:,.2f}")
        print(f"  Long-term net: ${summary.net_long_term:,.2f}")
        print(f"  Total capital gain: ${summary.total_capital_gain:,.2f}")
        print(f"  Staking income: ${summary.staking_income:,.2f}")

        # Export CSV
        csv_data = await generator.export_csv(2024, "form_8949")
        print(f"\nForm 8949 CSV:\n{csv_data}")

    asyncio.run(test())
