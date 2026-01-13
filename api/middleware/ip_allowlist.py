"""IP allowlist middleware for admin routes."""
import ipaddress
from typing import List, Set
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request, HTTPException
import logging

logger = logging.getLogger(__name__)


class IPAllowlistMiddleware(BaseHTTPMiddleware):
    """Restrict access to certain paths by IP address."""
    
    def __init__(self, app, allowed_ips: List[str] = None, protected_prefixes: List[str] = None):
        super().__init__(app)
        self.allowed_ips: Set[str] = set(allowed_ips or ["127.0.0.1", "::1"])
        self.allowed_networks = []
        self.protected_prefixes = protected_prefixes or ["/api/admin"]
        
        for ip in list(self.allowed_ips):
            if "/" in ip:
                self.allowed_networks.append(ipaddress.ip_network(ip, strict=False))
                self.allowed_ips.discard(ip)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        if not any(request.url.path.startswith(prefix) for prefix in self.protected_prefixes):
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        
        if not self._is_allowed(client_ip):
            logger.warning(f"Blocked access from {client_ip} to {request.url.path}")
            raise HTTPException(status_code=403, detail="Access denied")
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _is_allowed(self, ip: str) -> bool:
        if ip in self.allowed_ips:
            return True
        
        try:
            ip_obj = ipaddress.ip_address(ip)
            return any(ip_obj in network for network in self.allowed_networks)
        except ValueError:
            return False
    
    def add_ip(self, ip: str):
        """Add an IP to the allowlist."""
        if "/" in ip:
            self.allowed_networks.append(ipaddress.ip_network(ip, strict=False))
        else:
            self.allowed_ips.add(ip)
    
    def remove_ip(self, ip: str):
        """Remove an IP from the allowlist."""
        self.allowed_ips.discard(ip)
