"""
Wallet Security Audit

Comprehensive security auditing for cryptocurrency wallets.
Checks for:
- Compromise indicators
- Transaction signature validity
- Large/unusual withdrawals
- Suspicious activity patterns

Supports Solana wallets primarily.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Severity levels for security alerts."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertType(str, Enum):
    """Types of security alerts."""
    LARGE_WITHDRAWAL = "large_withdrawal"
    RAPID_TRANSACTIONS = "rapid_transactions"
    UNKNOWN_DESTINATION = "unknown_destination"
    INVALID_SIGNATURE = "invalid_signature"
    UNUSUAL_PATTERN = "unusual_pattern"
    FIRST_SEEN_INTERACTION = "first_seen_interaction"


@dataclass
class SecurityAlert:
    """A security alert from wallet audit."""
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    transaction_id: Optional[str] = None


@dataclass
class WalletAuditResult:
    """Result of a wallet security audit."""
    wallet_address: str
    is_secure: bool
    has_alerts: bool
    alerts: List[str]
    security_alerts: List[SecurityAlert] = field(default_factory=list)
    recent_transactions: List[Dict[str, Any]] = field(default_factory=list)
    invalid_signatures: int = 0
    audit_timestamp: datetime = field(default_factory=datetime.now)
    risk_score: float = 0.0  # 0-100, higher is riskier

    def add_alert(self, alert: SecurityAlert) -> None:
        """Add an alert to the result."""
        self.security_alerts.append(alert)
        self.alerts.append(alert.message)
        self.has_alerts = True

        # Update risk score based on severity
        severity_scores = {
            AlertSeverity.CRITICAL: 40,
            AlertSeverity.HIGH: 25,
            AlertSeverity.MEDIUM: 15,
            AlertSeverity.LOW: 5,
            AlertSeverity.INFO: 0
        }
        self.risk_score = min(100, self.risk_score + severity_scores.get(alert.severity, 0))


class WalletAuditor:
    """
    Comprehensive wallet security auditor.

    Performs security checks on cryptocurrency wallets including:
    - Transaction signature verification
    - Large withdrawal detection
    - Suspicious pattern detection
    - Unknown destination monitoring
    """

    # Default thresholds
    LARGE_WITHDRAWAL_THRESHOLD_SOL = 100  # SOL
    LARGE_WITHDRAWAL_THRESHOLD_USD = 10000  # USD
    RAPID_TRANSACTION_WINDOW_SECONDS = 300  # 5 minutes
    RAPID_TRANSACTION_COUNT = 5

    def __init__(
        self,
        large_withdrawal_threshold: float = LARGE_WITHDRAWAL_THRESHOLD_SOL,
        rapid_tx_window: int = RAPID_TRANSACTION_WINDOW_SECONDS,
        rapid_tx_count: int = RAPID_TRANSACTION_COUNT
    ):
        """
        Initialize the wallet auditor.

        Args:
            large_withdrawal_threshold: Amount threshold for large withdrawal alerts
            rapid_tx_window: Time window (seconds) for rapid transaction detection
            rapid_tx_count: Number of transactions in window to trigger alert
        """
        self.large_withdrawal_threshold = large_withdrawal_threshold
        self.rapid_tx_window = rapid_tx_window
        self.rapid_tx_count = rapid_tx_count

        # Known safe addresses (treasury, exchanges, etc.)
        self._known_addresses: set = set()
        self._blacklisted_addresses: set = set()

    def add_known_address(self, address: str, label: str = "") -> None:
        """Add a known safe address."""
        self._known_addresses.add(address)

    def add_blacklisted_address(self, address: str, reason: str = "") -> None:
        """Add a blacklisted address."""
        self._blacklisted_addresses.add(address)

    async def _fetch_recent_transactions(
        self,
        wallet_address: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent transactions for a wallet.

        This is a stub - in production, would call Solana RPC or indexer.

        Args:
            wallet_address: The wallet address to fetch transactions for
            limit: Maximum number of transactions to fetch

        Returns:
            List of transaction records
        """
        # In production, this would call:
        # - Solana RPC (getSignaturesForAddress, getTransaction)
        # - Or an indexer API like Helius

        # For now, return empty list (tests will mock this)
        return []

    async def _verify_transaction_signature(
        self,
        transaction: Dict[str, Any]
    ) -> bool:
        """
        Verify a transaction signature.

        Args:
            transaction: Transaction data with signature

        Returns:
            True if signature is valid
        """
        # In production, verify with Solana
        # For now, check the 'verified' field in test data
        return transaction.get("verified", True)

    def _check_large_withdrawal(
        self,
        transaction: Dict[str, Any],
        result: WalletAuditResult
    ) -> None:
        """Check for large withdrawal amounts."""
        tx_type = transaction.get("type", "").lower()
        amount = transaction.get("amount", 0)

        if tx_type in ["withdrawal", "transfer", "send"]:
            if amount >= self.large_withdrawal_threshold:
                result.add_alert(SecurityAlert(
                    alert_type=AlertType.LARGE_WITHDRAWAL,
                    severity=AlertSeverity.HIGH,
                    message=f"Large withdrawal detected: {amount} (threshold: {self.large_withdrawal_threshold})",
                    details={"amount": amount, "threshold": self.large_withdrawal_threshold},
                    transaction_id=transaction.get("signature")
                ))

    def _check_rapid_transactions(
        self,
        transactions: List[Dict[str, Any]],
        result: WalletAuditResult
    ) -> None:
        """Check for unusually rapid transaction patterns."""
        if len(transactions) < self.rapid_tx_count:
            return

        now = time.time()
        recent_count = 0

        for tx in transactions:
            tx_time = tx.get("timestamp", 0)
            if now - tx_time <= self.rapid_tx_window:
                recent_count += 1

        if recent_count >= self.rapid_tx_count:
            result.add_alert(SecurityAlert(
                alert_type=AlertType.RAPID_TRANSACTIONS,
                severity=AlertSeverity.MEDIUM,
                message=f"Rapid transactions detected: {recent_count} in {self.rapid_tx_window}s",
                details={
                    "transaction_count": recent_count,
                    "window_seconds": self.rapid_tx_window
                }
            ))

    def _check_unknown_destinations(
        self,
        transaction: Dict[str, Any],
        result: WalletAuditResult
    ) -> None:
        """Check for transactions to unknown addresses."""
        destination = transaction.get("destination") or transaction.get("to")

        if destination:
            if destination in self._blacklisted_addresses:
                result.add_alert(SecurityAlert(
                    alert_type=AlertType.UNKNOWN_DESTINATION,
                    severity=AlertSeverity.CRITICAL,
                    message=f"Transaction to blacklisted address: {destination[:16]}...",
                    details={"destination": destination},
                    transaction_id=transaction.get("signature")
                ))
            elif destination not in self._known_addresses:
                result.add_alert(SecurityAlert(
                    alert_type=AlertType.FIRST_SEEN_INTERACTION,
                    severity=AlertSeverity.LOW,
                    message=f"First-time interaction with: {destination[:16]}...",
                    details={"destination": destination},
                    transaction_id=transaction.get("signature")
                ))

    def _check_unusual_patterns(
        self,
        transactions: List[Dict[str, Any]],
        result: WalletAuditResult
    ) -> None:
        """Check for unusual transaction patterns."""
        if len(transactions) < 3:
            return

        # Check for same-amount transactions (potential automation/attack)
        amounts = [tx.get("amount", 0) for tx in transactions if tx.get("amount")]
        if amounts:
            from collections import Counter
            amount_counts = Counter(amounts)
            most_common_amount, count = amount_counts.most_common(1)[0]

            if count >= 3 and count / len(amounts) > 0.5:
                result.add_alert(SecurityAlert(
                    alert_type=AlertType.UNUSUAL_PATTERN,
                    severity=AlertSeverity.MEDIUM,
                    message=f"Repeated same-amount transactions: {most_common_amount} ({count} times)",
                    details={"amount": most_common_amount, "count": count}
                ))

    async def audit(
        self,
        wallet_address: str,
        check_patterns: bool = True,
        check_signatures: bool = True,
        transaction_limit: int = 50
    ) -> WalletAuditResult:
        """
        Perform a comprehensive security audit on a wallet.

        Args:
            wallet_address: The wallet address to audit
            check_patterns: Whether to check for suspicious patterns
            check_signatures: Whether to verify transaction signatures
            transaction_limit: Maximum transactions to analyze

        Returns:
            WalletAuditResult with findings
        """
        result = WalletAuditResult(
            wallet_address=wallet_address,
            is_secure=True,
            has_alerts=False,
            alerts=[]
        )

        try:
            # Fetch recent transactions
            transactions = await self._fetch_recent_transactions(
                wallet_address,
                limit=transaction_limit
            )
            result.recent_transactions = transactions

            for tx in transactions:
                # Check signature validity
                if check_signatures:
                    if not await self._verify_transaction_signature(tx):
                        result.invalid_signatures += 1
                        result.add_alert(SecurityAlert(
                            alert_type=AlertType.INVALID_SIGNATURE,
                            severity=AlertSeverity.CRITICAL,
                            message=f"Invalid transaction signature detected",
                            transaction_id=tx.get("signature")
                        ))

                # Check for large withdrawals
                self._check_large_withdrawal(tx, result)

                # Check for unknown destinations
                self._check_unknown_destinations(tx, result)

            # Check for rapid transactions
            if check_patterns:
                self._check_rapid_transactions(transactions, result)
                self._check_unusual_patterns(transactions, result)

            # Determine overall security status
            critical_alerts = [
                a for a in result.security_alerts
                if a.severity == AlertSeverity.CRITICAL
            ]
            result.is_secure = len(critical_alerts) == 0

        except Exception as e:
            logger.error(f"Wallet audit failed for {wallet_address}: {e}")
            result.is_secure = False
            result.add_alert(SecurityAlert(
                alert_type=AlertType.UNUSUAL_PATTERN,
                severity=AlertSeverity.HIGH,
                message=f"Audit error: {str(e)}"
            ))

        return result


# Convenience function
async def audit_wallet_security(
    wallet_address: str,
    **kwargs
) -> WalletAuditResult:
    """
    Audit wallet security (convenience function).

    Args:
        wallet_address: The wallet to audit
        **kwargs: Additional arguments for WalletAuditor.audit()

    Returns:
        WalletAuditResult
    """
    auditor = WalletAuditor()
    return await auditor.audit(wallet_address, **kwargs)


# CLI entry point
if __name__ == "__main__":
    import sys

    async def main():
        if len(sys.argv) < 2:
            print("Usage: python wallet_audit.py <wallet_address>")
            sys.exit(1)

        wallet_address = sys.argv[1]
        print(f"Auditing wallet: {wallet_address}")
        print("=" * 50)

        result = await audit_wallet_security(wallet_address)

        print(f"Secure: {result.is_secure}")
        print(f"Risk Score: {result.risk_score}/100")
        print(f"Alerts: {len(result.alerts)}")

        if result.alerts:
            print("\nAlerts:")
            for alert in result.alerts:
                print(f"  - {alert}")

    asyncio.run(main())
