"""
Trade History Export - Export trades to various formats for tax/reporting.
"""

import csv
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from io import StringIO
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Standardized trade record for export."""
    timestamp: str
    trade_id: str
    trade_type: str  # BUY, SELL
    asset_symbol: str
    asset_name: str
    asset_address: str
    quantity: float
    price_per_unit: float
    total_value: float
    fee_amount: float
    fee_currency: str
    base_currency: str  # SOL, USD
    tx_signature: str
    platform: str = "Jarvis"
    notes: str = ""


@dataclass
class ExportConfig:
    """Configuration for trade export."""
    format: str = "csv"  # csv, json, koinly, cointracker, taxbit
    include_fees: bool = True
    base_currency: str = "USD"
    timezone: str = "UTC"
    date_format: str = "%Y-%m-%d %H:%M:%S"


class TradeExporter:
    """
    Export trade history to various formats.

    Supported formats:
    - CSV: Standard comma-separated values
    - JSON: Machine-readable JSON
    - Koinly: Import format for Koinly tax software
    - CoinTracker: Import format for CoinTracker
    - TaxBit: Import format for TaxBit

    Usage:
        exporter = TradeExporter()
        trades = exporter.get_trades(start_date="2024-01-01")
        csv_data = exporter.export_csv(trades)
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path(__file__).parent.parent / "data" / "trades.db"
        self._ensure_db()

    def _ensure_db(self):
        """Ensure trades table exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                trade_id TEXT UNIQUE,
                trade_type TEXT NOT NULL,
                asset_symbol TEXT NOT NULL,
                asset_name TEXT,
                asset_address TEXT,
                quantity REAL NOT NULL,
                price_per_unit REAL,
                total_value REAL,
                fee_amount REAL DEFAULT 0,
                fee_currency TEXT DEFAULT 'SOL',
                base_currency TEXT DEFAULT 'SOL',
                tx_signature TEXT,
                platform TEXT DEFAULT 'Jarvis',
                notes TEXT
            )
        """)
        conn.commit()
        conn.close()

    def record_trade(self, trade: TradeRecord) -> int:
        """Record a trade to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO trades
                (timestamp, trade_id, trade_type, asset_symbol, asset_name,
                 asset_address, quantity, price_per_unit, total_value,
                 fee_amount, fee_currency, base_currency, tx_signature, platform, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.timestamp, trade.trade_id, trade.trade_type,
                trade.asset_symbol, trade.asset_name, trade.asset_address,
                trade.quantity, trade.price_per_unit, trade.total_value,
                trade.fee_amount, trade.fee_currency, trade.base_currency,
                trade.tx_signature, trade.platform, trade.notes
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_trades(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        trade_type: Optional[str] = None,
        asset_symbol: Optional[str] = None,
        limit: int = 10000
    ) -> List[TradeRecord]:
        """Query trades from database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        if trade_type:
            query += " AND trade_type = ?"
            params.append(trade_type)
        if asset_symbol:
            query += " AND asset_symbol = ?"
            params.append(asset_symbol)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            TradeRecord(
                timestamp=row['timestamp'],
                trade_id=row['trade_id'] or "",
                trade_type=row['trade_type'],
                asset_symbol=row['asset_symbol'],
                asset_name=row['asset_name'] or "",
                asset_address=row['asset_address'] or "",
                quantity=row['quantity'],
                price_per_unit=row['price_per_unit'] or 0,
                total_value=row['total_value'] or 0,
                fee_amount=row['fee_amount'] or 0,
                fee_currency=row['fee_currency'] or "SOL",
                base_currency=row['base_currency'] or "SOL",
                tx_signature=row['tx_signature'] or "",
                platform=row['platform'] or "Jarvis",
                notes=row['notes'] or ""
            )
            for row in rows
        ]

    def export_csv(self, trades: List[TradeRecord], config: ExportConfig = None) -> str:
        """Export trades to CSV format."""
        config = config or ExportConfig()
        output = StringIO()

        fieldnames = [
            'Date', 'Type', 'Asset', 'Asset Name', 'Quantity',
            'Price', 'Total Value', 'Fee', 'Fee Currency',
            'Currency', 'Transaction ID', 'Notes'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for trade in trades:
            writer.writerow({
                'Date': trade.timestamp,
                'Type': trade.trade_type,
                'Asset': trade.asset_symbol,
                'Asset Name': trade.asset_name,
                'Quantity': trade.quantity,
                'Price': trade.price_per_unit,
                'Total Value': trade.total_value,
                'Fee': trade.fee_amount if config.include_fees else "",
                'Fee Currency': trade.fee_currency if config.include_fees else "",
                'Currency': trade.base_currency,
                'Transaction ID': trade.tx_signature,
                'Notes': trade.notes
            })

        return output.getvalue()

    def export_json(self, trades: List[TradeRecord], config: ExportConfig = None) -> str:
        """Export trades to JSON format."""
        return json.dumps(
            [asdict(t) for t in trades],
            indent=2,
            default=str
        )

    def export_koinly(self, trades: List[TradeRecord]) -> str:
        """
        Export trades in Koinly universal format.

        Koinly format columns:
        Date, Sent Amount, Sent Currency, Received Amount, Received Currency,
        Fee Amount, Fee Currency, Net Worth Amount, Net Worth Currency,
        Label, Description, TxHash
        """
        output = StringIO()
        fieldnames = [
            'Date', 'Sent Amount', 'Sent Currency', 'Received Amount',
            'Received Currency', 'Fee Amount', 'Fee Currency',
            'Net Worth Amount', 'Net Worth Currency', 'Label',
            'Description', 'TxHash'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for trade in trades:
            if trade.trade_type == "BUY":
                row = {
                    'Date': trade.timestamp,
                    'Sent Amount': trade.total_value,
                    'Sent Currency': trade.base_currency,
                    'Received Amount': trade.quantity,
                    'Received Currency': trade.asset_symbol,
                    'Fee Amount': trade.fee_amount,
                    'Fee Currency': trade.fee_currency,
                    'Net Worth Amount': trade.total_value,
                    'Net Worth Currency': 'USD',
                    'Label': 'trade',
                    'Description': trade.notes,
                    'TxHash': trade.tx_signature
                }
            else:  # SELL
                row = {
                    'Date': trade.timestamp,
                    'Sent Amount': trade.quantity,
                    'Sent Currency': trade.asset_symbol,
                    'Received Amount': trade.total_value,
                    'Received Currency': trade.base_currency,
                    'Fee Amount': trade.fee_amount,
                    'Fee Currency': trade.fee_currency,
                    'Net Worth Amount': trade.total_value,
                    'Net Worth Currency': 'USD',
                    'Label': 'trade',
                    'Description': trade.notes,
                    'TxHash': trade.tx_signature
                }
            writer.writerow(row)

        return output.getvalue()

    def export_cointracker(self, trades: List[TradeRecord]) -> str:
        """
        Export trades in CoinTracker format.

        CoinTracker columns:
        Date, Received Quantity, Received Currency, Sent Quantity, Sent Currency,
        Fee Amount, Fee Currency, Tag
        """
        output = StringIO()
        fieldnames = [
            'Date', 'Received Quantity', 'Received Currency',
            'Sent Quantity', 'Sent Currency', 'Fee Amount', 'Fee Currency', 'Tag'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for trade in trades:
            if trade.trade_type == "BUY":
                row = {
                    'Date': trade.timestamp,
                    'Received Quantity': trade.quantity,
                    'Received Currency': trade.asset_symbol,
                    'Sent Quantity': trade.total_value,
                    'Sent Currency': trade.base_currency,
                    'Fee Amount': trade.fee_amount,
                    'Fee Currency': trade.fee_currency,
                    'Tag': ''
                }
            else:
                row = {
                    'Date': trade.timestamp,
                    'Received Quantity': trade.total_value,
                    'Received Currency': trade.base_currency,
                    'Sent Quantity': trade.quantity,
                    'Sent Currency': trade.asset_symbol,
                    'Fee Amount': trade.fee_amount,
                    'Fee Currency': trade.fee_currency,
                    'Tag': ''
                }
            writer.writerow(row)

        return output.getvalue()

    def export_taxbit(self, trades: List[TradeRecord]) -> str:
        """
        Export trades in TaxBit format.

        TaxBit columns:
        Date and Time, Transaction Type, Sent Quantity, Sent Currency,
        Sending Source, Received Quantity, Received Currency, Receiving Destination,
        Fee, Fee Currency, Exchange Transaction ID, Blockchain Transaction Hash
        """
        output = StringIO()
        fieldnames = [
            'Date and Time', 'Transaction Type', 'Sent Quantity', 'Sent Currency',
            'Sending Source', 'Received Quantity', 'Received Currency',
            'Receiving Destination', 'Fee', 'Fee Currency',
            'Exchange Transaction ID', 'Blockchain Transaction Hash'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for trade in trades:
            tx_type = "Buy" if trade.trade_type == "BUY" else "Sell"

            if trade.trade_type == "BUY":
                row = {
                    'Date and Time': trade.timestamp,
                    'Transaction Type': tx_type,
                    'Sent Quantity': trade.total_value,
                    'Sent Currency': trade.base_currency,
                    'Sending Source': trade.platform,
                    'Received Quantity': trade.quantity,
                    'Received Currency': trade.asset_symbol,
                    'Receiving Destination': trade.platform,
                    'Fee': trade.fee_amount,
                    'Fee Currency': trade.fee_currency,
                    'Exchange Transaction ID': trade.trade_id,
                    'Blockchain Transaction Hash': trade.tx_signature
                }
            else:
                row = {
                    'Date and Time': trade.timestamp,
                    'Transaction Type': tx_type,
                    'Sent Quantity': trade.quantity,
                    'Sent Currency': trade.asset_symbol,
                    'Sending Source': trade.platform,
                    'Received Quantity': trade.total_value,
                    'Received Currency': trade.base_currency,
                    'Receiving Destination': trade.platform,
                    'Fee': trade.fee_amount,
                    'Fee Currency': trade.fee_currency,
                    'Exchange Transaction ID': trade.trade_id,
                    'Blockchain Transaction Hash': trade.tx_signature
                }
            writer.writerow(row)

        return output.getvalue()

    def export(
        self,
        trades: List[TradeRecord],
        format: str = "csv",
        config: ExportConfig = None
    ) -> str:
        """Export trades in specified format."""
        exporters = {
            'csv': self.export_csv,
            'json': self.export_json,
            'koinly': self.export_koinly,
            'cointracker': self.export_cointracker,
            'taxbit': self.export_taxbit
        }

        exporter = exporters.get(format.lower())
        if not exporter:
            raise ValueError(f"Unknown export format: {format}")

        if format.lower() in ('csv', 'json'):
            return exporter(trades, config)
        return exporter(trades)

    def save_export(
        self,
        trades: List[TradeRecord],
        output_path: Path,
        format: str = "csv",
        config: ExportConfig = None
    ):
        """Export trades and save to file."""
        data = self.export(trades, format, config)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(data)

        logger.info(f"Exported {len(trades)} trades to {output_path}")

    def get_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """Get trade summary statistics."""
        trades = self.get_trades(start_date=start_date, end_date=end_date)

        if not trades:
            return {
                'total_trades': 0,
                'total_buys': 0,
                'total_sells': 0,
                'total_volume': 0,
                'total_fees': 0,
                'unique_assets': 0
            }

        buys = [t for t in trades if t.trade_type == "BUY"]
        sells = [t for t in trades if t.trade_type == "SELL"]
        unique_assets = set(t.asset_symbol for t in trades)

        return {
            'total_trades': len(trades),
            'total_buys': len(buys),
            'total_sells': len(sells),
            'total_buy_volume': sum(t.total_value for t in buys),
            'total_sell_volume': sum(t.total_value for t in sells),
            'total_fees': sum(t.fee_amount for t in trades),
            'unique_assets': len(unique_assets),
            'date_range': {
                'start': min(t.timestamp for t in trades),
                'end': max(t.timestamp for t in trades)
            }
        }


# Singleton
_exporter: Optional[TradeExporter] = None

def get_trade_exporter() -> TradeExporter:
    """Get singleton trade exporter."""
    global _exporter
    if _exporter is None:
        _exporter = TradeExporter()
    return _exporter
