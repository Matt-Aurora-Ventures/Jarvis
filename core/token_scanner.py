"""
Token Scanner - Discover and analyze new tokens.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import uuid

logger = logging.getLogger(__name__)


class TokenRisk(Enum):
    """Token risk levels."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    SCAM = "scam"


class TokenCategory(Enum):
    """Token categories."""
    DEFI = "defi"
    MEME = "meme"
    GAMING = "gaming"
    NFT = "nft"
    AI = "ai"
    INFRASTRUCTURE = "infrastructure"
    UTILITY = "utility"
    GOVERNANCE = "governance"
    STABLECOIN = "stablecoin"
    UNKNOWN = "unknown"


class HoneypotRisk(Enum):
    """Honeypot detection results."""
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    HONEYPOT = "honeypot"
    UNKNOWN = "unknown"


@dataclass
class TokenMetadata:
    """Token metadata."""
    address: str
    symbol: str
    name: str
    decimals: int
    total_supply: float
    circulating_supply: float
    holder_count: int
    created_at: str
    description: str = ""
    website: str = ""
    twitter: str = ""
    telegram: str = ""
    logo_url: str = ""


@dataclass
class TokenLiquidity:
    """Token liquidity information."""
    total_liquidity_usd: float
    main_pool: str
    main_pool_liquidity: float
    num_pools: int
    locked_liquidity_pct: float
    lock_expiry: Optional[str] = None


@dataclass
class TokenHolderInfo:
    """Token holder distribution."""
    top_10_pct: float
    top_20_pct: float
    top_50_pct: float
    dev_wallet_pct: float
    largest_holder_pct: float
    holder_count: int
    unique_buyers_24h: int
    unique_sellers_24h: int


@dataclass
class TokenTradingInfo:
    """Token trading information."""
    price_usd: float
    price_change_1h: float
    price_change_24h: float
    price_change_7d: float
    volume_24h: float
    trades_24h: int
    buy_sell_ratio: float
    market_cap: float
    fdv: float


@dataclass
class TokenRiskAssessment:
    """Token risk assessment."""
    overall_risk: TokenRisk
    risk_score: int  # 0-100
    honeypot_risk: HoneypotRisk
    rug_pull_risk: float
    manipulation_risk: float
    liquidity_risk: float
    holder_risk: float
    flags: List[str]
    recommendations: List[str]


@dataclass
class ScannedToken:
    """A scanned token with full analysis."""
    id: str
    metadata: TokenMetadata
    liquidity: TokenLiquidity
    holders: TokenHolderInfo
    trading: TokenTradingInfo
    risk: TokenRiskAssessment
    category: TokenCategory
    scanned_at: str
    score: float  # Overall investment score 0-100
    signals: List[str]


class TokenScannerDB:
    """SQLite storage for token scanner."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scanned_tokens (
                    id TEXT PRIMARY KEY,
                    address TEXT NOT NULL UNIQUE,
                    symbol TEXT,
                    name TEXT,
                    category TEXT,
                    overall_risk TEXT,
                    risk_score INTEGER,
                    score REAL,
                    price_usd REAL,
                    market_cap REAL,
                    liquidity_usd REAL,
                    volume_24h REAL,
                    holder_count INTEGER,
                    scanned_at TEXT,
                    metadata_json TEXT,
                    liquidity_json TEXT,
                    holders_json TEXT,
                    trading_json TEXT,
                    risk_json TEXT,
                    signals_json TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    symbol TEXT,
                    added_at TEXT,
                    reason TEXT,
                    target_price REAL,
                    stop_loss REAL,
                    notes TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_blacklist (
                    address TEXT PRIMARY KEY,
                    symbol TEXT,
                    reason TEXT,
                    added_at TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_address ON scanned_tokens(address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_symbol ON scanned_tokens(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_scanned ON scanned_tokens(scanned_at)")

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


class TokenScanner:
    """
    Discover and analyze new tokens.

    Usage:
        scanner = TokenScanner()

        # Scan a specific token
        token = await scanner.scan_token("So11111111111111111111111111111111111111112")

        # Scan new tokens
        new_tokens = await scanner.scan_new_tokens(hours=24)

        # Get top opportunities
        opportunities = scanner.get_opportunities(min_score=70)
    """

    # Known scam patterns
    SCAM_PATTERNS = [
        "free", "airdrop", "elon", "doge", "shib", "safe", "moon",
        "rocket", "100x", "1000x", "gem", "pump"
    ]

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "token_scanner.db"
        self.db = TokenScannerDB(db_path)
        self._data_providers: Dict[str, Callable] = {}
        self._blacklist: set = set()
        self._load_blacklist()

    def _load_blacklist(self):
        """Load blacklisted tokens."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT address FROM token_blacklist")
            self._blacklist = {row['address'] for row in cursor.fetchall()}

    def set_data_provider(self, name: str, provider: Callable):
        """Set data provider callback."""
        self._data_providers[name] = provider

    async def scan_token(self, address: str) -> Optional[ScannedToken]:
        """Scan a single token."""
        if address in self._blacklist:
            logger.warning(f"Token {address} is blacklisted")
            return None

        scan_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        try:
            # Fetch metadata
            metadata = await self._fetch_metadata(address)
            if not metadata:
                return None

            # Fetch liquidity info
            liquidity = await self._fetch_liquidity(address)

            # Fetch holder info
            holders = await self._fetch_holders(address)

            # Fetch trading info
            trading = await self._fetch_trading(address)

            # Perform risk assessment
            risk = self._assess_risk(metadata, liquidity, holders, trading)

            # Categorize token
            category = self._categorize_token(metadata)

            # Calculate score
            score = self._calculate_score(metadata, liquidity, holders, trading, risk)

            # Generate signals
            signals = self._generate_signals(metadata, liquidity, holders, trading, risk)

            token = ScannedToken(
                id=scan_id,
                metadata=metadata,
                liquidity=liquidity,
                holders=holders,
                trading=trading,
                risk=risk,
                category=category,
                scanned_at=now,
                score=score,
                signals=signals
            )

            # Save to database
            self._save_token(token)

            logger.info(f"Scanned {metadata.symbol}: score={score:.1f}, risk={risk.overall_risk.value}")

            return token

        except Exception as e:
            logger.error(f"Error scanning token {address}: {e}")
            return None

    async def _fetch_metadata(self, address: str) -> Optional[TokenMetadata]:
        """Fetch token metadata."""
        provider = self._data_providers.get('metadata')
        if provider:
            try:
                data = await provider(address)
                return TokenMetadata(
                    address=address,
                    symbol=data.get('symbol', 'UNKNOWN'),
                    name=data.get('name', 'Unknown Token'),
                    decimals=data.get('decimals', 9),
                    total_supply=data.get('total_supply', 0),
                    circulating_supply=data.get('circulating_supply', 0),
                    holder_count=data.get('holder_count', 0),
                    created_at=data.get('created_at', ''),
                    description=data.get('description', ''),
                    website=data.get('website', ''),
                    twitter=data.get('twitter', ''),
                    telegram=data.get('telegram', ''),
                    logo_url=data.get('logo_url', '')
                )
            except Exception as e:
                logger.error(f"Error fetching metadata: {e}")

        # Return minimal metadata
        return TokenMetadata(
            address=address,
            symbol="UNKNOWN",
            name="Unknown Token",
            decimals=9,
            total_supply=0,
            circulating_supply=0,
            holder_count=0,
            created_at=""
        )

    async def _fetch_liquidity(self, address: str) -> TokenLiquidity:
        """Fetch liquidity information."""
        provider = self._data_providers.get('liquidity')
        if provider:
            try:
                data = await provider(address)
                return TokenLiquidity(
                    total_liquidity_usd=data.get('total_liquidity_usd', 0),
                    main_pool=data.get('main_pool', ''),
                    main_pool_liquidity=data.get('main_pool_liquidity', 0),
                    num_pools=data.get('num_pools', 0),
                    locked_liquidity_pct=data.get('locked_liquidity_pct', 0),
                    lock_expiry=data.get('lock_expiry')
                )
            except Exception as e:
                logger.error(f"Error fetching liquidity: {e}")

        return TokenLiquidity(
            total_liquidity_usd=0,
            main_pool="",
            main_pool_liquidity=0,
            num_pools=0,
            locked_liquidity_pct=0
        )

    async def _fetch_holders(self, address: str) -> TokenHolderInfo:
        """Fetch holder information."""
        provider = self._data_providers.get('holders')
        if provider:
            try:
                data = await provider(address)
                return TokenHolderInfo(
                    top_10_pct=data.get('top_10_pct', 0),
                    top_20_pct=data.get('top_20_pct', 0),
                    top_50_pct=data.get('top_50_pct', 0),
                    dev_wallet_pct=data.get('dev_wallet_pct', 0),
                    largest_holder_pct=data.get('largest_holder_pct', 0),
                    holder_count=data.get('holder_count', 0),
                    unique_buyers_24h=data.get('unique_buyers_24h', 0),
                    unique_sellers_24h=data.get('unique_sellers_24h', 0)
                )
            except Exception as e:
                logger.error(f"Error fetching holders: {e}")

        return TokenHolderInfo(
            top_10_pct=100,
            top_20_pct=100,
            top_50_pct=100,
            dev_wallet_pct=0,
            largest_holder_pct=100,
            holder_count=0,
            unique_buyers_24h=0,
            unique_sellers_24h=0
        )

    async def _fetch_trading(self, address: str) -> TokenTradingInfo:
        """Fetch trading information."""
        provider = self._data_providers.get('trading')
        if provider:
            try:
                data = await provider(address)
                return TokenTradingInfo(
                    price_usd=data.get('price_usd', 0),
                    price_change_1h=data.get('price_change_1h', 0),
                    price_change_24h=data.get('price_change_24h', 0),
                    price_change_7d=data.get('price_change_7d', 0),
                    volume_24h=data.get('volume_24h', 0),
                    trades_24h=data.get('trades_24h', 0),
                    buy_sell_ratio=data.get('buy_sell_ratio', 1),
                    market_cap=data.get('market_cap', 0),
                    fdv=data.get('fdv', 0)
                )
            except Exception as e:
                logger.error(f"Error fetching trading: {e}")

        return TokenTradingInfo(
            price_usd=0,
            price_change_1h=0,
            price_change_24h=0,
            price_change_7d=0,
            volume_24h=0,
            trades_24h=0,
            buy_sell_ratio=1,
            market_cap=0,
            fdv=0
        )

    def _assess_risk(
        self,
        metadata: TokenMetadata,
        liquidity: TokenLiquidity,
        holders: TokenHolderInfo,
        trading: TokenTradingInfo
    ) -> TokenRiskAssessment:
        """Assess token risk."""
        flags = []
        recommendations = []
        risk_score = 0

        # Honeypot check
        honeypot_risk = HoneypotRisk.UNKNOWN
        provider = self._data_providers.get('honeypot')
        if provider:
            try:
                result = provider(metadata.address)
                honeypot_risk = HoneypotRisk(result.get('status', 'unknown'))
            except Exception:
                pass

        if honeypot_risk == HoneypotRisk.HONEYPOT:
            risk_score += 50
            flags.append("HONEYPOT DETECTED")
        elif honeypot_risk == HoneypotRisk.SUSPICIOUS:
            risk_score += 25
            flags.append("Suspicious contract behavior")

        # Liquidity risk
        liquidity_risk = 0
        if liquidity.total_liquidity_usd < 1000:
            liquidity_risk = 1.0
            risk_score += 20
            flags.append("Very low liquidity (<$1K)")
        elif liquidity.total_liquidity_usd < 10000:
            liquidity_risk = 0.7
            risk_score += 15
            flags.append("Low liquidity (<$10K)")
        elif liquidity.total_liquidity_usd < 50000:
            liquidity_risk = 0.4
            risk_score += 10

        if liquidity.locked_liquidity_pct < 50:
            risk_score += 15
            flags.append(f"Low locked liquidity ({liquidity.locked_liquidity_pct:.0f}%)")
            recommendations.append("Wait for liquidity lock")

        # Holder risk
        holder_risk = 0
        if holders.top_10_pct > 80:
            holder_risk = 0.9
            risk_score += 20
            flags.append(f"Top 10 holders own {holders.top_10_pct:.0f}%")
        elif holders.top_10_pct > 60:
            holder_risk = 0.6
            risk_score += 10

        if holders.largest_holder_pct > 20:
            risk_score += 15
            flags.append(f"Single holder owns {holders.largest_holder_pct:.0f}%")

        if holders.holder_count < 100:
            risk_score += 10
            flags.append("Very few holders")

        # Manipulation risk
        manipulation_risk = 0
        if trading.volume_24h > 0 and trading.market_cap > 0:
            vol_to_mcap = trading.volume_24h / trading.market_cap
            if vol_to_mcap > 5:
                manipulation_risk = 0.8
                risk_score += 15
                flags.append("Unusually high volume (potential wash trading)")

        if abs(trading.price_change_24h) > 100:
            manipulation_risk = max(manipulation_risk, 0.6)
            risk_score += 10
            flags.append(f"Extreme price movement ({trading.price_change_24h:+.0f}%)")

        # Rug pull risk
        rug_pull_risk = 0
        if liquidity.locked_liquidity_pct < 30 and holders.dev_wallet_pct > 10:
            rug_pull_risk = 0.8
            risk_score += 20
            flags.append("High rug pull risk")
            recommendations.append("AVOID - High rug pull indicators")

        # Name-based risk
        name_lower = (metadata.name + metadata.symbol).lower()
        for pattern in self.SCAM_PATTERNS:
            if pattern in name_lower:
                risk_score += 5
                flags.append(f"Suspicious name pattern: {pattern}")
                break

        # Determine overall risk
        risk_score = min(risk_score, 100)

        if risk_score >= 70:
            overall_risk = TokenRisk.VERY_HIGH
        elif risk_score >= 50:
            overall_risk = TokenRisk.HIGH
        elif risk_score >= 30:
            overall_risk = TokenRisk.MEDIUM
        elif risk_score >= 15:
            overall_risk = TokenRisk.LOW
        else:
            overall_risk = TokenRisk.VERY_LOW

        if honeypot_risk == HoneypotRisk.HONEYPOT:
            overall_risk = TokenRisk.SCAM

        # Add recommendations
        if overall_risk in [TokenRisk.LOW, TokenRisk.VERY_LOW]:
            recommendations.append("Token appears relatively safe")
        if liquidity.total_liquidity_usd > 100000:
            recommendations.append("Good liquidity depth")
        if holders.holder_count > 1000:
            recommendations.append("Good holder distribution")

        return TokenRiskAssessment(
            overall_risk=overall_risk,
            risk_score=risk_score,
            honeypot_risk=honeypot_risk,
            rug_pull_risk=rug_pull_risk,
            manipulation_risk=manipulation_risk,
            liquidity_risk=liquidity_risk,
            holder_risk=holder_risk,
            flags=flags,
            recommendations=recommendations
        )

    def _categorize_token(self, metadata: TokenMetadata) -> TokenCategory:
        """Categorize token based on metadata."""
        text = (metadata.name + " " + metadata.description + " " + metadata.symbol).lower()

        if any(w in text for w in ['defi', 'swap', 'yield', 'lending', 'stake']):
            return TokenCategory.DEFI
        if any(w in text for w in ['meme', 'doge', 'pepe', 'shib', 'wojak', 'frog']):
            return TokenCategory.MEME
        if any(w in text for w in ['game', 'play', 'nft', 'metaverse']):
            return TokenCategory.GAMING
        if any(w in text for w in ['ai', 'artificial', 'intelligence', 'machine learning']):
            return TokenCategory.AI
        if any(w in text for w in ['stable', 'usd', 'peg']):
            return TokenCategory.STABLECOIN
        if any(w in text for w in ['governance', 'dao', 'vote']):
            return TokenCategory.GOVERNANCE

        return TokenCategory.UNKNOWN

    def _calculate_score(
        self,
        metadata: TokenMetadata,
        liquidity: TokenLiquidity,
        holders: TokenHolderInfo,
        trading: TokenTradingInfo,
        risk: TokenRiskAssessment
    ) -> float:
        """Calculate overall investment score."""
        score = 50  # Start neutral

        # Risk adjustment (major factor)
        score -= risk.risk_score * 0.5

        # Liquidity bonus
        if liquidity.total_liquidity_usd >= 100000:
            score += 15
        elif liquidity.total_liquidity_usd >= 50000:
            score += 10
        elif liquidity.total_liquidity_usd >= 10000:
            score += 5

        # Locked liquidity bonus
        if liquidity.locked_liquidity_pct >= 90:
            score += 10
        elif liquidity.locked_liquidity_pct >= 70:
            score += 5

        # Holder distribution bonus
        if holders.top_10_pct < 50:
            score += 10
        elif holders.top_10_pct < 70:
            score += 5

        if holders.holder_count >= 1000:
            score += 10
        elif holders.holder_count >= 500:
            score += 5

        # Volume/activity bonus
        if trading.volume_24h >= 100000:
            score += 10
        elif trading.volume_24h >= 50000:
            score += 5

        if trading.trades_24h >= 1000:
            score += 5

        # Social presence bonus
        if metadata.website:
            score += 3
        if metadata.twitter:
            score += 3
        if metadata.telegram:
            score += 2

        return max(0, min(100, score))

    def _generate_signals(
        self,
        metadata: TokenMetadata,
        liquidity: TokenLiquidity,
        holders: TokenHolderInfo,
        trading: TokenTradingInfo,
        risk: TokenRiskAssessment
    ) -> List[str]:
        """Generate trading signals."""
        signals = []

        # Bullish signals
        if trading.buy_sell_ratio > 2:
            signals.append("BULLISH: Strong buying pressure")
        if trading.price_change_24h > 20 and trading.volume_24h > 50000:
            signals.append("BULLISH: Breakout with volume")
        if holders.unique_buyers_24h > holders.unique_sellers_24h * 2:
            signals.append("BULLISH: More buyers than sellers")

        # Bearish signals
        if trading.buy_sell_ratio < 0.5:
            signals.append("BEARISH: Strong selling pressure")
        if trading.price_change_24h < -30:
            signals.append("BEARISH: Sharp decline")
        if holders.unique_sellers_24h > holders.unique_buyers_24h * 2:
            signals.append("BEARISH: More sellers than buyers")

        # Warning signals
        if risk.overall_risk in [TokenRisk.HIGH, TokenRisk.VERY_HIGH]:
            signals.append("WARNING: High risk token")
        if risk.honeypot_risk == HoneypotRisk.SUSPICIOUS:
            signals.append("WARNING: Suspicious contract")

        # Neutral/info signals
        if trading.volume_24h > trading.market_cap * 0.5:
            signals.append("INFO: High volume relative to mcap")

        return signals

    def _save_token(self, token: ScannedToken):
        """Save scanned token to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO scanned_tokens
                (id, address, symbol, name, category, overall_risk, risk_score,
                 score, price_usd, market_cap, liquidity_usd, volume_24h,
                 holder_count, scanned_at, metadata_json, liquidity_json,
                 holders_json, trading_json, risk_json, signals_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                token.id, token.metadata.address, token.metadata.symbol,
                token.metadata.name, token.category.value, token.risk.overall_risk.value,
                token.risk.risk_score, token.score, token.trading.price_usd,
                token.trading.market_cap, token.liquidity.total_liquidity_usd,
                token.trading.volume_24h, token.holders.holder_count, token.scanned_at,
                json.dumps({
                    'address': token.metadata.address,
                    'symbol': token.metadata.symbol,
                    'name': token.metadata.name,
                    'decimals': token.metadata.decimals,
                    'total_supply': token.metadata.total_supply,
                    'website': token.metadata.website,
                    'twitter': token.metadata.twitter
                }),
                json.dumps({
                    'total_liquidity_usd': token.liquidity.total_liquidity_usd,
                    'locked_liquidity_pct': token.liquidity.locked_liquidity_pct,
                    'num_pools': token.liquidity.num_pools
                }),
                json.dumps({
                    'top_10_pct': token.holders.top_10_pct,
                    'holder_count': token.holders.holder_count,
                    'largest_holder_pct': token.holders.largest_holder_pct
                }),
                json.dumps({
                    'price_usd': token.trading.price_usd,
                    'price_change_24h': token.trading.price_change_24h,
                    'volume_24h': token.trading.volume_24h,
                    'market_cap': token.trading.market_cap
                }),
                json.dumps({
                    'overall_risk': token.risk.overall_risk.value,
                    'risk_score': token.risk.risk_score,
                    'flags': token.risk.flags,
                    'recommendations': token.risk.recommendations
                }),
                json.dumps(token.signals)
            ))
            conn.commit()

    def get_opportunities(
        self,
        min_score: float = 60,
        max_risk: TokenRisk = TokenRisk.MEDIUM,
        category: Optional[TokenCategory] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Get investment opportunities."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            risk_levels = {
                TokenRisk.VERY_LOW: ['very_low'],
                TokenRisk.LOW: ['very_low', 'low'],
                TokenRisk.MEDIUM: ['very_low', 'low', 'medium'],
                TokenRisk.HIGH: ['very_low', 'low', 'medium', 'high'],
                TokenRisk.VERY_HIGH: ['very_low', 'low', 'medium', 'high', 'very_high']
            }

            allowed_risks = risk_levels.get(max_risk, ['very_low', 'low', 'medium'])
            placeholders = ','.join(['?' for _ in allowed_risks])

            query = f"""
                SELECT * FROM scanned_tokens
                WHERE score >= ?
                AND overall_risk IN ({placeholders})
            """
            params = [min_score] + allowed_risks

            if category:
                query += " AND category = ?"
                params.append(category.value)

            query += " ORDER BY score DESC, scanned_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]

    def add_to_blacklist(self, address: str, symbol: str = "", reason: str = ""):
        """Add token to blacklist."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO token_blacklist (address, symbol, reason, added_at)
                VALUES (?, ?, ?, ?)
            """, (address, symbol, reason, datetime.now(timezone.utc).isoformat()))
            conn.commit()

        self._blacklist.add(address)
        logger.info(f"Blacklisted token {address}")

    def get_recent_scans(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Get recently scanned tokens."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM scanned_tokens
                WHERE datetime(scanned_at) > datetime('now', ?)
                ORDER BY scanned_at DESC
                LIMIT ?
            """, (f'-{hours} hours', limit))

            return [dict(row) for row in cursor.fetchall()]


# Singleton
_scanner: Optional[TokenScanner] = None


def get_token_scanner() -> TokenScanner:
    """Get singleton token scanner."""
    global _scanner
    if _scanner is None:
        _scanner = TokenScanner()
    return _scanner
