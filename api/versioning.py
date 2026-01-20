"""
API Versioning Support

Provides versioning infrastructure for JARVIS API:
- Version routing (/api/v1/, /api/v2/)
- Accept-Version header support
- Deprecation warnings
- Version negotiation
"""

import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime
from functools import wraps

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("jarvis.api.versioning")


# =============================================================================
# Version Configuration
# =============================================================================

CURRENT_VERSION = "v1"
SUPPORTED_VERSIONS = ["v1"]
DEPRECATED_VERSIONS = {}  # Format: {"v0": "2026-06-01"}

# Version-specific deprecation notices
ENDPOINT_DEPRECATIONS = {}  # Format: {("v1", "/api/v1/staking/stake"): ("v2", "2026-06-01")}


# =============================================================================
# Version Detection
# =============================================================================

def extract_version_from_path(path: str) -> Optional[str]:
    """Extract API version from URL path."""
    parts = path.split("/")
    for part in parts:
        if part.startswith("v") and part[1:].isdigit():
            return part
    return None


def extract_version_from_header(request: Request) -> Optional[str]:
    """Extract API version from Accept-Version header."""
    version = request.headers.get("Accept-Version", "").strip()
    if version and version in SUPPORTED_VERSIONS:
        return version
    return None


def get_request_version(request: Request) -> str:
    """
    Determine API version for request.

    Priority:
    1. URL path (/api/v1/...)
    2. Accept-Version header
    3. Default to current version
    """
    # Check path first
    version = extract_version_from_path(request.url.path)
    if version and version in SUPPORTED_VERSIONS:
        return version

    # Check header
    version = extract_version_from_header(request)
    if version:
        return version

    # Default
    return CURRENT_VERSION


# =============================================================================
# Versioning Middleware
# =============================================================================

class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle API versioning.

    - Detects version from path or header
    - Adds X-API-Version response header
    - Adds deprecation warnings
    """

    async def dispatch(self, request: Request, call_next):
        # Detect version
        version = get_request_version(request)

        # Store in request state for route handlers
        request.state.api_version = version

        # Call route handler
        response = await call_next(request)

        # Add version header
        response.headers["X-API-Version"] = version

        # Add deprecation warnings
        if version in DEPRECATED_VERSIONS:
            sunset_date = DEPRECATED_VERSIONS[version]
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = sunset_date
            response.headers["Warning"] = (
                f'299 - "API version {version} is deprecated. '
                f'Will be removed after {sunset_date}. '
                f'Please migrate to {CURRENT_VERSION}."'
            )

        # Check endpoint-specific deprecations
        endpoint_key = (version, request.url.path)
        if endpoint_key in ENDPOINT_DEPRECATIONS:
            new_version, sunset_date = ENDPOINT_DEPRECATIONS[endpoint_key]
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = sunset_date
            response.headers["Warning"] = (
                f'299 - "This endpoint is deprecated. '
                f'Use {new_version} version. '
                f'Will be removed after {sunset_date}."'
            )

        return response


# =============================================================================
# Version Router Factory
# =============================================================================

def create_versioned_router(
    version: str,
    prefix: str,
    tags: list[str],
    deprecated: bool = False,
    sunset_date: Optional[str] = None,
) -> APIRouter:
    """
    Create a versioned API router.

    Args:
        version: API version (e.g., "v1")
        prefix: Route prefix (e.g., "/staking")
        tags: OpenAPI tags
        deprecated: Whether this version is deprecated
        sunset_date: When this version will be removed (ISO date)

    Returns:
        Configured APIRouter
    """
    full_prefix = f"/api/{version}{prefix}"

    router = APIRouter(
        prefix=full_prefix,
        tags=[f"{version.upper()} {tag}" for tag in tags],
    )

    # Add deprecation metadata if needed
    if deprecated and sunset_date:
        DEPRECATED_VERSIONS[version] = sunset_date
        logger.warning(
            f"Router {full_prefix} is deprecated. "
            f"Sunset date: {sunset_date}"
        )

    return router


# =============================================================================
# Deprecation Decorator
# =============================================================================

def deprecated(
    new_version: str,
    sunset_date: str,
    message: Optional[str] = None
):
    """
    Mark an endpoint as deprecated.

    Usage:
        @router.get("/old-endpoint")
        @deprecated("v2", "2026-06-01", "Use /new-endpoint instead")
        async def old_handler():
            ...

    Args:
        new_version: Version to migrate to
        sunset_date: When this endpoint will be removed (ISO format)
        message: Optional custom deprecation message
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute original function
            result = await func(*args, **kwargs)
            return result

        # Mark function with deprecation metadata
        wrapper.__deprecated__ = True
        wrapper.__new_version__ = new_version
        wrapper.__sunset_date__ = sunset_date
        wrapper.__deprecation_message__ = message

        return wrapper
    return decorator


# =============================================================================
# Version Negotiation
# =============================================================================

class VersionNegotiator:
    """Handle version negotiation and compatibility."""

    @staticmethod
    def is_version_supported(version: str) -> bool:
        """Check if version is supported."""
        return version in SUPPORTED_VERSIONS

    @staticmethod
    def is_version_deprecated(version: str) -> bool:
        """Check if version is deprecated."""
        return version in DEPRECATED_VERSIONS

    @staticmethod
    def get_deprecation_info(version: str) -> Optional[Dict[str, Any]]:
        """Get deprecation info for version."""
        if version not in DEPRECATED_VERSIONS:
            return None

        sunset_date = DEPRECATED_VERSIONS[version]
        try:
            sunset_dt = datetime.fromisoformat(sunset_date)
            days_remaining = (sunset_dt - datetime.now()).days
        except Exception:
            days_remaining = None

        return {
            "version": version,
            "deprecated": True,
            "sunset_date": sunset_date,
            "days_remaining": days_remaining,
            "current_version": CURRENT_VERSION,
            "message": (
                f"Version {version} is deprecated. "
                f"Please migrate to {CURRENT_VERSION}."
            ),
        }

    @staticmethod
    def validate_version(version: str) -> None:
        """
        Validate version or raise HTTPException.

        Raises:
            HTTPException: If version is not supported
        """
        if not VersionNegotiator.is_version_supported(version):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "UNSUPPORTED_VERSION",
                    "message": f"API version '{version}' is not supported",
                    "supported_versions": SUPPORTED_VERSIONS,
                    "current_version": CURRENT_VERSION,
                }
            )


# =============================================================================
# Helper Endpoints
# =============================================================================

def create_version_info_router() -> APIRouter:
    """Create router with version information endpoints."""
    router = APIRouter(prefix="/api", tags=["API Info"])

    @router.get("/versions")
    async def list_versions():
        """List all API versions and their status."""
        versions = []

        for version in SUPPORTED_VERSIONS:
            is_deprecated = version in DEPRECATED_VERSIONS
            info = {
                "version": version,
                "current": version == CURRENT_VERSION,
                "deprecated": is_deprecated,
            }

            if is_deprecated:
                sunset_date = DEPRECATED_VERSIONS[version]
                try:
                    sunset_dt = datetime.fromisoformat(sunset_date)
                    days_remaining = (sunset_dt - datetime.now()).days
                    info["sunset_date"] = sunset_date
                    info["days_remaining"] = days_remaining
                except Exception:
                    info["sunset_date"] = sunset_date

            versions.append(info)

        return {
            "current_version": CURRENT_VERSION,
            "versions": versions,
        }

    @router.get("/version")
    async def get_version_info(request: Request):
        """Get version info for current request."""
        version = get_request_version(request)

        info = {
            "version": version,
            "current": version == CURRENT_VERSION,
            "deprecated": version in DEPRECATED_VERSIONS,
        }

        if version in DEPRECATED_VERSIONS:
            deprecation_info = VersionNegotiator.get_deprecation_info(version)
            if deprecation_info:
                info.update(deprecation_info)

        return info

    return router


# =============================================================================
# Route Wrapper Utilities
# =============================================================================

def wrap_route_with_version_check(route: APIRoute, required_version: Optional[str] = None):
    """
    Wrap a route to enforce version requirements.

    Args:
        route: Original APIRoute
        required_version: Required API version (None = any supported version)
    """
    original_handler = route.endpoint

    async def versioned_handler(request: Request, *args, **kwargs):
        version = get_request_version(request)

        # Validate version
        VersionNegotiator.validate_version(version)

        # Check required version
        if required_version and version != required_version:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "VERSION_MISMATCH",
                    "message": f"This endpoint requires API version {required_version}",
                    "requested_version": version,
                }
            )

        # Call original handler
        return await original_handler(request, *args, **kwargs)

    route.endpoint = versioned_handler
    return route
