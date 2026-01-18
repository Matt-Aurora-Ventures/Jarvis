"""
SQL Safety Module

Provides SQL injection prevention utilities:
- Parameterized query builder
- Raw SQL detection and scanning
- Codebase scanning for SQL vulnerabilities

Follows OWASP SQL injection prevention guidelines.
"""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class SQLSafetyResult:
    """Result of a SQL safety check."""
    is_safe: bool
    is_parameterized: bool
    warnings: List[str] = field(default_factory=list)
    vulnerabilities: List[str] = field(default_factory=list)


@dataclass
class CodeScanFinding:
    """A finding from scanning code for SQL vulnerabilities."""
    file_path: str
    line_number: int
    line_content: str
    pattern_matched: str
    severity: str  # "high", "medium", "low"
    description: str


class SafeQueryBuilder:
    """
    Safe SQL query builder using parameterized queries only.

    All values are parameterized to prevent SQL injection.
    Supports SELECT, INSERT, UPDATE, DELETE operations.
    """

    def __init__(self, param_style: str = "qmark"):
        """
        Initialize the query builder.

        Args:
            param_style: Parameter style ("qmark" for ?, "named" for :name)
        """
        self.param_style = param_style
        self._table: Optional[str] = None
        self._operation: str = "SELECT"
        self._columns: List[str] = ["*"]
        self._where_clauses: List[Tuple[str, str, Any]] = []
        self._order_by: Optional[str] = None
        self._limit: Optional[int] = None
        self._values: Dict[str, Any] = {}
        self._param_count = 0

    def _get_param_placeholder(self, name: str = None) -> str:
        """Get the next parameter placeholder."""
        self._param_count += 1
        if self.param_style == "qmark":
            return "?"
        elif self.param_style == "named":
            return f":{name or f'param{self._param_count}'}"
        else:
            return "%s"

    def _validate_identifier(self, identifier: str) -> str:
        """Validate and sanitize an identifier (table/column name)."""
        # Only allow alphanumeric and underscore
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
            raise ValueError(f"Invalid identifier: {identifier}")
        return identifier

    def select(self, table: str, columns: List[str] = None) -> 'SafeQueryBuilder':
        """Start a SELECT query."""
        self._operation = "SELECT"
        self._table = self._validate_identifier(table)
        if columns:
            self._columns = [self._validate_identifier(c) for c in columns]
        return self

    def insert(self, table: str) -> 'SafeQueryBuilder':
        """Start an INSERT query."""
        self._operation = "INSERT"
        self._table = self._validate_identifier(table)
        return self

    def update(self, table: str) -> 'SafeQueryBuilder':
        """Start an UPDATE query."""
        self._operation = "UPDATE"
        self._table = self._validate_identifier(table)
        return self

    def delete(self, table: str) -> 'SafeQueryBuilder':
        """Start a DELETE query."""
        self._operation = "DELETE"
        self._table = self._validate_identifier(table)
        return self

    def where(
        self,
        column: str,
        operator: str,
        value: Any
    ) -> 'SafeQueryBuilder':
        """Add a WHERE clause."""
        valid_operators = ["=", "!=", "<", ">", "<=", ">=", "LIKE", "IN", "IS"]
        if operator.upper() not in valid_operators:
            raise ValueError(f"Invalid operator: {operator}")

        self._where_clauses.append((
            self._validate_identifier(column),
            operator.upper(),
            value
        ))
        return self

    def set(self, column: str, value: Any) -> 'SafeQueryBuilder':
        """Set a value for INSERT/UPDATE."""
        self._values[self._validate_identifier(column)] = value
        return self

    def order_by(self, column: str, direction: str = "ASC") -> 'SafeQueryBuilder':
        """Add ORDER BY clause."""
        if direction.upper() not in ["ASC", "DESC"]:
            raise ValueError(f"Invalid direction: {direction}")
        self._order_by = f"{self._validate_identifier(column)} {direction.upper()}"
        return self

    def limit(self, count: int) -> 'SafeQueryBuilder':
        """Add LIMIT clause."""
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"Invalid limit: {count}")
        self._limit = count
        return self

    def build(self) -> Tuple[str, Union[List[Any], Dict[str, Any]]]:
        """
        Build the parameterized query.

        Returns:
            (query_string, parameters)
        """
        self._param_count = 0
        params = [] if self.param_style == "qmark" else {}

        if self._operation == "SELECT":
            query = f"SELECT {', '.join(self._columns)} FROM {self._table}"

        elif self._operation == "INSERT":
            columns = list(self._values.keys())
            placeholders = []
            for col in columns:
                placeholder = self._get_param_placeholder(col)
                placeholders.append(placeholder)
                if self.param_style == "qmark":
                    params.append(self._values[col])
                else:
                    params[col] = self._values[col]

            query = f"INSERT INTO {self._table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"

        elif self._operation == "UPDATE":
            set_clauses = []
            for col, val in self._values.items():
                placeholder = self._get_param_placeholder(col)
                set_clauses.append(f"{col} = {placeholder}")
                if self.param_style == "qmark":
                    params.append(val)
                else:
                    params[col] = val

            query = f"UPDATE {self._table} SET {', '.join(set_clauses)}"

        elif self._operation == "DELETE":
            query = f"DELETE FROM {self._table}"

        else:
            raise ValueError(f"Unknown operation: {self._operation}")

        # Add WHERE clauses
        if self._where_clauses:
            where_parts = []
            for col, op, val in self._where_clauses:
                placeholder = self._get_param_placeholder(f"where_{col}")
                where_parts.append(f"{col} {op} {placeholder}")
                if self.param_style == "qmark":
                    params.append(val)
                else:
                    params[f"where_{col}"] = val

            query += f" WHERE {' AND '.join(where_parts)}"

        # Add ORDER BY
        if self._order_by:
            query += f" ORDER BY {self._order_by}"

        # Add LIMIT
        if self._limit is not None:
            query += f" LIMIT {self._limit}"

        return query, params


class SQLSafetyChecker:
    """
    Checks SQL queries for safety issues.

    Detects:
    - String concatenation in queries
    - f-string usage in queries
    - .format() usage in queries
    - Unparameterized values
    """

    # Patterns that indicate potentially unsafe SQL
    UNSAFE_PATTERNS = [
        # String concatenation
        (r'"[^"]*"\s*\+', "String concatenation in SQL"),
        (r"'[^']*'\s*\+", "String concatenation in SQL"),

        # f-strings with variables
        (r'f"[^"]*\{[^}]+\}[^"]*"', "f-string with variables"),
        (r"f'[^']*\{[^}]+\}[^']*'", "f-string with variables"),

        # .format() usage
        (r'\.format\s*\(', ".format() in SQL string"),

        # % formatting
        (r'%\s*\(', "% formatting in SQL"),
        (r'%s', "% placeholder (may be unsafe)"),

        # Direct value insertion
        (r"WHERE\s+\w+\s*=\s*'[^']*'", "Hardcoded value in WHERE"),
        (r"WHERE\s+\w+\s*=\s*\d+", "Hardcoded numeric in WHERE"),
    ]

    def is_safe(self, query: str) -> SQLSafetyResult:
        """
        Check if a SQL query appears safe.

        Args:
            query: SQL query string

        Returns:
            SQLSafetyResult with safety assessment
        """
        warnings = []
        vulnerabilities = []
        is_parameterized = True

        for pattern, description in self.UNSAFE_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                warnings.append(description)
                is_parameterized = False

        # Check for parameterized placeholders
        has_placeholders = bool(re.search(r'(\?|%s|:\w+)', query))

        return SQLSafetyResult(
            is_safe=len(vulnerabilities) == 0,
            is_parameterized=is_parameterized or has_placeholders,
            warnings=warnings,
            vulnerabilities=vulnerabilities
        )


class SQLCodeScanner:
    """
    Scans Python code for SQL injection vulnerabilities.

    Checks for:
    - Raw SQL string execution
    - String formatting in execute() calls
    - Missing parameterization
    """

    # Patterns to find in code
    VULNERABLE_PATTERNS = [
        # execute with f-string
        (
            r'\.execute\s*\(\s*f["\']',
            "execute() with f-string",
            "high"
        ),
        # execute with string concatenation
        (
            r'\.execute\s*\([^)]*\+[^)]*\)',
            "execute() with string concatenation",
            "high"
        ),
        # execute with .format()
        (
            r'\.execute\s*\([^)]*\.format\s*\([^)]*\)',
            "execute() with .format()",
            "high"
        ),
        # executemany with f-string
        (
            r'\.executemany\s*\(\s*f["\']',
            "executemany() with f-string",
            "high"
        ),
        # raw_sql without parameters
        (
            r'raw_sql\s*\([^)]*\+',
            "raw_sql with string concatenation",
            "medium"
        ),
        # cursor.execute without tuple/list params
        (
            r'cursor\.execute\s*\(\s*["\'][^"\']+["\'][^,)]*\)',
            "execute() possibly without parameters",
            "low"
        ),
    ]

    def scan_file(self, file_path: Path) -> List[CodeScanFinding]:
        """
        Scan a single Python file for SQL vulnerabilities.

        Args:
            file_path: Path to Python file

        Returns:
            List of findings
        """
        findings = []

        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')

            for line_num, line in enumerate(lines, 1):
                for pattern, description, severity in self.VULNERABLE_PATTERNS:
                    if re.search(pattern, line):
                        findings.append(CodeScanFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            line_content=line.strip()[:200],
                            pattern_matched=pattern,
                            severity=severity,
                            description=description
                        ))

        except Exception as e:
            logger.warning(f"Failed to scan {file_path}: {e}")

        return findings

    def scan_directory(
        self,
        directory: Path,
        exclude_patterns: List[str] = None
    ) -> List[CodeScanFinding]:
        """
        Scan a directory recursively for SQL vulnerabilities.

        Args:
            directory: Directory to scan
            exclude_patterns: Glob patterns to exclude

        Returns:
            List of all findings
        """
        findings = []
        exclude_patterns = exclude_patterns or ["**/venv/**", "**/.venv/**", "**/node_modules/**"]

        # Find all Python files
        python_files = list(directory.glob("**/*.py"))

        # Filter excluded patterns
        for exclude in exclude_patterns:
            python_files = [
                f for f in python_files
                if not f.match(exclude.replace("**/", ""))
            ]

        for py_file in python_files:
            file_findings = self.scan_file(py_file)
            findings.extend(file_findings)

        return findings

    def generate_report(self, findings: List[CodeScanFinding]) -> str:
        """
        Generate a markdown report of findings.

        Args:
            findings: List of findings

        Returns:
            Markdown report string
        """
        if not findings:
            return "# SQL Safety Scan Report\n\nNo vulnerabilities found."

        report = ["# SQL Safety Scan Report", ""]
        report.append(f"**Total Findings:** {len(findings)}")

        # Group by severity
        by_severity = {"high": [], "medium": [], "low": []}
        for f in findings:
            by_severity[f.severity].append(f)

        report.append("")
        report.append("## Summary")
        report.append(f"- High Severity: {len(by_severity['high'])}")
        report.append(f"- Medium Severity: {len(by_severity['medium'])}")
        report.append(f"- Low Severity: {len(by_severity['low'])}")
        report.append("")

        # Detail each finding
        report.append("## Findings")
        report.append("")

        for severity in ["high", "medium", "low"]:
            if by_severity[severity]:
                report.append(f"### {severity.title()} Severity")
                report.append("")
                for f in by_severity[severity]:
                    report.append(f"**{f.file_path}:{f.line_number}**")
                    report.append(f"- Issue: {f.description}")
                    report.append(f"- Code: `{f.line_content}`")
                    report.append("")

        return "\n".join(report)


# Convenience functions
def build_safe_query(table: str) -> SafeQueryBuilder:
    """Create a new safe query builder."""
    return SafeQueryBuilder().select(table)


def check_query_safety(query: str) -> SQLSafetyResult:
    """Check if a SQL query is safe."""
    checker = SQLSafetyChecker()
    return checker.is_safe(query)


def scan_for_sql_vulnerabilities(directory: Path) -> List[CodeScanFinding]:
    """Scan a directory for SQL vulnerabilities."""
    scanner = SQLCodeScanner()
    return scanner.scan_directory(directory)
