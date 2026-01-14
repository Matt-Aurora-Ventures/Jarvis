"""
JARVIS Database Index Optimization

Analyzes query patterns and manages database indexes for optimal performance.
"""

import os
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class IndexRecommendation:
    """A recommended index."""
    table: str
    columns: List[str]
    name: str
    reason: str
    estimated_improvement: str
    priority: str  # high, medium, low


@dataclass
class IndexStats:
    """Statistics about an existing index."""
    name: str
    table: str
    columns: List[str]
    size_bytes: int
    usage_count: int
    last_used: Optional[datetime]
    is_unique: bool


class IndexOptimizer:
    """Analyzes and optimizes database indexes."""

    # Predefined index recommendations based on common query patterns
    RECOMMENDED_INDEXES = [
        IndexRecommendation(
            table="trades",
            columns=["user_id", "created_at DESC"],
            name="idx_trades_user_recent",
            reason="Fast lookup of recent trades per user",
            estimated_improvement="10x faster portfolio queries",
            priority="high"
        ),
        IndexRecommendation(
            table="trades",
            columns=["symbol", "status"],
            name="idx_trades_symbol_status",
            reason="Trade history filtering by symbol",
            estimated_improvement="5x faster trade searches",
            priority="medium"
        ),
        IndexRecommendation(
            table="messages",
            columns=["conversation_id", "created_at"],
            name="idx_messages_conversation_order",
            reason="Message retrieval in order",
            estimated_improvement="3x faster chat loading",
            priority="high"
        ),
        IndexRecommendation(
            table="conversations",
            columns=["user_id", "updated_at DESC"],
            name="idx_conversations_user_recent",
            reason="Recent conversations list",
            estimated_improvement="5x faster conversation listing",
            priority="high"
        ),
        IndexRecommendation(
            table="llm_usage",
            columns=["timestamp"],
            name="idx_llm_usage_timestamp",
            reason="Time-based usage queries",
            estimated_improvement="10x faster cost reports",
            priority="high"
        ),
        IndexRecommendation(
            table="llm_usage",
            columns=["provider", "model"],
            name="idx_llm_usage_provider_model",
            reason="Provider/model aggregations",
            estimated_improvement="5x faster provider stats",
            priority="medium"
        ),
        IndexRecommendation(
            table="audit_log",
            columns=["timestamp DESC"],
            name="idx_audit_log_recent",
            reason="Recent audit entries",
            estimated_improvement="10x faster audit queries",
            priority="high"
        ),
        IndexRecommendation(
            table="audit_log",
            columns=["user_id", "action"],
            name="idx_audit_log_user_action",
            reason="User activity lookup",
            estimated_improvement="5x faster user audits",
            priority="medium"
        ),
        IndexRecommendation(
            table="bot_metrics",
            columns=["bot_type", "timestamp DESC"],
            name="idx_bot_metrics_type_recent",
            reason="Bot performance history",
            estimated_improvement="5x faster bot dashboards",
            priority="medium"
        ),
        IndexRecommendation(
            table="system_metrics",
            columns=["component", "timestamp DESC"],
            name="idx_system_metrics_component_recent",
            reason="Component performance history",
            estimated_improvement="5x faster system monitoring",
            priority="medium"
        ),
        IndexRecommendation(
            table="portfolio_snapshots",
            columns=["user_id", "timestamp DESC"],
            name="idx_portfolio_user_recent",
            reason="Portfolio history lookup",
            estimated_improvement="3x faster P&L calculations",
            priority="high"
        ),
        IndexRecommendation(
            table="api_keys",
            columns=["key_hash"],
            name="idx_api_keys_hash",
            reason="API key authentication",
            estimated_improvement="10x faster auth",
            priority="high"
        ),
        IndexRecommendation(
            table="webhooks",
            columns=["user_id", "is_active"],
            name="idx_webhooks_user_active",
            reason="Active webhook lookup",
            estimated_improvement="3x faster webhook delivery",
            priority="low"
        ),
    ]

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "sqlite:///data/jarvis.db")
        self._connection = None

    def get_connection(self):
        """Get database connection."""
        if self._connection is None:
            import sqlalchemy
            engine = sqlalchemy.create_engine(self.db_url)
            self._connection = engine.connect()
        return self._connection

    def get_existing_indexes(self) -> List[IndexStats]:
        """Get all existing indexes."""
        conn = self.get_connection()

        if "sqlite" in self.db_url:
            return self._get_sqlite_indexes(conn)
        else:
            return self._get_postgres_indexes(conn)

    def _get_sqlite_indexes(self, conn) -> List[IndexStats]:
        """Get indexes for SQLite."""
        indexes = []

        # Get all tables
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()

        for (table_name,) in tables:
            # Get indexes for each table
            result = conn.execute(
                f"PRAGMA index_list('{table_name}')"
            ).fetchall()

            for row in result:
                idx_name = row[1]
                is_unique = bool(row[2])

                # Get columns in index
                cols_result = conn.execute(
                    f"PRAGMA index_info('{idx_name}')"
                ).fetchall()
                columns = [r[2] for r in cols_result]

                indexes.append(IndexStats(
                    name=idx_name,
                    table=table_name,
                    columns=columns,
                    size_bytes=0,  # SQLite doesn't easily expose this
                    usage_count=0,
                    last_used=None,
                    is_unique=is_unique
                ))

        return indexes

    def _get_postgres_indexes(self, conn) -> List[IndexStats]:
        """Get indexes for PostgreSQL."""
        query = """
        SELECT
            schemaname,
            tablename,
            indexname,
            pg_relation_size(indexrelid) as size_bytes,
            idx_scan as usage_count
        FROM pg_stat_user_indexes
        JOIN pg_indexes USING (schemaname, tablename, indexname)
        ORDER BY tablename, indexname
        """

        result = conn.execute(query).fetchall()
        indexes = []

        for row in result:
            indexes.append(IndexStats(
                name=row[2],
                table=row[1],
                columns=[],  # Would need additional query
                size_bytes=row[3],
                usage_count=row[4],
                last_used=None,
                is_unique=False
            ))

        return indexes

    def get_recommendations(self) -> List[IndexRecommendation]:
        """Get index recommendations based on existing indexes."""
        existing = self.get_existing_indexes()
        existing_names = {idx.name for idx in existing}

        # Filter to indexes that don't exist
        recommendations = [
            rec for rec in self.RECOMMENDED_INDEXES
            if rec.name not in existing_names
        ]

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

        return recommendations

    def get_unused_indexes(self, min_usage: int = 10) -> List[IndexStats]:
        """Find indexes that are rarely used."""
        existing = self.get_existing_indexes()
        return [
            idx for idx in existing
            if idx.usage_count < min_usage
            and not idx.name.startswith("sqlite_")
            and not idx.is_unique
        ]

    def generate_create_statements(
        self,
        recommendations: Optional[List[IndexRecommendation]] = None
    ) -> List[str]:
        """Generate CREATE INDEX statements."""
        if recommendations is None:
            recommendations = self.get_recommendations()

        statements = []
        for rec in recommendations:
            columns = ", ".join(rec.columns)
            stmt = f"CREATE INDEX IF NOT EXISTS {rec.name} ON {rec.table} ({columns});"
            statements.append(stmt)

        return statements

    def generate_drop_statements(
        self,
        indexes: Optional[List[IndexStats]] = None
    ) -> List[str]:
        """Generate DROP INDEX statements for unused indexes."""
        if indexes is None:
            indexes = self.get_unused_indexes()

        statements = []
        for idx in indexes:
            if "sqlite" in self.db_url:
                stmt = f"DROP INDEX IF EXISTS {idx.name};"
            else:
                stmt = f"DROP INDEX IF EXISTS {idx.name};"
            statements.append(stmt)

        return statements

    def apply_recommendations(
        self,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Apply recommended indexes."""
        recommendations = self.get_recommendations()
        statements = self.generate_create_statements(recommendations)

        results = {
            "dry_run": dry_run,
            "recommendations": len(recommendations),
            "statements": statements,
            "applied": [],
            "errors": []
        }

        if not dry_run:
            conn = self.get_connection()
            for stmt in statements:
                try:
                    conn.execute(stmt)
                    results["applied"].append(stmt)
                    logger.info(f"Created index: {stmt}")
                except Exception as e:
                    results["errors"].append({"statement": stmt, "error": str(e)})
                    logger.error(f"Failed to create index: {e}")

        return results

    def remove_unused(
        self,
        dry_run: bool = True,
        min_usage: int = 10
    ) -> Dict[str, Any]:
        """Remove unused indexes."""
        unused = self.get_unused_indexes(min_usage)
        statements = self.generate_drop_statements(unused)

        results = {
            "dry_run": dry_run,
            "unused_count": len(unused),
            "statements": statements,
            "dropped": [],
            "errors": []
        }

        if not dry_run:
            conn = self.get_connection()
            for stmt in statements:
                try:
                    conn.execute(stmt)
                    results["dropped"].append(stmt)
                    logger.info(f"Dropped index: {stmt}")
                except Exception as e:
                    results["errors"].append({"statement": stmt, "error": str(e)})
                    logger.error(f"Failed to drop index: {e}")

        return results

    def analyze_table(self, table: str) -> Dict[str, Any]:
        """Analyze a table and its indexes."""
        conn = self.get_connection()

        if "sqlite" in self.db_url:
            conn.execute(f"ANALYZE {table}")
        else:
            conn.execute(f"ANALYZE {table}")

        existing = [idx for idx in self.get_existing_indexes() if idx.table == table]
        recommended = [rec for rec in self.RECOMMENDED_INDEXES if rec.table == table]

        return {
            "table": table,
            "existing_indexes": len(existing),
            "recommended_indexes": len(recommended),
            "existing": [idx.name for idx in existing],
            "recommended": [rec.name for rec in recommended]
        }

    def get_report(self) -> str:
        """Generate a human-readable optimization report."""
        existing = self.get_existing_indexes()
        recommendations = self.get_recommendations()
        unused = self.get_unused_indexes()

        lines = [
            "=" * 60,
            "JARVIS Database Index Optimization Report",
            f"Generated: {datetime.utcnow().isoformat()}",
            "=" * 60,
            "",
            f"Existing Indexes: {len(existing)}",
            f"Recommendations: {len(recommendations)}",
            f"Unused Indexes: {len(unused)}",
            "",
        ]

        if recommendations:
            lines.append("RECOMMENDED INDEXES:")
            lines.append("-" * 40)
            for rec in recommendations:
                lines.append(f"  [{rec.priority.upper()}] {rec.name}")
                lines.append(f"    Table: {rec.table}")
                lines.append(f"    Columns: {', '.join(rec.columns)}")
                lines.append(f"    Reason: {rec.reason}")
                lines.append(f"    Impact: {rec.estimated_improvement}")
                lines.append("")

        if unused:
            lines.append("POTENTIALLY UNUSED INDEXES:")
            lines.append("-" * 40)
            for idx in unused:
                lines.append(f"  {idx.name} on {idx.table}")
                lines.append(f"    Usage count: {idx.usage_count}")
                lines.append("")

        lines.append("=" * 60)
        lines.append("To apply recommendations: python optimize_indexes.py --apply")
        lines.append("=" * 60)

        return "\n".join(lines)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Database Index Optimization")
    parser.add_argument("--apply", action="store_true", help="Apply recommendations")
    parser.add_argument("--remove-unused", action="store_true", help="Remove unused indexes")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--table", help="Analyze specific table")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    optimizer = IndexOptimizer()

    if args.report or (not args.apply and not args.remove_unused and not args.table):
        print(optimizer.get_report())

    if args.table:
        result = optimizer.analyze_table(args.table)
        print(f"\nTable Analysis: {result['table']}")
        print(f"  Existing indexes: {result['existing']}")
        print(f"  Recommended: {result['recommended']}")

    if args.apply:
        dry_run = args.dry_run
        result = optimizer.apply_recommendations(dry_run=dry_run)
        print(f"\nApplied recommendations (dry_run={dry_run}):")
        for stmt in result["statements"]:
            print(f"  {stmt}")

    if args.remove_unused:
        dry_run = args.dry_run
        result = optimizer.remove_unused(dry_run=dry_run)
        print(f"\nRemoved unused indexes (dry_run={dry_run}):")
        for stmt in result["statements"]:
            print(f"  {stmt}")


if __name__ == "__main__":
    main()
