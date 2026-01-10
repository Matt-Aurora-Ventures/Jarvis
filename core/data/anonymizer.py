"""
Data Anonymizer
Prompt #88: Anonymous Trade Data Collector - Anonymization pipeline

Provides privacy-preserving data transformations.
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re

logger = logging.getLogger("jarvis.data.anonymizer")


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class AnonymizationConfig:
    """Configuration for data anonymization"""

    # Hashing
    hash_wallet: bool = True
    hash_signature: bool = True
    hash_salt: str = ""  # Will use env var if empty

    # Bucketing
    round_amounts: bool = True
    amount_bucket_lamports: int = 100_000_000  # 0.1 SOL buckets
    bucket_timestamps: bool = True
    timestamp_bucket_minutes: int = 15

    # Noise
    add_noise_to_amounts: bool = False
    noise_percentage: float = 0.05  # 5% noise

    # Removal
    remove_ip_address: bool = True
    remove_user_agent: bool = True
    remove_exact_timestamps: bool = True

    # Retention
    k_anonymity_threshold: int = 5  # Minimum records in a group


# =============================================================================
# ANONYMIZER
# =============================================================================

class DataAnonymizer:
    """
    Anonymize user data for privacy-preserving collection.

    Techniques used:
    - One-way hashing for identifiers
    - Bucketing for amounts and timestamps
    - Noise addition for amounts
    - k-anonymity enforcement
    - PII removal
    """

    def __init__(self, config: AnonymizationConfig = None):
        self.config = config or AnonymizationConfig()

        # Get salt from config or environment
        self._salt = self.config.hash_salt or os.getenv(
            "ANONYMIZATION_SALT",
            "jarvis_anon_salt_change_in_production"
        )

        # Track for k-anonymity
        self._bucket_counts: Dict[str, int] = {}

    # =========================================================================
    # MAIN ANONYMIZATION
    # =========================================================================

    def anonymize_trade(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize a single trade record.

        Args:
            trade: Raw trade data with potentially identifying info

        Returns:
            Anonymized trade data safe for storage/analysis
        """
        anon = {}

        # Hash wallet address
        if "wallet" in trade:
            if self.config.hash_wallet:
                anon["user_hash"] = self._hash_identifier(trade["wallet"])
            # Never include raw wallet
        elif "user_id" in trade:
            if self.config.hash_wallet:
                anon["user_hash"] = self._hash_identifier(trade["user_id"])

        # Hash signature
        if "signature" in trade and self.config.hash_signature:
            anon["tx_hash"] = self._hash_identifier(trade["signature"])[:16]

        # Bucket amount
        if "amount" in trade:
            if self.config.round_amounts:
                anon["amount_bucket"] = self._bucket_amount(trade["amount"])
            else:
                anon["amount"] = trade["amount"]

            # Add noise if configured
            if self.config.add_noise_to_amounts:
                anon["amount_bucket"] = self._add_noise(anon.get("amount_bucket", trade["amount"]))

        # Bucket timestamp
        if "timestamp" in trade:
            if self.config.bucket_timestamps:
                anon["time_bucket"] = self._bucket_timestamp(trade["timestamp"])
            elif not self.config.remove_exact_timestamps:
                anon["timestamp"] = trade["timestamp"].isoformat() if isinstance(trade["timestamp"], datetime) else trade["timestamp"]

        # Copy non-sensitive fields directly
        safe_fields = [
            "token_mint", "symbol", "side", "direction",
            "outcome", "strategy", "strategy_name",
            "pnl_pct", "hold_duration_seconds",
            "price_impact_bps", "slippage_bps",
        ]

        for field in safe_fields:
            if field in trade:
                anon[field] = trade[field]

        # Copy market conditions
        if "market_conditions" in trade:
            anon["market_conditions"] = self._anonymize_market_conditions(
                trade["market_conditions"]
            )

        # Remove sensitive fields
        sensitive_fields = [
            "ip_address", "user_agent", "email", "phone",
            "api_key", "session_id", "device_id",
        ]
        for field in sensitive_fields:
            if field in anon:
                del anon[field]

        return anon

    def anonymize_batch(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Anonymize a batch of trades with k-anonymity checks.

        Args:
            trades: List of raw trades

        Returns:
            List of anonymized trades meeting k-anonymity threshold
        """
        # First pass: anonymize all
        anonymized = [self.anonymize_trade(t) for t in trades]

        # Second pass: enforce k-anonymity
        if self.config.k_anonymity_threshold > 1:
            anonymized = self._enforce_k_anonymity(anonymized)

        return anonymized

    # =========================================================================
    # HASHING
    # =========================================================================

    def _hash_identifier(self, value: str) -> str:
        """
        Create a one-way hash of an identifier.

        Uses salted SHA-256 for irreversibility.
        """
        if not value:
            return ""

        salted = f"{self._salt}:{value}"
        hash_bytes = hashlib.sha256(salted.encode()).digest()

        # Return first 16 bytes as hex (32 chars)
        return hash_bytes[:16].hex()

    def hash_for_lookup(self, value: str) -> str:
        """
        Hash a value for lookup (same as _hash_identifier).

        Use this when you need to find anonymized records
        for a known user.
        """
        return self._hash_identifier(value)

    # =========================================================================
    # BUCKETING
    # =========================================================================

    def _bucket_amount(self, amount: int) -> int:
        """
        Round amount to bucket.

        E.g., 150_000_000 lamports with 100M bucket -> 100_000_000
        """
        if amount <= 0:
            return 0

        bucket = self.config.amount_bucket_lamports
        return (amount // bucket) * bucket

    def _bucket_timestamp(self, ts: datetime) -> str:
        """
        Bucket timestamp to reduce precision.

        E.g., 15:47:32 with 15min bucket -> 15:45:00
        """
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))

        minutes = ts.minute - (ts.minute % self.config.timestamp_bucket_minutes)
        bucketed = ts.replace(minute=minutes, second=0, microsecond=0)

        return bucketed.isoformat()

    def _add_noise(self, amount: int) -> int:
        """Add random noise to amount within configured percentage"""
        import random

        noise_range = int(amount * self.config.noise_percentage)
        noise = random.randint(-noise_range, noise_range)

        return max(0, amount + noise)

    # =========================================================================
    # K-ANONYMITY
    # =========================================================================

    def _enforce_k_anonymity(
        self,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Enforce k-anonymity by removing records in small groups.

        Groups are defined by (user_hash, time_bucket, token_mint).
        """
        # Count groups
        group_counts: Dict[tuple, int] = {}
        for record in records:
            key = (
                record.get("user_hash", ""),
                record.get("time_bucket", ""),
                record.get("token_mint", ""),
            )
            group_counts[key] = group_counts.get(key, 0) + 1

        # Filter records
        k = self.config.k_anonymity_threshold
        filtered = []

        for record in records:
            key = (
                record.get("user_hash", ""),
                record.get("time_bucket", ""),
                record.get("token_mint", ""),
            )
            if group_counts.get(key, 0) >= k:
                filtered.append(record)

        removed = len(records) - len(filtered)
        if removed > 0:
            logger.info(f"Removed {removed} records for k-anonymity (k={k})")

        return filtered

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _anonymize_market_conditions(
        self,
        conditions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Anonymize market condition data"""
        safe_conditions = {}

        # These are aggregate market metrics, safe to keep
        safe_fields = [
            "volatility_24h", "volume_vs_avg", "trend_direction",
            "sentiment_score", "market_cap_tier", "liquidity_tier",
        ]

        for field in safe_fields:
            if field in conditions:
                safe_conditions[field] = conditions[field]

        return safe_conditions

    def validate_anonymized(self, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate that data is properly anonymized.

        Returns:
            (is_valid, list of issues)
        """
        issues = []

        # Check for wallet addresses (base58, 32-44 chars)
        wallet_pattern = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

        for key, value in data.items():
            if isinstance(value, str):
                # Check for potential wallet address
                if wallet_pattern.match(value) and key not in ["token_mint", "tx_hash"]:
                    issues.append(f"Potential wallet address in {key}")

                # Check for potential signature (88 chars base58)
                if len(value) == 88 and wallet_pattern.match(value):
                    issues.append(f"Potential signature in {key}")

                # Check for email
                if "@" in value and "." in value:
                    issues.append(f"Potential email in {key}")

                # Check for IP address
                ip_pattern = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
                if ip_pattern.search(value):
                    issues.append(f"Potential IP address in {key}")

        return len(issues) == 0, issues


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_anonymizer: Optional[DataAnonymizer] = None


def get_anonymizer() -> DataAnonymizer:
    """Get or create the anonymizer singleton"""
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = DataAnonymizer()
    return _anonymizer


def anonymize_trade(trade: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to anonymize a single trade"""
    return get_anonymizer().anonymize_trade(trade)


def anonymize_trades(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convenience function to anonymize multiple trades"""
    return get_anonymizer().anonymize_batch(trades)
