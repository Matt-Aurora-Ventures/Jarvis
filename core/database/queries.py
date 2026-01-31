"""Query builder and optimized queries."""
from typing import Any, List, Optional, Tuple
from dataclasses import dataclass

from core.security_validation import sanitize_sql_identifier


@dataclass
class QueryResult:
    rows: List[dict]
    total: int
    page: int
    page_size: int


class QueryBuilder:
    """Fluent SQL query builder."""
    
    def __init__(self, table: str):
        self.table = table
        self._select = ["*"]
        self._where = []
        self._params = []
        self._order_by = []
        self._limit = None
        self._offset = None
        self._joins = []
    
    def select(self, *columns) -> "QueryBuilder":
        self._select = list(columns)
        return self
    
    def where(self, condition: str, *params) -> "QueryBuilder":
        self._where.append(condition)
        self._params.extend(params)
        return self
    
    def where_in(self, column: str, values: list) -> "QueryBuilder":
        if values:
            safe_column = sanitize_sql_identifier(column)
            placeholders = ",".join("?" * len(values))
            self._where.append(f"{safe_column} IN ({placeholders})")
            self._params.extend(values)
        return self
    
    def order_by(self, column: str, direction: str = "ASC") -> "QueryBuilder":
        safe_column = sanitize_sql_identifier(column)
        # Only allow ASC or DESC
        safe_direction = "DESC" if direction.upper() == "DESC" else "ASC"
        self._order_by.append(f"{safe_column} {safe_direction}")
        return self
    
    def limit(self, limit: int) -> "QueryBuilder":
        self._limit = limit
        return self
    
    def offset(self, offset: int) -> "QueryBuilder":
        self._offset = offset
        return self
    
    def join(self, table: str, condition: str, join_type: str = "INNER") -> "QueryBuilder":
        safe_table = sanitize_sql_identifier(table)
        # Only allow valid join types
        valid_joins = {"INNER", "LEFT", "RIGHT", "FULL", "CROSS"}
        safe_join_type = join_type.upper() if join_type.upper() in valid_joins else "INNER"
        # Note: condition is more complex to sanitize safely - ensure callers use safe patterns
        self._joins.append(f"{safe_join_type} JOIN {safe_table} ON {condition}")
        return self
    
    def paginate(self, page: int, page_size: int) -> "QueryBuilder":
        self._limit = page_size
        self._offset = (page - 1) * page_size
        return self
    
    def build(self) -> Tuple[str, list]:
        safe_table = sanitize_sql_identifier(self.table)
        safe_columns = [sanitize_sql_identifier(col) if col != '*' else '*' for col in self._select]
        parts = [f"SELECT {', '.join(safe_columns)} FROM {safe_table}"]
        
        for join in self._joins:
            parts.append(join)
        
        if self._where:
            parts.append(f"WHERE {' AND '.join(self._where)}")
        
        if self._order_by:
            parts.append(f"ORDER BY {', '.join(self._order_by)}")
        
        if self._limit is not None:
            parts.append(f"LIMIT {self._limit}")
        
        if self._offset is not None:
            parts.append(f"OFFSET {self._offset}")
        
        return " ".join(parts), self._params
    
    def build_count(self) -> Tuple[str, list]:
        safe_table = sanitize_sql_identifier(self.table)
        parts = [f"SELECT COUNT(*) as count FROM {safe_table}"]
        for join in self._joins:
            parts.append(join)
        if self._where:
            parts.append(f"WHERE {' AND '.join(self._where)}")
        return " ".join(parts), self._params


class OptimizedQueries:
    """Pre-built optimized queries for common operations."""
    
    @staticmethod
    def get_trades_paginated(conn, symbol: str = None, status: str = None, 
                            page: int = 1, page_size: int = 50) -> QueryResult:
        qb = QueryBuilder("trades").select("*").order_by("created_at", "DESC").paginate(page, page_size)
        if symbol:
            qb.where("symbol = ?", symbol)
        if status:
            qb.where("status = ?", status)
        
        query, params = qb.build()
        count_query, count_params = qb.build_count()
        
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        total = conn.execute(count_query, count_params).fetchone()[0]
        
        return QueryResult(rows=rows, total=total, page=page, page_size=page_size)
    
    @staticmethod
    def get_position_summary(conn, user_id: str = None):
        query = """
            SELECT symbol,
                   SUM(CASE WHEN side='buy' THEN amount ELSE -amount END) as net_position,
                   SUM(CASE WHEN side='buy' THEN amount*price ELSE -amount*price END) / 
                   NULLIF(SUM(CASE WHEN side='buy' THEN amount ELSE -amount END), 0) as avg_price
            FROM trades 
            WHERE status = 'filled'
        """
        params = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " GROUP BY symbol HAVING net_position != 0"
        
        return [dict(r) for r in conn.execute(query, params).fetchall()]
    
    @staticmethod
    def get_daily_pnl(conn, days: int = 30):
        query = """
            SELECT DATE(created_at) as date,
                   SUM(CASE WHEN side='sell' THEN amount*price ELSE -amount*price END) as pnl,
                   COUNT(*) as trade_count
            FROM trades
            WHERE status = 'filled' AND created_at > datetime('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """
        return [dict(r) for r in conn.execute(query, [f"-{days} days"]).fetchall()]
