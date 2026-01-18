"""
Charity Handler - Manage charity distributions.

Distributes 5% of all fees to supported charities:
- Effective Altruism: AI safety research
- GiveWell: malaria prevention, education
- Water.org: clean water access
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# Default charities
DEFAULT_CHARITIES = [
    {
        "name": "Effective Altruism",
        "wallet_address": "EA11111111111111111111111111111111111111112",
        "category": "ai_safety",
        "description": "Research into AI safety and alignment",
        "weight": 1.0,
    },
    {
        "name": "GiveWell",
        "wallet_address": "GW11111111111111111111111111111111111111112",
        "category": "health",
        "description": "Malaria prevention, education, and health interventions",
        "weight": 1.0,
    },
    {
        "name": "Water.org",
        "wallet_address": "WO11111111111111111111111111111111111111112",
        "category": "water",
        "description": "Clean water access for communities in need",
        "weight": 1.0,
    },
]


@dataclass
class Charity:
    """A charity entry."""
    name: str
    wallet_address: str
    category: str
    description: str = ""
    weight: float = 1.0
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CharityDistribution:
    """A charity distribution record."""
    id: str
    charity: str
    amount: float
    month: str
    tx_hash: str
    timestamp: float = field(default_factory=time.time)
    wallet_address: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CharityHandler:
    """
    Manages charity distributions.

    Usage:
        handler = CharityHandler()

        # List charities
        charities = handler.list_charities()

        # Calculate payout
        payout = handler.calculate_payout(
            total_charity_funds=1000.0,
            month="2026-01"
        )

        # Record distribution
        handler.record_distribution("GiveWell", 100.0, "2026-01", "tx_hash")
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        load_defaults: bool = False
    ):
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).resolve().parents[2] / "data" / "revenue"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.charities_file = self.data_dir / "charities.json"
        self.ledger_file = self.data_dir / "charity_ledger.jsonl"

        # Load or initialize charities
        self._charities: Dict[str, Charity] = self._load_charities()

        if load_defaults and not self._charities:
            self._load_default_charities()

    def _load_charities(self) -> Dict[str, Charity]:
        """Load charities from file."""
        if self.charities_file.exists():
            try:
                data = json.loads(self.charities_file.read_text())
                return {
                    k: Charity(**v)
                    for k, v in data.items()
                    if k != '_metadata'
                }
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_charities(self) -> None:
        """Save charities to file."""
        data = {k: v.to_dict() for k, v in self._charities.items()}
        data['_metadata'] = {'updated_at': time.time()}
        self.charities_file.write_text(json.dumps(data, indent=2))

    def _load_default_charities(self) -> None:
        """Load default charities."""
        for charity_data in DEFAULT_CHARITIES:
            charity = Charity(**charity_data)
            self._charities[charity.name] = charity
        self._save_charities()

    def add_charity(
        self,
        name: str,
        wallet_address: str,
        category: str,
        description: str = "",
        weight: float = 1.0
    ) -> Charity:
        """
        Add a new charity.

        Args:
            name: Charity name
            wallet_address: Solana wallet address
            category: Category (health, water, ai_safety, etc.)
            description: Optional description
            weight: Distribution weight (default 1.0)

        Returns:
            Created Charity
        """
        charity = Charity(
            name=name,
            wallet_address=wallet_address,
            category=category,
            description=description,
            weight=weight,
        )

        self._charities[name] = charity
        self._save_charities()

        return charity

    def list_charities(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        List all charities.

        Args:
            active_only: Only return active charities

        Returns:
            List of charity dictionaries
        """
        charities = list(self._charities.values())

        if active_only:
            charities = [c for c in charities if c.active]

        return [c.to_dict() for c in charities]

    def calculate_payout(
        self,
        total_charity_funds: float,
        month: str
    ) -> Dict[str, Any]:
        """
        Calculate charity payout distribution.

        Distributes funds proportionally based on charity weights.

        Args:
            total_charity_funds: Total funds to distribute
            month: Month string (YYYY-MM)

        Returns:
            Payout breakdown by charity
        """
        active_charities = [c for c in self._charities.values() if c.active]

        if not active_charities:
            return {
                'month': month,
                'total': total_charity_funds,
                'distributions': [],
                'error': 'No active charities configured',
            }

        # Calculate total weight
        total_weight = sum(c.weight for c in active_charities)

        # Calculate distributions
        distributions = []
        for charity in active_charities:
            share = (charity.weight / total_weight) * total_charity_funds
            distributions.append({
                'charity': charity.name,
                'wallet_address': charity.wallet_address,
                'amount': round(share, 6),
                'share_pct': round((charity.weight / total_weight) * 100, 2),
            })

        return {
            'month': month,
            'total': total_charity_funds,
            'distributions': distributions,
            'charity_count': len(distributions),
        }

    def record_distribution(
        self,
        charity_name: str,
        amount: float,
        month: str,
        tx_hash: str
    ) -> CharityDistribution:
        """
        Record a charity distribution.

        Args:
            charity_name: Name of charity
            amount: Amount distributed
            month: Month string (YYYY-MM)
            tx_hash: Blockchain transaction hash

        Returns:
            Distribution record
        """
        charity = self._charities.get(charity_name)
        wallet_address = charity.wallet_address if charity else ""

        distribution = CharityDistribution(
            id=f"cd_{int(time.time() * 1000)}",
            charity=charity_name,
            amount=amount,
            month=month,
            tx_hash=tx_hash,
            wallet_address=wallet_address,
        )

        # Append to ledger
        with open(self.ledger_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(distribution.to_dict()) + "\n")

        return distribution

    def get_ledger(
        self,
        charity_name: Optional[str] = None,
        month: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get charity distribution ledger.

        Args:
            charity_name: Filter by charity (optional)
            month: Filter by month (optional)

        Returns:
            List of distribution records
        """
        records: List[Dict[str, Any]] = []

        if self.ledger_file.exists():
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)

                        # Apply filters
                        if charity_name and data.get('charity') != charity_name:
                            continue
                        if month and data.get('month') != month:
                            continue

                        records.append(data)
                    except json.JSONDecodeError:
                        continue

        return records

    def get_total_distributed(
        self,
        charity_name: Optional[str] = None
    ) -> float:
        """
        Get total amount distributed.

        Args:
            charity_name: Filter by charity (optional)

        Returns:
            Total amount distributed
        """
        records = self.get_ledger(charity_name=charity_name)
        return sum(r.get('amount', 0) for r in records)

    def execute_payout(
        self,
        total_charity_funds: float,
        month: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Execute monthly charity payout.

        Args:
            total_charity_funds: Total funds to distribute
            month: Month string (YYYY-MM)
            dry_run: If True, only simulate (no actual transfers)

        Returns:
            Payout results
        """
        payout = self.calculate_payout(total_charity_funds, month)

        results = {
            'month': month,
            'dry_run': dry_run,
            'total': total_charity_funds,
            'distributions': [],
        }

        for dist in payout.get('distributions', []):
            if dry_run:
                results['distributions'].append({
                    **dist,
                    'status': 'simulated',
                    'tx_hash': f"dry_run_{int(time.time())}",
                })
            else:
                # In production, this would call Solana transfer
                # For now, record with mock tx hash
                tx_hash = f"real_tx_{int(time.time())}"

                self.record_distribution(
                    charity_name=dist['charity'],
                    amount=dist['amount'],
                    month=month,
                    tx_hash=tx_hash,
                )

                results['distributions'].append({
                    **dist,
                    'status': 'completed',
                    'tx_hash': tx_hash,
                })

        return results
