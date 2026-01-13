"""
JARVIS API Versioning

Provides versioned API routing with:
- Semantic versioning (v1, v2, etc.)
- Version deprecation handling
- Version negotiation via headers
- Backward compatibility layer

Usage:
    from core.api.versioning import VersionedAPI, api_version

    # Create versioned router
    api = VersionedAPI()

    # Add version-specific routes
    @api.route("/users", version="v1")
    async def get_users_v1():
        return {"users": []}

    @api.route("/users", version="v2")
    async def get_users_v2():
        return {"data": {"users": []}, "meta": {}}

    # Mount to app
    app.include_router(api.get_router())
"""

import logging
import re
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class VersionStatus(Enum):
    """API version status."""
    CURRENT = "current"       # Recommended version
    SUPPORTED = "supported"   # Still maintained
    DEPRECATED = "deprecated" # Will be removed
    SUNSET = "sunset"         # Read-only, no updates


@dataclass
class APIVersion:
    """API version definition."""
    version: str              # e.g., "v1", "v2"
    status: VersionStatus = VersionStatus.CURRENT
    release_date: Optional[str] = None
    sunset_date: Optional[str] = None
    changelog: str = ""
    breaking_changes: List[str] = field(default_factory=list)

    @property
    def major(self) -> int:
        """Extract major version number."""
        match = re.match(r'v?(\d+)', self.version)
        return int(match.group(1)) if match else 0

    @property
    def is_deprecated(self) -> bool:
        return self.status in [VersionStatus.DEPRECATED, VersionStatus.SUNSET]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status.value,
            "release_date": self.release_date,
            "sunset_date": self.sunset_date,
            "changelog": self.changelog,
            "breaking_changes": self.breaking_changes,
        }


# Default API versions
DEFAULT_VERSIONS = [
    APIVersion(
        version="v1",
        status=VersionStatus.SUPPORTED,
        release_date="2024-01-01",
        changelog="Initial API release",
    ),
    APIVersion(
        version="v2",
        status=VersionStatus.CURRENT,
        release_date="2024-06-01",
        changelog="Enhanced response format, pagination improvements",
        breaking_changes=[
            "Response wrapper format changed",
            "Pagination params renamed",
        ],
    ),
]


class VersionRegistry:
    """
    Registry for API versions.

    Manages version metadata and routing.
    """

    def __init__(self):
        self._versions: Dict[str, APIVersion] = {}
        self._default_version: str = "v2"
        self._routes: Dict[str, Dict[str, Callable]] = {}  # path -> version -> handler

    def register_version(self, version: APIVersion) -> None:
        """Register an API version."""
        self._versions[version.version] = version

        if version.status == VersionStatus.CURRENT:
            self._default_version = version.version

        logger.info(f"Registered API version: {version.version} ({version.status.value})")

    def get_version(self, version: str) -> Optional[APIVersion]:
        """Get version metadata."""
        return self._versions.get(version)

    def get_all_versions(self) -> List[APIVersion]:
        """Get all registered versions."""
        return sorted(self._versions.values(), key=lambda v: v.major, reverse=True)

    def get_current_version(self) -> str:
        """Get the current (default) version."""
        return self._default_version

    def get_supported_versions(self) -> List[str]:
        """Get list of supported version strings."""
        return [
            v.version for v in self._versions.values()
            if v.status in [VersionStatus.CURRENT, VersionStatus.SUPPORTED]
        ]

    def is_version_valid(self, version: str) -> bool:
        """Check if version is valid and usable."""
        v = self._versions.get(version)
        return v is not None and v.status != VersionStatus.SUNSET

    def register_route(
        self,
        path: str,
        version: str,
        handler: Callable,
    ) -> None:
        """Register a versioned route handler."""
        if path not in self._routes:
            self._routes[path] = {}
        self._routes[path][version] = handler

    def get_handler(self, path: str, version: str) -> Optional[Callable]:
        """Get handler for path and version."""
        if path not in self._routes:
            return None

        versions = self._routes[path]

        # Exact match
        if version in versions:
            return versions[version]

        # Fall back to lower versions
        requested_major = APIVersion(version=version).major
        for v in sorted(versions.keys(), key=lambda x: APIVersion(version=x).major, reverse=True):
            if APIVersion(version=v).major <= requested_major:
                return versions[v]

        return None


# Global registry
_registry = VersionRegistry()

# Register default versions
for v in DEFAULT_VERSIONS:
    _registry.register_version(v)


def get_version_registry() -> VersionRegistry:
    """Get the global version registry."""
    return _registry


def create_versioned_router(prefix: str = "/api"):
    """
    Create a FastAPI router with version support.

    Returns:
        APIRouter with versioning middleware
    """
    try:
        from fastapi import APIRouter, Header, HTTPException, Request
        from fastapi.responses import JSONResponse
    except ImportError:
        logger.error("FastAPI not available")
        return None

    router = APIRouter()

    @router.get(f"{prefix}/versions", tags=["api"])
    async def list_versions():
        """
        List all API versions.

        Returns version metadata including status and changelog.
        """
        registry = get_version_registry()

        return {
            "current": registry.get_current_version(),
            "supported": registry.get_supported_versions(),
            "versions": [v.to_dict() for v in registry.get_all_versions()],
        }

    @router.get(f"{prefix}/version", tags=["api"])
    async def get_current_version():
        """Get current API version."""
        registry = get_version_registry()
        version = registry.get_version(registry.get_current_version())

        return version.to_dict() if version else {"version": "unknown"}

    return router


def version_header_middleware(app):
    """
    Middleware to handle API version header.

    Reads X-API-Version header and adds version info to response.
    """
    try:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import Response
    except ImportError:
        logger.warning("Starlette not available for middleware")
        return app

    class VersionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            # Get requested version
            version = request.headers.get("X-API-Version")
            registry = get_version_registry()

            if not version:
                version = registry.get_current_version()

            # Validate version
            version_info = registry.get_version(version)
            if version_info and version_info.is_deprecated:
                warnings.warn(
                    f"API version {version} is deprecated",
                    DeprecationWarning,
                )

            # Add to request state
            request.state.api_version = version

            # Process request
            response = await call_next(request)

            # Add version headers to response
            response.headers["X-API-Version"] = version
            response.headers["X-API-Supported-Versions"] = ", ".join(
                registry.get_supported_versions()
            )

            if version_info and version_info.is_deprecated:
                response.headers["Deprecation"] = "true"
                if version_info.sunset_date:
                    response.headers["Sunset"] = version_info.sunset_date

            return response

    return VersionMiddleware(app)


def api_version(version: str, deprecated: bool = False):
    """
    Decorator to mark endpoint with API version.

    Args:
        version: API version string (e.g., "v1", "v2")
        deprecated: Mark as deprecated

    Usage:
        @api_version("v2")
        @app.get("/users")
        async def get_users():
            return {"users": []}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Add version to response
            result = await func(*args, **kwargs)

            if isinstance(result, dict):
                result["_api_version"] = version

            if deprecated:
                warnings.warn(
                    f"API endpoint {func.__name__} is deprecated in {version}",
                    DeprecationWarning,
                )

            return result

        # Store metadata
        wrapper._api_version = version
        wrapper._deprecated = deprecated

        return wrapper

    return decorator


def versioned_response(
    data: Any,
    version: str = "v2",
    meta: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Create a versioned API response.

    v1 format: Raw data
    v2 format: Wrapped with meta

    Args:
        data: Response data
        version: API version
        meta: Optional metadata

    Returns:
        Formatted response
    """
    if version == "v1":
        # v1: Raw data
        return data if isinstance(data, dict) else {"data": data}

    # v2+: Wrapped format
    response = {
        "data": data,
        "meta": meta or {},
        "api_version": version,
    }

    if meta is None:
        response["meta"] = {
            "timestamp": datetime.utcnow().isoformat(),
        }

    return response


def paginated_response(
    items: List[Any],
    total: int,
    page: int = 1,
    per_page: int = 20,
    version: str = "v2",
) -> Dict[str, Any]:
    """
    Create a paginated API response.

    Args:
        items: Page items
        total: Total item count
        page: Current page
        per_page: Items per page
        version: API version

    Returns:
        Paginated response
    """
    total_pages = (total + per_page - 1) // per_page

    if version == "v1":
        return {
            "items": items,
            "total": total,
            "page": page,
            "pages": total_pages,
        }

    return {
        "data": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
        "meta": {
            "api_version": version,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


class VersionedAPI:
    """
    High-level versioned API manager.

    Provides a clean interface for creating versioned endpoints.
    """

    def __init__(self, prefix: str = "/api"):
        self.prefix = prefix
        self.registry = get_version_registry()
        self._routers: Dict[str, Any] = {}

    def add_version(self, version: APIVersion) -> None:
        """Add a new API version."""
        self.registry.register_version(version)

    def route(
        self,
        path: str,
        version: str = "v2",
        methods: List[str] = None,
        **kwargs,
    ) -> Callable:
        """
        Decorator to register a versioned route.

        Args:
            path: Route path
            version: API version
            methods: HTTP methods
            **kwargs: Additional route kwargs
        """
        methods = methods or ["GET"]

        def decorator(func: Callable) -> Callable:
            self.registry.register_route(path, version, func)

            # Store version metadata
            func._api_version = version
            func._api_path = path
            func._api_methods = methods

            return func

        return decorator

    def get_router(self):
        """
        Build FastAPI router with all versioned routes.
        """
        try:
            from fastapi import APIRouter
        except ImportError:
            return None

        router = APIRouter(prefix=self.prefix)

        # Add version info endpoints
        version_router = create_versioned_router(prefix="")
        if version_router:
            router.include_router(version_router)

        return router


if __name__ == "__main__":
    print("API Versioning Module")
    print("=" * 40)

    registry = get_version_registry()

    print("\nRegistered Versions:")
    for v in registry.get_all_versions():
        print(f"  {v.version}: {v.status.value}")
        if v.breaking_changes:
            print(f"    Breaking: {v.breaking_changes}")

    print(f"\nCurrent: {registry.get_current_version()}")
    print(f"Supported: {registry.get_supported_versions()}")

    # Test response formatting
    print("\nResponse Formats:")
    data = {"users": [{"id": 1, "name": "Test"}]}

    print(f"  v1: {versioned_response(data, 'v1')}")
    print(f"  v2: {versioned_response(data, 'v2')}")

    # Test pagination
    print("\nPaginated Response (v2):")
    paginated = paginated_response(
        items=[1, 2, 3],
        total=100,
        page=2,
        per_page=3,
    )
    print(f"  {paginated}")
