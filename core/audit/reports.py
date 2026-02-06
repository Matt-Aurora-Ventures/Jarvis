"""
Audit Reports and Anomaly Detection

Provides reporting and security analysis:
- Daily activity reports
- Security-focused reports
- Anomaly detection
- Alert triggering

Reports help identify:
- Access patterns
- Failed operations
- Suspicious activity
- System health
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Callable, Optional

from core.audit.storage import AuditStore

logger = logging.getLogger(__name__)

# Type alias for alert callbacks
AlertCallback = Callable[[Dict[str, Any]], None]


def generate_daily_report(
    store: AuditStore,
    date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Generate a daily activity report.

    Args:
        store: Audit store to query
        date: Date for the report (default: today)

    Returns:
        Report dictionary with activity summary
    """
    if date is None:
        date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    start_time = date
    end_time = date + timedelta(days=1)

    # Get logs for the day
    logs = store.get_logs(
        filters={"start_time": start_time, "end_time": end_time},
        limit=100000
    )

    # Aggregate statistics
    by_actor = defaultdict(int)
    by_action = defaultdict(int)
    by_resource = defaultdict(int)
    success_count = 0
    failure_count = 0
    errors = []

    for entry in logs:
        actor = entry.get("actor", "unknown")
        action = entry.get("action", "unknown")
        resource = entry.get("resource", "unknown")

        by_actor[actor] += 1
        by_action[action] += 1
        by_resource[resource] += 1

        if entry.get("success", True):
            success_count += 1
        else:
            failure_count += 1

        if action == "error":
            errors.append({
                "timestamp": entry.get("timestamp"),
                "error": entry.get("details", {}).get("error"),
                "context": entry.get("details", {}).get("context"),
            })

    total = len(logs)

    return {
        "date": date.strftime("%Y-%m-%d"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_events": total,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": success_count / total if total > 0 else 1.0,
        "by_actor": dict(sorted(by_actor.items(), key=lambda x: x[1], reverse=True)[:20]),
        "by_action": dict(sorted(by_action.items(), key=lambda x: x[1], reverse=True)[:20]),
        "by_resource": dict(sorted(by_resource.items(), key=lambda x: x[1], reverse=True)[:20]),
        "errors": errors[:50],  # Limit to 50 most recent errors
        "unique_actors": len(by_actor),
        "unique_actions": len(by_action),
        "unique_resources": len(by_resource),
    }


def generate_security_report(
    store: AuditStore,
    days: int = 1
) -> Dict[str, Any]:
    """
    Generate a security-focused report.

    Args:
        store: Audit store to query
        days: Number of days to analyze (default: 1)

    Returns:
        Security report with access patterns and alerts
    """
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    logs = store.get_logs(
        filters={"start_time": start_time, "end_time": end_time},
        limit=100000
    )

    # Security metrics
    access_denied_count = 0
    access_granted_count = 0
    failed_login_count = 0
    successful_login_count = 0
    sensitive_access = []
    failed_operations = []
    actors_with_failures = defaultdict(int)

    # Sensitive resource patterns
    sensitive_patterns = ["secret", "key", "password", "admin", "config", "wallet", "private"]

    for entry in logs:
        action = entry.get("action", "")
        details = entry.get("details", {})
        success = entry.get("success", True)
        resource = entry.get("resource", "")
        actor = entry.get("actor", "unknown")

        # Track access grants/denials
        if action == "access":
            if details.get("granted", True):
                access_granted_count += 1
            else:
                access_denied_count += 1

        # Track logins
        if action == "login":
            if success:
                successful_login_count += 1
            else:
                failed_login_count += 1

        # Track failures
        if not success:
            failed_operations.append({
                "timestamp": entry.get("timestamp"),
                "actor": actor,
                "action": action,
                "resource": resource,
                "error": entry.get("error_message"),
            })
            actors_with_failures[actor] += 1

        # Track sensitive resource access
        resource_lower = resource.lower()
        if any(pattern in resource_lower for pattern in sensitive_patterns):
            sensitive_access.append({
                "timestamp": entry.get("timestamp"),
                "actor": actor,
                "resource": resource,
                "action": action,
                "granted": details.get("granted", success),
            })

    return {
        "period_start": start_time.isoformat(),
        "period_end": end_time.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "access_granted_count": access_granted_count,
        "access_denied_count": access_denied_count,
        "failed_login_count": failed_login_count,
        "successful_login_count": successful_login_count,
        "total_events": len(logs),
        "failed_operations": failed_operations[:100],
        "sensitive_resource_access": sensitive_access[:100],
        "actors_with_most_failures": dict(
            sorted(actors_with_failures.items(), key=lambda x: x[1], reverse=True)[:10]
        ),
        "login_success_rate": (
            successful_login_count / (successful_login_count + failed_login_count)
            if (successful_login_count + failed_login_count) > 0
            else 1.0
        ),
        "access_success_rate": (
            access_granted_count / (access_granted_count + access_denied_count)
            if (access_granted_count + access_denied_count) > 0
            else 1.0
        ),
    }


def detect_anomalies(
    store: AuditStore,
    window_minutes: int = 60,
    high_frequency_threshold: int = 50,
    access_denied_threshold: int = 5,
) -> List[Dict[str, Any]]:
    """
    Detect anomalous activity patterns.

    Looks for:
    - High-frequency actors (potential automated attacks)
    - Access denied spikes (potential unauthorized access attempts)
    - Unusual action patterns

    Args:
        store: Audit store to query
        window_minutes: Time window to analyze
        high_frequency_threshold: Actions per actor threshold
        access_denied_threshold: Access denied threshold

    Returns:
        List of detected anomalies
    """
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=window_minutes)

    logs = store.get_logs(
        filters={"start_time": start_time, "end_time": end_time},
        limit=100000
    )

    anomalies = []

    # Track actor activity
    actor_actions = defaultdict(list)
    actor_denied = defaultdict(int)
    actor_errors = defaultdict(int)

    for entry in logs:
        actor = entry.get("actor", "unknown")
        action = entry.get("action", "")
        details = entry.get("details", {})
        success = entry.get("success", True)

        actor_actions[actor].append(entry)

        # Track access denials
        if action == "access" and not details.get("granted", True):
            actor_denied[actor] += 1

        # Track errors
        if not success or action == "error":
            actor_errors[actor] += 1

    # Detect high-frequency actors
    for actor, actions in actor_actions.items():
        if len(actions) >= high_frequency_threshold:
            anomalies.append({
                "type": "high_frequency",
                "severity": "high",
                "actor": actor,
                "action_count": len(actions),
                "threshold": high_frequency_threshold,
                "window_minutes": window_minutes,
                "message": f"Actor {actor} performed {len(actions)} actions in {window_minutes} minutes",
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

    # Detect access denied spikes
    for actor, denied_count in actor_denied.items():
        if denied_count >= access_denied_threshold:
            anomalies.append({
                "type": "access_denied_spike",
                "severity": "medium",
                "actor": actor,
                "denied_count": denied_count,
                "threshold": access_denied_threshold,
                "window_minutes": window_minutes,
                "message": f"Actor {actor} was denied access {denied_count} times in {window_minutes} minutes",
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

    # Detect error spikes
    for actor, error_count in actor_errors.items():
        if error_count >= access_denied_threshold:
            anomalies.append({
                "type": "error_spike",
                "severity": "medium",
                "actor": actor,
                "error_count": error_count,
                "threshold": access_denied_threshold,
                "window_minutes": window_minutes,
                "message": f"Actor {actor} had {error_count} errors in {window_minutes} minutes",
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

    return anomalies


def alert_on_suspicious(
    store: AuditStore,
    callback: AlertCallback,
    threshold: int = 5,
    window_minutes: int = 60,
) -> List[Dict[str, Any]]:
    """
    Check for suspicious activity and trigger alerts.

    Args:
        store: Audit store to query
        callback: Function to call with alert details
        threshold: Threshold for triggering alerts
        window_minutes: Time window to analyze

    Returns:
        List of alerts that were triggered
    """
    alerts_triggered = []

    # Detect anomalies with the given threshold
    anomalies = detect_anomalies(
        store,
        window_minutes=window_minutes,
        high_frequency_threshold=threshold * 10,
        access_denied_threshold=threshold,
    )

    # Also check for failed logins specifically
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=window_minutes)

    logs = store.get_logs(
        filters={"start_time": start_time, "end_time": end_time},
        limit=100000
    )

    # Count failed logins per actor
    failed_logins = defaultdict(int)
    for entry in logs:
        if entry.get("action") == "login" and not entry.get("success", True):
            actor = entry.get("actor", "unknown")
            failed_logins[actor] += 1

    # Add failed login alerts
    for actor, count in failed_logins.items():
        if count >= threshold:
            alert = {
                "type": "failed_login_spike",
                "severity": "high",
                "actor": actor,
                "failed_count": count,
                "threshold": threshold,
                "window_minutes": window_minutes,
                "message": f"Actor {actor} had {count} failed login attempts in {window_minutes} minutes",
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }
            anomalies.append(alert)

    # Trigger alerts for all anomalies
    for anomaly in anomalies:
        try:
            callback(anomaly)
            alerts_triggered.append(anomaly)
            logger.warning(f"Alert triggered: {anomaly['type']} - {anomaly['message']}")
        except Exception as e:
            logger.error(f"Failed to trigger alert: {e}")

    return alerts_triggered


def generate_compliance_report(
    store: AuditStore,
    start_date: datetime,
    end_date: datetime,
) -> Dict[str, Any]:
    """
    Generate a compliance report for auditing purposes.

    Args:
        store: Audit store to query
        start_date: Report period start
        end_date: Report period end

    Returns:
        Comprehensive compliance report
    """
    logs = store.get_logs(
        filters={"start_time": start_date, "end_time": end_date},
        limit=1000000
    )

    # Aggregate by category
    by_day = defaultdict(int)
    by_actor = defaultdict(int)
    by_action = defaultdict(int)
    by_resource = defaultdict(int)
    failures = []

    for entry in logs:
        # By day
        timestamp = entry.get("timestamp", "")
        if timestamp:
            try:
                day = timestamp[:10]  # YYYY-MM-DD
                by_day[day] += 1
            except Exception:
                pass

        # Other aggregations
        by_actor[entry.get("actor", "unknown")] += 1
        by_action[entry.get("action", "unknown")] += 1
        by_resource[entry.get("resource", "unknown")] += 1

        if not entry.get("success", True):
            failures.append(entry)

    total = len(logs)

    return {
        "report_type": "compliance",
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_events": total,
        "total_failures": len(failures),
        "failure_rate": len(failures) / total if total > 0 else 0.0,
        "events_by_day": dict(sorted(by_day.items())),
        "top_actors": dict(sorted(by_actor.items(), key=lambda x: x[1], reverse=True)[:20]),
        "top_actions": dict(sorted(by_action.items(), key=lambda x: x[1], reverse=True)[:20]),
        "top_resources": dict(sorted(by_resource.items(), key=lambda x: x[1], reverse=True)[:20]),
        "unique_actors": len(by_actor),
        "unique_actions": len(by_action),
        "unique_resources": len(by_resource),
        "sample_failures": failures[:50],
    }
