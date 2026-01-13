"""
Autonomy Health Monitor
Self-monitoring and healing for autonomous operation
"""

import asyncio
import logging
import os
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "health"
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class HealthCheck:
    """Result of a health check"""
    name: str
    status: str  # healthy, degraded, unhealthy
    message: str = ""
    last_check: str = ""
    consecutive_failures: int = 0


@dataclass
class ServiceStatus:
    """Status of a monitored service"""
    name: str
    is_running: bool = False
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    failure_count: int = 0
    restart_count: int = 0


class AutonomyHealthMonitor:
    """
    Monitor health of all autonomous systems.
    Auto-restart failed services, alert on issues.
    """
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.services: Dict[str, ServiceStatus] = {}
        self.alert_handlers: List[Callable] = []
        self.last_full_check = None
        self.check_interval = timedelta(minutes=5)
        self._running = False
        self._monitor_task = None
    
    def register_check(self, name: str, check_func: Callable):
        """Register a health check function"""
        self.health_checks[name] = HealthCheck(name=name, status="unknown")
        setattr(self, f"_check_{name}", check_func)
    
    def register_service(self, name: str):
        """Register a service to monitor"""
        self.services[name] = ServiceStatus(name=name)
    
    def add_alert_handler(self, handler: Callable):
        """Add an alert handler (e.g., Telegram notification)"""
        self.alert_handlers.append(handler)
    
    async def _send_alert(self, message: str, severity: str = "warning"):
        """Send alert to all handlers"""
        for handler in self.alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message, severity)
                else:
                    handler(message, severity)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
    
    async def check_twitter_api(self) -> HealthCheck:
        """Check Twitter API health"""
        check = HealthCheck(name="twitter_api", status="unknown")
        try:
            from bots.twitter.twitter_client import get_twitter_client
            client = get_twitter_client()
            # Simple connectivity check
            if client and hasattr(client, 'credentials') and client.credentials.is_valid():
                check.status = "healthy"
                check.message = "Twitter API credentials valid"
            else:
                check.status = "degraded"
                check.message = "Twitter credentials may need refresh"
        except Exception as e:
            check.status = "unhealthy"
            check.message = str(e)
        
        check.last_check = datetime.utcnow().isoformat()
        return check
    
    async def check_grok_api(self) -> HealthCheck:
        """Check Grok/xAI API health"""
        check = HealthCheck(name="grok_api", status="unknown")
        try:
            from bots.twitter.grok_client import get_grok_client
            grok = get_grok_client()
            if grok and grok.api_key:
                check.status = "healthy"
                check.message = "Grok API key configured"
            else:
                check.status = "unhealthy"
                check.message = "Grok API key missing"
        except Exception as e:
            check.status = "unhealthy"
            check.message = str(e)
        
        check.last_check = datetime.utcnow().isoformat()
        return check
    
    async def check_anthropic_api(self) -> HealthCheck:
        """Check Anthropic API health"""
        check = HealthCheck(name="anthropic_api", status="unknown")
        try:
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if api_key:
                check.status = "healthy"
                check.message = "Anthropic API key configured"
            else:
                check.status = "unhealthy"
                check.message = "Anthropic API key missing"
        except Exception as e:
            check.status = "unhealthy"
            check.message = str(e)
        
        check.last_check = datetime.utcnow().isoformat()
        return check
    
    async def check_system_resources(self) -> HealthCheck:
        """Check system resources"""
        check = HealthCheck(name="system", status="unknown")
        try:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            
            issues = []
            if cpu > 90:
                issues.append(f"CPU: {cpu}%")
            if memory.percent > 90:
                issues.append(f"Memory: {memory.percent}%")
            if disk.percent > 90:
                issues.append(f"Disk: {disk.percent}%")
            
            if issues:
                check.status = "degraded"
                check.message = ", ".join(issues)
            else:
                check.status = "healthy"
                check.message = f"CPU: {cpu}%, Mem: {memory.percent}%, Disk: {disk.percent}%"
        except Exception as e:
            check.status = "unknown"
            check.message = str(e)
        
        check.last_check = datetime.utcnow().isoformat()
        return check
    
    async def check_data_freshness(self) -> HealthCheck:
        """Check if data files are being updated"""
        check = HealthCheck(name="data_freshness", status="unknown")
        try:
            learning_file = DATA_DIR.parent / "learning" / "tweet_performance.json"
            if learning_file.exists():
                mtime = datetime.fromtimestamp(learning_file.stat().st_mtime)
                age = datetime.utcnow() - mtime
                if age < timedelta(hours=24):
                    check.status = "healthy"
                    check.message = f"Data updated {age.seconds // 3600}h ago"
                else:
                    check.status = "degraded"
                    check.message = f"Data is {age.days}d old"
            else:
                check.status = "degraded"
                check.message = "No learning data yet"
        except Exception as e:
            check.status = "unknown"
            check.message = str(e)
        
        check.last_check = datetime.utcnow().isoformat()
        return check
    
    async def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Run all health checks"""
        checks = {}
        
        # Run built-in checks
        checks["twitter_api"] = await self.check_twitter_api()
        checks["grok_api"] = await self.check_grok_api()
        checks["anthropic_api"] = await self.check_anthropic_api()
        checks["system"] = await self.check_system_resources()
        checks["data_freshness"] = await self.check_data_freshness()
        
        # Run registered checks
        for name, check in self.health_checks.items():
            if hasattr(self, f"_check_{name}"):
                try:
                    func = getattr(self, f"_check_{name}")
                    result = await func() if asyncio.iscoroutinefunction(func) else func()
                    checks[name] = result
                except Exception as e:
                    checks[name] = HealthCheck(name=name, status="unhealthy", message=str(e))
        
        self.health_checks = checks
        self.last_full_check = datetime.utcnow()
        
        # Check for issues and alert
        unhealthy = [c for c in checks.values() if c.status == "unhealthy"]
        if unhealthy:
            msg = "⚠️ Health issues:\n" + "\n".join(f"- {c.name}: {c.message}" for c in unhealthy)
            await self._send_alert(msg, "warning")
        
        return checks
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get overall status summary"""
        total = len(self.health_checks)
        healthy = len([c for c in self.health_checks.values() if c.status == "healthy"])
        degraded = len([c for c in self.health_checks.values() if c.status == "degraded"])
        unhealthy = len([c for c in self.health_checks.values() if c.status == "unhealthy"])
        
        if unhealthy > 0:
            overall = "unhealthy"
        elif degraded > 0:
            overall = "degraded"
        elif healthy == total and total > 0:
            overall = "healthy"
        else:
            overall = "unknown"
        
        return {
            "overall": overall,
            "total_checks": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "last_check": self.last_full_check.isoformat() if self.last_full_check else None,
            "checks": {name: {"status": c.status, "message": c.message} for name, c in self.health_checks.items()}
        }
    
    def mark_service_success(self, name: str):
        """Mark a service operation as successful"""
        if name in self.services:
            self.services[name].is_running = True
            self.services[name].last_success = datetime.utcnow().isoformat()
            self.services[name].failure_count = 0
    
    def mark_service_failure(self, name: str, error: str = ""):
        """Mark a service operation as failed"""
        if name in self.services:
            svc = self.services[name]
            svc.failure_count += 1
            svc.last_failure = datetime.utcnow().isoformat()
            
            if svc.failure_count >= 3:
                svc.is_running = False
                logger.error(f"Service {name} has failed {svc.failure_count} times")
    
    async def start_monitoring(self, interval_seconds: int = 300):
        """Start background monitoring"""
        if self._running:
            return
        
        self._running = True
        
        async def monitor_loop():
            while self._running:
                try:
                    await self.run_all_checks()
                except Exception as e:
                    logger.error(f"Health check error: {e}")
                await asyncio.sleep(interval_seconds)
        
        self._monitor_task = asyncio.create_task(monitor_loop())
        logger.info("Health monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        logger.info("Health monitoring stopped")


# Singleton
_monitor: Optional[AutonomyHealthMonitor] = None

def get_health_monitor() -> AutonomyHealthMonitor:
    global _monitor
    if _monitor is None:
        _monitor = AutonomyHealthMonitor()
    return _monitor
