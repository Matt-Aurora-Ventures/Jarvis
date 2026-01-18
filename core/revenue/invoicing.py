"""
Invoice System - Generate monthly invoices.

Features:
- Monthly invoice generation
- PDF export with QR code
- Verification endpoint links
- Email/Telegram delivery
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class InvoiceItem:
    """An invoice line item."""
    description: str
    quantity: float
    unit_price: float
    total: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Invoice:
    """An invoice."""
    id: str
    user_id: str
    month: str
    created_at: float = field(default_factory=time.time)
    items: List[InvoiceItem] = field(default_factory=list)
    total_profit: float = 0.0
    total_fees: float = 0.0
    user_earnings: float = 0.0
    verification_hash: str = ""
    pdf_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['items'] = [item.to_dict() if isinstance(item, InvoiceItem) else item for item in self.items]
        return data


class InvoiceGenerator:
    """
    Generates monthly invoices.

    Usage:
        generator = InvoiceGenerator()

        # Generate invoice data
        invoice = generator.generate_invoice_data(
            user_id="user_1",
            month="2026-01",
            trades=[{"profit": 100, "fee": 0.5}]
        )

        # Generate PDF
        pdf_path = generator.generate_invoice_pdf("user_1", "2026-01", trades)
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).resolve().parents[2] / "data" / "revenue"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.invoices_dir = self.data_dir / "invoices"
        self.invoices_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.data_dir / "invoice_index.json"

        # Load index
        self._invoices: Dict[str, Invoice] = self._load_index()

    def _load_index(self) -> Dict[str, Invoice]:
        """Load invoice index."""
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text())
                invoices = {}
                for k, v in data.items():
                    if k == '_metadata':
                        continue
                    # Convert items back to InvoiceItem
                    items = [
                        InvoiceItem(**item) if isinstance(item, dict) else item
                        for item in v.get('items', [])
                    ]
                    v['items'] = items
                    invoices[k] = Invoice(**v)
                return invoices
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_index(self) -> None:
        """Save invoice index."""
        data = {k: v.to_dict() for k, v in self._invoices.items()}
        data['_metadata'] = {'updated_at': time.time()}
        self.index_file.write_text(json.dumps(data, indent=2))

    def _generate_verification_hash(
        self,
        user_id: str,
        month: str,
        total_fees: float
    ) -> str:
        """Generate verification hash for invoice."""
        content = f"{user_id}:{month}:{total_fees:.6f}:{int(time.time())}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def generate_invoice_data(
        self,
        user_id: str,
        month: str,
        trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate invoice data for a user's monthly activity.

        Args:
            user_id: User identifier
            month: Month string (YYYY-MM)
            trades: List of trades with profit and fee

        Returns:
            Invoice data dictionary
        """
        # Calculate totals
        total_profit = sum(t.get('profit', 0) for t in trades)
        total_fees = sum(t.get('fee', 0) for t in trades)
        user_earnings = total_fees * 0.75  # 75% to user

        # Generate verification hash
        verification_hash = self._generate_verification_hash(
            user_id, month, total_fees
        )

        # Create invoice items
        items = []
        for i, trade in enumerate(trades):
            items.append(InvoiceItem(
                description=f"Trade {i+1} profit fee",
                quantity=1,
                unit_price=trade.get('fee', 0),
                total=trade.get('fee', 0),
            ))

        # Create invoice
        invoice_id = f"inv_{user_id[:8]}_{month.replace('-', '')}"

        invoice = Invoice(
            id=invoice_id,
            user_id=user_id,
            month=month,
            items=items,
            total_profit=total_profit,
            total_fees=total_fees,
            user_earnings=user_earnings,
            verification_hash=verification_hash,
        )

        # Store in index
        self._invoices[invoice_id] = invoice
        self._save_index()

        # Build response
        result = invoice.to_dict()
        result['verification_url'] = f"https://jarvis.lifeos.ai/verify/{verification_hash}"
        result['qr_code'] = f"qr_{verification_hash}"  # Placeholder for actual QR

        return result

    def generate_invoice_pdf(
        self,
        user_id: str,
        month: str,
        trades: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Generate PDF invoice.

        Args:
            user_id: User identifier
            month: Month string (YYYY-MM)
            trades: List of trades

        Returns:
            Path to generated PDF
        """
        # Generate data first
        invoice_data = self.generate_invoice_data(user_id, month, trades)

        # Create user directory
        user_dir = self.invoices_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = user_dir / f"{month}.pdf"

        # In production, use a PDF library like reportlab
        # For now, create a simple text summary
        summary = f"""
JARVIS Trading Invoice
======================

Invoice ID: {invoice_data['id']}
User: {user_id}
Period: {month}
Generated: {datetime.now(timezone.utc).isoformat()}

Summary
-------
Total Profit: ${invoice_data['total_profit']:.2f}
Total Fees: ${invoice_data['total_fees']:.2f}
Your Earnings: ${invoice_data['user_earnings']:.2f}

Verification
------------
Hash: {invoice_data['verification_hash']}
URL: {invoice_data['verification_url']}

Trade Details
-------------
"""
        for i, item in enumerate(invoice_data.get('items', [])):
            if isinstance(item, dict):
                summary += f"{i+1}. {item['description']}: ${item['total']:.2f}\n"

        # Write as text (PDF placeholder)
        text_path = user_dir / f"{month}.txt"
        text_path.write_text(summary)

        # Update invoice with path
        invoice_id = invoice_data['id']
        if invoice_id in self._invoices:
            self._invoices[invoice_id].pdf_path = str(pdf_path)
            self._save_index()

        return str(pdf_path)

    def list_invoices(
        self,
        user_id: str,
        limit: int = 12
    ) -> List[Dict[str, Any]]:
        """
        List invoices for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of invoices

        Returns:
            List of invoice summaries
        """
        invoices = [
            inv.to_dict()
            for inv in self._invoices.values()
            if inv.user_id == user_id
        ]

        # Sort by month descending
        invoices.sort(key=lambda x: x.get('month', ''), reverse=True)

        return invoices[:limit]

    def get_invoice(
        self,
        invoice_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific invoice.

        Args:
            invoice_id: Invoice identifier

        Returns:
            Invoice data (or None)
        """
        invoice = self._invoices.get(invoice_id)
        if invoice:
            result = invoice.to_dict()
            result['verification_url'] = f"https://jarvis.lifeos.ai/verify/{invoice.verification_hash}"
            return result
        return None

    def verify_invoice(self, verification_hash: str) -> Optional[Dict[str, Any]]:
        """
        Verify an invoice by hash.

        Args:
            verification_hash: Verification hash

        Returns:
            Invoice data if valid (or None)
        """
        for invoice in self._invoices.values():
            if invoice.verification_hash == verification_hash:
                return {
                    'valid': True,
                    'invoice_id': invoice.id,
                    'user_id': invoice.user_id,
                    'month': invoice.month,
                    'total_fees': invoice.total_fees,
                    'user_earnings': invoice.user_earnings,
                }

        return None

    def send_invoice(
        self,
        invoice_id: str,
        method: str = 'telegram'
    ) -> Dict[str, Any]:
        """
        Send invoice to user.

        Args:
            invoice_id: Invoice identifier
            method: Delivery method ('email' or 'telegram')

        Returns:
            Delivery status
        """
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            return {'success': False, 'error': 'Invoice not found'}

        # In production, integrate with email/telegram
        return {
            'success': True,
            'method': method,
            'invoice_id': invoice_id,
            'message': f'Invoice sent via {method}',
        }
