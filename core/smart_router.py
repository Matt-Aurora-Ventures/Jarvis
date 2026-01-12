"""
Smart Order Router - Optimal routing across multiple DEXes and liquidity sources.
Finds best execution paths considering slippage, fees, and liquidity depth.
"""
import asyncio
import heapq
import sqlite3
import threading
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set


class DEX(Enum):
    """Supported DEXes."""
    RAYDIUM = "raydium"
    ORCA = "orca"
    JUPITER = "jupiter"
    METEORA = "meteora"
    LIFINITY = "lifinity"
    PHOENIX = "phoenix"
    OPENBOOK = "openbook"


class RouteType(Enum):
    """Types of routes."""
    DIRECT = "direct"              # Single hop A -> B
    MULTI_HOP = "multi_hop"        # Multiple hops A -> X -> B
    SPLIT = "split"                # Split across multiple DEXes
    HYBRID = "hybrid"              # Combination of split and multi-hop


class LiquiditySource(Enum):
    """Types of liquidity sources."""
    AMM = "amm"                    # Automated Market Maker
    CLOB = "clob"                  # Central Limit Order Book
    CONCENTRATED = "concentrated"  # Concentrated liquidity
    STABLE = "stable"              # Stable swap
    HYBRID = "hybrid"              # Hybrid model


@dataclass
class Pool:
    """A liquidity pool."""
    pool_id: str
    dex: DEX
    token_a: str
    token_b: str
    reserve_a: float
    reserve_b: float
    fee_rate: float               # e.g., 0.003 for 0.3%
    liquidity_source: LiquiditySource
    tvl_usd: float
    volume_24h: float
    last_updated: datetime
    metadata: Dict = field(default_factory=dict)

    @property
    def price_a_to_b(self) -> float:
        """Price of token A in terms of token B."""
        return self.reserve_b / self.reserve_a if self.reserve_a > 0 else 0

    @property
    def price_b_to_a(self) -> float:
        """Price of token B in terms of token A."""
        return self.reserve_a / self.reserve_b if self.reserve_b > 0 else 0


@dataclass
class RouteStep:
    """A single step in a route."""
    pool: Pool
    token_in: str
    token_out: str
    amount_in: float
    amount_out: float
    price_impact: float
    fee: float


@dataclass
class Route:
    """A complete route for a swap."""
    route_id: str
    route_type: RouteType
    steps: List[RouteStep]
    token_in: str
    token_out: str
    amount_in: float
    amount_out: float
    total_fee: float
    total_price_impact: float
    effective_price: float
    execution_time_ms: int
    score: float                   # Higher is better
    metadata: Dict = field(default_factory=dict)


@dataclass
class SplitRoute:
    """A route split across multiple paths."""
    routes: List[Route]
    splits: List[float]            # Percentage per route
    total_amount_in: float
    total_amount_out: float
    weighted_price: float
    combined_score: float


@dataclass
class QuoteResult:
    """Result of a quote request."""
    token_in: str
    token_out: str
    amount_in: float
    best_route: Route
    alternative_routes: List[Route]
    split_route: Optional[SplitRoute]
    quoted_at: datetime
    expires_at: datetime


class SmartRouter:
    """
    Smart order routing across multiple DEXes.
    Finds optimal execution paths considering price impact, fees, and liquidity.
    """

    # Maximum hops in a route
    MAX_HOPS = 4

    # Maximum split routes
    MAX_SPLITS = 5

    # Quote expiry time
    QUOTE_EXPIRY_SECONDS = 30

    # Common intermediate tokens for routing
    INTERMEDIATE_TOKENS = ["SOL", "USDC", "USDT", "mSOL", "stSOL", "jitoSOL"]

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "smart_router.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # Pool registry: token_pair -> List[Pool]
        self.pools: Dict[str, List[Pool]] = defaultdict(list)

        # Token graph for pathfinding
        self.token_graph: Dict[str, Set[str]] = defaultdict(set)

        # DEX priority (higher = preferred)
        self.dex_priority = {
            DEX.JUPITER: 100,      # Aggregator
            DEX.RAYDIUM: 90,
            DEX.ORCA: 85,
            DEX.METEORA: 80,
            DEX.LIFINITY: 75,
            DEX.PHOENIX: 70,
            DEX.OPENBOOK: 60
        }

        self._lock = threading.Lock()
        self._load_pools()

    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS pools (
                    pool_id TEXT PRIMARY KEY,
                    dex TEXT NOT NULL,
                    token_a TEXT NOT NULL,
                    token_b TEXT NOT NULL,
                    reserve_a REAL NOT NULL,
                    reserve_b REAL NOT NULL,
                    fee_rate REAL NOT NULL,
                    liquidity_source TEXT NOT NULL,
                    tvl_usd REAL DEFAULT 0,
                    volume_24h REAL DEFAULT 0,
                    last_updated TEXT NOT NULL,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS route_history (
                    route_id TEXT PRIMARY KEY,
                    token_in TEXT NOT NULL,
                    token_out TEXT NOT NULL,
                    amount_in REAL NOT NULL,
                    amount_out REAL NOT NULL,
                    route_type TEXT NOT NULL,
                    steps TEXT NOT NULL,
                    total_fee REAL NOT NULL,
                    price_impact REAL NOT NULL,
                    executed_at TEXT NOT NULL,
                    success INTEGER DEFAULT 1
                );

                CREATE INDEX IF NOT EXISTS idx_pools_tokens ON pools(token_a, token_b);
                CREATE INDEX IF NOT EXISTS idx_pools_dex ON pools(dex);
                CREATE INDEX IF NOT EXISTS idx_routes_tokens ON route_history(token_in, token_out);
            """)

    def _load_pools(self):
        """Load pools from database."""
        import json

        with self._get_db() as conn:
            rows = conn.execute("SELECT * FROM pools").fetchall()

            for row in rows:
                pool = Pool(
                    pool_id=row["pool_id"],
                    dex=DEX(row["dex"]),
                    token_a=row["token_a"],
                    token_b=row["token_b"],
                    reserve_a=row["reserve_a"],
                    reserve_b=row["reserve_b"],
                    fee_rate=row["fee_rate"],
                    liquidity_source=LiquiditySource(row["liquidity_source"]),
                    tvl_usd=row["tvl_usd"],
                    volume_24h=row["volume_24h"],
                    last_updated=datetime.fromisoformat(row["last_updated"]),
                    metadata=json.loads(row["metadata"] or "{}")
                )
                self._add_pool_to_graph(pool)

    def _add_pool_to_graph(self, pool: Pool):
        """Add pool to internal graph."""
        pair_key = self._get_pair_key(pool.token_a, pool.token_b)
        self.pools[pair_key].append(pool)

        # Update token graph
        self.token_graph[pool.token_a].add(pool.token_b)
        self.token_graph[pool.token_b].add(pool.token_a)

    def _get_pair_key(self, token_a: str, token_b: str) -> str:
        """Get canonical pair key."""
        return f"{min(token_a, token_b)}/{max(token_a, token_b)}"

    def register_pool(
        self,
        pool_id: str,
        dex: DEX,
        token_a: str,
        token_b: str,
        reserve_a: float,
        reserve_b: float,
        fee_rate: float = 0.003,
        liquidity_source: LiquiditySource = LiquiditySource.AMM,
        tvl_usd: float = 0,
        volume_24h: float = 0,
        metadata: Optional[Dict] = None
    ) -> Pool:
        """Register a new liquidity pool."""
        import json

        now = datetime.now()
        pool = Pool(
            pool_id=pool_id,
            dex=dex,
            token_a=token_a,
            token_b=token_b,
            reserve_a=reserve_a,
            reserve_b=reserve_b,
            fee_rate=fee_rate,
            liquidity_source=liquidity_source,
            tvl_usd=tvl_usd,
            volume_24h=volume_24h,
            last_updated=now,
            metadata=metadata or {}
        )

        with self._lock:
            self._add_pool_to_graph(pool)

        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO pools
                (pool_id, dex, token_a, token_b, reserve_a, reserve_b,
                 fee_rate, liquidity_source, tvl_usd, volume_24h, last_updated, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pool_id, dex.value, token_a, token_b, reserve_a, reserve_b,
                fee_rate, liquidity_source.value, tvl_usd, volume_24h,
                now.isoformat(), json.dumps(metadata or {})
            ))

        return pool

    def update_pool_reserves(
        self,
        pool_id: str,
        reserve_a: float,
        reserve_b: float
    ) -> bool:
        """Update pool reserves."""
        with self._lock:
            for pools in self.pools.values():
                for pool in pools:
                    if pool.pool_id == pool_id:
                        pool.reserve_a = reserve_a
                        pool.reserve_b = reserve_b
                        pool.last_updated = datetime.now()

                        with self._get_db() as conn:
                            conn.execute("""
                                UPDATE pools SET
                                reserve_a = ?, reserve_b = ?, last_updated = ?
                                WHERE pool_id = ?
                            """, (reserve_a, reserve_b, pool.last_updated.isoformat(), pool_id))

                        return True
        return False

    def get_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: float,
        max_slippage: float = 0.01,
        max_hops: int = 3
    ) -> QuoteResult:
        """Get best quote for a swap."""
        import uuid

        # Find all possible routes
        all_routes = self._find_all_routes(
            token_in, token_out, amount_in, max_hops
        )

        if not all_routes:
            raise ValueError(f"No route found from {token_in} to {token_out}")

        # Score and sort routes
        scored_routes = []
        for route in all_routes:
            route.score = self._score_route(route, max_slippage)
            scored_routes.append(route)

        scored_routes.sort(key=lambda r: r.score, reverse=True)

        best_route = scored_routes[0]
        alternatives = scored_routes[1:5]  # Top 5 alternatives

        # Calculate optimal split if amount is large
        split_route = None
        if amount_in > 1000 and len(scored_routes) > 1:
            split_route = self._calculate_optimal_split(
                scored_routes[:self.MAX_SPLITS],
                amount_in
            )

        now = datetime.now()
        return QuoteResult(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            best_route=best_route,
            alternative_routes=alternatives,
            split_route=split_route,
            quoted_at=now,
            expires_at=now + timedelta(seconds=self.QUOTE_EXPIRY_SECONDS)
        )

    def _find_all_routes(
        self,
        token_in: str,
        token_out: str,
        amount_in: float,
        max_hops: int
    ) -> List[Route]:
        """Find all possible routes between two tokens."""
        import uuid

        routes = []

        # Direct routes
        direct_pools = self._get_pools_for_pair(token_in, token_out)
        for pool in direct_pools:
            route = self._build_route(
                str(uuid.uuid4())[:8],
                [pool],
                token_in,
                amount_in
            )
            if route:
                routes.append(route)

        # Multi-hop routes using intermediate tokens
        if max_hops >= 2:
            paths = self._find_paths(token_in, token_out, max_hops)
            for path in paths:
                if len(path) <= 1:
                    continue

                # Get pools for each hop
                hop_pools = []
                valid_path = True
                for i in range(len(path) - 1):
                    pools = self._get_pools_for_pair(path[i], path[i + 1])
                    if not pools:
                        valid_path = False
                        break
                    # Use best pool for this hop
                    hop_pools.append(max(pools, key=lambda p: p.tvl_usd))

                if valid_path and hop_pools:
                    route = self._build_route(
                        str(uuid.uuid4())[:8],
                        hop_pools,
                        token_in,
                        amount_in
                    )
                    if route:
                        routes.append(route)

        return routes

    def _get_pools_for_pair(self, token_a: str, token_b: str) -> List[Pool]:
        """Get all pools for a token pair."""
        pair_key = self._get_pair_key(token_a, token_b)
        return self.pools.get(pair_key, [])

    def _find_paths(
        self,
        start: str,
        end: str,
        max_hops: int
    ) -> List[List[str]]:
        """Find all paths between two tokens using BFS."""
        if start == end:
            return [[start]]

        paths = []
        queue = [(start, [start])]

        while queue:
            current, path = queue.pop(0)

            if len(path) > max_hops + 1:
                continue

            for neighbor in self.token_graph.get(current, set()):
                if neighbor in path:
                    continue

                new_path = path + [neighbor]

                if neighbor == end:
                    paths.append(new_path)
                elif len(new_path) <= max_hops:
                    queue.append((neighbor, new_path))

        return paths

    def _build_route(
        self,
        route_id: str,
        pools: List[Pool],
        token_in: str,
        amount_in: float
    ) -> Optional[Route]:
        """Build a route from a list of pools."""
        steps = []
        current_amount = amount_in
        current_token = token_in
        total_fee = 0
        total_impact = 0

        for pool in pools:
            # Determine swap direction
            if pool.token_a == current_token:
                token_out = pool.token_b
                reserve_in = pool.reserve_a
                reserve_out = pool.reserve_b
            else:
                token_out = pool.token_a
                reserve_in = pool.reserve_b
                reserve_out = pool.reserve_a

            # Calculate output using constant product formula
            fee = current_amount * pool.fee_rate
            amount_in_after_fee = current_amount - fee

            # x * y = k
            # (x + dx) * (y - dy) = k
            # dy = y * dx / (x + dx)
            amount_out = (reserve_out * amount_in_after_fee) / (reserve_in + amount_in_after_fee)

            # Calculate price impact
            price_before = reserve_out / reserve_in
            price_after = (reserve_out - amount_out) / (reserve_in + amount_in_after_fee)
            price_impact = abs(price_after - price_before) / price_before

            step = RouteStep(
                pool=pool,
                token_in=current_token,
                token_out=token_out,
                amount_in=current_amount,
                amount_out=amount_out,
                price_impact=price_impact,
                fee=fee
            )
            steps.append(step)

            total_fee += fee
            total_impact += price_impact
            current_amount = amount_out
            current_token = token_out

        if not steps:
            return None

        final_amount_out = steps[-1].amount_out
        effective_price = final_amount_out / amount_in if amount_in > 0 else 0

        route_type = RouteType.DIRECT if len(steps) == 1 else RouteType.MULTI_HOP

        return Route(
            route_id=route_id,
            route_type=route_type,
            steps=steps,
            token_in=token_in,
            token_out=steps[-1].token_out,
            amount_in=amount_in,
            amount_out=final_amount_out,
            total_fee=total_fee,
            total_price_impact=total_impact,
            effective_price=effective_price,
            execution_time_ms=len(steps) * 50,  # Estimate
            score=0  # Will be calculated later
        )

    def _score_route(self, route: Route, max_slippage: float) -> float:
        """Score a route based on multiple factors."""
        score = 100.0

        # Output amount (higher is better)
        score += route.amount_out * 0.1

        # Price impact penalty (lower is better)
        if route.total_price_impact > max_slippage:
            score -= (route.total_price_impact - max_slippage) * 1000
        score -= route.total_price_impact * 100

        # Fee penalty
        score -= route.total_fee * 10

        # Hop penalty (fewer hops is better)
        score -= len(route.steps) * 5

        # DEX preference bonus
        for step in route.steps:
            dex_priority = self.dex_priority.get(step.pool.dex, 50)
            score += dex_priority * 0.1

        # Liquidity bonus (higher TVL = more reliable)
        avg_tvl = sum(s.pool.tvl_usd for s in route.steps) / len(route.steps)
        score += min(avg_tvl / 100000, 10)  # Cap at 10 points

        return score

    def _calculate_optimal_split(
        self,
        routes: List[Route],
        total_amount: float
    ) -> Optional[SplitRoute]:
        """Calculate optimal split across multiple routes."""
        if len(routes) < 2:
            return None

        # Simple equal split for now
        # In production, use convex optimization
        n = min(len(routes), 3)
        splits = [1.0 / n] * n

        # Recalculate routes with split amounts
        split_routes = []
        total_out = 0

        for i, route in enumerate(routes[:n]):
            split_amount = total_amount * splits[i]
            # Rebuild route with new amount
            new_route = self._build_route(
                route.route_id + f"_split{i}",
                [s.pool for s in route.steps],
                route.token_in,
                split_amount
            )
            if new_route:
                split_routes.append(new_route)
                total_out += new_route.amount_out

        if not split_routes:
            return None

        return SplitRoute(
            routes=split_routes,
            splits=splits[:len(split_routes)],
            total_amount_in=total_amount,
            total_amount_out=total_out,
            weighted_price=total_out / total_amount if total_amount > 0 else 0,
            combined_score=sum(r.score for r in split_routes) / len(split_routes)
        )

    def get_best_dex_for_pair(
        self,
        token_a: str,
        token_b: str
    ) -> Optional[Tuple[DEX, Pool]]:
        """Get the best DEX for a token pair."""
        pools = self._get_pools_for_pair(token_a, token_b)

        if not pools:
            return None

        # Score by liquidity and DEX priority
        best_pool = max(
            pools,
            key=lambda p: p.tvl_usd + self.dex_priority.get(p.dex, 50) * 1000
        )

        return (best_pool.dex, best_pool)

    def get_liquidity_depth(
        self,
        token_in: str,
        token_out: str,
        price_levels: List[float] = None
    ) -> Dict:
        """Get liquidity depth for a token pair."""
        if price_levels is None:
            price_levels = [100, 1000, 10000, 100000]

        pools = self._get_pools_for_pair(token_in, token_out)

        if not pools:
            return {"depth": {}, "total_tvl": 0}

        depth = {}
        for amount in price_levels:
            total_out = 0
            total_impact = 0

            for pool in pools:
                if pool.token_a == token_in:
                    reserve_in = pool.reserve_a
                    reserve_out = pool.reserve_b
                else:
                    reserve_in = pool.reserve_b
                    reserve_out = pool.reserve_a

                amount_after_fee = amount * (1 - pool.fee_rate)
                out = (reserve_out * amount_after_fee) / (reserve_in + amount_after_fee)
                total_out += out

                impact = amount / reserve_in if reserve_in > 0 else 1
                total_impact = max(total_impact, impact)

            depth[amount] = {
                "output": total_out,
                "average_price": total_out / amount if amount > 0 else 0,
                "price_impact": total_impact
            }

        return {
            "depth": depth,
            "total_tvl": sum(p.tvl_usd for p in pools),
            "num_pools": len(pools)
        }

    def record_execution(
        self,
        route: Route,
        success: bool = True
    ):
        """Record route execution for analytics."""
        import json

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO route_history
                (route_id, token_in, token_out, amount_in, amount_out,
                 route_type, steps, total_fee, price_impact, executed_at, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                route.route_id, route.token_in, route.token_out,
                route.amount_in, route.amount_out, route.route_type.value,
                json.dumps([{
                    "pool": s.pool.pool_id,
                    "dex": s.pool.dex.value,
                    "in": s.token_in,
                    "out": s.token_out
                } for s in route.steps]),
                route.total_fee, route.total_price_impact,
                datetime.now().isoformat(), 1 if success else 0
            ))

    def get_routing_stats(self) -> Dict:
        """Get routing statistics."""
        with self._get_db() as conn:
            total_routes = conn.execute(
                "SELECT COUNT(*) FROM route_history"
            ).fetchone()[0]

            successful = conn.execute(
                "SELECT COUNT(*) FROM route_history WHERE success = 1"
            ).fetchone()[0]

            total_volume = conn.execute(
                "SELECT COALESCE(SUM(amount_in), 0) FROM route_history"
            ).fetchone()[0]

            by_dex = conn.execute("""
                SELECT steps, COUNT(*) as count FROM route_history
                GROUP BY steps
            """).fetchall()

        return {
            "total_routes": total_routes,
            "success_rate": successful / total_routes if total_routes > 0 else 0,
            "total_volume_routed": total_volume,
            "num_pools": sum(len(pools) for pools in self.pools.values()),
            "tokens_supported": len(self.token_graph)
        }


# Singleton instance
_smart_router: Optional[SmartRouter] = None


def get_smart_router() -> SmartRouter:
    """Get or create the smart router singleton."""
    global _smart_router
    if _smart_router is None:
        _smart_router = SmartRouter()
    return _smart_router
