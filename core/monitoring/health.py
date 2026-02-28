"""
System Health Monitor
Prompt #100: Comprehensive system health monitoring

Monitors all JARVIS components and provides health status.
"""

import asyncio
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import json

logger = logging.getLogger("jarvis.monitoring.health")


# =============================================================================
# MODELS
# =============================================================================

class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component"""
    name: str
    status: HealthStatus
    latency_ms: float
    message: str
    last_check: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health"""
    status: HealthStatus
    components: Dict[str, ComponentHealth]
    uptime_seconds: float
    version: str
    checked_at: datetime
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0


@dataclass
class HealthCheck:
    """A health check definition"""
    name: str
    check_func: Callable
    timeout_seconds: float = 5.0
    critical: bool = True  # If True, affects overall status
    interval_seconds: float = 60.0


# =============================================================================
# HEALTH MONITOR
# =============================================================================

class HealthMonitor:
    """
    Monitors system health across all components.

    Components monitored:
    - Database connections
    - API endpoints
    - Trading bot status
    - Treasury wallets
    - External services (RPC, price feeds)
    - Queue systems
    """

    VERSION = "3.6.0"

    def __init__(
        self,
        db_path: str = None,
    ):
        self.db_path = db_path or os.getenv(
            "HEALTH_DB",
            "data/health.db"
        )

        self._checks: Dict[str, HealthCheck] = {}
        self._results: Dict[str, ComponentHealth] = {}
        self._start_time = datetime.now(timezone.utc)
        self._last_check: Optional[datetime] = None

        self._init_database()
        self._register_default_checks()

    def _init_database(self):
        """Initialize health database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Health check history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms REAL,
                message TEXT,
                checked_at TEXT NOT NULL
            )
        """)

        # System status snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                healthy_count INTEGER,
                degraded_count INTEGER,
                unhealthy_count INTEGER,
                uptime_seconds REAL,
                snapshot_json TEXT,
                recorded_at TEXT NOT NULL
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_health_component
            ON health_history(component)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_health_time
            ON health_history(checked_at)
        """)

        conn.commit()
        conn.close()

    def _register_default_checks(self):
        """Register default health checks"""
        # Database check
        self.register_check(HealthCheck(
            name="database",
            check_func=self._check_database,
            timeout_seconds=5.0,
            critical=True,
        ))

        # Trade data database
        self.register_check(HealthCheck(
            name="trade_data_db",
            check_func=self._check_trade_db,
            timeout_seconds=5.0,
            critical=False,
        ))

        # Solana RPC
        self.register_check(HealthCheck(
            name="solana_rpc",
            check_func=self._check_solana_rpc,
            timeout_seconds=10.0,
            critical=True,
        ))

        # Treasury wallets
        self.register_check(HealthCheck(
            name="treasury",
            check_func=self._check_treasury,
            timeout_seconds=10.0,
            critical=True,
        ))

        # Trading bot
        self.register_check(HealthCheck(
            name="trading_bot",
            check_func=self._check_trading_bot,
            timeout_seconds=5.0,
            critical=False,
        ))

        # Data collector
        self.register_check(HealthCheck(
            name="data_collector",
            check_func=self._check_data_collector,
            timeout_seconds=5.0,
            critical=False,
        ))

    # =========================================================================
    # CHECK REGISTRATION
    # =========================================================================

    def register_check(
        self,
        check: Any,
        check_func: Optional[Callable] = None,
        timeout_seconds: float = 5.0,
        critical: bool = True,
        interval_seconds: float = 60.0,
    ):
        """Register a health check (HealthCheck object or legacy args)."""
        if isinstance(check, HealthCheck):
            health_check = check
        elif isinstance(check, str) and callable(check_func):
            health_check = HealthCheck(
                name=check,
                check_func=check_func,
                timeout_seconds=timeout_seconds,
                critical=critical,
                interval_seconds=interval_seconds,
            )
        else:
            raise TypeError(
                "register_check expects HealthCheck or (name: str, check_func: callable)"
            )

        self._checks[health_check.name] = health_check
        logger.debug(f"Registered health check: {health_check.name}")

    @property
    def checks(self) -> Dict[str, HealthCheck]:
        """Expose registered checks for legacy integrations/tests."""
        return self._checks

    def unregister_check(self, name: str):
        """Unregister a health check"""
        if name in self._checks:
            del self._checks[name]

    # =========================================================================
    # HEALTH CHECKS
    # =========================================================================

    async def check_health(self) -> SystemHealth:
        """
        Run all health checks and return system health.

        Returns:
            SystemHealth with all component statuses
        """
        components = {}
        healthy = 0
        degraded = 0
        unhealthy = 0

        # Run all checks
        for name, check in self._checks.items():
            try:
                result = await asyncio.wait_for(
                    check.check_func(),
                    timeout=check.timeout_seconds,
                )
                components[name] = result

                # Count by status
                if result.status == HealthStatus.HEALTHY:
                    healthy += 1
                elif result.status == HealthStatus.DEGRADED:
                    degraded += 1
                else:
                    unhealthy += 1

            except asyncio.TimeoutError:
                components[name] = ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=check.timeout_seconds * 1000,
                    message="Check timed out",
                    last_check=datetime.now(timezone.utc),
                )
                unhealthy += 1

            except Exception as e:
                components[name] = ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=0,
                    message=f"Check failed: {e}",
                    last_check=datetime.now(timezone.utc),
                )
                unhealthy += 1

        # Store results
        self._results = components
        self._last_check = datetime.now(timezone.utc)

        # Determine overall status
        critical_healthy = all(
            components.get(name, ComponentHealth(
                name=name,
                status=HealthStatus.UNKNOWN,
                latency_ms=0,
                message="Not checked",
                last_check=datetime.now(timezone.utc),
            )).status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
            for name, check in self._checks.items()
            if check.critical
        )

        if unhealthy > 0 and not critical_healthy:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded > 0 or (unhealthy > 0 and critical_healthy):
            overall_status = HealthStatus.DEGRADED
        elif healthy > 0:
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.UNKNOWN

        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        system_health = SystemHealth(
            status=overall_status,
            components=components,
            uptime_seconds=uptime,
            version=self.VERSION,
            checked_at=datetime.now(timezone.utc),
            healthy_count=healthy,
            degraded_count=degraded,
            unhealthy_count=unhealthy,
        )

        # Save snapshot
        await self._save_snapshot(system_health)

        return system_health

    async def check_component(self, name: str) -> Optional[ComponentHealth]:
        """Check a single component"""
        check = self._checks.get(name)
        if check is None:
            return None

        try:
            result = await asyncio.wait_for(
                check.check_func(),
                timeout=check.timeout_seconds,
            )
            self._results[name] = result
            return result

        except Exception as e:
            result = ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=0,
                message=str(e),
                last_check=datetime.now(timezone.utc),
            )
            self._results[name] = result
            return result

    # =========================================================================
    # DEFAULT CHECK IMPLEMENTATIONS
    # =========================================================================

    async def _check_database(self) -> ComponentHealth:
        """Check main database connection"""
        start = time.time()

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()

            latency = (time.time() - start) * 1000

            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                message="Database connection OK",
                last_check=datetime.now(timezone.utc),
            )

        except Exception as e:
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.time() - start) * 1000,
                message=f"Database error: {e}",
                last_check=datetime.now(timezone.utc),
            )

    async def _check_trade_db(self) -> ComponentHealth:
        """Check trade data database"""
        start = time.time()
        trade_db = os.getenv("TRADE_DATA_DB", "data/trade_data.db")

        try:
            if not os.path.exists(trade_db):
                return ComponentHealth(
                    name="trade_data_db",
                    status=HealthStatus.DEGRADED,
                    latency_ms=(time.time() - start) * 1000,
                    message="Trade database not initialized",
                    last_check=datetime.now(timezone.utc),
                )

            conn = sqlite3.connect(trade_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM anonymized_trades")
            count = cursor.fetchone()[0]
            conn.close()

            latency = (time.time() - start) * 1000

            return ComponentHealth(
                name="trade_data_db",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                message=f"Trade DB OK ({count} records)",
                last_check=datetime.now(timezone.utc),
                metadata={"record_count": count},
            )

        except Exception as e:
            return ComponentHealth(
                name="trade_data_db",
                status=HealthStatus.DEGRADED,
                latency_ms=(time.time() - start) * 1000,
                message=f"Trade DB error: {e}",
                last_check=datetime.now(timezone.utc),
            )

    async def _check_solana_rpc(self) -> ComponentHealth:
        """Check Solana RPC connection"""
        start = time.time()
        rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                rpc_url,
                data=json.dumps({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getHealth"
                }).encode(),
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read())

            latency = (time.time() - start) * 1000

            if data.get("result") == "ok":
                return ComponentHealth(
                    name="solana_rpc",
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                    message="Solana RPC OK",
                    last_check=datetime.now(timezone.utc),
                )
            else:
                return ComponentHealth(
                    name="solana_rpc",
                    status=HealthStatus.DEGRADED,
                    latency_ms=latency,
                    message=f"RPC returned: {data.get('result')}",
                    last_check=datetime.now(timezone.utc),
                )

        except Exception as e:
            return ComponentHealth(
                name="solana_rpc",
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.time() - start) * 1000,
                message=f"RPC error: {e}",
                last_check=datetime.now(timezone.utc),
            )

    async def _check_treasury(self) -> ComponentHealth:
        """Check treasury status"""
        start = time.time()

        try:
            from core.treasury.manager import get_treasury_manager

            manager = get_treasury_manager()
            status = await manager.get_status()

            latency = (time.time() - start) * 1000

            if status.get("running"):
                return ComponentHealth(
                    name="treasury",
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                    message="Treasury running",
                    last_check=datetime.now(timezone.utc),
                    metadata=status,
                )
            else:
                return ComponentHealth(
                    name="treasury",
                    status=HealthStatus.DEGRADED,
                    latency_ms=latency,
                    message="Treasury not running",
                    last_check=datetime.now(timezone.utc),
                )

        except Exception as e:
            return ComponentHealth(
                name="treasury",
                status=HealthStatus.DEGRADED,
                latency_ms=(time.time() - start) * 1000,
                message=f"Treasury check failed: {e}",
                last_check=datetime.now(timezone.utc),
            )

    async def _check_trading_bot(self) -> ComponentHealth:
        """Check trading bot status"""
        start = time.time()

        try:
            from core.trading.treasury_bot import get_treasury_bot

            bot = get_treasury_bot()
            is_running = bot.is_running if hasattr(bot, 'is_running') else False

            latency = (time.time() - start) * 1000

            if is_running:
                return ComponentHealth(
                    name="trading_bot",
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                    message="Trading bot active",
                    last_check=datetime.now(timezone.utc),
                )
            else:
                return ComponentHealth(
                    name="trading_bot",
                    status=HealthStatus.DEGRADED,
                    latency_ms=latency,
                    message="Trading bot not running",
                    last_check=datetime.now(timezone.utc),
                )

        except Exception as e:
            return ComponentHealth(
                name="trading_bot",
                status=HealthStatus.DEGRADED,
                latency_ms=(time.time() - start) * 1000,
                message=f"Trading bot check failed: {e}",
                last_check=datetime.now(timezone.utc),
            )

    async def _check_data_collector(self) -> ComponentHealth:
        """Check data collector status"""
        start = time.time()

        try:
            from core.data.collector import get_trade_collector

            collector = get_trade_collector()
            stats = await collector.get_stats()

            latency = (time.time() - start) * 1000

            return ComponentHealth(
                name="data_collector",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                message=f"Collected {stats.get('total_collected', 0)} trades",
                last_check=datetime.now(timezone.utc),
                metadata=stats,
            )

        except Exception as e:
            return ComponentHealth(
                name="data_collector",
                status=HealthStatus.DEGRADED,
                latency_ms=(time.time() - start) * 1000,
                message=f"Collector check failed: {e}",
                last_check=datetime.now(timezone.utc),
            )

    # =========================================================================
    # HISTORY
    # =========================================================================

    async def _save_snapshot(self, health: SystemHealth):
        """Save health snapshot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Save component statuses
        for name, component in health.components.items():
            cursor.execute("""
                INSERT INTO health_history
                (component, status, latency_ms, message, checked_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                name,
                component.status.value,
                component.latency_ms,
                component.message,
                component.last_check.isoformat(),
            ))

        # Save system snapshot
        snapshot = {
            "components": {
                name: {
                    "status": c.status.value,
                    "latency_ms": c.latency_ms,
                    "message": c.message,
                }
                for name, c in health.components.items()
            },
        }

        cursor.execute("""
            INSERT INTO system_snapshots
            (status, healthy_count, degraded_count, unhealthy_count,
             uptime_seconds, snapshot_json, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            health.status.value,
            health.healthy_count,
            health.degraded_count,
            health.unhealthy_count,
            health.uptime_seconds,
            json.dumps(snapshot),
            health.checked_at.isoformat(),
        ))

        conn.commit()
        conn.close()

    async def get_health_history(
        self,
        component: str = None,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get health check history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        query = "SELECT * FROM health_history WHERE checked_at >= ?"
        params = [since]

        if component:
            query += " AND component = ?"
            params.append(component)

        query += " ORDER BY checked_at DESC"

        cursor.execute(query, params)

        columns = [d[0] for d in cursor.description]
        history = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return history

    async def get_uptime_stats(self, days: int = 7) -> Dict[str, float]:
        """Get uptime statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT status, COUNT(*) FROM system_snapshots
            WHERE recorded_at >= ?
            GROUP BY status
        """, (since,))

        counts = {row[0]: row[1] for row in cursor.fetchall()}
        total = sum(counts.values())

        conn.close()

        if total == 0:
            return {"uptime_pct": 100.0}

        healthy = counts.get("healthy", 0) + counts.get("degraded", 0)
        return {
            "uptime_pct": (healthy / total) * 100,
            "healthy_pct": (counts.get("healthy", 0) / total) * 100,
            "degraded_pct": (counts.get("degraded", 0) / total) * 100,
            "unhealthy_pct": (counts.get("unhealthy", 0) / total) * 100,
            "total_checks": total,
        }


# =============================================================================
# SINGLETON
# =============================================================================

_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get or create the health monitor singleton"""
    global _monitor
    if _monitor is None:
        _monitor = HealthMonitor()
    return _monitor
