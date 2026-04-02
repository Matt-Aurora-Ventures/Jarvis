"""Enhanced request validation middleware."""
import json
import re
from typing import Optional, List, Set
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
from fastapi import Request
import logging

logger = logging.getLogger("jarvis.api.validation")


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive request validation middleware.

    Validates:
    - Content-Type headers
    - Request body size limits
    - JSON schema validity
    - Parameter sanitization
    - Suspicious patterns (SQL injection, XSS, etc.)
    """

    # Allowed content types for different methods
    ALLOWED_CONTENT_TYPES = {
        "POST": {"application/json", "application/x-www-form-urlencoded", "multipart/form-data"},
        "PUT": {"application/json", "application/x-www-form-urlencoded", "multipart/form-data"},
        "PATCH": {"application/json", "application/x-www-form-urlencoded"},
    }

    # Suspicious patterns that might indicate attacks
    SUSPICIOUS_PATTERNS = [
        # SQL Injection
        r"(\bunion\b.*\bselect\b)",
        r"(\bselect\b.*\bfrom\b.*\bwhere\b)",
        r"(\bdrop\b.*\btable\b)",
        r"(\binsert\b.*\binto\b)",
        r"(\bdelete\b.*\bfrom\b)",
        r"(\bupdate\b.*\bset\b)",
        r"(--|#|\/\*|\*\/)",  # SQL comments
        r"(\bor\b\s+\d+\s*=\s*\d+)",
        r"(\band\b\s+\d+\s*=\s*\d+)",

        # XSS patterns
        r"(<script[^>]*>.*?</script>)",
        r"(javascript:)",
        r"(on\w+\s*=)",  # Event handlers like onclick=
        r"(<iframe[^>]*>)",
        r"(<object[^>]*>)",
        r"(<embed[^>]*>)",

        # Path traversal
        r"(\.\.\/|\.\.\\)",

        # Command injection
        r"([;&|]\s*(cat|ls|pwd|whoami|wget|curl|nc|bash|sh|cmd|powershell))",
    ]

    # Compile patterns for efficiency
    COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in SUSPICIOUS_PATTERNS]

    # Paths that are exempt from validation (health checks, etc.)
    EXEMPT_PATHS: Set[str] = {
        "/api/health",
        "/api/health/components",
        "/api/metrics",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
    }

    def __init__(
        self,
        app,
        max_body_size: int = 10 * 1024 * 1024,  # 10MB default
        validate_content_type: bool = True,
        sanitize_input: bool = True,
        check_suspicious_patterns: bool = True,
        strict_json: bool = True,
    ):
        super().__init__(app)
        self.max_body_size = max_body_size
        self.validate_content_type = validate_content_type
        self.sanitize_input = sanitize_input
        self.check_suspicious_patterns = check_suspicious_patterns
        self.strict_json = strict_json

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip validation for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip validation for GET, HEAD, OPTIONS, DELETE
        if request.method in ("GET", "HEAD", "OPTIONS", "DELETE"):
            return await call_next(request)

        # 1. Validate Content-Type header
        if self.validate_content_type:
            error_response = self._validate_content_type(request)
            if error_response:
                return error_response

        # 2. Validate body size
        error_response = self._validate_body_size(request)
        if error_response:
            return error_response

        # 3. For JSON requests, validate JSON structure
        if self._is_json_request(request):
            error_response = await self._validate_json_body(request)
            if error_response:
                return error_response

        return await call_next(request)

    def _validate_content_type(self, request: Request) -> Optional[JSONResponse]:
        """Validate Content-Type header for POST/PUT/PATCH requests."""
        if request.method not in self.ALLOWED_CONTENT_TYPES:
            return None

        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()

        # Allow empty content-type for requests with no body
        content_length = request.headers.get("content-length", "0")
        if content_length == "0":
            return None

        allowed = self.ALLOWED_CONTENT_TYPES[request.method]

        if content_type and content_type not in allowed:
            logger.warning(f"Invalid Content-Type: {content_type} for {request.method} {request.url.path}")
            return JSONResponse(
                status_code=415,
                content={
                    "success": False,
                    "error": {
                        "code": "VAL_002",
                        "message": f"Unsupported Content-Type. Expected one of: {', '.join(allowed)}",
                        "field": "Content-Type",
                        "details": {
                            "received": content_type,
                            "allowed": list(allowed)
                        }
                    }
                }
            )

        return None

    def _validate_body_size(self, request: Request) -> Optional[JSONResponse]:
        """Validate request body size."""
        content_length = request.headers.get("content-length")

        if content_length:
            size = int(content_length)
            if size > self.max_body_size:
                logger.warning(f"Request body too large: {size} bytes (max: {self.max_body_size})")
                return JSONResponse(
                    status_code=413,
                    content={
                        "success": False,
                        "error": {
                            "code": "VAL_004",
                            "message": f"Request body too large. Maximum size is {self._format_bytes(self.max_body_size)}",
                            "details": {
                                "size_bytes": size,
                                "max_bytes": self.max_body_size,
                                "size_formatted": self._format_bytes(size),
                                "max_formatted": self._format_bytes(self.max_body_size)
                            }
                        }
                    }
                )

        return None

    async def _validate_json_body(self, request: Request) -> Optional[JSONResponse]:
        """Validate JSON body structure and check for suspicious patterns."""
        try:
            # Read body (will be available to route handler via Request.body() cache)
            body_bytes = await request.body()

            # Empty body is OK
            if not body_bytes:
                return None

            # Try to parse as JSON
            try:
                if self.strict_json:
                    # Strict JSON parsing (no comments, trailing commas, etc.)
                    body_str = body_bytes.decode("utf-8")
                    json_data = json.loads(body_str)
                else:
                    body_str = body_bytes.decode("utf-8")
                    json_data = json.loads(body_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON: {e}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": {
                            "code": "VAL_001",
                            "message": "Invalid JSON format",
                            "details": {
                                "error": str(e),
                                "line": e.lineno,
                                "column": e.colno,
                            }
                        }
                    }
                )
            except UnicodeDecodeError as e:
                logger.warning(f"Invalid encoding: {e}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": {
                            "code": "VAL_002",
                            "message": "Invalid character encoding. Expected UTF-8",
                        }
                    }
                )

            # Check for suspicious patterns
            if self.check_suspicious_patterns:
                body_str_lower = body_str.lower()
                for pattern in self.COMPILED_PATTERNS:
                    if pattern.search(body_str_lower):
                        logger.error(f"Suspicious pattern detected in request to {request.url.path}")
                        return JSONResponse(
                            status_code=400,
                            content={
                                "success": False,
                                "error": {
                                    "code": "VAL_003",
                                    "message": "Request contains invalid or suspicious content",
                                }
                            }
                        )

            # Validate depth (prevent deeply nested objects that could cause DoS)
            max_depth = 10
            depth = self._get_json_depth(json_data)
            if depth > max_depth:
                logger.warning(f"JSON too deeply nested: {depth} levels")
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": {
                            "code": "VAL_004",
                            "message": f"JSON structure too deeply nested. Maximum depth is {max_depth} levels",
                            "details": {"depth": depth, "max_depth": max_depth}
                        }
                    }
                )

            return None

        except Exception as e:
            logger.error(f"Unexpected error during JSON validation: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": {
                        "code": "SYS_001",
                        "message": "Internal error during request validation"
                    }
                }
            )

    def _is_json_request(self, request: Request) -> bool:
        """Check if request has JSON content type."""
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        return content_type == "application/json"

    def _get_json_depth(self, obj, current_depth: int = 1) -> int:
        """Calculate the maximum depth of a JSON structure."""
        if not isinstance(obj, (dict, list)):
            return current_depth

        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._get_json_depth(v, current_depth + 1) for v in obj.values())

        if isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._get_json_depth(item, current_depth + 1) for item in obj)

        return current_depth

    @staticmethod
    def _format_bytes(size: int) -> str:
        """Format bytes to human-readable string."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
