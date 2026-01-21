"""
Tax Reporter - Track cost basis and generate tax reports for crypto trades.

Features:
- Cost basis tracking (FIFO, LIFO, HIFO)
- Short-term vs long-term gain classification
- Wash sale detection and tracking
- Tax lot optimization for specific identification
- Export to CSV, TurboTax, and IRS Form 8949 formats
"""

import logging
import sqlite3
import csv
import json
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class CostBasisMethod(Enum):
    """Cost basis calculation methods."""
    FIFO = "fifo"    # First In, First Out
    LIFO = "lifo"    # Last In, First Out
    HIFO = "hifo"    # Highest In, First Out


class InsufficientLotsError(Exception):
    """Raised when attempting to sell more than available quantity."""
    pass


@dataclass
class TaxLot:
    """A tax lot representing a purchase of an asset."""
    id: int = 0
    symbol: str = ""
    quantity: float = 0.0
    remaining_quantity: float = 0.0
    cost_per_unit: float = 0.0
    total_cost: float = 0.0
    fee: float = 0.0
    purchase_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tx_id: str = ""
    adjusted_cost_basis: float = 0.0  # After wash sale adjustments
    wash_sale_adjustment: float = 0.0

    def __post_init__(self):
        if self.adjusted_cost_basis == 0.0:
            self.adjusted_cost_basis = self.cost_per_unit


@dataclass
class SaleResult:
    """Result of a sale transaction."""
    symbol: str = ""
    quantity: float = 0.0
    sale_price: float = 0.0
    sale_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    proceeds: float = 0.0
    cost_basis: float = 0.0
    gain_loss: float = 0.0
    fee: float = 0.0
    is_long_term: bool = False
    holding_period_days: int = 0
    long_term_gain_loss: Optional[float] = None
    short_term_gain_loss: Optional[float] = None
    lots_used: List[Tuple[int, float]] = field(default_factory=list)  # (lot_id, quantity)
    tx_id: str = ""


@dataclass
class WashSale:
    """A wash sale record."""
    id: int = 0
    symbol: str = ""
    sale_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sale_tx_id: str = ""
    replacement_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    replacement_tx_id: str = ""
    disallowed_loss: float = 0.0
    replacement_lot_id: int = 0


@dataclass
class AnnualSummary:
    """Annual tax summary."""
    year: int = 0
    total_proceeds: float = 0.0
    total_cost_basis: float = 0.0
    net_gain_loss: float = 0.0
    short_term_gain: float = 0.0
    short_term_loss: float = 0.0
    long_term_gain: float = 0.0
    long_term_loss: float = 0.0
    wash_sale_disallowed: float = 0.0
    total_transactions: int = 0


class TaxReporterDB:
    """SQLite storage for tax data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        # Support in-memory databases
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Tax lots table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tax_lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    remaining_quantity REAL NOT NULL,
                    cost_per_unit REAL NOT NULL,
                    total_cost REAL NOT NULL,
                    fee REAL DEFAULT 0,
                    purchase_date TEXT NOT NULL,
                    tx_id TEXT UNIQUE,
                    adjusted_cost_basis REAL NOT NULL,
                    wash_sale_adjustment REAL DEFAULT 0
                )
            """)

            # Sales table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    sale_price REAL NOT NULL,
                    sale_date TEXT NOT NULL,
                    proceeds REAL NOT NULL,
                    cost_basis REAL NOT NULL,
                    gain_loss REAL NOT NULL,
                    fee REAL DEFAULT 0,
                    is_long_term INTEGER NOT NULL,
                    holding_period_days INTEGER NOT NULL,
                    long_term_gain_loss REAL,
                    short_term_gain_loss REAL,
                    lots_used_json TEXT,
                    tx_id TEXT UNIQUE
                )
            """)

            # Wash sales table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wash_sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    sale_date TEXT NOT NULL,
                    sale_tx_id TEXT,
                    replacement_date TEXT NOT NULL,
                    replacement_tx_id TEXT,
                    disallowed_loss REAL NOT NULL,
                    replacement_lot_id INTEGER
                )
            """)

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_lots_symbol ON tax_lots(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_lots_date ON tax_lots(purchase_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_symbol ON sales(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


class TaxReporter:
    """
    Tax reporter for cryptocurrency trades.

    Tracks cost basis, calculates gains/losses, detects wash sales,
    and generates tax reports.

    Usage:
        reporter = TaxReporter(cost_basis_method=CostBasisMethod.FIFO)

        # Record purchases
        reporter.record_buy("SOL", 10.0, 100.0, datetime.now(timezone.utc), "tx123")

        # Record sales
        result = reporter.record_sell("SOL", 5.0, 150.0, datetime.now(timezone.utc), "tx456")
        print(f"Gain/Loss: ${result.gain_loss}")

        # Generate reports
        summary = reporter.get_annual_summary(2024)
        reporter.export_to_csv("taxes_2024.csv", 2024)
    """

    def __init__(
        self,
        cost_basis_method: CostBasisMethod = CostBasisMethod.FIFO,
        db_path: Optional[Path] = None
    ):
        self.cost_basis_method = cost_basis_method
        db_path = db_path or Path(__file__).parent.parent.parent / "data" / "tax.db"
        self.db = TaxReporterDB(db_path)

    def record_buy(
        self,
        symbol: str,
        quantity: float,
        price: float,
        timestamp: datetime,
        tx_id: str,
        fee: float = 0.0
    ) -> TaxLot:
        """
        Record a purchase transaction.

        Args:
            symbol: Asset symbol (e.g., "SOL")
            quantity: Amount purchased
            price: Price per unit
            timestamp: Purchase date/time
            tx_id: Transaction ID
            fee: Transaction fee

        Returns:
            TaxLot: The created tax lot
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if price < 0:
            raise ValueError("Price cannot be negative")

        symbol = symbol.upper()
        total_cost = (price * quantity) + fee
        cost_per_unit = total_cost / quantity

        lot = TaxLot(
            symbol=symbol,
            quantity=quantity,
            remaining_quantity=quantity,
            cost_per_unit=cost_per_unit,
            total_cost=total_cost,
            fee=fee,
            purchase_date=timestamp,
            tx_id=tx_id,
            adjusted_cost_basis=cost_per_unit
        )

        # Save to database
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tax_lots
                (symbol, quantity, remaining_quantity, cost_per_unit, total_cost,
                 fee, purchase_date, tx_id, adjusted_cost_basis, wash_sale_adjustment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lot.symbol, lot.quantity, lot.remaining_quantity, lot.cost_per_unit,
                lot.total_cost, lot.fee, lot.purchase_date.isoformat(), lot.tx_id,
                lot.adjusted_cost_basis, lot.wash_sale_adjustment
            ))
            conn.commit()
            lot.id = cursor.lastrowid

        # Check for wash sale (purchase within 30 days of a loss sale)
        self._check_wash_sale_on_buy(lot)

        logger.info(f"Recorded buy: {quantity} {symbol} @ ${price:.2f}")
        return lot

    def record_sell(
        self,
        symbol: str,
        quantity: float,
        price: float,
        timestamp: datetime,
        tx_id: str,
        fee: float = 0.0
    ) -> SaleResult:
        """
        Record a sale transaction.

        Args:
            symbol: Asset symbol
            quantity: Amount sold
            price: Sale price per unit
            timestamp: Sale date/time
            tx_id: Transaction ID
            fee: Transaction fee

        Returns:
            SaleResult: Sale details including gain/loss
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if price < 0:
            raise ValueError("Price cannot be negative")

        symbol = symbol.upper()
        lots = self._get_available_lots(symbol)

        # Check sufficient quantity
        total_available = sum(lot.remaining_quantity for lot in lots)
        if total_available < quantity:
            raise InsufficientLotsError(
                f"Insufficient {symbol} lots. Available: {total_available}, requested: {quantity}"
            )

        # Select lots based on cost basis method
        selected_lots = self._select_lots(lots, quantity, timestamp)

        # Calculate cost basis and gain/loss
        total_cost_basis = 0.0
        lots_used = []
        long_term_gain = 0.0
        short_term_gain = 0.0
        total_holding_days = 0
        total_quantity_for_avg = 0.0

        for lot, qty_from_lot in selected_lots:
            lot_cost = qty_from_lot * lot.adjusted_cost_basis
            total_cost_basis += lot_cost
            lots_used.append((lot.id, qty_from_lot))

            # Calculate holding period for this portion
            holding_days = (timestamp - lot.purchase_date).days
            is_long = holding_days > 365

            # Calculate gain/loss for this portion
            portion_proceeds = qty_from_lot * price
            portion_gain = portion_proceeds - lot_cost

            if is_long:
                long_term_gain += portion_gain
            else:
                short_term_gain += portion_gain

            total_holding_days += holding_days * qty_from_lot
            total_quantity_for_avg += qty_from_lot

            # Update lot remaining quantity
            self._update_lot_quantity(lot.id, lot.remaining_quantity - qty_from_lot)

        # Calculate proceeds after fees
        gross_proceeds = price * quantity
        proceeds = gross_proceeds - fee
        gain_loss = proceeds - total_cost_basis

        # Determine if primarily long-term
        avg_holding_days = int(total_holding_days / total_quantity_for_avg) if total_quantity_for_avg > 0 else 0
        is_long_term = avg_holding_days > 365

        result = SaleResult(
            symbol=symbol,
            quantity=quantity,
            sale_price=price,
            sale_date=timestamp,
            proceeds=proceeds,
            cost_basis=total_cost_basis,
            gain_loss=gain_loss,
            fee=fee,
            is_long_term=is_long_term,
            holding_period_days=avg_holding_days,
            long_term_gain_loss=long_term_gain if long_term_gain != 0 else None,
            short_term_gain_loss=short_term_gain if short_term_gain != 0 else None,
            lots_used=lots_used,
            tx_id=tx_id
        )

        # Save sale to database
        self._save_sale(result)

        # Check for wash sale (loss sale followed by purchase within 30 days)
        if gain_loss < 0:
            self._check_wash_sale_on_sell(result)

        logger.info(f"Recorded sell: {quantity} {symbol} @ ${price:.2f}, gain/loss: ${gain_loss:.2f}")
        return result

    def _get_available_lots(self, symbol: str) -> List[TaxLot]:
        """Get all lots with remaining quantity for a symbol."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM tax_lots
                WHERE symbol = ? AND remaining_quantity > 0
                ORDER BY purchase_date ASC
            """, (symbol,))

            return [self._row_to_lot(row) for row in cursor.fetchall()]

    def _select_lots(
        self,
        lots: List[TaxLot],
        quantity: float,
        sale_date: datetime
    ) -> List[Tuple[TaxLot, float]]:
        """Select lots based on cost basis method."""
        if self.cost_basis_method == CostBasisMethod.FIFO:
            sorted_lots = sorted(lots, key=lambda l: l.purchase_date)
        elif self.cost_basis_method == CostBasisMethod.LIFO:
            sorted_lots = sorted(lots, key=lambda l: l.purchase_date, reverse=True)
        elif self.cost_basis_method == CostBasisMethod.HIFO:
            sorted_lots = sorted(lots, key=lambda l: l.adjusted_cost_basis, reverse=True)
        else:
            sorted_lots = lots

        selected = []
        remaining = quantity

        for lot in sorted_lots:
            if remaining <= 0:
                break

            qty_from_lot = min(remaining, lot.remaining_quantity)
            selected.append((lot, qty_from_lot))
            remaining -= qty_from_lot

        return selected

    def _update_lot_quantity(self, lot_id: int, new_quantity: float):
        """Update remaining quantity for a lot."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tax_lots SET remaining_quantity = ? WHERE id = ?
            """, (new_quantity, lot_id))
            conn.commit()

    def _save_sale(self, result: SaleResult):
        """Save sale to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sales
                (symbol, quantity, sale_price, sale_date, proceeds, cost_basis,
                 gain_loss, fee, is_long_term, holding_period_days,
                 long_term_gain_loss, short_term_gain_loss, lots_used_json, tx_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.symbol, result.quantity, result.sale_price,
                result.sale_date.isoformat(), result.proceeds, result.cost_basis,
                result.gain_loss, result.fee, 1 if result.is_long_term else 0,
                result.holding_period_days, result.long_term_gain_loss,
                result.short_term_gain_loss, json.dumps(result.lots_used), result.tx_id
            ))
            conn.commit()

    def _check_wash_sale_on_buy(self, new_lot: TaxLot):
        """Check if this purchase triggers a wash sale."""
        # Look for loss sales within 30 days before this purchase
        window_start = new_lot.purchase_date - timedelta(days=30)
        window_end = new_lot.purchase_date

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sales
                WHERE symbol = ? AND gain_loss < 0
                AND datetime(sale_date) >= datetime(?)
                AND datetime(sale_date) <= datetime(?)
            """, (new_lot.symbol, window_start.isoformat(), window_end.isoformat()))

            for row in cursor.fetchall():
                # This is a wash sale - disallow the loss
                disallowed_loss = abs(row['gain_loss'])

                # Adjust the cost basis of the replacement lot
                new_adjusted = new_lot.adjusted_cost_basis + (disallowed_loss / new_lot.quantity)

                cursor.execute("""
                    UPDATE tax_lots
                    SET adjusted_cost_basis = ?, wash_sale_adjustment = ?
                    WHERE id = ?
                """, (new_adjusted, disallowed_loss / new_lot.quantity, new_lot.id))

                # Record the wash sale
                cursor.execute("""
                    INSERT INTO wash_sales
                    (symbol, sale_date, sale_tx_id, replacement_date, replacement_tx_id,
                     disallowed_loss, replacement_lot_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_lot.symbol, row['sale_date'], row['tx_id'],
                    new_lot.purchase_date.isoformat(), new_lot.tx_id,
                    disallowed_loss, new_lot.id
                ))

            conn.commit()

    def _check_wash_sale_on_sell(self, sale: SaleResult):
        """Check if purchases within 30 days before/after create a wash sale."""
        # IRS wash sale rule: 30 days BEFORE or AFTER a loss sale
        window_start = sale.sale_date - timedelta(days=30)
        window_end = sale.sale_date + timedelta(days=30)

        # Get IDs of lots used in this sale to exclude them
        lots_used_ids = [lot_id for lot_id, _ in sale.lots_used]

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Build query - exclude lots used in this sale, include 30 days before AND after
            if lots_used_ids:
                placeholders = ','.join('?' * len(lots_used_ids))
                cursor.execute(f"""
                    SELECT * FROM tax_lots
                    WHERE symbol = ? AND remaining_quantity > 0
                    AND id NOT IN ({placeholders})
                    AND datetime(purchase_date) >= datetime(?)
                    AND datetime(purchase_date) <= datetime(?)
                """, [sale.symbol] + lots_used_ids + [window_start.isoformat(), window_end.isoformat()])
            else:
                cursor.execute("""
                    SELECT * FROM tax_lots
                    WHERE symbol = ? AND remaining_quantity > 0
                    AND datetime(purchase_date) >= datetime(?)
                    AND datetime(purchase_date) <= datetime(?)
                """, (sale.symbol, window_start.isoformat(), window_end.isoformat()))

            for row in cursor.fetchall():
                # This is a wash sale
                disallowed_loss = abs(sale.gain_loss)

                # Adjust the cost basis of the replacement lot
                lot = self._row_to_lot(row)
                new_adjusted = lot.adjusted_cost_basis + (disallowed_loss / lot.quantity)

                cursor.execute("""
                    UPDATE tax_lots
                    SET adjusted_cost_basis = ?, wash_sale_adjustment = ?
                    WHERE id = ?
                """, (new_adjusted, disallowed_loss / lot.quantity, row['id']))

                # Record the wash sale
                cursor.execute("""
                    INSERT INTO wash_sales
                    (symbol, sale_date, sale_tx_id, replacement_date, replacement_tx_id,
                     disallowed_loss, replacement_lot_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    sale.symbol, sale.sale_date.isoformat(), sale.tx_id,
                    row['purchase_date'], row['tx_id'],
                    disallowed_loss, row['id']
                ))

            conn.commit()

    def _row_to_lot(self, row: sqlite3.Row) -> TaxLot:
        """Convert database row to TaxLot."""
        return TaxLot(
            id=row['id'],
            symbol=row['symbol'],
            quantity=row['quantity'],
            remaining_quantity=row['remaining_quantity'],
            cost_per_unit=row['cost_per_unit'],
            total_cost=row['total_cost'],
            fee=row['fee'],
            purchase_date=datetime.fromisoformat(row['purchase_date']),
            tx_id=row['tx_id'],
            adjusted_cost_basis=row['adjusted_cost_basis'],
            wash_sale_adjustment=row['wash_sale_adjustment']
        )

    def get_lots(self, symbol: str) -> List[TaxLot]:
        """Get all lots for a symbol with remaining quantity."""
        return self._get_available_lots(symbol)

    def get_wash_sales(self, year: int) -> List[WashSale]:
        """Get all wash sales for a given year."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM wash_sales
                WHERE strftime('%Y', sale_date) = ?
            """, (str(year),))

            wash_sales = []
            for row in cursor.fetchall():
                wash_sales.append(WashSale(
                    id=row['id'],
                    symbol=row['symbol'],
                    sale_date=datetime.fromisoformat(row['sale_date']),
                    sale_tx_id=row['sale_tx_id'] or "",
                    replacement_date=datetime.fromisoformat(row['replacement_date']),
                    replacement_tx_id=row['replacement_tx_id'] or "",
                    disallowed_loss=row['disallowed_loss'],
                    replacement_lot_id=row['replacement_lot_id']
                ))

            return wash_sales

    def optimize_lots(
        self,
        symbol: str,
        quantity: float,
        sale_price: float,
        sale_date: Optional[datetime] = None,
        strategy: str = "min_tax"
    ) -> List[TaxLot]:
        """
        Optimize lot selection for a planned sale.

        Args:
            symbol: Asset symbol
            quantity: Planned sale quantity
            sale_price: Expected sale price
            sale_date: Planned sale date (default: now)
            strategy: Optimization strategy ("min_tax", "long_term_priority")

        Returns:
            List of recommended lots to sell
        """
        sale_date = sale_date or datetime.now(timezone.utc)
        lots = self._get_available_lots(symbol)

        if strategy == "min_tax":
            # Sort by highest cost (minimizes gain)
            sorted_lots = sorted(lots, key=lambda l: l.adjusted_cost_basis, reverse=True)
        elif strategy == "long_term_priority":
            # Sort by age (oldest first for long-term treatment)
            def sort_key(lot):
                holding_days = (sale_date - lot.purchase_date).days
                is_long = holding_days > 365
                return (-1 if is_long else 1, lot.purchase_date)

            sorted_lots = sorted(lots, key=sort_key)
        else:
            sorted_lots = lots

        # Select lots up to quantity
        selected = []
        remaining = quantity

        for lot in sorted_lots:
            if remaining <= 0:
                break
            if lot.remaining_quantity > 0:
                selected.append(lot)
                remaining -= lot.remaining_quantity

        return selected

    def get_annual_summary(self, year: int) -> AnnualSummary:
        """Get annual tax summary."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Get all sales for the year
            cursor.execute("""
                SELECT * FROM sales
                WHERE strftime('%Y', sale_date) = ?
            """, (str(year),))

            sales = cursor.fetchall()

            total_proceeds = 0.0
            total_cost_basis = 0.0
            short_term_gain = 0.0
            short_term_loss = 0.0
            long_term_gain = 0.0
            long_term_loss = 0.0

            for sale in sales:
                total_proceeds += sale['proceeds']
                total_cost_basis += sale['cost_basis']

                if sale['is_long_term']:
                    if sale['gain_loss'] > 0:
                        long_term_gain += sale['gain_loss']
                    else:
                        long_term_loss += abs(sale['gain_loss'])
                else:
                    if sale['gain_loss'] > 0:
                        short_term_gain += sale['gain_loss']
                    else:
                        short_term_loss += abs(sale['gain_loss'])

            # Get wash sale adjustments
            cursor.execute("""
                SELECT SUM(disallowed_loss) as total FROM wash_sales
                WHERE strftime('%Y', sale_date) = ?
            """, (str(year),))
            result = cursor.fetchone()
            wash_sale_disallowed = result['total'] or 0.0

            return AnnualSummary(
                year=year,
                total_proceeds=total_proceeds,
                total_cost_basis=total_cost_basis,
                net_gain_loss=total_proceeds - total_cost_basis,
                short_term_gain=short_term_gain,
                short_term_loss=short_term_loss,
                long_term_gain=long_term_gain,
                long_term_loss=long_term_loss,
                wash_sale_disallowed=wash_sale_disallowed,
                total_transactions=len(sales)
            )

    def export_to_csv(self, filepath: str, year: int):
        """Export transactions to CSV format."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sales
                WHERE strftime('%Y', sale_date) = ?
                ORDER BY sale_date
            """, (str(year),))

            sales = cursor.fetchall()

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Symbol', 'Quantity', 'Sale Date', 'Sale Price',
                'Proceeds', 'Cost Basis', 'Gain/Loss', 'Holding Period (Days)',
                'Long-Term', 'Transaction ID'
            ])

            for sale in sales:
                writer.writerow([
                    sale['symbol'],
                    sale['quantity'],
                    sale['sale_date'],
                    sale['sale_price'],
                    sale['proceeds'],
                    sale['cost_basis'],
                    sale['gain_loss'],
                    sale['holding_period_days'],
                    'Yes' if sale['is_long_term'] else 'No',
                    sale['tx_id']
                ])

        logger.info(f"Exported {len(sales)} transactions to {filepath}")

    def export_to_turbotax(self, filepath: str, year: int):
        """Export to TurboTax-compatible CSV format."""
        sale_details = []

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, l.purchase_date as acquired_date
                FROM sales s
                LEFT JOIN (
                    SELECT tx_id, purchase_date FROM tax_lots
                ) l ON json_extract(s.lots_used_json, '$[0][0]') = l.tx_id
                WHERE strftime('%Y', s.sale_date) = ?
                ORDER BY s.sale_date
            """, (str(year),))

            sales = cursor.fetchall()

            # Get lot details for each sale (inside connection context)
            for sale in sales:
                lots_used = json.loads(sale['lots_used_json']) if sale['lots_used_json'] else []

                # Get the earliest purchase date from lots used
                acquired_date = None
                if lots_used:
                    cursor.execute("""
                        SELECT MIN(purchase_date) as min_date FROM tax_lots
                        WHERE id IN ({})
                    """.format(','.join('?' * len(lots_used))), [l[0] for l in lots_used])
                    result = cursor.fetchone()
                    if result and result['min_date']:
                        acquired_date = result['min_date']

                sale_details.append({
                    'sale': sale,
                    'acquired_date': acquired_date or sale['sale_date']
                })

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Description', 'Date Acquired', 'Date Sold',
                'Proceeds', 'Cost Basis', 'Gain or Loss'
            ])

            for detail in sale_details:
                sale = detail['sale']
                writer.writerow([
                    f"{sale['quantity']} {sale['symbol']}",
                    detail['acquired_date'][:10] if detail['acquired_date'] else '',
                    sale['sale_date'][:10],
                    f"{sale['proceeds']:.2f}",
                    f"{sale['cost_basis']:.2f}",
                    f"{sale['gain_loss']:.2f}"
                ])

        logger.info(f"Exported {len(sale_details)} transactions to TurboTax format: {filepath}")

    def generate_8949_report(self, year: int) -> Dict[str, Any]:
        """Generate IRS Form 8949 data structure."""
        part_i = []  # Short-term transactions
        part_ii = []  # Long-term transactions

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sales
                WHERE strftime('%Y', sale_date) = ?
                ORDER BY sale_date
            """, (str(year),))

            sales = cursor.fetchall()

            for sale in sales:
                lots_used = json.loads(sale['lots_used_json']) if sale['lots_used_json'] else []

                # Get acquired date
                acquired_date = None
                if lots_used:
                    cursor.execute("""
                        SELECT MIN(purchase_date) as min_date FROM tax_lots
                        WHERE id IN ({})
                    """.format(','.join('?' * len(lots_used))), [l[0] for l in lots_used])
                    result = cursor.fetchone()
                    if result:
                        acquired_date = result['min_date']

                entry = {
                    'description': f"{sale['quantity']} {sale['symbol']}",
                    'date_acquired': acquired_date[:10] if acquired_date else '',
                    'date_sold': sale['sale_date'][:10],
                    'proceeds': sale['proceeds'],
                    'cost_basis': sale['cost_basis'],
                    'adjustment_code': '',
                    'adjustment_amount': 0,
                    'gain_or_loss': sale['gain_loss']
                }

                if sale['is_long_term']:
                    part_ii.append(entry)
                else:
                    part_i.append(entry)

        # Calculate totals
        part_i_totals = {
            'proceeds': sum(e['proceeds'] for e in part_i),
            'cost_basis': sum(e['cost_basis'] for e in part_i),
            'adjustment_amount': sum(e['adjustment_amount'] for e in part_i),
            'gain_or_loss': sum(e['gain_or_loss'] for e in part_i)
        }

        part_ii_totals = {
            'proceeds': sum(e['proceeds'] for e in part_ii),
            'cost_basis': sum(e['cost_basis'] for e in part_ii),
            'adjustment_amount': sum(e['adjustment_amount'] for e in part_ii),
            'gain_or_loss': sum(e['gain_or_loss'] for e in part_ii)
        }

        return {
            'year': year,
            'part_i': {
                'transactions': part_i,
                'totals': part_i_totals
            },
            'part_ii': {
                'transactions': part_ii,
                'totals': part_ii_totals
            }
        }


# Singleton
_reporter: Optional[TaxReporter] = None


def get_tax_reporter(
    cost_basis_method: CostBasisMethod = CostBasisMethod.FIFO
) -> TaxReporter:
    """Get singleton tax reporter."""
    global _reporter
    if _reporter is None:
        _reporter = TaxReporter(cost_basis_method=cost_basis_method)
    return _reporter
