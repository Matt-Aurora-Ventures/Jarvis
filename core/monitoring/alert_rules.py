"""
Alert Rules Engine - Configurable alerting rules with cooldown.

Built-in rules:
- CPU > 80% -> WARNING
- Memory > 90% -> CRITICAL
- API latency > 1s -> WARNING
- Error rate > 1% -> WARNING
- No trades in 24h -> INFO (sanity check)
- Backup missing (>24h old) -> CRITICAL

Custom rules: JSON configurable in lifeos/config/alert_rules.json
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("jarvis.monitoring.alert_rules")


@dataclass
class AlertRule:
    """Definition of an alert rule."""
    id: str
    condition: str
    severity: str
    actions: List[str]
    cooldown_minutes: int
    message: str
    last_triggered: Optional[float] = None


class AlertRulesEngine:
    """
    Evaluates alert rules against metrics.

    Supports simple comparison conditions like:
    - cpu_percent > 80
    - memory_percent > 90
    - api_latency_p95 > 1000
    """

    def __init__(self, rules_path: Optional[str] = None):
        self.rules: List[Dict[str, Any]] = []
        self._rule_states: Dict[str, float] = {}  # Rule ID -> last triggered time

        # Load rules from file if provided
        if rules_path:
            self._load_rules(rules_path)
        else:
            # Try default path
            default_path = Path("lifeos/config/alert_rules.json")
            if default_path.exists():
                self._load_rules(str(default_path))

    def _load_rules(self, rules_path: str):
        """Load rules from JSON file."""
        try:
            with open(rules_path) as f:
                data = json.load(f)
                self.rules = data.get("rules", [])
                logger.info(f"Loaded {len(self.rules)} alert rules from {rules_path}")
        except Exception as e:
            logger.error(f"Failed to load alert rules: {e}")
            self.rules = []

    def add_rule(self, rule: Dict[str, Any]):
        """Add a rule at runtime."""
        required_keys = ["id", "condition", "severity", "actions", "cooldown_minutes", "message"]
        for key in required_keys:
            if key not in rule:
                raise ValueError(f"Rule missing required key: {key}")
        self.rules.append(rule)
        logger.info(f"Added alert rule: {rule['id']}")

    def remove_rule(self, rule_id: str):
        """Remove a rule by ID."""
        self.rules = [r for r in self.rules if r["id"] != rule_id]

    def _parse_condition(self, condition: str) -> Optional[tuple]:
        """
        Parse a condition string into (metric, operator, value).

        Examples:
            "cpu_percent > 80" -> ("cpu_percent", ">", 80)
            "memory_percent >= 90" -> ("memory_percent", ">=", 90)
        """
        # Pattern: metric operator value
        pattern = r"(\w+)\s*([><=!]+)\s*([0-9.]+)"
        match = re.match(pattern, condition.strip())
        if match:
            metric = match.group(1)
            operator = match.group(2)
            value = float(match.group(3))
            return (metric, operator, value)
        return None

    def _evaluate_condition(
        self,
        condition: str,
        metrics: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a condition against provided metrics.

        Returns True if condition is met.
        """
        parsed = self._parse_condition(condition)
        if not parsed:
            logger.warning(f"Could not parse condition: {condition}")
            return False

        metric, operator, threshold = parsed

        if metric not in metrics:
            return False

        value = metrics[metric]

        try:
            if operator == ">":
                return value > threshold
            elif operator == ">=":
                return value >= threshold
            elif operator == "<":
                return value < threshold
            elif operator == "<=":
                return value <= threshold
            elif operator == "==":
                return value == threshold
            elif operator == "!=":
                return value != threshold
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
        except Exception as e:
            logger.warning(f"Error evaluating condition: {e}")
            return False

    def _is_in_cooldown(self, rule_id: str, cooldown_minutes: int) -> bool:
        """Check if a rule is still in cooldown period."""
        if rule_id not in self._rule_states:
            return False

        last_triggered = self._rule_states[rule_id]
        cooldown_seconds = cooldown_minutes * 60
        elapsed = time.time() - last_triggered

        return elapsed < cooldown_seconds

    def evaluate(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate all rules against metrics.

        Args:
            metrics: Dictionary of metric name -> value

        Returns:
            List of triggered rules (that aren't in cooldown)
        """
        triggered = []

        for rule in self.rules:
            rule_id = rule["id"]
            condition = rule["condition"]
            cooldown = rule.get("cooldown_minutes", 0)

            # Skip if in cooldown
            if self._is_in_cooldown(rule_id, cooldown):
                continue

            # Evaluate condition
            if self._evaluate_condition(condition, metrics):
                triggered.append(rule)
                self._rule_states[rule_id] = time.time()
                logger.info(f"Alert rule triggered: {rule_id}")

        return triggered

    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all configured rules."""
        return self.rules.copy()

    def get_rule_states(self) -> Dict[str, float]:
        """Get the last triggered time for each rule."""
        return self._rule_states.copy()

    def reset_cooldown(self, rule_id: str):
        """Reset cooldown for a specific rule."""
        if rule_id in self._rule_states:
            del self._rule_states[rule_id]

    def reset_all_cooldowns(self):
        """Reset all cooldowns."""
        self._rule_states.clear()


# Default built-in rules
DEFAULT_RULES = [
    {
        "id": "cpu_high",
        "condition": "cpu_percent > 80",
        "severity": "warning",
        "actions": ["log"],
        "cooldown_minutes": 30,
        "message": "CPU usage exceeds 80%"
    },
    {
        "id": "memory_critical",
        "condition": "memory_percent > 90",
        "severity": "critical",
        "actions": ["telegram", "log"],
        "cooldown_minutes": 10,
        "message": "Memory usage exceeds 90%"
    },
    {
        "id": "api_latency_high",
        "condition": "api_latency_p95 > 1000",
        "severity": "warning",
        "actions": ["log"],
        "cooldown_minutes": 15,
        "message": "API latency P95 exceeds 1 second"
    },
    {
        "id": "error_rate_high",
        "condition": "error_rate > 1",
        "severity": "warning",
        "actions": ["telegram", "log"],
        "cooldown_minutes": 30,
        "message": "Error rate exceeds 1%"
    },
]


# Singleton
_rules_engine: Optional[AlertRulesEngine] = None


def get_alert_rules_engine() -> AlertRulesEngine:
    """Get or create the alert rules engine singleton."""
    global _rules_engine
    if _rules_engine is None:
        _rules_engine = AlertRulesEngine()
        # Add default rules if none loaded
        if len(_rules_engine.rules) == 0:
            for rule in DEFAULT_RULES:
                _rules_engine.add_rule(rule)
    return _rules_engine
