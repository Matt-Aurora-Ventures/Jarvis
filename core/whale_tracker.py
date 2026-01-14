"""
Whale Tracker - Monitor large wallet movements and whale activity.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import json
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class WhaleCategory(Enum):
    """Categories of whale wallets."""
    EXCHANGE = "exchange"
    MARKET_MAKER = "market_maker"
    INFLUENCER = "influencer"
    SMART_MONEY = "smart_money"
    FUND = "fund"
    UNKNOWN = "unknown"


class MovementType(Enum):
    """Types of whale movements."""
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    TRANSFER = "transfer"
    SWAP = "swap"
    NFT = "nft"


@dataclass
class WhaleWallet:
    """A tracked whale wallet."""
    address: str
    label: str
    category: WhaleCategory
    total_value_usd: float = 0.0
    sol_balance: float = 0.0
    is_active: bool = True
    first_seen: str = ""
    last_activity: str = ""
    win_rate: float = 0.0  # For smart money tracking
    avg_trade_size: float = 0.0
    notes: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class WhaleMovement:
    """A significant whale movement/transaction."""
    id: Optional[int] = None
    wallet_address: str = ""
    wallet_label: str = ""
    timestamp: str = ""
    movement_type: MovementType = MovementType.TRANSFER
    token_symbol: str = ""
    token_mint: str = ""
    amount: float = 0.0
    value_usd: float = 0.0
    direction: str = ""  # BUY, SELL, IN, OUT
    tx_signature: str = ""
    counterparty: str = ""
    is_significant: bool = False


@dataclass
class WhaleAlert:
    """Alert triggered by whale activity."""
    wallet_address: str
    wallet_label: str
    alert_type: str
    message: str
    value_usd: float
    timestamp: str
    token_symbol: str = ""
    tx_signature: str = ""


class WhaleDB:
    """SQLite storage for whale tracking."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whale_wallets (
                    address TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    category TEXT DEFAULT 'unknown',
                    total_value_usd REAL DEFAULT 0,
                    sol_balance REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    first_seen TEXT,
                    last_activity TEXT,
                    win_rate REAL DEFAULT 0,
                    avg_trade_size REAL DEFAULT 0,
                    notes TEXT,
                    tags_json TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whale_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_address TEXT,
                    wallet_label TEXT,
                    timestamp TEXT,
                    movement_type TEXT,
                    token_symbol TEXT,
                    token_mint TEXT,
                    amount REAL,
                    value_usd REAL,
                    direction TEXT,
                    tx_signature TEXT UNIQUE,
                    counterparty TEXT,
                    is_significant INTEGER DEFAULT 0,
                    FOREIGN KEY (wallet_address) REFERENCES whale_wallets(address)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whale_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_address TEXT,
                    wallet_label TEXT,
                    alert_type TEXT,
                    message TEXT,
                    value_usd REAL,
                    timestamp TEXT,
                    token_symbol TEXT,
                    tx_signature TEXT,
                    acknowledged INTEGER DEFAULT 0
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_movements_wallet ON whale_movements(wallet_address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_movements_token ON whale_movements(token_mint)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_movements_time ON whale_movements(timestamp)")

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


class WhaleTracker:
    """
    Track whale wallets and their activity.

    Usage:
        tracker = WhaleTracker()

        # Add whale wallet
        tracker.add_wallet(WhaleWallet(
            address="ABC123...",
            label="Smart Money #1",
            category=WhaleCategory.SMART_MONEY
        ))

        # Record movement
        tracker.record_movement(WhaleMovement(
            wallet_address="ABC123...",
            movement_type=MovementType.ACCUMULATION,
            token_symbol="SOL",
            amount=1000,
            value_usd=100000
        ))

        # Get whale activity for token
        movements = tracker.get_token_activity("SOL", hours=24)
    """

    # Threshold values
    MIN_MOVEMENT_USD = 10000  # $10k minimum for tracking
    SIGNIFICANT_MOVEMENT_USD = 100000  # $100k for alerts

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "whales.db"
        self.db = WhaleDB(db_path)
        self._alert_callbacks: List[Callable] = []
        self._known_exchanges = self._load_known_wallets()

    def _load_known_wallets(self) -> Dict[str, WhaleWallet]:
        """Load known whale wallets (exchanges, market makers, etc)."""
        known = {
            # Major exchanges (example - would need real addresses)
            "FWAFz...": WhaleWallet(
                address="FWAFz...",
                label="Binance Hot Wallet",
                category=WhaleCategory.EXCHANGE
            ),
            "9WzDX...": WhaleWallet(
                address="9WzDX...",
                label="Coinbase",
                category=WhaleCategory.EXCHANGE
            ),
        }
        return known

    def add_wallet(self, wallet: WhaleWallet) -> bool:
        """Add a whale wallet to track."""
        wallet.first_seen = datetime.now(timezone.utc).isoformat()
        wallet.last_activity = wallet.first_seen

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO whale_wallets
                    (address, label, category, total_value_usd, sol_balance,
                     is_active, first_seen, last_activity, win_rate, avg_trade_size,
                     notes, tags_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    wallet.address, wallet.label, wallet.category.value,
                    wallet.total_value_usd, wallet.sol_balance, 1 if wallet.is_active else 0,
                    wallet.first_seen, wallet.last_activity, wallet.win_rate,
                    wallet.avg_trade_size, wallet.notes, json.dumps(wallet.tags)
                ))
                conn.commit()
                logger.info(f"Added whale wallet: {wallet.label} ({wallet.address[:8]}...)")
                return True
            except sqlite3.IntegrityError:
                logger.warning(f"Wallet already exists: {wallet.address}")
                return False

    def remove_wallet(self, address: str) -> bool:
        """Remove a whale wallet from tracking."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE whale_wallets SET is_active = 0 WHERE address = ?", (address,))
            conn.commit()
            return cursor.rowcount > 0

    def get_wallet(self, address: str) -> Optional[WhaleWallet]:
        """Get a whale wallet by address."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM whale_wallets WHERE address = ?", (address,))
            row = cursor.fetchone()
            return self._row_to_wallet(row) if row else None

    def get_all_wallets(
        self,
        category: WhaleCategory = None,
        active_only: bool = True
    ) -> List[WhaleWallet]:
        """Get all tracked whale wallets."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM whale_wallets WHERE 1=1"
            params = []

            if active_only:
                query += " AND is_active = 1"
            if category:
                query += " AND category = ?"
                params.append(category.value)

            cursor.execute(query, params)
            return [self._row_to_wallet(row) for row in cursor.fetchall()]

    def _row_to_wallet(self, row: sqlite3.Row) -> WhaleWallet:
        """Convert database row to WhaleWallet."""
        return WhaleWallet(
            address=row['address'],
            label=row['label'],
            category=WhaleCategory(row['category']),
            total_value_usd=row['total_value_usd'] or 0,
            sol_balance=row['sol_balance'] or 0,
            is_active=bool(row['is_active']),
            first_seen=row['first_seen'] or "",
            last_activity=row['last_activity'] or "",
            win_rate=row['win_rate'] or 0,
            avg_trade_size=row['avg_trade_size'] or 0,
            notes=row['notes'] or "",
            tags=json.loads(row['tags_json']) if row['tags_json'] else []
        )

    def record_movement(self, movement: WhaleMovement) -> int:
        """Record a whale movement."""
        movement.timestamp = movement.timestamp or datetime.now(timezone.utc).isoformat()
        movement.is_significant = movement.value_usd >= self.SIGNIFICANT_MOVEMENT_USD

        # Get wallet label
        wallet = self.get_wallet(movement.wallet_address)
        if wallet:
            movement.wallet_label = wallet.label

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO whale_movements
                    (wallet_address, wallet_label, timestamp, movement_type,
                     token_symbol, token_mint, amount, value_usd, direction,
                     tx_signature, counterparty, is_significant)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    movement.wallet_address, movement.wallet_label, movement.timestamp,
                    movement.movement_type.value, movement.token_symbol, movement.token_mint,
                    movement.amount, movement.value_usd, movement.direction,
                    movement.tx_signature, movement.counterparty,
                    1 if movement.is_significant else 0
                ))

                # Update wallet last activity
                cursor.execute("""
                    UPDATE whale_wallets SET last_activity = ?
                    WHERE address = ?
                """, (movement.timestamp, movement.wallet_address))

                conn.commit()
                movement_id = cursor.lastrowid

                # Trigger alert if significant
                if movement.is_significant:
                    self._create_alert(movement)

                return movement_id

            except sqlite3.IntegrityError:
                logger.debug(f"Duplicate movement: {movement.tx_signature}")
                return 0

    def get_movements(
        self,
        wallet_address: str = None,
        token_mint: str = None,
        hours: int = 24,
        significant_only: bool = False
    ) -> List[WhaleMovement]:
        """Get whale movements."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM whale_movements
                WHERE datetime(timestamp) > datetime('now', ?)
            """
            params = [f'-{hours} hours']

            if wallet_address:
                query += " AND wallet_address = ?"
                params.append(wallet_address)
            if token_mint:
                query += " AND token_mint = ?"
                params.append(token_mint)
            if significant_only:
                query += " AND is_significant = 1"

            query += " ORDER BY timestamp DESC"

            cursor.execute(query, params)

            return [
                WhaleMovement(
                    id=row['id'],
                    wallet_address=row['wallet_address'],
                    wallet_label=row['wallet_label'] or "",
                    timestamp=row['timestamp'],
                    movement_type=MovementType(row['movement_type']),
                    token_symbol=row['token_symbol'] or "",
                    token_mint=row['token_mint'] or "",
                    amount=row['amount'],
                    value_usd=row['value_usd'],
                    direction=row['direction'] or "",
                    tx_signature=row['tx_signature'] or "",
                    counterparty=row['counterparty'] or "",
                    is_significant=bool(row['is_significant'])
                )
                for row in cursor.fetchall()
            ]

    def get_token_activity(
        self,
        token_symbol: str = None,
        token_mint: str = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get whale activity summary for a token."""
        movements = self.get_movements(
            token_mint=token_mint,
            hours=hours
        )

        if token_symbol:
            movements = [m for m in movements if m.token_symbol.upper() == token_symbol.upper()]

        buys = [m for m in movements if m.direction == "BUY"]
        sells = [m for m in movements if m.direction == "SELL"]

        total_buy_volume = sum(m.value_usd for m in buys)
        total_sell_volume = sum(m.value_usd for m in sells)

        unique_whales = len(set(m.wallet_address for m in movements))

        return {
            'token': token_symbol or token_mint,
            'period_hours': hours,
            'total_movements': len(movements),
            'buy_count': len(buys),
            'sell_count': len(sells),
            'total_buy_volume_usd': total_buy_volume,
            'total_sell_volume_usd': total_sell_volume,
            'net_flow_usd': total_buy_volume - total_sell_volume,
            'unique_whales': unique_whales,
            'whale_sentiment': 'BULLISH' if total_buy_volume > total_sell_volume * 1.5 else
                               'BEARISH' if total_sell_volume > total_buy_volume * 1.5 else
                               'NEUTRAL',
            'significant_movements': [m for m in movements if m.is_significant]
        }

    def _create_alert(self, movement: WhaleMovement):
        """Create and dispatch an alert for significant movement."""
        alert = WhaleAlert(
            wallet_address=movement.wallet_address,
            wallet_label=movement.wallet_label,
            alert_type=f"whale_{movement.direction.lower()}",
            message=f"Whale {movement.wallet_label or movement.wallet_address[:8]} "
                    f"{movement.direction} ${movement.value_usd:,.0f} of {movement.token_symbol}",
            value_usd=movement.value_usd,
            timestamp=movement.timestamp,
            token_symbol=movement.token_symbol,
            tx_signature=movement.tx_signature
        )

        # Save alert
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO whale_alerts
                (wallet_address, wallet_label, alert_type, message, value_usd,
                 timestamp, token_symbol, tx_signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.wallet_address, alert.wallet_label, alert.alert_type,
                alert.message, alert.value_usd, alert.timestamp,
                alert.token_symbol, alert.tx_signature
            ))
            conn.commit()

        # Dispatch to callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def add_alert_callback(self, callback: Callable[[WhaleAlert], None]):
        """Add a callback for whale alerts."""
        self._alert_callbacks.append(callback)

    def get_alerts(
        self,
        hours: int = 24,
        unacknowledged_only: bool = True
    ) -> List[WhaleAlert]:
        """Get whale alerts."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM whale_alerts
                WHERE datetime(timestamp) > datetime('now', ?)
            """
            params = [f'-{hours} hours']

            if unacknowledged_only:
                query += " AND acknowledged = 0"

            query += " ORDER BY timestamp DESC"

            cursor.execute(query, params)

            return [
                WhaleAlert(
                    wallet_address=row['wallet_address'],
                    wallet_label=row['wallet_label'],
                    alert_type=row['alert_type'],
                    message=row['message'],
                    value_usd=row['value_usd'],
                    timestamp=row['timestamp'],
                    token_symbol=row['token_symbol'],
                    tx_signature=row['tx_signature']
                )
                for row in cursor.fetchall()
            ]

    def get_smart_money_signals(self, hours: int = 24) -> List[Dict]:
        """Get trading signals based on smart money activity."""
        smart_wallets = self.get_all_wallets(category=WhaleCategory.SMART_MONEY)

        if not smart_wallets:
            return []

        signals = []

        for wallet in smart_wallets:
            movements = self.get_movements(wallet_address=wallet.address, hours=hours)

            if not movements:
                continue

            # Group by token
            by_token: Dict[str, List[WhaleMovement]] = {}
            for m in movements:
                if m.token_symbol:
                    if m.token_symbol not in by_token:
                        by_token[m.token_symbol] = []
                    by_token[m.token_symbol].append(m)

            for token, token_movements in by_token.items():
                buys = [m for m in token_movements if m.direction == "BUY"]
                sells = [m for m in token_movements if m.direction == "SELL"]

                buy_volume = sum(m.value_usd for m in buys)
                sell_volume = sum(m.value_usd for m in sells)

                if buy_volume > 0 and buy_volume > sell_volume * 2:
                    signals.append({
                        'wallet_label': wallet.label,
                        'wallet_win_rate': wallet.win_rate,
                        'token': token,
                        'signal': 'ACCUMULATION',
                        'volume_usd': buy_volume,
                        'confidence': min(wallet.win_rate / 100, 0.9) if wallet.win_rate else 0.5
                    })
                elif sell_volume > 0 and sell_volume > buy_volume * 2:
                    signals.append({
                        'wallet_label': wallet.label,
                        'wallet_win_rate': wallet.win_rate,
                        'token': token,
                        'signal': 'DISTRIBUTION',
                        'volume_usd': sell_volume,
                        'confidence': min(wallet.win_rate / 100, 0.9) if wallet.win_rate else 0.5
                    })

        return signals

    def format_alert_telegram(self, alert: WhaleAlert) -> str:
        """Format a whale alert for Telegram in JARVIS voice."""
        direction_emoji = "🟢" if "buy" in alert.alert_type else "🔴" if "sell" in alert.alert_type else "🔄"
        value_fmt = f"${alert.value_usd:,.0f}"

        lines = [
            f"<b>{direction_emoji} WHALE ALERT</b>",
            "",
            f"<b>{alert.wallet_label or 'Unknown Whale'}</b>",
            f"Action: {alert.alert_type.replace('whale_', '').upper()}",
            f"Token: <code>${alert.token_symbol}</code>" if alert.token_symbol else "",
            f"Value: <b>{value_fmt}</b>",
            "",
        ]

        # JARVIS commentary
        if alert.value_usd >= 500000:
            lines.append("💭 <i>that's serious size. someone knows something</i>")
        elif alert.value_usd >= 100000:
            lines.append("💭 <i>notable move. worth watching</i>")
        else:
            lines.append("💭 <i>medium-sized whale activity</i>")

        if alert.tx_signature:
            short_sig = alert.tx_signature[:12] + "..."
            lines.append(f"<a href='https://solscan.io/tx/{alert.tx_signature}'>View TX: {short_sig}</a>")

        return "\n".join(line for line in lines if line or line == "")

    async def send_telegram_alert(self, alert: WhaleAlert, bot_token: str, chat_id: str):
        """Send a whale alert to Telegram."""
        import aiohttp

        message = self.format_alert_telegram(alert)

        async with aiohttp.ClientSession() as session:
            url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
            await session.post(url, json={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            })
            logger.info(f"Sent whale alert to Telegram: {alert.wallet_label} {alert.alert_type}")

    def get_whale_summary_telegram(self, hours: int = 24) -> str:
        """Generate a whale activity summary for Telegram."""
        alerts = self.get_alerts(hours=hours, unacknowledged_only=False)

        if not alerts:
            return "🐋 <b>Whale Activity Summary</b>\n\nNo significant whale movements in the last 24h.\n\n<i>either accumulation is quiet or they're hiding</i>"

        total_buy_value = sum(a.value_usd for a in alerts if "buy" in a.alert_type)
        total_sell_value = sum(a.value_usd for a in alerts if "sell" in a.alert_type)

        net_flow = total_buy_value - total_sell_value
        flow_emoji = "🟢" if net_flow > 0 else "🔴" if net_flow < 0 else "🟡"

        sentiment = "BULLISH" if net_flow > 100000 else "BEARISH" if net_flow < -100000 else "NEUTRAL"

        # Top tokens by whale activity
        token_activity: Dict[str, float] = {}
        for alert in alerts:
            if alert.token_symbol:
                token_activity[alert.token_symbol] = token_activity.get(alert.token_symbol, 0) + alert.value_usd

        top_tokens = sorted(token_activity.items(), key=lambda x: x[1], reverse=True)[:5]

        lines = [
            f"🐋 <b>Whale Activity Summary ({hours}h)</b>",
            "",
            f"Total Movements: <b>{len(alerts)}</b>",
            f"Buy Volume: <code>${total_buy_value:,.0f}</code>",
            f"Sell Volume: <code>${total_sell_value:,.0f}</code>",
            f"Net Flow: {flow_emoji} <b>${abs(net_flow):,.0f}</b> {'IN' if net_flow > 0 else 'OUT'}",
            f"Whale Sentiment: <b>{sentiment}</b>",
            "",
        ]

        if top_tokens:
            lines.append("<b>Top Tokens by Whale Activity:</b>")
            for token, value in top_tokens:
                lines.append(f"  ${token}: <code>${value:,.0f}</code>")

        lines.extend([
            "",
            f"💭 <i>{'whales loading' if sentiment == 'BULLISH' else 'whales distributing' if sentiment == 'BEARISH' else 'whales watching. we watch too'}</i>"
        ])

        return "\n".join(lines)


# Singleton
_tracker: Optional[WhaleTracker] = None

def get_whale_tracker() -> WhaleTracker:
    """Get singleton whale tracker."""
    global _tracker
    if _tracker is None:
        _tracker = WhaleTracker()
    return _tracker
