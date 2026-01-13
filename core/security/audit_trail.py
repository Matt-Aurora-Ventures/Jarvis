"""Audit trail logging for security events."""
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    API_ACCESS = "api_access"
    DATA_ACCESS = "data_access"
    DATA_MODIFY = "data_modify"
    DATA_DELETE = "data_delete"
    CONFIG_CHANGE = "config_change"
    PERMISSION_CHANGE = "permission_change"
    SECRET_ACCESS = "secret_access"
    SECRET_ROTATE = "secret_rotate"
    ADMIN_ACTION = "admin_action"
    SECURITY_ALERT = "security_alert"
    TRADE_EXECUTE = "trade_execute"
    WALLET_ACCESS = "wallet_access"


@dataclass
class AuditEvent:
    timestamp: float
    event_type: AuditEventType
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    ip_address: str = ""
    user_agent: str = ""
    details: Dict[str, Any] = None
    success: bool = True
    error_message: str = ""
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['event_type'] = self.event_type.value
        d['timestamp_iso'] = datetime.fromtimestamp(self.timestamp).isoformat()
        return d


class AuditTrail:
    """Comprehensive audit trail logging."""
    
    def __init__(self, log_path: Path = None, max_file_size_mb: int = 100):
        self.log_path = log_path or Path("logs/audit.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size_mb * 1024 * 1024
    
    def log(
        self,
        event_type: AuditEventType,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        ip_address: str = "",
        user_agent: str = "",
        details: Dict[str, Any] = None,
        success: bool = True,
        error_message: str = ""
    ):
        """Log an audit event."""
        event = AuditEvent(
            timestamp=time.time(),
            event_type=event_type,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            success=success,
            error_message=error_message
        )
        
        self._write_event(event)
        
        if event_type == AuditEventType.SECURITY_ALERT or not success:
            logger.warning(f"Audit: {event_type.value} - {action} by {actor_id} on {resource_type}/{resource_id}")
    
    def log_login(self, user_id: str, ip_address: str, success: bool, error: str = ""):
        """Log a login attempt."""
        self.log(
            event_type=AuditEventType.LOGIN if success else AuditEventType.LOGIN_FAILED,
            actor_id=user_id,
            action="login",
            resource_type="auth",
            resource_id="session",
            ip_address=ip_address,
            success=success,
            error_message=error
        )
    
    def log_api_access(self, user_id: str, method: str, path: str, ip_address: str, status_code: int):
        """Log an API access."""
        self.log(
            event_type=AuditEventType.API_ACCESS,
            actor_id=user_id,
            action=f"{method} {path}",
            resource_type="api",
            resource_id=path,
            ip_address=ip_address,
            details={"status_code": status_code},
            success=status_code < 400
        )
    
    def log_trade(self, user_id: str, action: str, symbol: str, amount: float, details: dict = None):
        """Log a trade execution."""
        self.log(
            event_type=AuditEventType.TRADE_EXECUTE,
            actor_id=user_id,
            action=action,
            resource_type="trade",
            resource_id=symbol,
            details={"amount": amount, **(details or {})}
        )
    
    def query(
        self,
        start_time: float = None,
        end_time: float = None,
        event_type: AuditEventType = None,
        actor_id: str = None,
        resource_type: str = None,
        limit: int = 1000
    ) -> List[dict]:
        """Query audit events."""
        results = []
        
        if not self.log_path.exists():
            return results
        
        with open(self.log_path, 'r') as f:
            for line in f:
                if len(results) >= limit:
                    break
                
                try:
                    event = json.loads(line)
                    
                    if start_time and event['timestamp'] < start_time:
                        continue
                    if end_time and event['timestamp'] > end_time:
                        continue
                    if event_type and event['event_type'] != event_type.value:
                        continue
                    if actor_id and event['actor_id'] != actor_id:
                        continue
                    if resource_type and event['resource_type'] != resource_type:
                        continue
                    
                    results.append(event)
                except json.JSONDecodeError:
                    continue
        
        return results
    
    def _write_event(self, event: AuditEvent):
        """Write an event to the log file."""
        self._rotate_if_needed()
        
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(event.to_dict()) + '\n')
    
    def _rotate_if_needed(self):
        """Rotate log file if it exceeds max size."""
        if not self.log_path.exists():
            return
        
        if self.log_path.stat().st_size > self.max_file_size:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            rotated_path = self.log_path.with_suffix(f'.{timestamp}.jsonl')
            self.log_path.rename(rotated_path)
            logger.info(f"Rotated audit log to {rotated_path}")


audit_trail = AuditTrail()
