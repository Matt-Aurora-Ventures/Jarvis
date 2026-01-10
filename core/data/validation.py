"""
Data Validation System
Prompt #90: Data quality validation and rules engine

Validates collected data against configurable rules.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
import json

logger = logging.getLogger("jarvis.data.validation")


# =============================================================================
# MODELS
# =============================================================================

class ValidationSeverity(Enum):
    """Severity level of validation issues"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RuleType(Enum):
    """Type of validation rule"""
    REQUIRED = "required"
    TYPE_CHECK = "type_check"
    RANGE = "range"
    PATTERN = "pattern"
    CUSTOM = "custom"
    ENUM = "enum"
    UNIQUE = "unique"
    RELATIONSHIP = "relationship"


@dataclass
class ValidationRule:
    """A single validation rule"""
    name: str
    field: str
    rule_type: RuleType
    params: Dict[str, Any] = field(default_factory=dict)
    severity: ValidationSeverity = ValidationSeverity.ERROR
    message: Optional[str] = None
    enabled: bool = True


@dataclass
class ValidationIssue:
    """A validation issue found in data"""
    rule_name: str
    field: str
    severity: ValidationSeverity
    message: str
    value: Any = None


@dataclass
class ValidationResult:
    """Result of validating a record"""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings: int = 0
    errors: int = 0
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# DATA VALIDATOR
# =============================================================================

class DataValidator:
    """
    Validates data against configurable rules.

    Features:
    - Declarative rule definitions
    - Multiple rule types (required, type, range, pattern, custom)
    - Severity levels
    - Extensible with custom validators
    """

    def __init__(self):
        self._rules: Dict[str, List[ValidationRule]] = {}
        self._custom_validators: Dict[str, Callable] = {}

        self._load_default_rules()

    def _load_default_rules(self):
        """Load default validation rules for trade data"""
        trade_rules = [
            # Required fields
            ValidationRule(
                name="user_hash_required",
                field="user_hash",
                rule_type=RuleType.REQUIRED,
                severity=ValidationSeverity.ERROR,
                message="User hash is required",
            ),
            ValidationRule(
                name="time_bucket_required",
                field="time_bucket",
                rule_type=RuleType.REQUIRED,
                severity=ValidationSeverity.ERROR,
                message="Time bucket is required",
            ),
            ValidationRule(
                name="token_mint_required",
                field="token_mint",
                rule_type=RuleType.REQUIRED,
                severity=ValidationSeverity.ERROR,
                message="Token mint is required",
            ),

            # Type checks
            ValidationRule(
                name="pnl_pct_numeric",
                field="pnl_pct",
                rule_type=RuleType.TYPE_CHECK,
                params={"types": ["float", "int", "NoneType"]},
                severity=ValidationSeverity.ERROR,
                message="P&L percentage must be numeric",
            ),
            ValidationRule(
                name="amount_bucket_numeric",
                field="amount_bucket",
                rule_type=RuleType.TYPE_CHECK,
                params={"types": ["int", "NoneType"]},
                severity=ValidationSeverity.ERROR,
                message="Amount bucket must be an integer",
            ),

            # Range checks
            ValidationRule(
                name="pnl_pct_range",
                field="pnl_pct",
                rule_type=RuleType.RANGE,
                params={"min": -100.0, "max": 10000.0},
                severity=ValidationSeverity.WARNING,
                message="P&L percentage outside normal range",
            ),
            ValidationRule(
                name="amount_bucket_positive",
                field="amount_bucket",
                rule_type=RuleType.RANGE,
                params={"min": 0},
                severity=ValidationSeverity.ERROR,
                message="Amount bucket must be non-negative",
            ),

            # Pattern checks
            ValidationRule(
                name="user_hash_format",
                field="user_hash",
                rule_type=RuleType.PATTERN,
                params={"pattern": r"^[a-f0-9]{64}$"},
                severity=ValidationSeverity.ERROR,
                message="User hash must be a valid SHA-256 hash",
            ),
            ValidationRule(
                name="token_mint_format",
                field="token_mint",
                rule_type=RuleType.PATTERN,
                params={"pattern": r"^[A-Za-z0-9]{32,44}$"},
                severity=ValidationSeverity.ERROR,
                message="Token mint must be a valid Solana address",
            ),

            # Enum checks
            ValidationRule(
                name="side_valid",
                field="side",
                rule_type=RuleType.ENUM,
                params={"values": ["buy", "sell", ""]},
                severity=ValidationSeverity.ERROR,
                message="Side must be 'buy' or 'sell'",
            ),
            ValidationRule(
                name="outcome_valid",
                field="outcome",
                rule_type=RuleType.ENUM,
                params={"values": ["win", "loss", "break_even", ""]},
                severity=ValidationSeverity.WARNING,
                message="Invalid outcome value",
            ),
        ]

        self._rules["trade"] = trade_rules

    # =========================================================================
    # RULE MANAGEMENT
    # =========================================================================

    def add_rule(self, data_type: str, rule: ValidationRule):
        """Add a validation rule for a data type"""
        if data_type not in self._rules:
            self._rules[data_type] = []
        self._rules[data_type].append(rule)

    def remove_rule(self, data_type: str, rule_name: str):
        """Remove a validation rule"""
        if data_type in self._rules:
            self._rules[data_type] = [
                r for r in self._rules[data_type]
                if r.name != rule_name
            ]

    def get_rules(self, data_type: str) -> List[ValidationRule]:
        """Get all rules for a data type"""
        return self._rules.get(data_type, [])

    def register_custom_validator(
        self,
        name: str,
        validator: Callable[[Any, Dict[str, Any]], tuple[bool, str]],
    ):
        """
        Register a custom validator function.

        Args:
            name: Validator name
            validator: Function taking (value, params) returning (is_valid, message)
        """
        self._custom_validators[name] = validator

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def validate(
        self,
        data: Dict[str, Any],
        data_type: str = "trade",
    ) -> ValidationResult:
        """
        Validate a data record.

        Args:
            data: Data to validate
            data_type: Type of data (determines which rules to apply)

        Returns:
            ValidationResult with issues found
        """
        issues: List[ValidationIssue] = []
        rules = self._rules.get(data_type, [])

        for rule in rules:
            if not rule.enabled:
                continue

            issue = self._apply_rule(rule, data)
            if issue:
                issues.append(issue)

        # Count by severity
        warnings = sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)
        errors = sum(1 for i in issues if i.severity in [
            ValidationSeverity.ERROR, ValidationSeverity.CRITICAL
        ])

        return ValidationResult(
            is_valid=errors == 0,
            issues=issues,
            warnings=warnings,
            errors=errors,
        )

    def validate_batch(
        self,
        records: List[Dict[str, Any]],
        data_type: str = "trade",
    ) -> tuple[List[ValidationResult], float]:
        """
        Validate a batch of records.

        Args:
            records: List of records to validate
            data_type: Type of data

        Returns:
            (results, validity_rate)
        """
        results = [self.validate(record, data_type) for record in records]
        valid_count = sum(1 for r in results if r.is_valid)
        validity_rate = valid_count / len(records) if records else 1.0

        return results, validity_rate

    def _apply_rule(
        self,
        rule: ValidationRule,
        data: Dict[str, Any],
    ) -> Optional[ValidationIssue]:
        """Apply a single validation rule"""
        value = data.get(rule.field)

        try:
            if rule.rule_type == RuleType.REQUIRED:
                if not self._check_required(value):
                    return self._create_issue(rule, value)

            elif rule.rule_type == RuleType.TYPE_CHECK:
                if not self._check_type(value, rule.params):
                    return self._create_issue(rule, value)

            elif rule.rule_type == RuleType.RANGE:
                if not self._check_range(value, rule.params):
                    return self._create_issue(rule, value)

            elif rule.rule_type == RuleType.PATTERN:
                if not self._check_pattern(value, rule.params):
                    return self._create_issue(rule, value)

            elif rule.rule_type == RuleType.ENUM:
                if not self._check_enum(value, rule.params):
                    return self._create_issue(rule, value)

            elif rule.rule_type == RuleType.CUSTOM:
                if not self._check_custom(value, rule.params):
                    return self._create_issue(rule, value)

        except Exception as e:
            logger.warning(f"Rule {rule.name} failed: {e}")
            return ValidationIssue(
                rule_name=rule.name,
                field=rule.field,
                severity=ValidationSeverity.WARNING,
                message=f"Rule check failed: {e}",
                value=value,
            )

        return None

    def _create_issue(
        self,
        rule: ValidationRule,
        value: Any,
    ) -> ValidationIssue:
        """Create a validation issue from a rule"""
        return ValidationIssue(
            rule_name=rule.name,
            field=rule.field,
            severity=rule.severity,
            message=rule.message or f"Validation failed for {rule.field}",
            value=value,
        )

    # =========================================================================
    # RULE CHECKERS
    # =========================================================================

    def _check_required(self, value: Any) -> bool:
        """Check if value is present"""
        if value is None:
            return False
        if isinstance(value, str) and value.strip() == "":
            return False
        return True

    def _check_type(self, value: Any, params: Dict[str, Any]) -> bool:
        """Check if value is of expected type"""
        if value is None and "NoneType" in params.get("types", []):
            return True

        expected_types = params.get("types", [])
        actual_type = type(value).__name__

        return actual_type in expected_types

    def _check_range(self, value: Any, params: Dict[str, Any]) -> bool:
        """Check if value is within range"""
        if value is None:
            return True  # Range checks don't apply to None

        if not isinstance(value, (int, float)):
            return True  # Skip non-numeric

        min_val = params.get("min")
        max_val = params.get("max")

        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False

        return True

    def _check_pattern(self, value: Any, params: Dict[str, Any]) -> bool:
        """Check if value matches pattern"""
        if value is None or value == "":
            return True  # Pattern checks don't apply to empty

        pattern = params.get("pattern")
        if not pattern:
            return True

        if not isinstance(value, str):
            value = str(value)

        return bool(re.match(pattern, value))

    def _check_enum(self, value: Any, params: Dict[str, Any]) -> bool:
        """Check if value is in allowed values"""
        if value is None:
            return True

        allowed = params.get("values", [])
        return value in allowed

    def _check_custom(self, value: Any, params: Dict[str, Any]) -> bool:
        """Run custom validator"""
        validator_name = params.get("validator")
        if not validator_name:
            return True

        validator = self._custom_validators.get(validator_name)
        if not validator:
            logger.warning(f"Custom validator not found: {validator_name}")
            return True

        is_valid, _ = validator(value, params)
        return is_valid

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def is_valid(
        self,
        data: Dict[str, Any],
        data_type: str = "trade",
    ) -> bool:
        """Quick check if data is valid"""
        return self.validate(data, data_type).is_valid

    def get_issues_summary(
        self,
        results: List[ValidationResult],
    ) -> Dict[str, Any]:
        """Get summary of validation issues"""
        total_issues = sum(len(r.issues) for r in results)
        total_warnings = sum(r.warnings for r in results)
        total_errors = sum(r.errors for r in results)
        valid_count = sum(1 for r in results if r.is_valid)

        # Issue frequency by rule
        issue_counts: Dict[str, int] = {}
        for result in results:
            for issue in result.issues:
                issue_counts[issue.rule_name] = issue_counts.get(issue.rule_name, 0) + 1

        return {
            "total_records": len(results),
            "valid_records": valid_count,
            "invalid_records": len(results) - valid_count,
            "validity_rate": valid_count / len(results) if results else 1.0,
            "total_issues": total_issues,
            "total_warnings": total_warnings,
            "total_errors": total_errors,
            "issues_by_rule": dict(sorted(
                issue_counts.items(),
                key=lambda x: -x[1]
            )[:10]),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_validator: Optional[DataValidator] = None


def get_data_validator() -> DataValidator:
    """Get or create the data validator singleton"""
    global _validator
    if _validator is None:
        _validator = DataValidator()
    return _validator
