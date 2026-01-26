"""
Scam Detector

Advanced anti-scam detection system:
- Pump-and-dump pattern detection
- Suspicious trade identification
- Honeypot monitoring
- Known scam tracking
- Wash trading detection
- Coordinated activity detection
"""

import json
import logging
import sqlite3
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from enum import Enum

logger = logging.getLogger(__name__)


class ScamType(str, Enum):
    """Types of scams."""
    RUGPULL = "rugpull"
    HONEYPOT = "honeypot"
    PUMP_AND_DUMP = "pump_and_dump"
    WASH_TRADING = "wash_trading"
    FAKE_VOLUME = "fake_volume"
    INSIDER_TRADING = "insider_trading"
    COORDINATED_MANIPULATION = "coordinated_manipulation"


class WalletRole(str, Enum):
    """Roles in scam operations."""
    CREATOR = "creator"
    PROMOTER = "promoter"
    DUMPER = "dumper"
    WASH_TRADER = "wash_trader"
    BENEFICIARY = "beneficiary"


@dataclass
class ScamReport:
    """A reported scam."""
    token_address: str
    scam_type: str
    reported_at: datetime
    evidence: Dict[str, Any]
    reporter: Optional[str] = None
    confirmed: bool = False


@dataclass
class PricePoint:
    """A price data point."""
    timestamp: datetime
    price: float
    volume: Optional[float] = None


class ScamDetector:
    """
    Advanced scam detection system.

    Analyzes trading patterns, price movements, and wallet behavior
    to detect various types of crypto scams.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        pump_threshold: float = 3.0,  # 3x price increase
        dump_threshold: float = 0.5,  # 50% drop
        wash_trade_threshold: float = 0.7,  # 70% similarity score
        min_pump_duration_minutes: int = 5,
        max_pump_duration_hours: int = 24
    ):
        """
        Initialize the scam detector.

        Args:
            cache_dir: Directory for caching scam database
            pump_threshold: Multiplier for pump detection
            dump_threshold: Percentage drop for dump detection
            wash_trade_threshold: Threshold for wash trade similarity
            min_pump_duration_minutes: Minimum duration for pump
            max_pump_duration_hours: Maximum duration before dump
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path("data/scam_detector")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.pump_threshold = pump_threshold
        self.dump_threshold = dump_threshold
        self.wash_trade_threshold = wash_trade_threshold
        self.min_pump_duration = timedelta(minutes=min_pump_duration_minutes)
        self.max_pump_duration = timedelta(hours=max_pump_duration_hours)

        # In-memory scam database
        self._known_scams: Dict[str, ScamReport] = {}
        self._scam_wallets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._watchlist: Dict[str, Dict[str, Any]] = {}

        # Load from persistent storage
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for persistence."""
        self._db_path = self.cache_dir / "scam_database.db"

        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS known_scams (
                token_address TEXT PRIMARY KEY,
                scam_type TEXT NOT NULL,
                reported_at TEXT NOT NULL,
                evidence TEXT,
                reporter TEXT,
                confirmed INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS scam_wallets (
                wallet_address TEXT NOT NULL,
                role TEXT NOT NULL,
                associated_token TEXT,
                reported_at TEXT NOT NULL,
                PRIMARY KEY (wallet_address, associated_token)
            );

            CREATE TABLE IF NOT EXISTS watchlist (
                token_address TEXT PRIMARY KEY,
                alert_threshold REAL NOT NULL,
                callback_url TEXT,
                added_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_scam_type ON known_scams(scam_type);
            CREATE INDEX IF NOT EXISTS idx_wallet ON scam_wallets(wallet_address);
        """)

        conn.commit()
        conn.close()

        # Load into memory
        self._load_from_database()

    def _load_from_database(self):
        """Load scam data from database."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        # Load known scams
        cursor.execute("SELECT * FROM known_scams")
        for row in cursor.fetchall():
            token_address, scam_type, reported_at, evidence, reporter, confirmed = row
            self._known_scams[token_address] = ScamReport(
                token_address=token_address,
                scam_type=scam_type,
                reported_at=datetime.fromisoformat(reported_at),
                evidence=json.loads(evidence) if evidence else {},
                reporter=reporter,
                confirmed=bool(confirmed)
            )

        # Load scam wallets
        cursor.execute("SELECT * FROM scam_wallets")
        for row in cursor.fetchall():
            wallet, role, token, reported_at = row
            self._scam_wallets[wallet].append({
                "role": role,
                "associated_token": token,
                "reported_at": reported_at
            })

        # Load watchlist
        cursor.execute("SELECT * FROM watchlist")
        for row in cursor.fetchall():
            token, threshold, callback, added_at = row
            self._watchlist[token] = {
                "alert_threshold": threshold,
                "callback_url": callback,
                "added_at": added_at
            }

        conn.close()

    def _parse_price_history(
        self,
        price_history: List[Dict[str, Any]]
    ) -> List[PricePoint]:
        """Parse price history into PricePoint objects."""
        points = []
        for item in price_history:
            try:
                ts = item.get("timestamp")
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                elif isinstance(ts, (int, float)):
                    ts = datetime.fromtimestamp(ts, tz=timezone.utc)

                points.append(PricePoint(
                    timestamp=ts,
                    price=float(item.get("price", 0)),
                    volume=item.get("volume")
                ))
            except (ValueError, TypeError):
                continue

        return sorted(points, key=lambda p: p.timestamp)

    def detect_pump_and_dump(
        self,
        token_address: str,
        price_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detect pump-and-dump patterns in price history.

        Args:
            token_address: Token address
            price_history: List of price points

        Returns:
            Dict with detection results
        """
        if len(price_history) < 3:
            return {
                "is_pump_and_dump": False,
                "confidence": 0.0,
                "reason": "Insufficient price data"
            }

        points = self._parse_price_history(price_history)
        if len(points) < 3:
            return {
                "is_pump_and_dump": False,
                "confidence": 0.0,
                "reason": "Could not parse price data"
            }

        prices = [p.price for p in points]
        min_price = min(prices)
        max_price = max(prices)
        final_price = prices[-1]

        # Check for pump pattern
        pump_detected = False
        dump_detected = False
        indicators = []
        confidence = 0.0

        if min_price > 0:
            # Pump: significant price increase
            price_increase = max_price / min_price
            if price_increase >= self.pump_threshold:
                pump_detected = True
                indicators.append("price_spike")
                confidence += 0.4

            # Dump: significant drop from peak
            if max_price > 0:
                drop_from_peak = final_price / max_price
                if drop_from_peak <= self.dump_threshold:
                    dump_detected = True
                    indicators.append("price_crash")
                    confidence += 0.4

        # Check timing
        if pump_detected and dump_detected:
            max_idx = prices.index(max_price)
            min_idx = prices.index(min_price)

            # Pump should come before dump
            if max_idx > min_idx:
                pump_duration = points[max_idx].timestamp - points[min_idx].timestamp

                if self.min_pump_duration <= pump_duration <= self.max_pump_duration:
                    indicators.append("timing_pattern")
                    confidence += 0.2

        confidence = min(confidence, 1.0)

        return {
            "is_pump_and_dump": pump_detected and dump_detected and confidence > 0.5,
            "pump_detected": pump_detected,
            "dump_detected": dump_detected,
            "confidence": round(confidence, 3),
            "indicators": indicators,
            "price_increase_factor": max_price / min_price if min_price > 0 else 0,
            "final_price_ratio": final_price / max_price if max_price > 0 else 0
        }

    def identify_suspicious_trade(
        self,
        trade_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Identify suspicious trading patterns.

        Args:
            trade_data: Trade information

        Returns:
            Dict with suspicion analysis
        """
        reasons = []
        is_suspicious = False

        # Check price impact
        price_impact = trade_data.get("price_impact_pct", 0)
        if price_impact > 10:
            reasons.append(f"high_price_impact:{price_impact}%")
            is_suspicious = True

        # Check trade size
        trade_size = trade_data.get("trade_size_usd", 0)
        if trade_size > 100000:
            reasons.append(f"large_trade:{trade_size}usd")

        # Check for known scam wallets
        buyer = trade_data.get("buyer_address")
        seller = trade_data.get("seller_address")

        if buyer and buyer in self._scam_wallets:
            reasons.append("buyer_is_known_scammer")
            is_suspicious = True

        if seller and seller in self._scam_wallets:
            reasons.append("seller_is_known_scammer")
            is_suspicious = True

        # Check wallet history if available
        history = self._get_wallet_history(buyer, seller)
        if history:
            shared_txs = history.get("shared_transactions", 0)
            if shared_txs > 10:
                reasons.append(f"frequent_counterparty:{shared_txs}_txs")
                is_suspicious = True

            avg_interval = history.get("avg_trade_interval_seconds", float('inf'))
            if avg_interval < 120:  # Less than 2 minutes between trades
                reasons.append("rapid_trading")
                is_suspicious = True

        return {
            "is_suspicious": is_suspicious,
            "reasons": reasons,
            "trade_size_usd": trade_size,
            "price_impact_pct": price_impact
        }

    def _get_wallet_history(
        self,
        wallet1: Optional[str],
        wallet2: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Get shared history between two wallets."""
        # Placeholder - would query blockchain/database
        return None

    def detect_wash_trading(
        self,
        token_address: str,
        recent_trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detect wash trading patterns.

        Args:
            token_address: Token address
            recent_trades: Recent trades to analyze

        Returns:
            Dict with wash trading analysis
        """
        if len(recent_trades) < 4:
            return {
                "wash_trading_detected": False,
                "wash_trading_score": 0.0,
                "reason": "Insufficient trades to analyze"
            }

        # Build wallet pair frequency map
        pair_counts: Dict[frozenset, int] = defaultdict(int)
        total_trades = len(recent_trades)

        for trade in recent_trades:
            buyer = trade.get("buyer")
            seller = trade.get("seller")
            if buyer and seller:
                pair = frozenset([buyer, seller])
                pair_counts[pair] += 1

        # Calculate wash trading score
        if not pair_counts:
            return {
                "wash_trading_detected": False,
                "wash_trading_score": 0.0
            }

        # Find repeated pairs
        repeated_pairs = [
            (pair, count) for pair, count in pair_counts.items()
            if count >= 2
        ]

        repeated_trade_count = sum(count for _, count in repeated_pairs)
        wash_score = repeated_trade_count / total_trades if total_trades > 0 else 0

        return {
            "wash_trading_detected": wash_score >= self.wash_trade_threshold,
            "wash_trading_score": round(wash_score, 3),
            "repeated_pairs": len(repeated_pairs),
            "total_trades_analyzed": total_trades
        }

    def detect_honeypot(
        self,
        token_address: str
    ) -> Dict[str, Any]:
        """
        Detect if token is a honeypot.

        Args:
            token_address: Token address

        Returns:
            Dict with honeypot analysis
        """
        # Simulate a sell to check if possible
        sell_result = self._simulate_sell(token_address)

        if sell_result is None:
            return {
                "is_honeypot": False,
                "confidence": 0.5,
                "reason": "Could not simulate sell"
            }

        reasons = []
        is_honeypot = False

        # Check if sell is blocked
        if not sell_result.get("can_sell", True):
            reasons.append("sell_blocked")
            is_honeypot = True

        # Check for high sell tax
        sell_tax = sell_result.get("tax_on_sell", 0)
        if sell_tax > 50:
            reasons.append(f"extreme_sell_tax:{sell_tax}%")
            is_honeypot = True
        elif sell_tax > 20:
            reasons.append(f"high_sell_tax:{sell_tax}%")

        return {
            "is_honeypot": is_honeypot,
            "reasons": reasons,
            "sell_tax_pct": sell_tax,
            "can_sell": sell_result.get("can_sell", True)
        }

    def _simulate_sell(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Simulate a sell transaction."""
        # Placeholder - would use simulation API
        return {"can_sell": True, "tax_on_sell": 0}

    def check_known_scam(
        self,
        token_address: str
    ) -> Dict[str, Any]:
        """
        Check if token is in known scam database.

        Args:
            token_address: Token address

        Returns:
            Dict with scam database result
        """
        if token_address in self._known_scams:
            scam = self._known_scams[token_address]
            return {
                "is_known_scam": True,
                "scam_type": scam.scam_type,
                "reported_at": scam.reported_at.isoformat(),
                "confirmed": scam.confirmed,
                "evidence": scam.evidence
            }

        return {
            "is_known_scam": False
        }

    def report_scam(
        self,
        token_address: str,
        scam_type: str,
        evidence: Dict[str, Any],
        reporter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Report a token as a scam.

        Args:
            token_address: Token address
            scam_type: Type of scam
            evidence: Supporting evidence
            reporter: Who reported it

        Returns:
            Result of report
        """
        scam = ScamReport(
            token_address=token_address,
            scam_type=scam_type,
            reported_at=datetime.now(timezone.utc),
            evidence=evidence,
            reporter=reporter
        )

        self._known_scams[token_address] = scam

        # Persist to database
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO known_scams
            (token_address, scam_type, reported_at, evidence, reporter, confirmed)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (
            token_address,
            scam_type,
            scam.reported_at.isoformat(),
            json.dumps(evidence),
            reporter
        ))
        conn.commit()
        conn.close()

        return {"success": True, "token_address": token_address}

    def report_scam_wallet(
        self,
        wallet_address: str,
        role: str,
        associated_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Report a wallet involved in scams.

        Args:
            wallet_address: Wallet address
            role: Role in scam
            associated_token: Associated scam token

        Returns:
            Result of report
        """
        entry = {
            "role": role,
            "associated_token": associated_token,
            "reported_at": datetime.now(timezone.utc).isoformat()
        }

        self._scam_wallets[wallet_address].append(entry)

        # Persist
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO scam_wallets
            (wallet_address, role, associated_token, reported_at)
            VALUES (?, ?, ?, ?)
        """, (
            wallet_address,
            role,
            associated_token,
            entry["reported_at"]
        ))
        conn.commit()
        conn.close()

        return {"success": True, "wallet_address": wallet_address}

    def check_wallet_reputation(
        self,
        wallet_address: str
    ) -> Dict[str, Any]:
        """
        Check reputation of a wallet.

        Args:
            wallet_address: Wallet address

        Returns:
            Reputation analysis
        """
        associations = self._scam_wallets.get(wallet_address, [])

        if not associations:
            return {
                "reputation_score": 1.0,
                "scam_associations": 0,
                "is_known_scammer": False
            }

        # Calculate reputation score
        score = 1.0 - (0.2 * len(associations))
        score = max(0, score)

        return {
            "reputation_score": round(score, 3),
            "scam_associations": len(associations),
            "is_known_scammer": len(associations) > 0,
            "roles": list(set(a["role"] for a in associations))
        }

    def comprehensive_scan(
        self,
        token_address: str,
        price_history: Optional[List[Dict[str, Any]]] = None,
        recent_trades: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Run comprehensive scam scan on token.

        Args:
            token_address: Token address
            price_history: Optional price history
            recent_trades: Optional recent trades

        Returns:
            Comprehensive scan results
        """
        results = {
            "token_address": token_address,
            "scan_time": datetime.now(timezone.utc).isoformat()
        }

        # Check known scam database
        results["scam_database_match"] = self.check_known_scam(token_address)

        # Check honeypot
        results["honeypot_risk"] = self.detect_honeypot(token_address)

        # Pump and dump analysis
        if price_history:
            results["pump_dump_risk"] = self.detect_pump_and_dump(
                token_address, price_history
            )
        else:
            results["pump_dump_risk"] = {"analyzed": False}

        # Wash trading analysis
        if recent_trades:
            results["wash_trading_risk"] = self.detect_wash_trading(
                token_address, recent_trades
            )
        else:
            results["wash_trading_risk"] = {"analyzed": False}

        # Calculate overall risk
        risk_factors = []

        if results["scam_database_match"].get("is_known_scam"):
            risk_factors.append(1.0)
        if results["honeypot_risk"].get("is_honeypot"):
            risk_factors.append(0.9)
        if results.get("pump_dump_risk", {}).get("is_pump_and_dump"):
            risk_factors.append(0.8)
        if results.get("wash_trading_risk", {}).get("wash_trading_detected"):
            risk_factors.append(0.6)

        overall_risk = max(risk_factors) if risk_factors else 0.1

        results["overall_risk_score"] = round(overall_risk, 3)

        if overall_risk >= 0.8:
            results["recommendation"] = "DO_NOT_TRADE"
        elif overall_risk >= 0.5:
            results["recommendation"] = "HIGH_RISK"
        elif overall_risk >= 0.3:
            results["recommendation"] = "MODERATE_RISK"
        else:
            results["recommendation"] = "LOW_RISK"

        return results

    def add_to_watchlist(
        self,
        token_address: str,
        alert_threshold: float = 0.7,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add token to monitoring watchlist.

        Args:
            token_address: Token address
            alert_threshold: Risk threshold for alerts
            callback_url: URL to call on alert

        Returns:
            Result
        """
        self._watchlist[token_address] = {
            "alert_threshold": alert_threshold,
            "callback_url": callback_url,
            "added_at": datetime.now(timezone.utc).isoformat()
        }

        # Persist
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO watchlist
            (token_address, alert_threshold, callback_url, added_at)
            VALUES (?, ?, ?, ?)
        """, (
            token_address,
            alert_threshold,
            callback_url,
            self._watchlist[token_address]["added_at"]
        ))
        conn.commit()
        conn.close()

        return {"success": True, "token_address": token_address}

    def remove_from_watchlist(self, token_address: str) -> Dict[str, Any]:
        """Remove token from watchlist."""
        if token_address in self._watchlist:
            del self._watchlist[token_address]

            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM watchlist WHERE token_address = ?",
                (token_address,)
            )
            conn.commit()
            conn.close()

            return {"success": True}
        return {"success": False, "error": "Not in watchlist"}

    def is_watchlisted(self, token_address: str) -> bool:
        """Check if token is watchlisted."""
        return token_address in self._watchlist

    def check_watchlist(self) -> List[Dict[str, Any]]:
        """Check all watchlisted tokens and return alerts."""
        alerts = []

        for token_address, config in self._watchlist.items():
            threshold = config.get("alert_threshold", 0.7)
            scan_result = self.comprehensive_scan(token_address)

            if scan_result.get("overall_risk_score", 0) >= threshold:
                alerts.append({
                    "token_address": token_address,
                    "risk_score": scan_result.get("overall_risk_score", 0),
                    "recommendation": scan_result.get("recommendation", "UNKNOWN"),
                    "callback_url": config.get("callback_url")
                })

        return alerts

    def detect_coordinated_activity(
        self,
        token_address: str,
        events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detect coordinated buying/selling activity.

        Args:
            token_address: Token address
            events: List of buy/sell events

        Returns:
            Coordination analysis
        """
        if len(events) < 3:
            return {
                "coordinated_activity_detected": False,
                "confidence": 0.0
            }

        # Parse timestamps and check for clustering
        timestamps = []
        for event in events:
            ts = event.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            timestamps.append(ts)

        if len(timestamps) < 3:
            return {
                "coordinated_activity_detected": False,
                "confidence": 0.0
            }

        # Calculate time deltas
        timestamps = sorted(timestamps)
        deltas = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i-1]).total_seconds()
            deltas.append(delta)

        # Check for suspiciously regular timing or clustering
        avg_delta = statistics.mean(deltas) if deltas else float('inf')
        std_delta = statistics.stdev(deltas) if len(deltas) > 1 else float('inf')

        confidence = 0.0

        # Very short average time between events
        if avg_delta < 10:  # Less than 10 seconds
            confidence += 0.5

        # Low variance = regular timing (bot-like)
        if std_delta < 2 and avg_delta < 60:
            confidence += 0.3

        # Many events in short window
        total_duration = (timestamps[-1] - timestamps[0]).total_seconds()
        if total_duration > 0 and len(events) / total_duration > 0.1:  # >1 per 10 sec
            confidence += 0.2

        confidence = min(confidence, 1.0)

        return {
            "coordinated_activity_detected": confidence > 0.5,
            "confidence": round(confidence, 3),
            "event_count": len(events),
            "avg_interval_seconds": round(avg_delta, 2),
            "std_interval_seconds": round(std_delta, 2) if std_delta != float('inf') else None
        }

    def detect_insider_trading(
        self,
        token_address: str,
        trades: List[Dict[str, Any]],
        announcement_time: str,
        price_before: float,
        price_after: float
    ) -> Dict[str, Any]:
        """
        Detect potential insider trading.

        Args:
            token_address: Token address
            trades: Pre-announcement trades
            announcement_time: Time of announcement
            price_before: Price before announcement
            price_after: Price after announcement

        Returns:
            Insider trading analysis
        """
        announcement = datetime.fromisoformat(
            announcement_time.replace("Z", "+00:00")
        )

        suspect_wallets = []

        for trade in trades:
            trade_time = trade.get("timestamp")
            if isinstance(trade_time, str):
                trade_time = datetime.fromisoformat(
                    trade_time.replace("Z", "+00:00")
                )

            # Check if trade was within 24h before announcement
            time_diff = (announcement - trade_time).total_seconds()
            if 0 < time_diff < 86400:  # Within 24 hours before
                amount = trade.get("amount", 0)
                wallet = trade.get("wallet")

                # Large trade before announcement = suspicious
                if amount > 10000:
                    suspect_wallets.append(wallet)

        # Calculate price movement
        price_change = (price_after - price_before) / price_before if price_before > 0 else 0

        return {
            "insider_trading_suspected": len(suspect_wallets) > 0 and price_change > 0.5,
            "suspect_wallets": list(set(suspect_wallets)),
            "price_change_pct": round(price_change * 100, 2),
            "pre_announcement_trades": len(trades)
        }

    def detect_bot_activity(
        self,
        token_address: str,
        trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detect bot-like trading activity.

        Args:
            token_address: Token address
            trades: Recent trades

        Returns:
            Bot activity analysis
        """
        if len(trades) < 5:
            return {
                "bot_activity_detected": False,
                "bot_confidence": 0.0
            }

        # Parse timestamps with millisecond precision
        timestamps = []
        for trade in trades:
            ts = trade.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to parse trade timestamp '{ts}': {e}")
                    continue
            timestamps.append(ts)

        if len(timestamps) < 5:
            return {
                "bot_activity_detected": False,
                "bot_confidence": 0.0
            }

        timestamps = sorted(timestamps)

        # Calculate deltas in milliseconds
        deltas = []
        for i in range(1, len(timestamps)):
            delta_ms = (timestamps[i] - timestamps[i-1]).total_seconds() * 1000
            deltas.append(delta_ms)

        avg_delta = statistics.mean(deltas)
        confidence = 0.0

        # Very fast trades (< 1 second apart average)
        if avg_delta < 1000:
            confidence += 0.5

        # Regular intervals (low variance)
        if len(deltas) > 1:
            std_delta = statistics.stdev(deltas)
            cv = std_delta / avg_delta if avg_delta > 0 else float('inf')
            if cv < 0.1:  # Very consistent timing
                confidence += 0.4

        # Check for round numbers in trade amounts
        amounts = [t.get("amount", 0) for t in trades]
        round_count = sum(1 for a in amounts if a == int(a))
        if round_count / len(amounts) > 0.8:
            confidence += 0.1

        confidence = min(confidence, 1.0)

        return {
            "bot_activity_detected": confidence > 0.7,
            "bot_confidence": round(confidence, 3),
            "avg_trade_interval_ms": round(avg_delta, 2),
            "timing_regularity": round(1 - (statistics.stdev(deltas) / avg_delta if avg_delta > 0 and len(deltas) > 1 else 1), 3)
        }


# Singleton
_detector: Optional[ScamDetector] = None


def get_scam_detector() -> ScamDetector:
    """Get or create the scam detector singleton."""
    global _detector
    if _detector is None:
        _detector = ScamDetector()
    return _detector
