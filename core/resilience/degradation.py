"""Graceful degradation patterns."""
import asyncio
import time
from typing import Callable, Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class ServiceLevel(str, Enum):
    FULL = "full"
    DEGRADED = "degraded"
    MINIMAL = "minimal"
    OFFLINE = "offline"


@dataclass
class ServiceHealth:
    name: str
    healthy: bool = True
    last_check: float = 0
    error_count: int = 0
    response_time: float = 0


class GracefulDegradation:
    """Manage graceful degradation based on service health."""
    
    def __init__(self):
        self.services: Dict[str, ServiceHealth] = {}
        self.service_level = ServiceLevel.FULL
        self._degraded_features: set = set()
        self._offline_threshold = 3
    
    def register_service(self, name: str):
        self.services[name] = ServiceHealth(name=name)
    
    def report_success(self, service_name: str, response_time: float = 0):
        if service_name in self.services:
            svc = self.services[service_name]
            svc.healthy = True
            svc.last_check = time.time()
            svc.error_count = 0
            svc.response_time = response_time
        self._update_service_level()
    
    def report_failure(self, service_name: str):
        if service_name in self.services:
            svc = self.services[service_name]
            svc.error_count += 1
            svc.last_check = time.time()
            if svc.error_count >= self._offline_threshold:
                svc.healthy = False
        self._update_service_level()
    
    def _update_service_level(self):
        unhealthy = sum(1 for s in self.services.values() if not s.healthy)
        total = len(self.services)
        
        if unhealthy == 0:
            self.service_level = ServiceLevel.FULL
        elif unhealthy < total / 2:
            self.service_level = ServiceLevel.DEGRADED
        elif unhealthy < total:
            self.service_level = ServiceLevel.MINIMAL
        else:
            self.service_level = ServiceLevel.OFFLINE
    
    def is_feature_available(self, feature: str) -> bool:
        return feature not in self._degraded_features
    
    def disable_feature(self, feature: str):
        self._degraded_features.add(feature)
        logger.warning(f"Feature disabled: {feature}")
    
    def enable_feature(self, feature: str):
        self._degraded_features.discard(feature)
        logger.info(f"Feature enabled: {feature}")
    
    def get_status(self) -> dict:
        return {
            "level": self.service_level.value,
            "services": {n: {"healthy": s.healthy, "errors": s.error_count} for n, s in self.services.items()},
            "disabled_features": list(self._degraded_features)
        }


_degradation = GracefulDegradation()


def degrade_gracefully(feature: str, fallback_value: Any = None):
    """Decorator to handle graceful degradation."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not _degradation.is_feature_available(feature):
                logger.info(f"Feature {feature} degraded, using fallback")
                return fallback_value
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Feature {feature} failed: {e}")
                _degradation.disable_feature(feature)
                return fallback_value
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not _degradation.is_feature_available(feature):
                return fallback_value
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Feature {feature} failed: {e}")
                _degradation.disable_feature(feature)
                return fallback_value
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def get_degradation_manager() -> GracefulDegradation:
    return _degradation
